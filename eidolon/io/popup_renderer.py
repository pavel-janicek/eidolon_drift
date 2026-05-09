import curses
import logging
from eidolon.config import LOG_LEVEL
from eidolon.mechanics.game_state import GameState


class PopupRenderer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(filename="eidolon.log", encoding="utf-8", level=LOG_LEVEL)
        self.mode = None
        self.active = False

        # scanning
        self.scan_ticks_left = 0

        # interact
        self.options = []
        self.selected = 0

        # confirm
        self.confirm_message = ""

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def open_scanning(self, ticks: int):
        self.mode = GameState.SCANNING
        self.scan_ticks_left = ticks
        self.active = True

    def open_interact(self, options):
        """
        options = list of tuples: (label, payload)
        payload = ("use", obj) / ("inspect", obj) / ("cancel", None) / ...
        """
        self.mode = GameState.INTERACT
        self.options = options
        self.selected = 0
        self.active = True

    def open_confirm(self, message: str):
        self.mode = GameState.CONFIRM
        self.confirm_message = message
        self.active = True

    def close(self):
        self.mode = GameState.RUNNING
        self.active = False

    # ------------------------------------------------------------
    # UPDATE (called each game tick)
    # ------------------------------------------------------------

    def tick(self):
        """
        Returns True if scanning finished.
        """
        if self.mode == GameState.SCANNING:
            self.scan_ticks_left -= 1
            if self.scan_ticks_left <= 0:
                self.logger.debug("Scanning finished.")
                return True
        return False

    # ------------------------------------------------------------
    # INPUT HANDLING (logical actions)
    # ------------------------------------------------------------

    def handle_input(self, action):
        """
        action is logical input:
        - navigate_up
        - navigate_down
        - confirm
        - cancel
        Returns payload or None.
        """

        if not self.active:
            return None

        # SCANNING ignores input
        if self.mode == GameState.SCANNING:
            self.logger.debug("Input ignored during scanning.")
            return None

        # INTERACT MENU
        if self.mode == GameState.INTERACT:
            self.logger.debug("Handling input in INTERACT mode: %s", action)
            if action == "navigate_up":
                self.selected = max(0, self.selected - 1)

            elif action == "navigate_down":
                self.selected = min(len(self.options) - 1, self.selected + 1)

            elif action == "confirm":
                self.logger.debug("Selected option: %s", self.options[self.selected][0])
                return self.options[self.selected][1]

            elif action == "cancel":
                return ("cancel", None)

        # CONFIRM DIALOG
        elif self.mode == GameState.CONFIRM:
            self.logger.debug("Handling input in CONFIRM mode: %s", action)
            if action == "confirm":
                return ("yes", None)
            if action == "cancel":
                return ("no", None)

        return None

    # ------------------------------------------------------------
    # RENDERING
    # ------------------------------------------------------------

    def render(self, stdscr):
        if not self.active:
            return

        if self.mode == GameState.SCANNING:
            self._render_scanning(stdscr)

        elif self.mode == GameState.INTERACT:
            self._render_interact(stdscr)

        elif self.mode == GameState.CONFIRM:
            self._render_confirm(stdscr)

    # ------------------------------------------------------------
    # INTERNAL RENDERERS
    # ------------------------------------------------------------

    def _render_scanning(self, stdscr):
        h, w = stdscr.getmaxyx()
        text = "SCANNING..."
        box_w = len(text) + 6
        box_h = 3

        x0 = (w - box_w) // 2
        y0 = (h - box_h) // 2

        win = curses.newwin(box_h, box_w, y0, x0)
        win.border()
        win.addstr(1, 3, text)
        win.refresh()

    def _render_interact(self, stdscr):
        h, w = stdscr.getmaxyx()

        box_w = max(len(label) for label, _ in self.options) + 6
        box_h = len(self.options) + 4

        x0 = (w - box_w) // 2
        y0 = (h - box_h) // 2

        win = curses.newwin(box_h, box_w, y0, x0)
        win.keypad(True)
        win.border()

        win.addstr(1, 2, "What do you want to do?")

        for i, (label, _) in enumerate(self.options):
            if i == self.selected:
                win.attron(curses.A_REVERSE)
                win.addstr(3 + i, 2, label)
                win.attroff(curses.A_REVERSE)
            else:
                win.addstr(3 + i, 2, label)

        win.refresh()

    def _render_confirm(self, stdscr):
        h, w = stdscr.getmaxyx()

        box_w = max(len(self.confirm_message), len("[Y]es / [N]o")) + 6
        box_h = 5

        x0 = (w - box_w) // 2
        y0 = (h - box_h) // 2

        win = curses.newwin(box_h, box_w, y0, x0)
        win.border()

        win.addstr(1, 2, self.confirm_message)
        win.addstr(3, 2, "[Confirm] / [Cancel]")

        win.refresh()
