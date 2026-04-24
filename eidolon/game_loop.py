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
        self.map = MapGenerator().generate()
        # start player near bridge (0,0) by default
        self.player = Player(x=0, y=0)
        self.input_handler = None
        self.renderer = None
        self.running = True
        self.messages = []  # recent messages to show to player

    def push_message(self, text: str):
        # keep last 6 messages
        if not text:
            return
        for line in text.splitlines():
            self.messages.append(line)
        self.messages = self.messages[-6:]

    def _curses_main(self, stdscr):
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        self.stdscr = stdscr
        self.input_handler = InputHandler(stdscr)
        self.renderer = OutputRenderer(stdscr, self.map, self.player, self)
        # initial message
        self.push_message("IRU-7 terminal initialized. Type 'help' for commands.")
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
                # handle command via commands module
                result = cmdmod.handle_command(self, cmd)
                if result:
                    self.push_message(result)
            else:
                moved = move_player(self.map, self.player, key)
                if moved:
                    # optional: auto-scan on move or small message
                    sector = self.map.get_sector(self.player.x, self.player.y)
                    self.push_message(f"Moved to {sector.name}.")
                else:
                    self.push_message("Cannot move there.")
            self.renderer.render()

    def run(self):
        curses.wrapper(self._curses_main)
