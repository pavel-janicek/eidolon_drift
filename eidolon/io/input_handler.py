# eidolon/io/input_handler.py
import curses

class InputHandler:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.command_mode = False
        self.cmd_buffer = ""

    def get_key(self):
        ch = self.stdscr.getch()
        if ch == -1:
            return None
        # Enter command mode with ':'
        if not self.command_mode and ch == ord(':'):
            self.command_mode = True
            self.cmd_buffer = ""
            self._prompt(":")
            return None
        if self.command_mode:
            if ch in (curses.KEY_ENTER, 10, 13):
                cmd = self.cmd_buffer
                self.command_mode = False
                self._clear_prompt()
                return f"CMD:{cmd}"
            elif ch in (27,):  # ESC cancels
                self.command_mode = False
                self._clear_prompt()
                return None
            elif ch in (curses.KEY_BACKSPACE, 127):
                self.cmd_buffer = self.cmd_buffer[:-1]
                self._prompt(":" + self.cmd_buffer)
                return None
            else:
                try:
                    self.cmd_buffer += chr(ch)
                except:
                    pass
                self._prompt(":" + self.cmd_buffer)
                return None
        # movement keys
        if ch in (ord('w'), ord('W'), curses.KEY_UP):
            return 'UP'
        if ch in (ord('s'), ord('S'), curses.KEY_DOWN):
            return 'DOWN'
        if ch in (ord('a'), ord('A'), curses.KEY_LEFT):
            return 'LEFT'
        if ch in (ord('d'), ord('D'), curses.KEY_RIGHT):
            return 'RIGHT'
        if ch in (ord('q'), ord('Q')):
            return 'QUIT'
        return None

    def _prompt(self, text):
        maxy, maxx = self.stdscr.getmaxyx()
        self.stdscr.addstr(maxy-1, 0, text.ljust(maxx-1))
        self.stdscr.refresh()

    def _clear_prompt(self):
        maxy, maxx = self.stdscr.getmaxyx()
        self.stdscr.addstr(maxy-1, 0, " ".ljust(maxx-1))
        self.stdscr.refresh()
