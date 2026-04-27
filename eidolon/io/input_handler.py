# eidolon/io/input_handler.py
# Cross-platform curses import
try:
    import curses
except ImportError:
    try:
        # Try windows-curses for Windows
        import windows_curses as curses
    except ImportError:
        # Fallback: create a mock curses module for basic functionality
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
import random
from typing import Optional


class InputHandler:
    """
    InputHandler pouze čte klávesy a vrací tokeny.
    Žádná logika hry, žádné změny stavu.
    """

    def __init__(self, game=None, stdscr=None):
        if stdscr is None and game is not None and hasattr(game, "stdscr"):
            stdscr = getattr(game, "stdscr")
        self.game = game
        self.stdscr = stdscr
        self.command_mode = False
        self.cmd_buffer = ""

    def _read_key(self):
        ch = self.stdscr.getch()
        if ch == -1:
            return None

        # Ctrl+C → QUIT_REQUEST
        if ch == 3:
            return "QUIT_REQUEST"

        # command mode
        if not self.command_mode and ch == ord(':'):
            self.command_mode = True
            self.cmd_buffer = ""
            self._prompt(":")
            return None

        if self.command_mode:
            if ch in (curses.KEY_ENTER, 10, 13):
                cmd = self.cmd_buffer.strip()
                self.command_mode = False
                self._clear_prompt()
                return f"CMD:{cmd}"

            if ch == 27:  # ESC
                self.command_mode = False
                self._clear_prompt()
                return None

            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.cmd_buffer = self.cmd_buffer[:-1]
                self._prompt(":" + self.cmd_buffer)
                return None

            if 0 <= ch <= 255:
                self.cmd_buffer += chr(ch)
                self._prompt(":" + self.cmd_buffer)
            return None

        # movement
        if ch in (ord('w'), ord('W'), curses.KEY_UP):
            return "UP"
        if ch in (ord('s'), ord('S'), curses.KEY_DOWN):
            return "DOWN"
        if ch in (ord('a'), ord('A'), curses.KEY_LEFT):
            return "LEFT"
        if ch in (ord('d'), ord('D'), curses.KEY_RIGHT):
            return "RIGHT"

        # quit
        if ch in (ord('q'), ord('Q')):
            return "QUIT_REQUEST"

        return None

    def process_once(self):
        return self._read_key()

    def _prompt(self, text):
        try:
            maxy, maxx = self.stdscr.getmaxyx()
            self.stdscr.addstr(maxy - 1, 0, text.ljust(maxx - 1))
            self.stdscr.refresh()
        except Exception:
            pass

    def _clear_prompt(self):
        try:
            maxy, maxx = self.stdscr.getmaxyx()
            self.stdscr.addstr(maxy - 1, 0, " ".ljust(maxx - 1))
            self.stdscr.refresh()
        except Exception:
            pass
