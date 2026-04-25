# eidolon/io/output_renderer.py
import curses


class OutputRenderer:
    def __init__(self, stdscr, ship_map, player, game):
        self.stdscr = stdscr
        self.map = ship_map
        self.player = player
        self.game = game
        self._init_colors()

    def _init_colors(self):
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)

    def render(self):
        self.stdscr.erase()
        maxy, maxx = self.stdscr.getmaxyx()

        title = "EIDOLON DRIFT - Incident Response Terminal"
        try:
            self.stdscr.addstr(0, 0, title, curses.color_pair(1) | curses.A_BOLD)
        except curses.error:
            pass

        self._draw_minimap(2, 0)
        self._draw_sector_info(2, 25, maxx - 26)

        try:
            self.stdscr.addstr(maxy - 4, 0, "WASD to move  : to enter command  Q to quit")
        except curses.error:
            pass

        self._draw_messages(maxy - 10, 0, 6)
        self.stdscr.refresh()

    def _draw_minimap(self, starty, startx):
        for y in range(self.map.height):
            line = ""
            for x in range(self.map.width):
                tile_char = self.map.get_tile_char(x, y)
                obj_marker = None
                sector = self.map.get_sector(x, y)
                if sector and sector.objects:
                    for o in sector.objects:
                        if isinstance(o, dict):
                            typ = o.get("type")
                            if typ == "log":
                                obj_marker = "l"
                                break
                            if typ == "enc":
                                obj_marker = "e"
                                break
                            if typ == "item":
                                obj_marker = "i"
                                break
                            if typ == "anomaly":
                                obj_marker = "x"
                                break
                        else:
                            obj_marker = "*"
                    if obj_marker is None:
                        obj_marker = "*"

                if self.player.x == x and self.player.y == y:
                    ch = "@"
                else:
                    ch = obj_marker if obj_marker else tile_char
                line += ch

            try:
                self.stdscr.addstr(starty + y, startx, line)
            except curses.error:
                pass

    def _draw_sector_info(self, starty, startx, width):
        sector = self.map.get_sector(self.player.x, self.player.y)
        if sector is None:
            lines = ["Unknown sector"]
        else:
            lines = [
                f"Sector: {sector.name}",
                f"Type: {sector.type}",
                "",
            ]
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
                self.stdscr.addstr(starty + i, startx, l[:width])
            except curses.error:
                pass

    def _draw_messages(self, starty, startx, max_lines):
        try:
            self.stdscr.addstr(starty, startx, "Messages:", curses.A_UNDERLINE)
        except curses.error:
            pass

        msgs = self.game.messages[-max_lines:]
        for i, m in enumerate(msgs):
            try:
                self.stdscr.addstr(starty + 1 + i, startx, m[:max(0, curses.COLS - 1)])
            except curses.error:
                pass

    def _wrap_text(self, text, width):
        words = text.split()
        if not words:
            return [""]

        lines = []
        current = ""
        for word in words:
            if len(current) + 1 + len(word) <= width:
                current = (current + " " + word).strip()
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)
        return lines
