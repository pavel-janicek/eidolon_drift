# eidolon/io/output_renderer.py
import curses
from eidolon.world.map import Map

class OutputRenderer:
    def __init__(self, stdscr, ship_map, player):
        self.stdscr = stdscr
        self.map = ship_map
        self.player = player

    def render(self):
        self.stdscr.erase()
        maxy, maxx = self.stdscr.getmaxyx()
        # draw title
        self.stdscr.addstr(0, 0, "EIDOLON DRIFT - Incident Response Terminal", curses.A_BOLD)
        # draw mini map top-left
        self._draw_minimap(2, 0)
        # draw sector description right side
        self._draw_sector_info(2, 25)
        # draw footer
        self.stdscr.addstr(maxy-3, 0, "WASD to move  : to enter command  Q to quit")
        self.stdscr.refresh()

    def _draw_minimap(self, starty, startx):
        for y in range(self.map.height):
            line = ""
            for x in range(self.map.width):
                if self.player.x == x and self.player.y == y:
                    ch = "@"
                else:
                    ch = self.map.get_tile_char(x, y)
                line += ch
            self.stdscr.addstr(starty + y, startx, line)

    def _draw_sector_info(self, starty, startx):
        sector = self.map.get_sector(self.player.x, self.player.y)
        lines = [
            f"Sector: {sector.name}",
            f"Type: {sector.type}",
            "",
            sector.description,
        ]
        for i, l in enumerate(lines):
            self.stdscr.addstr(starty + i, startx, l)
