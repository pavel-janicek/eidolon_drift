# main.py
import traceback
from pathlib import Path

# Cross-platform curses import
try:
    import curses
except ImportError:
    try:
        # Try windows-curses for Windows
        import windows_curses as curses
    except ImportError:
        # Fallback: create a mock curses module
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
            is_mock = True

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
                # For mock curses, just call the function directly
                try:
                    return func(None, *args)
                except TypeError:
                    return func(*args)

        curses = MockCurses()
        print(
            "Warning: Curses not available. Using fallback text interface.",
            file=sys.stderr,
        )

from eidolon.game_loop import Game

# optional imports
try:
    from eidolon.io.output_renderer import OutputRenderer
except Exception:
    OutputRenderer = None

try:
    from eidolon.io.input_handler import InputHandler
except Exception:
    InputHandler = None

# map generator and config
try:
    from eidolon.generation.map_generator import MapGenerator
except Exception:
    MapGenerator = None

try:
    from eidolon.config import (
        MIN_MAP_WIDTH,
        MIN_MAP_HEIGHT,
        DEFAULT_BASE_DENSITY,
        DEFAULT_MIN_DISTANCE,
    )
except Exception:
    MIN_MAP_WIDTH = 10
    MIN_MAP_HEIGHT = 5
    DEFAULT_BASE_DENSITY = 0.06
    DEFAULT_MIN_DISTANCE = 3

CRASH_LOG = Path("crash.log")


def _init_curses(stdscr):
    # curses.wrapper() already handles noecho() and cbreak()
    # only do stdscr-specific setup here
    try:
        curses.curs_set(0)
    except Exception:
        pass
    try:
        stdscr.keypad(True)
        stdscr.timeout(100)
    except Exception:
        pass
    if curses.has_colors():
        try:
            curses.start_color()
            curses.use_default_colors()
        except Exception:
            pass


def _safe_write_crash(exc: Exception):
    try:
        with CRASH_LOG.open("a", encoding="utf-8") as f:
            f.write("=== Crash ===\n")
            traceback.print_exc(file=f)
            f.write("\n\n")
    except Exception:
        pass


def _compute_map_tiles_from_term(stdscr):
    """
    Vrátí (tiles_w, tiles_h) — počet dlaždic mapy, které se vejdou do map_win.
    Logika odpovídá rozložení rendereru: status nahoře, messages dole, popis vpravo pokud prostor dovolí.
    """
    maxy, maxx = stdscr.getmaxyx()
    status_h = 3
    msg_h = max(4, maxy // 5)
    avail_h = maxy - status_h - msg_h - 5
    if avail_h < MIN_MAP_HEIGHT:
        avail_h = MIN_MAP_HEIGHT

    preferred_desc_w = 30
    max_map_w_with_desc = maxx - (preferred_desc_w + 6)
    if max_map_w_with_desc >= MIN_MAP_WIDTH:
        # side description possible
        map_win_w = min(max_map_w_with_desc, maxx - 4)
    else:
        # no side description, map can use full width
        map_win_w = maxx - 4

    # inner tile counts (remove box borders)
    tiles_w = max(MIN_MAP_WIDTH, map_win_w - 2)
    tiles_h = max(MIN_MAP_HEIGHT, avail_h - 2)

    return tiles_w, tiles_h


def _ensure_player_on_map(game):
    """
    Ujistí se, že game.player existuje a je v rámci game.map.
    Pokud player neexistuje, pokusí se importovat Player; pokud to selže,
    vytvoří jednoduchý fallback objekt s potřebnými atributy.
    """
    # ensure map exists
    m = getattr(game, "map", None)
    if m is None:
        return

    p = getattr(game, "player", None)
    if p is None:
        # try to import Player class if available
        try:
            from eidolon.world.player import Player  # type: ignore

            game.player = Player(x=0, y=0)
            p = game.player
        except Exception:
            # fallback minimal player
            class _P:
                def __init__(self, x=0, y=0):
                    self.x = x
                    self.y = y
                    self.health = 100
                    self.max_health = 100

            game.player = _P(0, 0)
            p = game.player

    # clamp player position to map bounds
    try:
        p.x = max(0, min(getattr(m, "width", 1) - 1, getattr(p, "x", 0)))
        p.y = max(0, min(getattr(m, "height", 1) - 1, getattr(p, "y", 0)))
    except Exception:
        try:
            p.x = 0
            p.y = 0
        except Exception:
            pass


def _run(stdscr):
    _init_curses(stdscr)

    # compute desired tile counts from terminal size (before generator)
    tiles_w, tiles_h = _compute_map_tiles_from_term(stdscr)

    # generate map if MapGenerator available, otherwise Game will create its own map
    generated_map = None
    if MapGenerator is not None:
        try:
            gen = MapGenerator(
                width=tiles_w,
                height=tiles_h,
                base_density=DEFAULT_BASE_DENSITY,
                min_distance=DEFAULT_MIN_DISTANCE,
            )
            # prefer explicit generate(width,height)
            generated_map = gen.generate(width=tiles_w, height=tiles_h)
        except Exception as e:
            # non-fatal: log to stderr and continue
            import sys

            print(f"[mapgen] generation failed: {e}", file=sys.stderr)
            generated_map = None

    # create Game (pass stdscr if supported)
    if "stdscr" in Game.__init__.__code__.co_varnames:
        game = Game(stdscr=stdscr)
    else:
        game = Game()

    # if we generated a map, override game.map and ensure player fits
    if generated_map is not None:
        try:
            game.map = generated_map
            _ensure_player_on_map(game)
        except Exception as e:
            try:
                game.push_message(f"[debug] failed to assign generated map: {e}")
            except Exception:
                pass

    # create renderer now that game.map and game.player are set
    if OutputRenderer is not None:
        try:
            game.renderer = OutputRenderer(stdscr, game.map, game.player, game)
            try:
                game.renderer.render()
                # game.push_message("[debug] renderer.render() called once from main")
            except Exception as e:
                game.push_message(f"[debug] renderer.render() failed: {e}")
        except Exception as e:
            try:
                game.push_message(f"[debug] failed to create renderer: {e}")
            except Exception:
                pass

    # create input handler if available
    if InputHandler is not None:
        try:
            game.input_handler = InputHandler(game, stdscr)
        except Exception as e:
            try:
                game.push_message(f"[debug] failed to create input handler: {e}")
            except Exception:
                pass
    else:
        try:
            game.push_message(
                "[debug] InputHandler not found; using Game's internal input loop"
            )
        except Exception:
            pass

    # run main loop
    try:
        if "stdscr" in Game.run.__code__.co_varnames:
            game.run(stdscr=stdscr)
        else:
            game.run()
    except Exception as exc:
        _safe_write_crash(exc)
        try:
            game.push_message(
                "[fatal] Unhandled exception occurred. See crash.log for details."
            )
        except Exception:
            pass


def main():
    try:
        # Check if we have real curses or mock curses
        if hasattr(curses, "wrapper") and not getattr(curses, "is_mock", False):
            # Real curses available
            curses.wrapper(_run)
        else:
            # Mock curses or no curses - run in text mode
            try:
                from eidolon.config import GAME_VERSION

                version = GAME_VERSION
            except:
                version = "0.9.0"

            print(f"EIDOLON DRIFT - Incident Response Terminal v{version}")
            print("Running in text mode (curses not available)")
            print("Use 'python main.py --text' for better text interface")
            print()

            # Create game without curses
            game = Game()

            # Simple text-based game loop
            print("Welcome to Eidolon Drift!")
            print("Type ':help' for commands, ':quit' to exit")
            print()

            while True:
                try:
                    cmd = input("> ").strip()
                    if cmd.lower() in ("quit", "q", "exit"):
                        break
                    if cmd:
                        result = game.handle_command(cmd)
                        if result:
                            print(result)
                        # Print recent messages
                        for msg in game.messages[-5:]:
                            print(f"  {msg}")
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error: {e}")

    except Exception as e:
        _safe_write_crash(e)
        print("Fatal error starting the game. See crash.log for details.")


if __name__ == "__main__":
    main()
