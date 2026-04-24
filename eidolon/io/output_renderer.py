# eidolon/io/output_renderer.py
import curses
from eidolon.world.map import Map

class OutputRenderer:
    def __init__(self, stdscr, ship_map, player, game):
        self.stdscr = stdscr
        self.map = ship_map
        self.player = player
        self.game = game

    def render(self):
        self.stdscr.erase()
        maxy, maxx = self.stdscr.getmaxyx()
        # title
        title = "EIDOLON DRIFT - Incident Response Terminal"
        try:
            self.stdscr.addstr(0, 0, title, curses.A_BOLD)
        except curses.error:
            pass
        # minimap
        self._draw_minimap(2, 0)
        # sector info + objects
        self._draw_sector_info(2, 25, maxx - 26)
        # footer help
        try:
            self.stdscr.addstr(maxy-4, 0, "WASD to move  : to enter command  Q to quit")
        except curses.error:
            pass
        # message log
        self._draw_messages(maxy-10, 0, 6)
        self.stdscr.refresh()

    def _draw_minimap(self, starty, startx):
        for y in range(self.map.height):
            line = ""
            for x in range(self.map.width):
                # default tile char
                tile_char = self.map.get_tile_char(x, y)
                # detect object marker
                obj_marker = None
                sector = self.map.get_sector(x, y)
                if sector and sector.objects:
                    for o in sector.objects:
                        if isinstance(o, dict):
                            t = o.get("type")
                            if t == "log":
                                obj_marker = "l"; break
                            if t == "enc":
                                obj_marker = "e"; break
                            if t == "item":
                                obj_marker = "i"; break
                            if t == "anomaly":
                                obj_marker = "x"; break
                        else:
                            # plain string object
                            obj_marker = "*"
                    # fallback marker if objects exist but none matched
                    if obj_marker is None:
                        obj_marker = "*"
                # choose final char
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
            # wrap description to width
            desc = sector.description or ""
            desc_lines = self._wrap_text(desc, width)
            lines.extend(desc_lines)
            lines.append("")
            # objects summary header
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
        # draw lines
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
                self.stdscr.addstr(starty + 1 + i, startx, m[:curses.COLS-1])
            except curses.error:
                pass

    def _wrap_text(self, text, width):
        # simple word-wrap
        words = text.split()
        if not words:
            return [""]
        lines = []
        cur = ""
        for w in words:
            if len(cur) + 1 + len(w) <= width:
                cur = (cur + " " + w).strip()
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines
