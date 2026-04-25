# eidolon/game_loop.py
import curses
from eidolon.generation.map_generator import MapGenerator
from eidolon.world.player import Player
from eidolon.io.input_handler import InputHandler
from eidolon.io.output_renderer import OutputRenderer
from eidolon.mechanics.movement import move_player
from eidolon.mechanics import commands as cmdmod
from eidolon.mechanics.events import EventEngine
from eidolon.mechanics.event_loader import load_event_defs


class Game:
    def __init__(self, stdscr=None):
        self.stdscr = stdscr
        self.map = MapGenerator().generate()

        start = None
        for (x, y), s in self.map.grid.items():
            if getattr(s, "type", "").upper() == "AIRLOCK":
                start = (x, y)
                break
        if start is None:
            start = (0, 0)

        self.player = Player(x=start[0], y=start[1])
        self.input_handler = None
        self.renderer = None
        self.running = True
        self.messages = []
        self.event_defs = load_event_defs()
        self.event_engine = EventEngine(self, event_defs=self.event_defs)
        self._last_pos = (self.player.x, self.player.y)

        self.push_message("[debug] game initialized, messages buffer created")
        self.push_message(
            "Distress call received from vessel 'Eidolon'. You answered. Objective: reach the Command Module and use the escape pod."
        )
        self.push_message("Type 'help' for commands. Use WASD to move.")

    def push_message(self, text):
        if not hasattr(self, "messages"):
            self.messages = []

        self.messages.append(str(text))
        if len(self.messages) > 200:
            self.messages = self.messages[-200:]

        try:
            with open("eidolon_messages.log", "a", encoding="utf-8") as f:
                f.write(str(text).replace("\n", " ") + "\n")
        except Exception:
            pass

    def _curses_main(self, stdscr):
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        self.stdscr = stdscr
        self.input_handler = InputHandler(stdscr)
        self.renderer = OutputRenderer(stdscr, self.map, self.player, self)
        self.renderer.render()

        while self.running:
            key = self.input_handler.get_key()
            if key is None:
                continue

            if key == "QUIT":
                self.running = False
                break

            if key.startswith("CMD:"):
                cmd = key[4:]
                result = cmdmod.handle_command(self, cmd)
                if result:
                    self.push_message(result)
                self.tick(action_type="command")
            else:
                moved = move_player(self.map, self.player, key)
                if moved:
                    sector = self.map.get_sector(self.player.x, self.player.y)
                    name = sector.name if sector else f"({self.player.x},{self.player.y})"
                    self.push_message(f"Moved to {name}.")
                else:
                    self.push_message("Cannot move there.")
                self.tick(action_type="move")

            self.renderer.render()

    def run(self, stdscr=None):
        import time

        try:
            self.push_message("[debug] Game.run starting")
        except Exception:
            pass

        if getattr(self, "renderer", None):
            try:
                self.renderer.render()
                try:
                    self.push_message("[debug] initial renderer.render() OK")
                except Exception:
                    pass
            except Exception as e:
                try:
                    self.push_message(f"[debug] initial renderer.render() failed: {e}")
                except Exception:
                    pass

        try:
            while getattr(self, "running", True):
                if getattr(self, "renderer", None):
                    try:
                        self.renderer.render()
                    except Exception as e:
                        try:
                            self.push_message(f"[debug] renderer.render error: {e}")
                        except Exception:
                            pass

                if getattr(self, "input_handler", None):
                    try:
                        self.input_handler.process_once()
                    except Exception as e:
                        try:
                            self.push_message(f"[debug] input_handler error: {e}")
                        except Exception:
                            pass
                else:
                    if stdscr:
                        try:
                            ch = stdscr.getch()
                            if ch in (ord("q"), 27):
                                try:
                                    self.push_message("[debug] quitting via key")
                                except Exception:
                                    pass
                                self.running = False
                        except Exception:
                            pass

                try:
                    self.tick()
                except Exception as e:
                    try:
                        self.push_message(f"[debug] tick error: {e}")
                    except Exception:
                        pass

                time.sleep(0.02)

                if stdscr:
                    try:
                        maxy, maxx = stdscr.getmaxyx()
                        for i, line in enumerate(self.messages[-6:], start=1):
                            try:
                                stdscr.addstr(i, 1, line[:maxx - 2])
                            except Exception:
                                pass
                        stdscr.refresh()
                    except Exception:
                        pass

        except Exception as e:
            try:
                self.push_message(f"[fatal] Game.run crashed: {e}")
            except Exception:
                pass
            raise

    def tick(self, action_type="move"):
        sector = self.map.get_sector(self.player.x, self.player.y)
        if sector is None:
            return

        if getattr(self, "_last_pos", None) == (self.player.x, self.player.y):
            sector.linger_counter = getattr(sector, "linger_counter", 0) + 1
        else:
            sector.linger_counter = 0

        self._last_pos = (self.player.x, self.player.y)

        thresholds = getattr(sector, "linger_thresholds", {}) or {}
        for th, event_list in list(thresholds.items()):
            if sector.linger_counter >= int(th):
                for event_id in (event_list if isinstance(event_list, list) else [event_list]):
                    event_def = self.event_defs.get(event_id)
                    if event_def:
                        self.event_engine.trigger(event_def, sector)
                sector.linger_counter = 0

    def handle_death(self, reason="You died."):
        self.push_message(reason)
        self.push_message("You have died. Game over.")
        if self.renderer:
            self.renderer.render()
        self.running = False
