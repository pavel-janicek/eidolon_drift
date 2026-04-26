# eidolon/io/input_handler.py
import curses
import random
from typing import Optional


class InputHandler:
    """
    InputHandler přijímá buď (game, stdscr) nebo jen game (který má atribut stdscr),
    nebo jen stdscr (pro starší verze). Konstruktor nevyhazuje chybu pokud stdscr
    není dostupné — místo toho bude process_once ticho ignorovat vstup.
    """

    def __init__(self, game=None, stdscr=None):
        # pokud byl předán pouze stdscr (starší API), podpoříme to
        if stdscr is None and game is not None and hasattr(game, "stdscr"):
            stdscr = getattr(game, "stdscr")
        # pokud byl předán jen stdscr (bez game), game zůstane None
        self.game = game
        self.stdscr = stdscr
        self.command_mode = False
        self.cmd_buffer = ""


    # --- nízkoúrovňě čte klávesu a vrací tokeny ---
    def _read_key(self) -> Optional[str]:
        ch = self.stdscr.getch()
        if ch == -1:
            return None
        # Enter command mode with ':'
        if not self.command_mode and ch == ord(':'):
            self.command_mode = True
            self.cmd_buffer = ""
            self._prompt(":")
            return None
        if self.command_mode:
            # finish command
            if ch in (curses.KEY_ENTER, 10, 13):
                cmd = self.cmd_buffer.strip()
                self.command_mode = False
                self._clear_prompt()
                return f"CMD:{cmd}"
            # cancel
            if ch in (27,):  # ESC
                self.command_mode = False
                self._clear_prompt()
                return None
            # backspace
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.cmd_buffer = self.cmd_buffer[:-1]
                self._prompt(":" + self.cmd_buffer)
                return None
            # normal char
            try:
                # ignore non-printable
                if 0 <= ch <= 255:
                    self.cmd_buffer += chr(ch)
                    self._prompt(":" + self.cmd_buffer)
            except Exception:
                pass
            return None

        # movement keys
        if ch in (ord('w'), ord('W'), curses.KEY_UP):
            return 'UP'
        if ch in (ord('s'), ord('S'), curses.KEY_DOWN):
            return 'DOWN'
        if ch in (ord('a'), ord('A'), curses.KEY_LEFT):
            return 'LEFT'
        if ch in (ord('d'), ord('D'), curses.KEY_RIGHT):
            return 'RIGHT'
        # quit
        if ch in (ord('q'), ord('Q')):
            return 'QUIT'
        # no-op
        return None

    # --- veřejné API volané z Game.run() ---
    def process_once(self):
        """
        Přečte jeden vstup a provede odpovídající akci na objektu game.
        Vrací True pokud něco provedl, False nebo None pokud nic.
        """
        token = self._read_key()
        if token is None:
            return None

        # příkaz
        if token.startswith("CMD:"):
            cmd = token[4:].strip()
            if not cmd:
                return None
            # pokud Game má handler příkazů, zavolat ho
            if hasattr(self.game, "handle_command"):
                try:
                    # handle_command by měl vrátit string nebo None
                    res = self.game.handle_command(cmd)
                    # pokud handle_command vrátí text, pushneme ho do messages
                    if isinstance(res, str) and res:
                        self.game.push_message(res)
                except Exception as e:
                    self.game.push_message(f"[debug] command handler error: {e}")
            else:
                # fallback: push message
                self.game.push_message(f"Command entered: {cmd}")
            return True

        # quit
        if token == 'QUIT':
            self.game.push_message("[debug] quitting (input)")
            self.game.running = False
            return True

        # movement
        if token in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
            dx, dy = 0, 0
            if token == 'UP':
                dy = -1
            elif token == 'DOWN':
                dy = 1
            elif token == 'LEFT':
                dx = -1
            elif token == 'RIGHT':
                dx = 1

            if self.game.player.sanity < 30:
                if random.random() < 0.1:
                    dx, dy = random.choice([(1,0),(-1,0),(0,1),(0,-1)])
                    self.game.push_message("You stumble...")
    

            # prefer game.move_player(dx,dy) if existuje
            try:
                if hasattr(self.game, "move_player"):
                    self.game.move_player(dx, dy)
                    return True
                if hasattr(self.game, "move"):
                    # some projects use move(direction) - try both
                    try:
                        self.game.move(dx, dy)
                        return True
                    except TypeError:
                        # maybe expects a string
                        pass
                # fallback: uprav souřadnice hráče přímo s kontrolou hranic
                p = getattr(self.game, "player", None)
                m = getattr(self.game, "map", None)
                if p is not None and m is not None:
                    new_x = max(0, min(m.width - 1, p.x + dx))
                    new_y = max(0, min(m.height - 1, p.y + dy))
                    if (new_x, new_y) != (p.x, p.y):
                        p.x, p.y = new_x, new_y
                        # pokud Game má tick nebo on_move hook, zavolej ho
                        if hasattr(self.game, "on_player_move"):
                            try:
                                self.game.on_player_move()
                            except Exception:
                                pass
                        # push simple message
                        #self.game.push_message(f"You move to {p.x},{p.y}.")
                    else:
                        self.game.push_message("You can't move that way.")
                    return True
            except Exception as e:
                self.game.push_message(f"[debug] movement handling error: {e}")
                return True

        return None

    # --- prompt helpers (draw prompt on bottom line) ---
    def _prompt(self, text):
        try:
            maxy, maxx = self.stdscr.getmaxyx()
            # write prompt on last line
            self.stdscr.addstr(maxy - 1, 0, text.ljust(maxx - 1))
            self.stdscr.refresh()
        except Exception:
            pass

    def _clear_prompt(self):
        try:
            maxy, maxx = self.stdscr.getmaxyx()
            self.stdscr.addstr(maxy - 1, 0, " ".ljust(maxx - 1))
            self.stdscr.refresh()
        except Exception:
            pass
