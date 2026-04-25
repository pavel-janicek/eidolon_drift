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
        # init colors after curses is initialized
        self._init_colors_and_report()

    def _init_colors_and_report(self):
        try:
            if curses.has_colors():
                curses.start_color()
                # allow default terminal background
                try:
                    curses.use_default_colors()
                except Exception:
                    # some curses builds may not support use_default_colors
                    pass
                # init basic pairs (fg, bg=-1 default)
                try:
                    curses.init_pair(1, curses.COLOR_CYAN, -1)    # title
                    curses.init_pair(2, curses.COLOR_YELLOW, -1)  # player
                    curses.init_pair(3, curses.COLOR_GREEN, -1)   # objects
                    curses.init_pair(4, curses.COLOR_RED, -1)     # warnings/messages
                    curses.init_pair(5, curses.COLOR_MAGENTA, -1) # sector type
                    self.colors_available = True
                except curses.error:
                    self.colors_available = False
            else:
                self.colors_available = False
        except Exception:
            self.colors_available = False

        # push a short diagnostic message so you can see what curses detected
        try:
            cols = getattr(curses, "COLORS", None)
            pairs = getattr(curses, "COLOR_PAIRS", None)
            self.game.push_message(f"[debug] curses.has_colors={curses.has_colors()}, COLORS={cols}, COLOR_PAIRS={pairs}")
        except Exception:
            pass

    def render(self):
        self.stdscr.erase()
        maxy, maxx = self.stdscr.getmaxyx()

        title = "EIDOLON DRIFT - Incident Response Terminal"
        try:
            attr = (curses.color_pair(1) | curses.A_BOLD) if self.colors_available else curses.A_BOLD
            self.stdscr.addstr(0, 0, title[:maxx-1], attr)
        except curses.error:
            pass

        self._draw_minimap(2, 0)
        self._draw_sector_info(2, 25, maxx - 26)

        try:
            footer = "WASD to move  : to enter command  Q to quit"
            self.stdscr.addstr(maxy - 4, 0, footer[:maxx-1])
        except curses.error:
            pass

        self._draw_messages(maxy - 14, 0, 12, maxx)
        self.stdscr.refresh()

    def _draw_minimap(self, starty, startx):
        for y in range(self.map.height):
            col = 0
            for x in range(self.map.width):
                tile_char = self.map.get_tile_char(x, y)
                obj_marker = None
                sector = self.map.get_sector(x, y)
                if sector and sector.objects:
                    for o in sector.objects:
                        if isinstance(o, dict):
                            typ = o.get("type")
                            if typ == "log":
                                obj_marker = "l"; break
                            if typ == "enc":
                                obj_marker = "e"; break
                            if typ == "item":
                                obj_marker = "i"; break
                            if typ == "anomaly":
                                obj_marker = "x"; break
                        else:
                            obj_marker = "*"
                    if obj_marker is None:
                        obj_marker = "*"

                if self.player.x == x and self.player.y == y:
                    ch = "@"
                    attr = curses.color_pair(2) | curses.A_BOLD if self.colors_available else curses.A_BOLD
                else:
                    ch = obj_marker if obj_marker else tile_char
                    if obj_marker:
                        attr = curses.color_pair(3) if self.colors_available else curses.A_NORMAL
                    else:
                        attr = curses.A_NORMAL

                try:
                    self.stdscr.addstr(starty + y, startx + col, ch, attr)
                except curses.error:
                    pass
                col += 1

    def _draw_sector_info(self, starty, startx, width):
        sector = self.map.get_sector(self.player.x, self.player.y)
        if sector is None:
            lines = ["Unknown sector"]
        else:
            header = f"Sector: {sector.name}"
            stype = f"Type: {sector.type}"
            lines = [header, stype, ""]
            desc = sector.description or ""
            lines.extend(self._wrap_text(desc, width))
            lines.append("")
            if sector.objects:
                lines.append("Objects here:")
                for o in sector.objects:
                    if isinstance(o, dict):
                        title = o.get("title") or o.get("name") or "<unnamed>"
                        oid = o.get("name", "")
                        typ = o.get("type", "object")
                        lines.append(f"  - {title}  ({typ}; id: {oid})")
                    else:
                        lines.append(f"  - {o}")
            else:
                lines.append("No visible objects.")

        for i, l in enumerate(lines):
            try:
                if i == 1 and self.colors_available:
                    self.stdscr.addstr(starty + i, startx, l[:width], curses.color_pair(5) | curses.A_BOLD)
                elif l.startswith("Objects here:") and self.colors_available:
                    self.stdscr.addstr(starty + i, startx, l[:width], curses.color_pair(3) | curses.A_UNDERLINE)
                elif l.strip().startswith("-") and self.colors_available:
                    self.stdscr.addstr(starty + i, startx, l[:width], curses.color_pair(3))
                else:
                    self.stdscr.addstr(starty + i, startx, l[:width])
            except curses.error:
                pass

    def _draw_messages(self, starty, startx, max_lines, maxx):
        try:
            self.stdscr.addstr(starty, startx, "Messages:", curses.A_UNDERLINE)
        except curses.error:
            pass

        msgs = self.game.messages[-max_lines:]
        for i, m in enumerate(msgs):
            try:
                if self.colors_available and ("ANOMALY" in m.upper() or "WARNING" in m.upper() or "[DEBUG]" in m.upper() or "[debug]" in m):
                    attr = curses.color_pair(4) | curses.A_BOLD
                else:
                    attr = curses.A_NORMAL
                self.stdscr.addstr(starty + 1 + i, startx, m[:maxx-1], attr)
            except curses.error:
                pass

    def _wrap_text(self, text, width):
        words = text.split()
        if not words:
            return [""]
        lines = []
        current = ""
        for word in words:
            if len(current) + (1 if current else 0) + len(word) <= width:
                current = (current + " " + word).strip()
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
