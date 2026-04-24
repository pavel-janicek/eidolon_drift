# eidolon/game_loop.py
import curses
from eidolon.generation.map_generator import MapGenerator
from eidolon.world.player import Player
from eidolon.io.input_handler import InputHandler
from eidolon.io.output_renderer import OutputRenderer
from eidolon.mechanics.movement import move_player

class Game:
    def __init__(self, stdscr=None):
        self.stdscr = stdscr
        self.map = MapGenerator().generate()
        self.player = Player(x=0, y=0)
        self.input_handler = None
        self.renderer = None
        self.running = True

    def _curses_main(self, stdscr):
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        self.stdscr = stdscr
        self.input_handler = InputHandler(stdscr)
        self.renderer = OutputRenderer(stdscr, self.map, self.player)
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
                # simple command handling
                if cmd.strip().lower() == 'quit':
                    self.running = False
                # extend with commands module
            else:
                moved = move_player(self.map, self.player, key)
            self.renderer.render()

    def run(self):
        curses.wrapper(self._curses_main)
