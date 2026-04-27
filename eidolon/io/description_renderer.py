# eidolon/io/description_renderer.py
# Cross-platform curses import
try:
    import curses
except ImportError:
    try:
        # Try windows-curses for Windows
        import windows_curses as curses
    except ImportError:
        # Fallback: create a mock curses module for basic functionality
        class MockCurses:
            COLOR_CYAN = 1
            COLOR_YELLOW = 2
            COLOR_GREEN = 3
            COLOR_RED = 4
            COLOR_MAGENTA = 5
            COLOR_WHITE = 7
            COLOR_BLACK = 0
            A_BOLD = 1
            A_NORMAL = 0
            A_REVERSE = 2
            KEY_UP = 259
            KEY_DOWN = 258
            KEY_LEFT = 260
            KEY_RIGHT = 261
            KEY_BACKSPACE = 263
            KEY_ENTER = 10
            KEY_NPAGE = 338
            KEY_PPAGE = 339
            KEY_HOME = 262
            KEY_END = 360

            @staticmethod
            def has_colors():
                return False

            @staticmethod
            def start_color():
                pass

            @staticmethod
            def use_default_colors():
                pass

            @staticmethod
            def init_pair(*args):
                pass

            @staticmethod
            def color_pair(n):
                return 0

            @staticmethod
            def curs_set(n):
                pass

            @staticmethod
            def wrapper(func, *args):
                return func(*args)

        curses = MockCurses()
import textwrap


class DescriptionRenderer:
    def __init__(self, output_renderer):
        self.output_renderer = output_renderer
    
    def render(self):
        """
        Vykreslí obsah pravého (description) okna včetně ambientní zprávy.
        Používá self.desc_win a self.game (Game instance).
        """
        if not getattr(self.output_renderer, "desc_win", None):
            return

        win = self.output_renderer.desc_win
        game = self.output_renderer.game

        try:
            if win:
                win.erase()
                win.box()

            maxy, maxx = win.getmaxyx()
            if maxy < 3 or maxx < 3:
                return

            # Get current sector description
            sector = game.map.get_sector(game.player.x, game.player.y) if game.map else None
            if sector:
                desc_lines = self.output_renderer.wrap_text(sector.description or "Unknown sector", maxx - 4)
            else:
                desc_lines = ["No sector data"]

            # Add ambient message if available
            ambient_msg = getattr(game, "ambient_messages", None)
            if ambient_msg and len(ambient_msg) > 0:
                # Choose message using game RNG for reproducibility
                rng = getattr(game, "rng", None)
                if rng:
                    msg = rng.choice(ambient_msg)
                else:
                    msg = ambient_msg[0]
                desc_lines.append("")
                desc_lines.append("Ambient:")
                desc_lines.extend(self.output_renderer.wrap_text(msg, maxx - 4))

            # Render lines
            for i, line in enumerate(desc_lines[:maxy - 2]):
                try:
                    win.addstr(1 + i, 2, line[:maxx - 4])
                except Exception:
                    continue

        except Exception as e:
            if not getattr(self.output_renderer, "_desc_render_err_emitted", False):
                game.push_message(f"[debug] description render error: {e}")
                self.output_renderer._desc_render_err_emitted = True
