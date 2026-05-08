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
from email.policy import default
import logging
import threading
import time
import queue
import os
from typing import Callable, Dict, List, Optional, Tuple

from eidolon.io.controller_map import CONTROLLERS_DIR, find_controller_map_by_name, _load_json_file, merge_with_defaults
from eidolon.mechanics.game_state import GameState


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
        is_legacy = (
            on_action_or_game is not None
            and stdscr is None
            and hasattr(on_action_or_game, "getch")
            and not callable(on_action_or_game)
            and not hasattr(on_action_or_game, "gameState")   # nebo jiný znak Game objektu
        )

        if is_legacy:
            self.stdscr = on_action_or_game
            self.on_action = None
        else:
            self.game = on_action_or_game
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
            map_data = find_controller_map_by_name(j.get_name())
            default_map = _load_json_file(os.path.join(CONTROLLERS_DIR, "default.json")) or {}
            final_map = merge_with_defaults(map_data, default_map)
            self._pygame_joystick = j
            self._using_controller = True
            self.deadzone = final_map.get("deadzone", DEFAULT_DEADZONE)
            self.invert_y = final_map.get("invert_y", False)
            self.controller_buttons = final_map.get("buttons", {})
            self.axis_map = final_map.get("axes", {})
            self.dpad_button_map = final_map.get("dpad_buttons", {})
            # convert dpad keys to ints
            dpad = final_map.get("dpad_buttons", {})
            self.dpad_map = {int(k): v for k, v in dpad.items()} if dpad else {}
            self.action_by_button_name = final_map.get("action_by_button_name", {}) or {}
            # pokud hráč explicitně NEDEFINUJE action_map v JSONu,
            # nech ho prázdný → použije se action_by_button_name
            self.action_map = final_map.get("action_map", {})

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
    
    def _get_axis_index(self, key, default=0):
        try:
            return int(self.axis_map.get(key, default))
        except Exception:
            return default        
                

    # --- public poll (call each frame) ------------------------------------
    def poll(self):
        """
        Call this each frame from the main loop.
        - If pygame joystick present, pump events and handle them.
        - Else if evdev backend, poll device list (detection only)
        """
        #self.logger.debug("InputHandler.poll backend=%r pygame_joystick=%r", self.backend, bool(self._pygame_joystick))

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
            lx_idx = self._get_axis_index("left_x", 0)
            ly_idx = self._get_axis_index("left_y", 1)
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
        for action, spec in list(self.dpad_button_map.items()):
            # defensive: spec must be a sequence and have at least one element
            if not isinstance(spec, (list, tuple)):
                # skip plain integer mappings (these are controller index maps, not action specs)
                continue
            if len(spec) == 0:
                continue
            if spec[0] == "axis_pos":
                # unpack safely
                try:
                    _, axis_idx, threshold = spec
                except Exception:
                    continue
                if axis_idx is None:
                    continue
                try:
                    val = self._pygame_joystick.get_axis(axis_idx)
                    if val is None:
                        continue
                    norm = (val + 1.0) / 2.0
                    if norm > (threshold if threshold is not None else 0.5):
                        self._dispatch_action(action)
                except Exception:
                    self.logger.debug("InputHandler: axis read failed", exc_info=True)


    def _handle_button_down(self, btn_index: int):
        # 0) debug (dočasně) — vypiš mapy, abys viděl, co máš v paměti
        self.logger.debug("button_down idx=%r dpad_map=%r action_map_keys=%r controller_buttons=%r",
                      btn_index,
                      getattr(self, "dpad_button_map", None),
                      list(getattr(self, "action_map", {}).keys()),
                      getattr(self, "controller_buttons", None))

        # 1) D‑Pad tlačítka (surová mapa z JSON, klíče jsou int)
        dmap = getattr(self, "dpad_map", None) or getattr(self, "controller_dpad", None)
        if dmap and isinstance(dmap, dict):
            dir_name = dmap.get(btn_index)
            if dir_name:
                # v menu nechceme pohyb, ale navigaci
                nav_action = "navigate_up" if dir_name == "UP" else "navigate_down" if dir_name == "DOWN" else None
                if nav_action:
                    self._enqueue_event({"type": "action", "name": nav_action})
                
                self._enqueue_event({"type": "move_dir", "dir": dir_name})
                return

        # 2) action bindings: očekáváme, že action_map obsahuje spec jako ("button", idx)
        #    (pokud máš jiný název pro action bindings, použij ho)
        action_map = getattr(self, "action_map", None)
        if action_map and isinstance(action_map, dict):
            for action, spec in action_map.items():
                # defenzivně: spec musí být sekvence a mít typ "button"
                if not isinstance(spec, (list, tuple)) or len(spec) < 2:
                    continue
                if spec[0] == "button" and spec[1] == btn_index:
                    # dispatchuj akci (např. "use", "inspect", ...)
                    self._dispatch_action(action)
                    return

        # 3) fallback: surová controller button map (name -> idx) -> invertovat na idx->name
        ctrl_buttons = getattr(self, "controller_buttons", None)
        if isinstance(ctrl_buttons, dict):
            # ctrl_buttons: {"x":0, "circle":1, ...}
            inv = {v: k for k, v in ctrl_buttons.items() if isinstance(v, int)}
            name = inv.get(btn_index)
            if name:
                if name == "triangle":
                    self._dispatch_action("scan")
                elif name == "square":
                    self._dispatch_action("logs")
                default_bind = getattr(self, "action_by_button_name", {}).get(name)
                if default_bind:
                    self._dispatch_action(default_bind)
                    return

                else:
                    # obecný fallback: pokud máš defaultní action_map_by_name, použij ji
                    default_bind = getattr(self, "action_by_button_name", {}).get(name)
                    if default_bind:
                        self._dispatch_action(default_bind)
                return

        # 4) nic neodpovídá
        self.logger.debug("Unhandled button_down index=%r", btn_index)


    def _dispatch_action(self, action_name):
        game = self.game

        # --- PRIMARY BUTTON (X) ---
        if action_name == "primary":
            if game.gameState in (GameState.INTERACT, GameState.CONFIRM):
                self._enqueue_event({"type": "action", "name": "confirm"})
            else:
                self._enqueue_event({"type": "action", "name": "interact"})
            return

        # --- SECONDARY BUTTON (Circle) ---
        if action_name == "secondary":
            if game.gameState in (GameState.INTERACT, GameState.CONFIRM):
                self._enqueue_event({"type": "action", "name": "cancel"})
            else:
                self._enqueue_event({"type": "action", "name": "inspect"})
            return

        # --- ostatní akce z JSONu ---
        self._enqueue_event({"type": "action", "name": action_name})


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
        
        # enter
        if ch in (10, 13, curses.KEY_ENTER):
            self._enqueue_event({"type": "action", "name": "confirm"})
            return  

        # arrow keys and WASD
        try:
            if ch == curses.KEY_UP or ch in (ord('w'), ord('W')):
                self._enqueue_event({"type": "move_dir", "dir": "UP"})
                self._enqueue_event({"type": "action", "name": "navigate_up"})
                return
            if ch == curses.KEY_DOWN or ch in (ord('s'), ord('S')):
                self._enqueue_event({"type": "move_dir", "dir": "DOWN"})
                self._enqueue_event({"type": "action", "name": "navigate_down"})
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
        if ch in (ord('j'), ord('J')):
            self._enqueue_event({"type": "action", "name": "inspect"})
            return
        if ch in (ord('q'), ord('Q')):
            self._enqueue_event({"type": "control", "key": "QUIT"})
            return
        if ch in (ord('i'), ord('I')):
            self._enqueue_event({"type": "action", "name": "interact"})
            return
        if ch in (27, ord('k'), ord('K')):
            self._enqueue_event({"type": "action", "name": "cancel"})
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
