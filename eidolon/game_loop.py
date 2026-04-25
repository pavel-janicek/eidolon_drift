# eidolon/game_loop.py
import curses
from eidolon.generation.map_generator import MapGenerator
from eidolon.world.player import Player
from eidolon.io.input_handler import InputHandler
from eidolon.io.output_renderer import OutputRenderer
from eidolon.mechanics.movement import move_player
from eidolon.mechanics import commands as cmdmod


class Game:
    def __init__(self, stdscr=None):
        self.stdscr = stdscr
        # generate ship map
        self.map = MapGenerator().generate()
        # find a starting airlock sector (first found)
        start = None
        for (x, y), s in self.map.grid.items():
            if getattr(s, "type", "").upper() == "AIRLOCK":
                start = (x, y)
                break
        if start is None:
            start = (0, 0)
        # create player at start
        self.player = Player(x=start[0], y=start[1])
        # other runtime fields
        self.input_handler = None
        self.renderer = None
        self.running = True
        self.messages = []
        # initial message
        self.push_message("Distress call received from vessel 'Eidolon'. You answered. Objective: reach the Command Module and use the escape pod.")
        self.push_message("Type 'help' for commands. Use WASD to move.")

    def push_message(self, text: str):
        if not text:
            return
        for line in text.splitlines():
            self.messages.append(line)
        # keep last 20 lines
        self.messages = self.messages[-20:]

    def _curses_main(self, stdscr):
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        self.stdscr = stdscr
        self.input_handler = InputHandler(stdscr)
        self.renderer = OutputRenderer(stdscr, self.map, self.player, self)
        self.renderer.render()

        while self.running:
            key = self.input_handler.get_key()
            if key is None:
                continue
            if key == 'QUIT':
                self.running = False
                break
            if key.startswith('CMD:'):
                cmd = key[4:]
                result = cmdmod.handle_command(self, cmd)
                if result:
                    self.push_message(result)
            else:
                moved = move_player(self.map, self.player, key)
                if moved:
                    sector = self.map.get_sector(self.player.x, self.player.y)
                    name = sector.name if sector else f"({self.player.x},{self.player.y})"
                    self.push_message(f"Moved to {name}.")
                else:
                    self.push_message("Cannot move there.")
            self.renderer.render()

    def run(self):
        curses.wrapper(self._curses_main)

