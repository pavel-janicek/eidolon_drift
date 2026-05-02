# eidolon/io/input_handler.py
"""
Unified input handler for Eidolon Drift.

Features:
 - Detects and uses controller backends (pygame preferred, evdev fallback).
 - Maps left stick and D-pad to movement.
 - Maps PS4 face buttons to game actions (triangle/scan, square/logs, X/use, circle/inspect).
 - Right trigger (R2) mapped to help.
 - Curses fallback for terminal-only environments.
 - CLI test modes: --map-test (prints events), --monitor (hotplug monitor).
"""

from __future__ import annotations
import logging
import threading
import time
import queue
from typing import Callable, Dict, List, Optional, Tuple


logger = logging.getLogger("eidolon.input")
logger.addHandler(logging.NullHandler())

# try curses (for terminal UI fallback)
try:
    import curses
except Exception:
    curses = None  # caller should handle missing curses if needed

# detect_input is expected to exist (your module). Provide safe fallback.
try:
    from eidolon.io.detect_input import (
        backend_name,
        list_controllers,
        start_monitoring,
        stop_monitoring,
    )
except Exception:

    def backend_name() -> Optional[str]:
        return None

    def list_controllers() -> List[Dict]:
        return []

    def start_monitoring(cb, poll_interval=1.0):
        raise RuntimeError("detect_input.start_monitoring not available")

    def stop_monitoring():
        pass


# try pygame (SDL) for event-driven controller input
_PYGAME = None
try:
    import pygame as _pg

    _PYGAME = _pg
except Exception:
    _PYGAME = None

# try evdev (Linux) as fallback for polling
_EVDEV = None
try:
    import evdev as _ev

    _EVDEV = _ev
except Exception:
    _EVDEV = None

# --- configuration ---------------------------------------------------------
DEFAULT_DEADZONE = 0.20
DEFAULT_POLL_INTERVAL = 0.01  # seconds for main loop poll
HOTPLUG_POLL = 1.0  # seconds for detect_input monitor

# PS4 mapping defaults (may vary by platform/driver)
PS4_BUTTON_MAP = {
    "square": 2,
    "x": 0,
    "circle": 1,
    "triangle": 3,
    "l1": 9,
    "r1": 10,
    "l2": 6,
    "r2": 7,
    "share": 8,
    "options": 9,
    "l3": 10,
    "r3": 11,
    "ps": 12,
    "touch": 13,    
}


PS4_AXIS_MAP = {
    "left_x": 0,
    "left_y": 1,
    "right_x": 2,   # uprav podle map-testu pokud je potřeba
    "right_y": 3,   # uprav podle map-testu pokud je potřeba
    "l2_axis": 4,
    "r2_axis": 5,
}
# mapování tlačítek D‑Pad (upravit indexy podle map-testu)
PS4_DPAD_BUTTON_MAP = {
    11: "UP",     # podle tvého výstupu
    12: "DOWN",   # doplň podle map-testu
    13: "LEFT",   # doplň podle map-testu
    14: "RIGHT",  # doplň podle map-testu
}



DEFAULT_ACTIONS = {
    "move": "move",
    "help": "help",
    "scan": "scan",
    "logs": "logs",
    "use": "use",
    "inspect": "inspect",
}


# --- helpers --------------------------------------------------------------
def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# --- InputHandler ---------------------------------------------------------
class InputHandler:
    from eidolon.config import LOG_LEVEL
    """
    InputHandler unifikuje klávesnici a gamepad for the game.
    Provide an on_action callback: on_action(action_name: str, payload: Optional[dict])
    """

    def __init__(
        self, on_action_or_game=None, stdscr=None, deadzone: float = DEFAULT_DEADZONE
    ):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(filename='eidolon.log', encoding='utf-8', level=self.LOG_LEVEL)
        """
        Backward-compatible constructor:
        - legacy call: InputHandler(stdscr)  -> on_action_or_game is curses window
        - new call:    InputHandler(on_action_callable, stdscr)
        """
        # detect legacy usage: first arg is curses window (has getch)
        if (
            on_action_or_game is not None
            and stdscr is None
            and hasattr(on_action_or_game, "getch")
        ):
            # legacy: InputHandler(stdscr)
            self.stdscr = on_action_or_game
            self.on_action = None
        else:
            # new-style: first arg is callback (callable) or None
            self.on_action = on_action_or_game if callable(on_action_or_game) else None
            self.stdscr = stdscr

        if getattr(self, "stdscr", None):
            try:
                self.stdscr.nodelay(True)
                self.stdscr.keypad(True)
            except Exception:
                pass     

        self.deadzone = float(deadzone)
        self.backend = backend_name()
        self._using_controller = False
        self._pygame_joystick = None
        self._monitoring = False
        self._last_move = (0.0, 0.0)
        self._hotplug_thread = None
        self._event_queue: "queue.Queue[dict]" = queue.Queue()

        # mapping: action -> ("button", index) or ("axis_pos", axis_index, threshold)
        self.button_map = {
            "scan": ("button", PS4_BUTTON_MAP.get("triangle")),
            "logs": ("button", PS4_BUTTON_MAP.get("square")),
            "use": ("button", PS4_BUTTON_MAP.get("x")),
            "inspect": ("button", PS4_BUTTON_MAP.get("circle")),
            "help": ("axis_pos", PS4_AXIS_MAP.get("r2_axis"), 0.5),
        }

        # try to start hotplug monitoring (detect_input may raise)
        try:
            start_monitoring(self._hotplug_cb, poll_interval=HOTPLUG_POLL)
            self._monitoring = True
        except Exception:
            self.logger.debug("InputHandler: detect_input monitoring not available")

        # --- ensure pygame joystick subsystem is initialized if pygame is available ---
        if _PYGAME:
            try:
                # initialize pygame subsystems (safe to call multiple times)
                _PYGAME.init()
                _PYGAME.joystick.init()
                self.logger.debug("InputHandler: pygame available, joystick count=%d", _PYGAME.joystick.get_count())
                # If detect_input didn't claim a backend but pygame is present, prefer pygame
                if not self.backend:
                    self.logger.debug("InputHandler: no backend from detect_input; falling back to pygame")
                    self.backend = "pygame"
                # try to init joystick(s) now
                try:
                    self._init_pygame_joystick()
                except Exception:
                    self.logger.exception("InputHandler: _init_pygame_joystick failed")
            except Exception:
                self.logger.exception("InputHandler: pygame init failed")


        # if evdev backend and no pygame joystick, we'll poll devices on demand
        if not self._pygame_joystick and _EVDEV and self.backend == "evdev":
            # nothing to init here; poll will detect devices
            self.logger.debug("InputHandler: evdev available as fallback")

    

    # --- hotplug callback -------------------------------------------------
    def _hotplug_cb(self, ev_type: str, info: dict):
        self.logger.info("InputHandler hotplug %s: %s", ev_type, info)
        if ev_type == "added":
            # try to init pygame joystick if pygame backend
            if _PYGAME and self.backend == "pygame":
                self._init_pygame_joystick()
            else:
                # mark controller available
                self._using_controller = True
        elif ev_type == "removed":
            self._pygame_joystick = None
            self._using_controller = False

    # --- pygame init ------------------------------------------------------
    def _init_pygame_joystick(self):
        if not _PYGAME:
            return
        try:
            count = _PYGAME.joystick.get_count()
            if count <= 0:
                self.logger.debug("InputHandler: no pygame joysticks found")
                return
            j = _PYGAME.joystick.Joystick(0)
            j.init()
            self._pygame_joystick = j
            self._using_controller = True
            self.logger.info("InputHandler: using pygame joystick '%s'", j.get_name())
        except Exception:
            self.logger.exception("InputHandler: failed to init pygame joystick")

    # --- deadzone / axis helpers ------------------------------------------
    def _apply_deadzone(self, v: float) -> float:
        if abs(v) < self.deadzone:
            return 0.0
        sign = 1 if v > 0 else -1
        adj = (abs(v) - self.deadzone) / (1.0 - self.deadzone)
        return sign * _clamp(adj, 0.0, 1.0)

    def _axis_to_move(self, ax: float, ay: float) -> Tuple[float, float]:
        return (self._apply_deadzone(ax), self._apply_deadzone(ay))

    # --- public poll (call each frame) ------------------------------------
    def poll(self):
        """
        Call this each frame from the main loop.
        - If pygame joystick present, pump events and handle them.
        - Else if evdev backend, poll device list (detection only)
        """
        self.logger.debug("InputHandler.poll backend=%r pygame_joystick=%r", self.backend, bool(self._pygame_joystick))

          # poll curses keyboard first (priority)
        if getattr(self, "stdscr", None):
            try:
                self._poll_curses_once()
            except Exception as e:
                self.logger.exception(f"InputHandler: curses poll failed {e}")
        if _PYGAME and self._pygame_joystick:
            for ev in _PYGAME.event.get():
                self._handle_pygame_event(ev)
            # also evaluate axis-based actions (triggers as axis)
            self._check_axis_actions()
        elif _EVDEV and self.backend == "evdev":
            self._poll_evdev_once()
        else:
            # no controller backend available
            pass

    # --- pygame event handling -------------------------------------------
    def _handle_pygame_event(self, ev):
        self.logger.debug("pygame event: %r", ev)

        if ev.type == _PYGAME.JOYAXISMOTION:
            # read left stick axes by configured indices
            lx_idx = PS4_AXIS_MAP.get("left_x", 0)
            ly_idx = PS4_AXIS_MAP.get("left_y", 1)
            try:
                lx = self._pygame_joystick.get_axis(lx_idx)
            except Exception:
                lx = 0.0    
            try:
                ly = self._pygame_joystick.get_axis(ly_idx)
            except Exception:
                ly = 0.0
            mx, my = self._axis_to_move(lx, ly)
            if (mx, my) != self._last_move:
                self._last_move = (mx, my)
                self._emit_move(mx, my)
        elif ev.type == _PYGAME.JOYHATMOTION:
            hatx, haty = ev.value
            self._emit_move(float(hatx), float(haty))
        elif ev.type == _PYGAME.JOYBUTTONDOWN:
            self._handle_button_down(ev.button)
        elif ev.type == _PYGAME.JOYDEVICEADDED:
            self.logger.info("InputHandler: pygame device added")
            self._init_pygame_joystick()
        elif ev.type == _PYGAME.JOYDEVICEREMOVED:
            self.logger.info("InputHandler: pygame device removed")
            self._pygame_joystick = None
            self._using_controller = False

    def _check_axis_actions(self):
        # check axis-based mappings (e.g., triggers)
        for action, spec in self.button_map.items():
            if spec[0] == "axis_pos":
                _, axis_idx, threshold = spec
                if axis_idx is None:
                    continue
                try:
                    val = self._pygame_joystick.get_axis(axis_idx)
                    if val is None:
                        continue
                    # normalize from [-1..1] to [0..1] if needed
                    norm = (val + 1.0) / 2.0  # -1 -> 0, 1 -> 1
                    if norm > (threshold if threshold is not None else 0.5):
                        self._dispatch_action(action)
                except Exception:
                    self.logger.debug("InputHandler: axis read failed", exc_info=True)

    def _handle_button_down(self, btn_index: int):
        dir_name = PS4_DPAD_BUTTON_MAP.get(btn_index)
        if dir_name:
            # vytvoříme token typu move_dir, který Game.handle_token očekává
            self._enqueue_event({"type": "move_dir", "dir": dir_name})
            return

        # direct mapping
        for action, spec in self.button_map.items():
            if spec[0] == "button" and spec[1] == btn_index:
                self._dispatch_action(action)
                return
        # fallback name-based mapping using PS4_BUTTON_MAP inverse
        inv = {v: k for k, v in PS4_BUTTON_MAP.items() if isinstance(v, int)}
        name = inv.get(btn_index)
        if name:
            if name == "triangle":
                self._dispatch_action("scan")
            elif name == "square":
                self._dispatch_action("logs")
            elif name == "x":
                self._dispatch_action("use")
            elif name == "circle":
                self._dispatch_action("inspect")

    def _dispatch_action(self, action_key: str):
        action_name = DEFAULT_ACTIONS.get(action_key, action_key)
        logger.debug("InputHandler dispatch action %s", action_name)
        try:
            self.on_action(action_name, None)
        except Exception:
            logger.exception("InputHandler: on_action raised")

    def _emit_move(self, mx: float, my: float):
        if mx == 0 and my == 0:
            self.on_action("move", {"x": 0.0, "y": 0.0})
            return
        self.on_action("move", {"x": mx, "y": my})

    # --- evdev fallback (detection only) ---------------------------------
    def _poll_evdev_once(self):
        devices = list_controllers()
        if devices and not self._using_controller:
            self._using_controller = True
            self.controller_info = devices[0]
            logger.info(
                "InputHandler: evdev controller detected %s", self.controller_info
            )
        elif not devices and self._using_controller:
            self._using_controller = False
            self.controller_info = None
            logger.info("InputHandler: evdev controller removed")
        # full evdev event reading is intentionally omitted here; prefer pygame.
        
    def _poll_curses_once(self):
        """
        Non-blocking read from curses stdscr (if provided).
        Converts keys to token dicts and enqueues them.
        """
        if not getattr(self, "stdscr", None):
            return

        try:
            # ensure non-blocking
            try:
                self.stdscr.nodelay(True)
            except Exception:
                pass

            ch = self.stdscr.getch()
        except Exception:
            ch = -1

        if ch in (None, -1):
            return

        # Ctrl-C / SIGINT
        if ch == 3:
            self._enqueue_event({"type": "control", "key": "SIGINT"})
            return

        # arrow keys and WASD
        try:
            if ch == curses.KEY_UP or ch in (ord('w'), ord('W')):
                self._enqueue_event({"type": "move_dir", "dir": "UP"})
                return
            if ch == curses.KEY_DOWN or ch in (ord('s'), ord('S')):
                self._enqueue_event({"type": "move_dir", "dir": "DOWN"})
                return
            if ch == curses.KEY_LEFT or ch in (ord('a'), ord('A')):
                self._enqueue_event({"type": "move_dir", "dir": "LEFT"})
                return
            if ch == curses.KEY_RIGHT or ch in (ord('d'), ord('D')):
                self._enqueue_event({"type": "move_dir", "dir": "RIGHT"})
                return
        except Exception:
            pass

        # quick command shortcuts
        if ch in (ord('h'), ord('H')):
            self._enqueue_event({"type": "command", "cmd": "help"})
            return
        if ch in (ord('c'), ord('C')):
            self._enqueue_event({"type": "command", "cmd": "scan"})
            return
        if ch in (ord('l'), ord('L')):
            self._enqueue_event({"type": "command", "cmd": "logs"})
            return
        if ch in (ord('x'), ord('X')):
            self._enqueue_event({"type": "action", "name": "use"})
            return
        if ch in (ord('i'), ord('I')):
            self._enqueue_event({"type": "action", "name": "inspect"})
            return
        if ch in (ord('q'), ord('Q')):
            self._enqueue_event({"type": "control", "key": "QUIT"})
            return

       # colon command entry: ':' then read line (blocking)
        if ch == ord(':'):
            try:
                # prepare terminal for line input
                try:
                    # switch to blocking read so getstr waits for Enter
                    self.stdscr.nodelay(False)
                except Exception:
                    pass

                # show cursor and enable echo so user sees typed characters
                try:
                    curses.curs_set(1)
                except Exception:
                    pass
                try:
                    curses.echo()
                except Exception:
                    pass

                # draw a simple prompt on the bottom line
                try:
                    h, w = self.stdscr.getmaxyx()
                    prompt = ":"
                    # clear the bottom line
                    try:
                        self.stdscr.move(h - 1, 0)
                        self.stdscr.clrtoeol()
                    except Exception:
                        pass
                    try:
                        self.stdscr.addstr(h - 1, 0, prompt)
                    except Exception:
                        # fallback: try addstr without coords
                        try:
                            self.stdscr.addstr(prompt)
                        except Exception:
                            pass
                    try:
                        self.stdscr.refresh()
                    except Exception:
                        pass
                except Exception:
                    pass

                # blocking read of the rest of the line
                s = self.stdscr.getstr().decode(errors="ignore").strip()
                if s:
                    self._enqueue_event({"type": "command", "cmd": s})
            except Exception:
                # swallow errors but ensure terminal state restored
                try:
                    curses.noecho()
                except Exception:
                    pass
            finally:
                # restore non-blocking mode and hide cursor, disable echo
                try:
                    curses.noecho()
                except Exception:
                    pass
                try:
                    curses.curs_set(0)
                except Exception:
                    pass
                try:
                    self.stdscr.nodelay(True)
                except Exception:
                    pass
            return

        # printable fallback: enqueue as single-char command
        if 0 <= ch < 256:
            chs = chr(ch)
            if chs.isprintable():
                self._enqueue_event({"type": "command", "cmd": chs})
    

    # --- utilities / cleanup ---------------------------------------------
    def stop(self):
        try:
            stop_monitoring()
        except Exception:
            pass
        if _PYGAME and self._pygame_joystick:
            try:
                self._pygame_joystick.quit()
            except Exception:
                pass
        self._pygame_joystick = None
        self._using_controller = False

    def _enqueue_event(self, token: dict) -> None:
        """
        Interně vloží token do fronty a zároveň zavolá on_action (pokud je nastaveno).
        Token má strukturu např. {'type':'action','name':'use'} nebo {'type':'move','x':0.5,'y':-0.2}.
        """
        try:
            # neblokující put (fronta je neomezená, ale pro jistotu)
            self.logger.debug(f"Enqueueing event: {token}")
            self._event_queue.put_nowait(token)
        except Exception:
            self.logger.exception("InputHandler: failed to enqueue event")
        # zachovej callback pro kompatibilitu
        try:
            if self.on_action:
                # callback dostane stejný token (nebo jen název akce podle potřeby)
                # zde voláme callback asynchronně (synchronně v rámci vlákna main loopy)
                if token.get("type") == "action":
                    self.on_action(token.get("name"), None)
                else:
                    self.on_action(token.get("type"), token)
        except Exception:
            self.logger.exception("InputHandler: on_action raised in _enqueue_event")

    def _dispatch_action(self, action_key: str):
        action_name = DEFAULT_ACTIONS.get(action_key, action_key)
        self.logger.debug("InputHandler dispatch action %s", action_name)
        token = {"type": "action", "name": action_name}
        # vlož do fronty a zavolej callback
        self._enqueue_event(token)

    def _emit_move(self, mx: float, my: float):
        if mx == 0 and my == 0:
            token = {"type": "move", "x": 0.0, "y": 0.0}
        else:
            token = {"type": "move", "x": mx, "y": my}
        # vlož do fronty a zavolej callback
        self._enqueue_event(token)

    def process_once(self, timeout: Optional[float] = None) -> Optional[dict]:
        """
        Vrátí jeden token z fronty událostí nebo None pokud nic nepřišlo do timeoutu.
        - timeout = None -> blokuje dokud nepřijde událost
        - timeout = 0 -> neblokující (okamžitý návrat)
        - timeout > 0 -> blokuje maximálně timeout sekund
        Tokeny: {'type':'action','name':...} nebo {'type':'move','x':..., 'y':...}
        """
        try:
            self.poll()
        except Exception as e:
             self.logger.exception(f"poll inside process_once failed {e}")
        try:
            if timeout is None:    
                token = self._event_queue.get(block=True)
                return token
            elif timeout == 0:
                try:
                    return self._event_queue.get_nowait()
                except queue.Empty:
                    return None
            else:
                try:
                    return self._event_queue.get(block=True, timeout=float(timeout))
                except queue.Empty:
                    return None
        except Exception as e:
            self.logger.exception(f"InputHandler: process_once failed: {e}")
            return None 


# --- CLI helpers for mapping and monitoring -------------------------------
def _map_test_loop(poll_interval: float = 0.01):
    """
    Run a small interactive loop that prints pygame events and axis/button indices.
    Useful to discover actual indices for your controller.
    """
    if not _PYGAME:
        print("pygame not available; install pygame to use map-test.")
        return
    _PYGAME.init()
    _PYGAME.joystick.init()
    count = _PYGAME.joystick.get_count()
    print("pygame joysticks:", count)
    if count == 0:
        print("No joystick found.")
        return
    j = _PYGAME.joystick.Joystick(0)
    j.init()
    print("Joystick name:", j.get_name())
    print(
        "Axes:",
        j.get_numaxes(),
        "Buttons:",
        j.get_numbuttons(),
        "Hats:",
        j.get_numhats(),
    )
    print("Press buttons or move sticks; Ctrl-C to exit.")
    try:
        while True:
            for ev in _PYGAME.event.get():
                print(ev)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("map-test exiting")


def _monitor_cli(poll_interval: float = 1.0):
    """
    Simple monitor that prints hotplug events from detect_input.list_controllers.
    """
    prev = set()
    try:
        while True:
            devs = list_controllers()
            ids = set(d.get("id") for d in devs)
            added = ids - prev
            removed = prev - ids
            for a in added:
                print("added:", a)
            for r in removed:
                print("removed:", r)
            prev = ids
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("monitor exiting")


# --- module CLI ----------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="InputHandler debug CLI")
    parser.add_argument(
        "--map-test",
        action="store_true",
        help="Run pygame event map test (prints events)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor hotplug via detect_input.list_controllers",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    if args.map_test:
        _map_test_loop()
    elif args.monitor:
        _monitor_cli()
    else:
        # quick smoke: instantiate handler and print backend
        def cb(a, p):
            print("ACTION:", a, p)

        ih = InputHandler(cb)
        print("backend:", backend_name())
        try:
            while True:
                ih.poll()
                time.sleep(DEFAULT_POLL_INTERVAL)
        except KeyboardInterrupt:
            ih.stop()
            print("exiting")
