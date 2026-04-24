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
        # draw title
        title = "EIDOLON DRIFT - Incident Response Terminal"
        self.stdscr.addstr(0, 0, title, curses.A_BOLD)
        # draw mini map top-left
        self._draw_minimap(2, 0)
        # draw sector description right side
        self._draw_sector_info(2, 25)
        # draw footer help
        self.stdscr.addstr(maxy-4, 0, "WASD to move  : to enter command  Q to quit")
        # draw message log above footer
        self._draw_messages(maxy-10, 0, 6)
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
            try:
                self.stdscr.addstr(starty + y, startx, line)
            except curses.error:
                pass

    def _draw_sector_info(self, starty, startx):
        sector = self.map.get_sector(self.player.x, self.player.y)
        if sector is None:
            lines = ["Unknown sector"]
        else:
            lines = [
                f"Sector: {sector.name}",
                f"Type: {sector.type}",
                "",
                sector.description,
            ]
        for i, l in enumerate(lines):
            try:
                self.stdscr.addstr(starty + i, startx, l)
            except curses.error:
                pass

    def _draw_messages(self, starty, startx, max_lines):
        # draw a simple box title
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
