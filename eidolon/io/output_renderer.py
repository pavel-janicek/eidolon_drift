# eidolon/io/output_renderer.py
import curses
from eidolon.world.map import Map


class OutputRenderer:
    def __init__(self, stdscr, ship_map, player, game):
        self.stdscr = stdscr
        self.map = ship_map
        self.player = player
        self.game = game
        self.colors_available = False
        self._init_colors()
        # windows placeholders
        self.map_win = None
        self.status_win = None
        self.msg_win = None

    def _layout(self):
        maxy, maxx = self.stdscr.getmaxyx()
        # sizes
        status_h = 3
        msg_h = max(6, maxy // 4)
        map_h = maxy - status_h - msg_h - 4  # margins
        map_w = min(self.map.width + 2, maxx - 30)  # leave space for right panel if needed
        # center map horizontally
        map_x = max(1, (maxx - map_w) // 2)
        map_y = 2
        # create or resize windows
        if self.map_win is None:
            self.map_win = curses.newwin(map_h, map_w, map_y, map_x)
        else:
            self.map_win.resize(map_h, map_w)
            self.map_win.mvwin(map_y, map_x)
        # status window at top
        if self.status_win is None:
            self.status_win = curses.newwin(status_h, maxx - 2, 0, 1)
        else:
            self.status_win.resize(status_h, maxx - 2)
            self.status_win.mvwin(0, 1)
        # message window at bottom
        if self.msg_win is None:
            self.msg_win = curses.newwin(msg_h, maxx - 2, maxy - msg_h - 1, 1)
        else:
            self.msg_win.resize(msg_h, maxx - 2)
            self.msg_win.mvwin(maxy - msg_h - 1, 1)

    def render(self):
        # recompute layout each frame (handles resize)
        self._layout()
        self.stdscr.erase()
        maxy, maxx = self.stdscr.getmaxyx()
        # title
        title = " EIDOLON DRIFT - Incident Response Terminal "
        try:
            title_x = max(0, (maxx - len(title)) // 2)
            self.stdscr.addstr(0, title_x, title, curses.A_BOLD | (curses.color_pair(1) if self.colors_available else 0))
        except curses.error:
            pass

        # draw windows
        self._render_status()
        self._render_map()
        self._render_messages()

        # refresh all
        try:
            self.status_win.noutrefresh()
            self.map_win.noutrefresh()
            self.msg_win.noutrefresh()
            curses.doupdate()
        except curses.error:
            pass

    def _render_status(self):
        self.status_win.erase()
        self.status_win.box()
        # health bar
        p = self.player
        bar_len = 20
        filled = int((p.health / p.max_health) * bar_len) if p.max_health else 0
        bar = "[" + "#" * filled + "-" * (bar_len - filled) + "]"
        try:
            self.status_win.addstr(1, 2, f"Health: {p.health}/{p.max_health} {bar}", curses.color_pair(4) if self.colors_available and p.health < p.max_health*0.3 else 0)
        except curses.error:
            pass

    def _render_map(self):
        self.map_win.erase()
        self.map_win.box()
        # inner drawing area offset
        h, w = self.map_win.getmaxyx()
        for y in range(min(self.map.height, h-2)):
            for x in range(min(self.map.width, w-2)):
                ch = self.map.get_tile_char(x, y)
                # override with object marker or player
                sector = self.map.get_sector(x, y)
                obj_marker = None
                if sector and sector.objects:
                    for o in sector.objects:
                        if isinstance(o, dict) and o.get("type") == "log":
                            obj_marker = "l"; break
                        if isinstance(o, dict) and o.get("type") == "anomaly":
                            obj_marker = "x"; break
                        if isinstance(o, dict) and o.get("type") == "item":
                            obj_marker = "i"; break
                if self.player.x == x and self.player.y == y:
                    ch = "@"
                    attr = curses.A_BOLD | (curses.color_pair(2) if self.colors_available else 0)
                else:
                    ch = obj_marker if obj_marker else ch
                    attr = curses.color_pair(3) if (self.colors_available and obj_marker) else curses.A_NORMAL
                try:
                    self.map_win.addch(1 + y, 1 + x, ch, attr)
                except curses.error:
                    pass

    def _render_messages(self):
        self.msg_win.erase()
        self.msg_win.box()
        # messages: show last N lines
        maxy, maxx = self.msg_win.getmaxyx()
        lines = self.game.messages[-(maxy-2):]
        for i, line in enumerate(lines):
            try:
                attr = curses.color_pair(4) | curses.A_BOLD if self.colors_available and ("WARNING" in line.upper() or "ANOMALY" in line.upper()) else curses.A_NORMAL
                self.msg_win.addstr(1 + i, 2, line[:maxx-4], attr)
            except curses.error:
                pass

        # --- Pager: full-screen reader with scrolling ---
    def open_pager(self, lines):
        """
        Open a full-screen pager showing `lines` (list of strings).
        Controls: Up/Down, PageUp/PageDown, Home/End, q or Esc to close.
        """
        stdscr = self.stdscr
        maxy, maxx = stdscr.getmaxyx()
        pad_h = max(len(lines) + 2, maxy)
        pad_w = maxx - 2
        pad = curses.newpad(pad_h, pad_w)
        # fill pad
        for i, ln in enumerate(lines):
            try:
                pad.addstr(i, 0, ln[:pad_w-1])
            except curses.error:
                pass
        # initial viewport
        top = 0
        view_h = maxy - 2
        view_w = pad_w
        # draw border and title on stdscr to indicate pager
        title = " LOG VIEWER (q to close) "
        while True:
            stdscr.erase()
            # draw a simple border
            try:
                stdscr.box()
                stdscr.addstr(0, max(1, (maxx - len(title)) // 2), title, curses.A_REVERSE)
            except curses.error:
                pass
            # refresh border
            stdscr.noutrefresh()
            # display pad viewport
            try:
                pad.noutrefresh(top, 0, 1, 1, view_h, view_w)
                curses.doupdate()
            except curses.error:
                pass
            # handle keys (blocking)
            ch = stdscr.getch()
            if ch in (ord('q'), 27):  # q or Esc
                break
            elif ch in (curses.KEY_DOWN, ord('j')):
                if top + view_h < pad_h:
                    top += 1
            elif ch in (curses.KEY_UP, ord('k')):
                if top > 0:
                    top -= 1
            elif ch == curses.KEY_NPAGE:  # PageDown
                top = min(top + view_h, pad_h - view_h)
            elif ch == curses.KEY_PPAGE:  # PageUp
                top = max(top - view_h, 0)
            elif ch == curses.KEY_HOME:
                top = 0
            elif ch == curses.KEY_END:
                top = max(0, pad_h - view_h)
            # loop continues until closed
        # restore normal screen (renderer.render will redraw)
        self.render()

    # --- Themes support ---
    THEMES = {
        "dark": {
            1: (curses.COLOR_CYAN, -1),    # title
            2: (curses.COLOR_YELLOW, -1),  # player
            3: (curses.COLOR_GREEN, -1),   # objects
            4: (curses.COLOR_RED, -1),     # warnings
            5: (curses.COLOR_MAGENTA, -1)  # sector type
        },
        "retro": {
            1: (curses.COLOR_WHITE, curses.COLOR_BLUE),
            2: (curses.COLOR_BLACK, curses.COLOR_YELLOW),
            3: (curses.COLOR_BLACK, curses.COLOR_GREEN),
            4: (curses.COLOR_WHITE, curses.COLOR_RED),
            5: (curses.COLOR_BLACK, curses.COLOR_MAGENTA)
        },
        "high_contrast": {
            1: (curses.COLOR_WHITE, curses.COLOR_BLACK),
            2: (curses.COLOR_BLACK, curses.COLOR_WHITE),
            3: (curses.COLOR_YELLOW, curses.COLOR_BLACK),
            4: (curses.COLOR_RED, curses.COLOR_BLACK),
            5: (curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        }
    }

    def apply_theme(self, name):
        """
        Apply theme by name. Returns True if applied.
        """
        if not curses.has_colors():
            self.colors_available = False
            return False
        theme = self.THEMES.get(name)
        if not theme:
            return False
        try:
            curses.start_color()
            try:
                curses.use_default_colors()
            except Exception:
                pass
            for pair_idx, (fg, bg) in theme.items():
                curses.init_pair(pair_idx, fg, bg)
            self.colors_available = True
            self.theme = name
            return True
        except Exception:
            self.colors_available = False
            return False

