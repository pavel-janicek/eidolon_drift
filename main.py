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
    curses.curs_set(0)  # skryj kurzor
    stdscr.keypad(True)
    # povolit barevné páry pokud terminál podporuje barvy
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass
    # volitelně nastav timeout pro getch (ms) pokud chceš non-blocking
    stdscr.timeout(100)  # 100 ms, uprav podle potřeby


def _safe_write_crash(exc: Exception):
    with CRASH_LOG.open("a", encoding="utf-8") as f:
        f.write("=== Crash ===\n")
        traceback.print_exc(file=f)
        f.write("\n\n")


def _run(stdscr):
    # inicializace curses
    _init_curses(stdscr)

    # vytvoř hru (Game může přijímat stdscr nebo ne; pokud ano, předat)
    # pokud Game.__init__ očekává stdscr, uprav volání; zde voláme bez argumentu
    game = Game(stdscr=stdscr) if "stdscr" in Game.__init__.__code__.co_varnames else Game()

    # vytvoř renderer pokud modul existuje a přiřaď ho do game
    if OutputRenderer is not None:
        try:
            game.renderer = OutputRenderer(stdscr, game.map, game.player, game)
        except Exception as e:
            # pokud renderer selže, zaznamenej chybu do messages a pokračuj bez něj
            game.push_message(f"[debug] failed to create renderer: {e}")
    else:
        game.push_message("[debug] OutputRenderer not found; running headless")

    # vytvoř input handler pokud existuje a přiřaď ho
    if InputHandler is not None:
        try:
            game.input_handler = InputHandler(game)
        except Exception as e:
            game.push_message(f"[debug] failed to create input handler: {e}")
    else:
        # pokud nemáš InputHandler, předpokládáme, že Game.run() interně zpracuje vstup
        game.push_message("[debug] InputHandler not found; using Game's internal input loop")

    # krátké info pro uživatele
    game.push_message("[debug] game starting; renderer set: " + ("yes" if getattr(game, "renderer", None) else "no"))

    # spusť hlavní loop; Game.run by měl být robustní a volat renderer.render()
    try:
        # pokud Game.run přijímá stdscr, předáme ho; jinak zavoláme bez argumentu
        if "stdscr" in Game.run.__code__.co_varnames:
            game.run(stdscr=stdscr)
        else:
            game.run()
    except Exception as exc:
        # loguj chybu do souboru a do message bufferu
        _safe_write_crash(exc)
        try:
            game.push_message("[fatal] Unhandled exception occurred. See crash.log for details.")
        except Exception:
            pass
        # re-raise pokud chceš, nebo jen počkej na klávesu
        # raise


def main():
    # wrapper zajistí, že curses bude korektně ukončen i při výjimce
    try:
        curses.wrapper(_run)
    except Exception as e:
        # pokud wrapper selže, zapíšeme crash log
        _safe_write_crash(e)
        print("Fatal error starting the game. See crash.log for details.")


if __name__ == "__main__":
    main()
