from eidolon.config import HEALTH_RED_THRESHOLD, HEALTH_YELLOW_THRESHOLD
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


class StatusRenderer:
    def __init__(self, parent):
        self.parent = parent

    def render(self):
        win = self.parent.status_win or self.parent.stdscr
        try:
            win.erase()
            if self.parent.status_win:
                win.box()
            p = self.parent.player
            # safety: avoid ZeroDivisionError
            max_health = p.max_health if getattr(p, "max_health", None) else 1
            cur = max(0, min(p.health, max_health))
            pct = cur / max_health

            # bar length based on available space
            try:
                avail_w = win.getmaxyx()[1] - 20  # leave space for text
                bar_len = max(6, min(40, avail_w))
            except Exception:
                bar_len = 20

            filled = int(pct * bar_len)
            empty = bar_len - filled

            # choose color pair: green (>50%), yellow (25-50%), red (<25%)
            if pct > HEALTH_YELLOW_THRESHOLD:
                color_pair = curses.color_pair(
                    10) if self.parent.colors_available else 0
            elif pct > HEALTH_RED_THRESHOLD:
                color_pair = curses.color_pair(
                    11) if self.parent.colors_available else 0
            else:
                color_pair = curses.color_pair(
                    12) if self.parent.colors_available else 0

            # build visual bar: filled part colored, empty part normal
            filled_str = "#" * filled
            empty_str = "-" * empty
            bar = "[" + filled_str + empty_str + "]"

            # draw text and bar
            text = f"Health: {cur}/{max_health} "
            # ensure we don't overflow the window
            max_line = win.getmaxyx()[1] - 4
            try:
                # draw label
                win.addstr(1, 2, text[:max_line], curses.A_NORMAL)
                # draw colored filled part after label
                start_x = 2 + len(text)
                # draw left bracket
                win.addstr(1, start_x, "[", curses.A_NORMAL)
                # draw filled colored segment
                if filled > 0:
                    try:
                        win.addstr(
                            1, start_x + 1, filled_str[:max_line], color_pair | curses.A_BOLD)
                    except Exception:
                        # fallback: draw without color
                        win.addstr(1, start_x + 1,
                                   filled_str[:max_line], curses.A_BOLD)
                # draw empty segment
                try:
                    win.addstr(1, start_x + 1 + filled,
                               empty_str[:max_line], curses.A_DIM)
                except Exception:
                    pass
                # draw right bracket
                try:
                    win.addstr(1, start_x + 1 + filled +
                               empty, "]", curses.A_NORMAL)
                except Exception:
                    pass
            except Exception as e:
                # if anything fails, push a single debug message (no flood)
                if not getattr(self.parent, "_status_draw_err_emitted", False):
                    self.parent.game.push_message(f"[debug] status draw error: {e}")
                    self.parent._status_draw_err_emitted = True
        except Exception as e:
            self.parent.game.push_message(f"[debug] status render error: {e}")
        except Exception as e:
            if not getattr(self.parent, "_status_outer_err_emitted", False):
                self.parent.game.push_message(f"[debug] status outer error: {e}")
                self.parent._status_outer_err_emitted = True    

       # --- SANITY BAR ---
        p = self.parent.player   
        san = max(0, min(p.sanity, 100))
        san_pct = san / 100

        # sanity bar length = stejný jako health bar
        san_filled = int(san_pct * bar_len)
        san_empty = bar_len - san_filled

        san_filled_str = "#" * san_filled
        san_empty_str = "-" * san_empty

        # sanity bar text
        san_text = f"Sanity: {san}/100 "
        san_start_x = 2 + len(san_text)

        # sanity bar color
        san_color = curses.color_pair(13) if self.parent.colors_available else 0

        # řádek sanity baru = o řádek níž než health bar
        san_y = 2

        try:
            # label
            win.addstr(san_y, 2, san_text[:max_line], curses.A_NORMAL)

            # left bracket
            win.addstr(san_y, san_start_x, "[", curses.A_NORMAL)

            # filled part
            if san_filled > 0:
                win.addstr(san_y, san_start_x + 1,
                    san_filled_str[:max_line], san_color | curses.A_BOLD)

            # empty part
            win.addstr(san_y, san_start_x + 1 + san_filled,
               san_empty_str[:max_line], curses.A_DIM)

            # right bracket
            win.addstr(san_y, san_start_x + 1 + san_filled + san_empty,
               "]", curses.A_NORMAL)

        except Exception:
            pass

       
                