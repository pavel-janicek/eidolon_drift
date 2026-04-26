# eidolon/game_loop.py
import curses
from importlib.resources import path
from pathlib import Path
import random
from eidolon.generation.map_generator import MapGenerator
from eidolon.world.player import Player
from eidolon.io.input_handler import InputHandler
from eidolon.io.output_renderer import OutputRenderer
from eidolon.mechanics.movement import move_player
from eidolon.mechanics import commands as cmdmod
from eidolon.mechanics.events import EventEngine
from eidolon.mechanics.event_loader import load_event_defs


class Game:
    def __init__(self, stdscr=None, map_width=None, map_height=None, map_seed=None, base_density=None, min_distance=None):
        """
        Initialize game state.
        Optional args:
          - stdscr: curses screen (or None)
          - map_width/map_height: override generator size
          - map_seed: optional seed passed to MapGenerator (None => config.SEED or system randomness)
          - base_density/min_distance: optional generator tuning
        """
        self.stdscr = stdscr

        # --- create generator and map (keep generator reference) ---
        # create MapGenerator with optional tuning; MapGenerator handles seed fallback
        gen = MapGenerator(width=map_width, height=map_height, seed=map_seed,
                           base_density=base_density, min_distance=min_distance)
        game_map = gen.generate(width=map_width, height=map_height)
        # keep generator reference on the map for later use (spawning, instantiation)
        setattr(game_map, "generator", gen)
        self.map = game_map

        # reuse generator RNG for game-level randomness (consistent seeding)
        self.rng = getattr(gen, "rng", random.Random())

        # --- find player start (prefer AIRLOCK) ---
        start = None
        try:
            for (x, y), s in self.map.grid.items():
                if getattr(s, "type", "").upper() == "AIRLOCK":
                    start = (x, y)
                    break
        except Exception:
            start = None
        if start is None:
            # fallback: try map.get_sector if available, else (0,0)
            try:
                sec = self.map.get_sector(0, 0)
                if sec:
                    start = (sec.x, sec.y)
                else:
                    start = (0, 0)
            except Exception:
                start = (0, 0)

        # --- player and core systems ---
        self.player = Player(x=start[0], y=start[1])
        self.input_handler = None
        self.renderer = None
        self.running = True

        # messages buffer and debug push helper
        self.messages = []
        # event system
        self.event_defs = load_event_defs()
        self.event_engine = EventEngine(self, event_defs=self.event_defs)

        # last position for linger logic
        self._last_pos = (self.player.x, self.player.y)

        # tick and ambient systems
        self.tick_counter = 0
        # ambient tuning (can be overridden later)
        self.ambient_spawn_interval = getattr(self, "ambient_spawn_interval", 20)
        self.ambient_message_chance = getattr(self, "ambient_message_chance", 0.06)

        # load ambient messages (non-fatal)
        try:
            # expects Game._load_ambient_messages(path) to exist; if not, this is a no-op
            if hasattr(self, "_load_ambient_messages"):
                self._load_ambient_messages("data/ambient_messages.json")
            else:
                # minimal fallback: empty list
                self.ambient_messages = []
        except Exception:
            self.ambient_messages = []

        # expose map generator on game for convenience (some code expects game.map.generator)
        self.map.generator = gen

        # startup flavor messages
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

                if stdscr and not getattr(self, "renderer", None):
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

    def handle_command(self, cmd):
        try:
            return cmdmod.handle_command(self, cmd)
        except Exception as e:
            self.push_message(f"[debug] game.handle_command error: {e}")
            return f"Command error: {e}"

    def handle_death(self, reason="You died."):
        self.push_message(reason)
        self.push_message("You have died. Game over.")
        if self.renderer:
            self.renderer.render()
        self.running = False

    # in Game class
    def tick_spawn_ambient(self):
        # called every few ticks
        if not getattr(self, "map", None):
            return
        # small chance per tick to spawn 0..2 items
        if self.rng.random() > 0.25:
            return
        attempts = 8
        for _ in range(self.rng.randint(1,2)):
            rx = self.rng.randrange(0, self.map.width)
            ry = self.rng.randrange(0, self.map.height)
            sec = self.map.grid.get((rx, ry))
            if not sec:
                continue
            # prefer empty or low-object sectors
            if getattr(sec, "objects", None) and len(sec.objects) >= 2:
                continue
            # choose a filler template id list (match ids you added)
            filler_ids = ["debris_small", "battery_pack", "note_scrap"]
            tpl = self.map.generator.template_index.get(self.rng.choice(filler_ids))
            if not tpl:
                # fallback: pick any template with small weight
                candidates = [t for t in self.map.generator.templates if t.get("kind")=="template" and t.get("type") in ("debris","item","log")]
                if not candidates:
                    continue
                tpl = self.rng.choice(candidates)
            obj = self.map.generator._instantiate_from_template(tpl, sec)
            sec.objects.append(obj)
    
    def _load_ambient_messages(self, path: str = "data/ambient_messages.json"):
        """
        Load ambient messages from a JSON file into self.ambient_messages.
        Non‑fatal: on error or missing file, sets an empty list.
        """
        from pathlib import Path
        import json
        self.ambient_messages = []
        try:
            p = Path(path)
            # try a few sensible fallbacks
            if not p.exists():
                p = Path.cwd() / "data" / "ambient_messages.json"
            if not p.exists():
                # try relative to the project (two levels up from this file)
                p = Path(__file__).resolve().parents[2] / "data" / "ambient_messages.json"
            if not p.exists():
                # nothing found — keep empty list
                return
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                # keep only non-empty strings
                self.ambient_messages = [str(s).strip() for s in data if isinstance(s, str) and s.strip()]
        except Exception as e:
            # non-fatal: keep empty list and log to stderr if possible
            try:
                import sys
                print(f"[debug] failed to load ambient messages: {e}", file=sys.stderr)
            except Exception:
                pass
            self.ambient_messages = []

