# eidolon/game_loop.py
# Cross-platform curses import
try:
    import curses
    import signal
except ImportError:
    try:
        # Try windows-curses for Windows
        import windows_curses as curses
    except ImportError:
        # Fallback: create a mock curses module for basic functionality
        import sys
        class MockCurses:
            COLOR_CYAN = 1
            COLOR_YELLOW = 2
            COLOR_GREEN = 3
            COLOR_RED = 4
            COLOR_MAGENTA = 5
            COLOR_WHITE = 7
            COLOR_BLACK = 0
            A_BOLD = 1
            A_NORMAL = 0
            A_REVERSE = 2
            KEY_UP = 259
            KEY_DOWN = 258
            KEY_LEFT = 260
            KEY_RIGHT = 261
            KEY_BACKSPACE = 263
            KEY_ENTER = 10
            KEY_NPAGE = 338
            KEY_PPAGE = 339
            KEY_HOME = 262
            KEY_END = 360

            @staticmethod
            def has_colors():
                return False

            @staticmethod
            def start_color():
                pass

            @staticmethod
            def use_default_colors():
                pass

            @staticmethod
            def init_pair(*args):
                pass

            @staticmethod
            def color_pair(n):
                return 0

            @staticmethod
            def curs_set(n):
                pass

            @staticmethod
            def wrapper(func, *args):
                return func(*args)

        curses = MockCurses()
from pathlib import Path
import random
from eidolon.generation.map_generator import MapGenerator
from eidolon.world import sector
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
        self.ambient_spawn_interval = getattr(self, "ambient_spawn_interval", 3000)
        self.ambient_message_interval = getattr(self, "ambient_message_interval", 200)
        self.current_ambient_message = None

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

        if getattr(self, "ambient_messages", None):
            self.current_ambient_message = self.ambient_messages[0]

        # expose map generator on game for convenience (some code expects game.map.generator)
        self.map.generator = gen

        # startup flavor messages
        self.push_message(
            "Distress call received from vessel 'Eidolon'. You answered. Objective: reach the Command Module and use the escape pod."
        )
        self.push_message("Type 'help' for commands. Use WASD to move.")
        self.awaiting_quit_confirm = False
        # stav pro escape dialog
        self.awaiting_escape_confirm = False



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

            if key == "QUIT_REQUEST":
                self.awaiting_quit_confirm = True
                self.push_message("Quit game? (y/n)")
                continue


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
        import signal

        def _sigint_handler(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _sigint_handler)

        try:
            self.push_message("[debug] Game.run starting")

            if self.renderer:
                try:
                    self.renderer.render()
                except Exception as e:
                    self.push_message(f"[debug] initial renderer.render() failed: {e}")

            while self.running:

                # quit confirm modal
                if self.awaiting_quit_confirm:
                    self._handle_quit_confirm()
                    continue

                # render
                if self.renderer:
                    try:
                        self.renderer.render()
                    except Exception as e:
                        self.push_message(f"[debug] renderer.render error: {e}")

                # input
                if self.input_handler:
                    token = self.input_handler.process_once()
                else:
                    token = None

                if token == "QUIT_REQUEST":
                    self.awaiting_quit_confirm = True
                    self.push_message("Quit game? (y/n)")
                    continue

                if token and token.startswith("CMD:"):
                    cmd = token[4:]
                    result = cmdmod.handle_command(self, cmd)
                    if result:
                        self.push_message(result)
                    self.tick(action_type="command")
                    continue

                # movement
                if token in ("UP", "DOWN", "LEFT", "RIGHT"):
                    moved = move_player(self.map, self.player, token)
                    if moved:
                        sec = self.map.get_sector(self.player.x, self.player.y)
                        #self.push_message(f"Moved to {sec.name}.")
                    else:
                        self.push_message("Cannot move there.")
                    self.tick(action_type="move")
                    continue

                # tick
                self.tick()

                time.sleep(0.02)

        except KeyboardInterrupt:
            self.awaiting_quit_confirm = True
            self.run()
        except Exception as e:
            self.push_message(f"[debug] Game.run error: {e}")



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
        # --- SANITY HANDLING ---

        # 1) sanity decay over time (slow, atmospheric)
        if not hasattr(self, "_sanity_tick_counter"):
            self._sanity_tick_counter = 0

        self._sanity_tick_counter += 1

        # lose 1 sanity every 70 ticks
        if self._sanity_tick_counter >= 70:
            self.player.lose_sanity(1)
            self._sanity_tick_counter = 0

        # 2) anomaly proximity
        sector = self.map.get_sector(self.player.x, self.player.y)
        if sector and any(o.get("type") == "anomaly" for o in sector.objects):
            self.player.lose_sanity(1)
            self.push_message("You feel a pressure in your skull...")

        # 3) optional: dark sectors
        if sector and getattr(sector, "dark", False):
            if random.random() < 0.05:  # 5% chance per tick
                self.player.lose_sanity(1)
        
        # --- SANITY RECOVERY: MEDBAY ---
        if not hasattr(self, "_sanity_medbay_counter"):
                self._sanity_medbay_counter = 0

        sector = self.map.get_sector(self.player.x, self.player.y)

        if sector and sector.type == "MEDBAY":
            # medbay slowly restores sanity
        
            self._sanity_medbay_counter += 1

        # restore 1 sanity every 5 ticks
        if self._sanity_medbay_counter >= 5:
            self.player.gain_sanity(1)
            self._sanity_medbay_counter = 0
            self.push_message("You feel calmer here.")

        # --- AMBIENT MESSAGE UPDATE ---
        if not hasattr(self, "_ambient_message_tick_counter"):
            self._ambient_message_tick_counter = 0

        self._ambient_message_tick_counter += 1
        if self._ambient_message_tick_counter >= self.ambient_message_interval:
            if getattr(self, "ambient_messages", None):
                self.current_ambient_message = (
                    self.rng.choice(self.ambient_messages)
                    if getattr(self, "rng", None)
                    else self.ambient_messages[0]
                )
            self._ambient_message_tick_counter = 0

        # --- AMBIENT SPAWNING ---
        # Call ambient spawning on a configurable interval
        if not hasattr(self, "_ambient_tick_counter"):
            self._ambient_tick_counter = 0

        self._ambient_tick_counter += 1
        if self._ambient_tick_counter >= self.ambient_spawn_interval:
            self.tick_spawn_ambient()
            self._ambient_tick_counter = 0
        
        

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
        # called on the ambient spawn interval
        if not getattr(self, "map", None):
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
    
    def _load_ambient_messages(self, path: str = None):
        """
        Robustní loader ambientních zpráv.
        - path: může být absolutní nebo relativní; pokud None, zkusíme několik standardních míst.
        - výstup: self.ambient_messages = list[str]
        - debug: vypisuje do stderr, co našel / proč selhal.
        """
        from pathlib import Path
        import json, sys

        self.ambient_messages = []

        # candidate paths (in order)
        candidates = []
        if path:
            candidates.append(Path(path))
        # data/ sibling of the eidolon package directory (installed layout)
        candidates.append(Path(__file__).resolve().parent / "data" / "ambient_messages.json")
        # one level above the package (source tree / legacy installed layout)
        candidates.append(Path(__file__).resolve().parent.parent / "data" / "ambient_messages.json")
        # cwd/data (fallback for running from project root)
        candidates.append(Path.cwd() / "data" / "ambient_messages.json")

        tried = []
        for p in candidates:
            try:
                p = p.resolve()
            except Exception:
                # ignore resolution errors, keep original Path
                pass
            tried.append(str(p))
            if not p.exists():
                continue
            try:
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    msgs = [str(s).strip() for s in data if isinstance(s, str) and s.strip()]
                    if msgs:
                        self.ambient_messages = msgs
                        print(f"[debug] loaded {len(msgs)} ambient messages from {p}", file=sys.stderr)
                        return
                    else:
                        print(f"[debug] file {p} parsed but contains no valid strings", file=sys.stderr)
                else:
                    print(f"[debug] file {p} parsed but top-level JSON is not a list", file=sys.stderr)
            except Exception as e:
                print(f"[debug] failed to read/parse {p}: {e}", file=sys.stderr)

        # nothing found
        print(f"[debug] ambient messages not found. Tried: {tried}", file=sys.stderr)
        self.ambient_messages = []


    def debug_emit_ambient(self):
        if not getattr(self, "ambient_messages", None):
            import sys
            print("[debug] no ambient messages loaded", file=sys.stderr)
            return
        # choose using game RNG for reproducibility
        msg = self.rng.choice(self.ambient_messages) if getattr(self, "rng", None) else self.ambient_messages[0]
        # debug print to stderr and push to in‑game messages
        import sys
        print(f"[debug] forcing ambient message: {msg}", file=sys.stderr)
        self.push_message(msg)

    def _handle_quit_confirm(self):
         if not self.awaiting_quit_confirm:
             self.awaiting_quit_confirm = True
         self._show_quit_dialog()
        
    def _show_quit_dialog(self):
        """
        Vykreslí modální quit dialog doprostřed obrazovky.
        Blokuje, dokud hráč nezmáčkne Y nebo N.
        """
        h, w = self.stdscr.getmaxyx()

        dialog_w = 32
        dialog_h = 5

        x0 = (w - dialog_w) // 2
        y0 = (h - dialog_h) // 2

        win = curses.newwin(dialog_h, dialog_w, y0, x0)
        win.border()

        win.addstr(1, (dialog_w - len("Quit the game?")) // 2, "Quit the game?")
        win.addstr(3, (dialog_w - len("[Y]es   [N]o")) // 2, "[Y]es   [N]o")

        win.refresh()

        while True:
            ch = self.stdscr.getch()
            if ch in (ord('y'), ord('Y')):
                self.running = False
                return
            if ch in (ord('n'), ord('N')):
                self.awaiting_quit_confirm = False
            return
    
    def restart(self, new_seed=None):
        """
        Restartuje hru na stejném stdscr s novým seedem (pokud je předán).
        Volá __init__ na existující instanci, což znovu inicializuje mapu, hráče, RNG atd.
        """
        # uložíme stdscr, aby __init__ mohl znovu použít terminál
        stdscr = getattr(self, "stdscr", None)
        # volitelně zachovej rozměry mapy, pokud existují
        map_w = getattr(self, "map", None) and getattr(self.map, "width", None)
        map_h = getattr(self, "map", None) and getattr(self.map, "height", None)

        try:
            # zavolat __init__ znovu s novým seedem
            self.__init__(stdscr=stdscr, map_width=map_w, map_height=map_h, map_seed=new_seed)
            # krátká debug zpráva (push_message je volána v __init__, ale necháme i tuto)
            try:
                self.push_message("[debug] Game restarted.")
            except Exception:
                pass
        except Exception as e:
            try:
                self.push_message(f"[debug] restart failed: {e}")
            except Exception:
                pass

    def _show_escape_dialog(self):
        """
        Vykreslí modální dialog po použití escape podu.
        Zobrazí final stats a nabídne Play again? [Yes] [No].
        Pokud hráč zvolí Yes, restartuje hru s novým seedem.
        Pokud No, ukončí hru.
        """
        try:
            h, w = self.stdscr.getmaxyx()
        except Exception:
            # pokud stdscr není dostupné, fallback na textové potvrzení
            try:
                self.push_message("You successfully used escape pod and escaped to safety.")
                self.push_message(f"Final Health: {getattr(self.player, 'health', 'N/A')}")
                self.push_message(f"Final Sanity: {getattr(self.player, 'sanity', 'N/A')}")
                self.push_message("Play again? (y/n)")
            except Exception:
                pass
            return

        dialog_w = min(50, w - 4)
        dialog_h = 9
        x0 = (w - dialog_w) // 2
        y0 = (h - dialog_h) // 2

        win = curses.newwin(dialog_h, dialog_w, y0, x0)
        try:
            win.keypad(True)
        except Exception:
            pass
        win.border()

        title = " Escape Pod "
        try:
            # center title on top border
            win.addstr(0, max(1, (dialog_w - len(title)) // 2), title, curses.A_BOLD)
        except Exception:
            pass

        # body text
        lines = [
            "You successfully used the escape pod and escaped to safety.",
            "",
            f"Final Health: {getattr(self.player, 'health', 'N/A')}",
            f"Final Sanity: {getattr(self.player, 'sanity', 'N/A')}",
            "",
            "Play again? [Y]es   [N]o"
        ]

        for i, line in enumerate(lines, start=1):
            try:
                # center lines horizontally
                pad = max(0, (dialog_w - 2 - len(line)) // 2)
                win.addstr(i, 1 + pad, line[:dialog_w - 2])
            except Exception:
                pass

        win.refresh()

        # blokující smyčka pro volbu
        while True:
            try:
                ch = self.stdscr.getch()
            except KeyboardInterrupt:
                # ignoruj opakované Ctrl+C během dialogu
                continue
            except Exception:
                # pokud getch selže, ukončí dialog a nech hru skončit
                self.running = False
                return

            if ch in (ord('y'), ord('Y')):
                # restart s novým náhodným seedem
                try:
                    new_seed = self.rng.randint(0, 2**31 - 1)
                except Exception:
                    import time
                    new_seed = int(time.time()) & 0x7fffffff
                # zavolat restart
                self.restart(new_seed=new_seed)
                return
            if ch in (ord('n'), ord('N')):
                # ukončit hru
                self.running = False
                return
            # jiná klávesa → ignoruj a čekej dál

    def _handle_escape_confirm(self):
        # wrapper, aby byl konzistentní s quit handlerem
        self._show_escape_dialog()
        

