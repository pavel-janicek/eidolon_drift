# main.py
import curses
import traceback
from pathlib import Path

from eidolon.game_loop import Game

# pokusíme se importovat renderer a input handler, ale pokud v projektu
# používáš jiné jméno, uprav importy podle toho
try:
    from eidolon.io.output_renderer import OutputRenderer
except Exception:
    OutputRenderer = None

try:
    from eidolon.io.input_handler import InputHandler
except Exception:
    InputHandler = None


CRASH_LOG = Path("crash.log")


def _init_curses(stdscr):
    # základní nastavení curses
    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass
    stdscr.timeout(100)


def _safe_write_crash(exc: Exception):
    with CRASH_LOG.open("a", encoding="utf-8") as f:
        f.write("=== Crash ===\n")
        traceback.print_exc(file=f)
        f.write("\n\n")


def _run(stdscr):
    _init_curses(stdscr)

    if "stdscr" in Game.__init__.__code__.co_varnames:
        game = Game(stdscr=stdscr)
    else:
        game = Game()

    if OutputRenderer is not None:
        try:
            game.renderer = OutputRenderer(stdscr, game.map, game.player, game)
            try:
                game.renderer.render()
                game.push_message("[debug] renderer.render() called once from main")
            except Exception as e:
                game.push_message(f"[debug] renderer.render() failed: {e}")
        except Exception as e:
            game.push_message(f"[debug] failed to create renderer: {e}")

        # vytvoř input handler pokud existuje a přiřaď ho
    if InputHandler is not None:
        try:
            # předáme game a stdscr (některé verze InputHandler očekávají stdscr)
            game.input_handler = InputHandler(game, stdscr)
            game.push_message("[debug] InputHandler created")
        except Exception as e:
            game.push_message(f"[debug] failed to create input handler: {e}")
    else:
        game.push_message("[debug] InputHandler not found; using Game's internal input loop")



    game.push_message(
        "[debug] game starting; renderer set: "
        + ("yes" if getattr(game, "renderer", None) else "no")
    )

    try:
        if "stdscr" in Game.run.__code__.co_varnames:
            game.run(stdscr=stdscr)
        else:
            game.run()
    except Exception as exc:
        _safe_write_crash(exc)
        try:
            game.push_message("[fatal] Unhandled exception occurred. See crash.log for details.")
        except Exception:
            pass


def main():
    try:
        curses.wrapper(_run)
    except Exception as e:
        _safe_write_crash(e)
        print("Fatal error starting the game. See crash.log for details.")


if __name__ == "__main__":
    main()
