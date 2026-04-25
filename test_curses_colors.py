# test_curses_colors.py
import curses

def main(stdscr):
    stdscr.clear()
    has = curses.has_colors()
    try:
        curses.start_color()
        curses.use_default_colors()
    except Exception as e:
        stdscr.addstr(0,0, f"start_color/use_default_colors error: {e}")
    cols = getattr(curses, "COLORS", None)
    pairs = getattr(curses, "COLOR_PAIRS", None)
    stdscr.addstr(1,0, f"TERM={__import__('os').environ.get('TERM')}")
    stdscr.addstr(2,0, f"curses.has_colors(): {has}")
    stdscr.addstr(3,0, f"curses.COLORS: {cols}")
    stdscr.addstr(4,0, f"curses.COLOR_PAIRS: {pairs}")
    stdscr.addstr(6,0, "If has_colors is True and COLORS >= 8, colors should work.")
    stdscr.addstr(8,0, "Press any key to exit.")
    stdscr.refresh()
    stdscr.getch()

if __name__ == "__main__":
    curses.wrapper(main)
