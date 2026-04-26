# eidolon/io/output_renderer.py
import textwrap
import curses
from eidolon.io.map_renderer import MapRenderer
from eidolon.world.map import Map
from eidolon.config import HEALTH_RED_THRESHOLD, HEALTH_YELLOW_THRESHOLD, MIN_MAP_WIDTH, MIN_MAP_HEIGHT, DEFAULT_THEME

MIN_MAP_W = MIN_MAP_WIDTH if 'MIN_MAP_WIDTH' in globals() else 10
MIN_MAP_H = MIN_MAP_HEIGHT if 'MIN_MAP_HEIGHT' in globals() else 5


class OutputRenderer:
    def __init__(self, stdscr, ship_map, player, game):
        self.stdscr = stdscr
        self.map = ship_map
        self.player = player
        self.game = game
        self._layout_debug_emitted = False

        # windows
        self.map_win = None
        self.status_win = None
        self.msg_win = None
        self.desc_win = None  # new: description window

        # colors and theme
        self.colors_available = False
        self.theme = DEFAULT_THEME if 'DEFAULT_THEME' in globals() else "dark"
        self.THEMES = {
            "dark": {1: (curses.COLOR_CYAN, -1), 2: (curses.COLOR_YELLOW, -1), 3: (curses.COLOR_GREEN, -1), 4: (curses.COLOR_RED, -1), 5: (curses.COLOR_MAGENTA, -1)},
            "retro": {1: (curses.COLOR_WHITE, curses.COLOR_BLUE), 2: (curses.COLOR_BLACK, curses.COLOR_YELLOW), 3: (curses.COLOR_BLACK, curses.COLOR_GREEN), 4: (curses.COLOR_WHITE, curses.COLOR_RED), 5: (curses.COLOR_BLACK, curses.COLOR_MAGENTA)},
            "high_contrast": {1: (curses.COLOR_WHITE, curses.COLOR_BLACK), 2: (curses.COLOR_BLACK, curses.COLOR_WHITE), 3: (curses.COLOR_YELLOW, curses.COLOR_BLACK), 4: (curses.COLOR_RED, curses.COLOR_BLACK), 5: (curses.COLOR_MAGENTA, curses.COLOR_BLACK)}
        }

        self._init_colors()
        try:
            self.apply_theme(self.theme)
            # object colors
            self.obj_color_map = {
            "item": 30,
            }

            # sector colors (only if no object)
            self.sector_color_map = {
            "MEDBAY": 31,
            "BRIDGE": 32,
            "ENGINEERING": 33,
            "AIRLOCK": 34,
            }
        except Exception:
            pass

    def _init_colors(self):
        try:
            if curses.has_colors():
                curses.start_color()
                try:
                    curses.use_default_colors()
                except Exception:
                    pass
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, curses.COLOR_GREEN, -1)
                curses.init_pair(4, curses.COLOR_RED, -1)
                curses.init_pair(5, curses.COLOR_MAGENTA, -1)
                # health bar specific pairs
                # pair 10 = green on default background
                curses.init_pair(10, curses.COLOR_GREEN, -1)
                # pair 11 = yellow on default background
                curses.init_pair(11, curses.COLOR_YELLOW, -1)
                # pair 12 = red on default background
                curses.init_pair(12, curses.COLOR_RED, -1)
                curses.init_pair(30, 250, -1)   # items (light gray)
                curses.init_pair(31, 118, -1)   # medbay (greenish)
                curses.init_pair(32, 160, -1)   # bridge (red)
                curses.init_pair(33, 141, -1)   # engineering (light lavender)
                curses.init_pair(34, 189, -1)   # airlock (silver-blue)
                self.colors_available = True
        except Exception:
            self.colors_available = False

    def apply_theme(self, name):
        if not curses.has_colors():
            self.colors_available = False
            return False
        theme = self.THEMES.get(name)
        if not theme:
            return False
        try:
            curses.start_color()
            try:
                curses.use_default_colors()
            except Exception:
                pass
            for pair_idx, (fg, bg) in theme.items():
                curses.init_pair(pair_idx, fg, bg)
            self.colors_available = True
            self.theme = name
            return True
        except Exception:
            self.colors_available = False
            return False

    def _layout(self):
        maxy, maxx = self.stdscr.getmaxyx()
        status_h = 3
        msg_h = max(4, maxy // 5)

        # dostupná výška pro mapu a popis
        avail_h = maxy - status_h - msg_h - 4
        if avail_h < MIN_MAP_HEIGHT:
            avail_h = MIN_MAP_HEIGHT

        # preferovaná šířka popisu, ale pouze jako návrh
        preferred_desc_w = 30

        # maximální šířka mapy podle skutečné map.width (obsah) a dostupného prostoru
        # necháme mapě prioritu: chceme zobrazit co nejvíce mapy, ale ne více než terminál dovolí
        # nejprve zjistíme maximální možnou map_w pokud by popis byl vpravo
        max_map_w_with_desc = maxx - (preferred_desc_w + 6)
        # pokud to není možné, map může zabrat téměř celou šířku
        max_map_w_full = maxx - 4

        # cílová šířka mapy = min(nativní šířka mapy + okraje, dostupný prostor)
        desired_map_w = min(
            self.map.width + 2, max_map_w_with_desc if max_map_w_with_desc >= MIN_MAP_WIDTH else max_map_w_full)
        # zajistit minimální šířku
        if desired_map_w < MIN_MAP_WIDTH:
            desired_map_w = MIN_MAP_WIDTH

        # rozhodnutí, zda popis bude vpravo nebo pod mapou
        side_desc = (desired_map_w + preferred_desc_w + 6 <= maxx)

        if side_desc:
            map_w = desired_map_w
            desc_w = min(preferred_desc_w, maxx - map_w - 6)
            desc_h = avail_h
            desc_x = 1 + map_w + 2
            desc_y = status_h
            map_x = 1
            map_y = status_h
            map_h = avail_h
        else:
            # popis pod mapou
            map_w = min(self.map.width + 2, maxx - 4)
        if map_w < MIN_MAP_WIDTH:
            map_w = MIN_MAP_WIDTH
            map_h = avail_h
            map_x = 1
            map_y = status_h
            desc_w = max(20, maxx - 4)
            desc_h = max(4, (maxy - status_h - msg_h - map_h - 6))
            desc_x = 1
            desc_y = map_y + map_h + 1

        # bezpečné vytvoření/resize oken
        try:
            if self.map_win is None:
                self.map_win = curses.newwin(map_h, map_w, map_y, map_x)
            else:
                self.map_win.resize(map_h, map_w)
                self.map_win.mvwin(map_y, map_x)
        except Exception as e:
            self.map_win = None
            if not getattr(self, "_map_win_err_emitted", False):
                self.game.push_message(f"[debug] map_win error: {e}")
                self._map_win_err_emitted = True

        try:
            if self.status_win is None:
                self.status_win = curses.newwin(status_h, maxx - 2, 0, 1)
            else:
                self.status_win.resize(status_h, maxx - 2)
                self.status_win.mvwin(0, 1)
        except Exception as e:
            self.status_win = None
            if not getattr(self, "_status_win_err_emitted", False):
                self.game.push_message(f"[debug] status_win error: {e}")
                self._status_win_err_emitted = True

        try:
            if self.msg_win is None:
                self.msg_win = curses.newwin(msg_h, maxx - 2, maxy - msg_h - 1, 1)
            else:
                self.msg_win.resize(msg_h, maxx - 2)
                self.msg_win.mvwin(maxy - msg_h - 1, 1)
        except Exception as e:
            self.msg_win = None
            if not getattr(self, "_msg_win_err_emitted", False):
                self.game.push_message(f"[debug] msg_win error: {e}")
                self._msg_win_err_emitted = True

        try:
            if self.desc_win is None:
                self.desc_win = curses.newwin(desc_h, desc_w, desc_y, desc_x)
            else:
                self.desc_win.resize(desc_h, desc_w)
                self.desc_win.mvwin(desc_y, desc_x)
        except Exception as e:
            self.desc_win = None
            if not getattr(self, "_desc_win_err_emitted", False):
                self.game.push_message(f"[debug] desc_win error: {e}")
                self._desc_win_err_emitted = True

    # jednorázový layout debug
        if not self._layout_debug_emitted:
            try:
                info = {
                    "term": (maxy, maxx),
                    "map_win": None if not self.map_win else (self.map_win.getbegyx(), self.map_win.getmaxyx()),
                    "status_win": None if not self.status_win else (self.status_win.getbegyx(), self.status_win.getmaxyx()),
                    "msg_win": None if not self.msg_win else (self.msg_win.getbegyx(), self.msg_win.getmaxyx()),
                    "desc_win": None if not self.desc_win else (self.desc_win.getbegyx(), self.desc_win.getmaxyx()),
                }
                self.game.push_message(f"[debug] layout info: {info}")
            except Exception:
                pass
            self._layout_debug_emitted = True

    def render(self):
        try:
            self._layout()
        except Exception as e:
            try:
                self.stdscr.erase()
                self.stdscr.addstr(
                    0, 0, " EIDOLON DRIFT - Incident Response Terminal ", curses.A_BOLD)
                self.stdscr.refresh()
            except Exception:
                pass
            self.game.push_message(f"[debug] layout error: {e}")
            return

        try:
            self.stdscr.move(0, 0)
            self.stdscr.clrtoeol()
        except Exception:
            pass
        maxy, maxx = self.stdscr.getmaxyx()
        title = " EIDOLON DRIFT - Incident Response Terminal "
        try:
            title_x = max(0, (maxx - len(title)) // 2)
            attr = curses.A_BOLD | (curses.color_pair(
                1) if self.colors_available else 0)
            self.stdscr.addstr(0, title_x, title[:maxx-1], attr)
        except Exception:
            pass

        try:
            self._render_status()
        except Exception as e:
            self.game.push_message(f"[debug] status render error: {e}")
        try:
            maprenderer = MapRenderer(self)
            maprenderer.render_map()
        except Exception as e:
            self.game.push_message(f"[debug] map render error: {e}")
        try:
            self._render_description()
        except Exception as e:
            self.game.push_message(f"[debug] description render error: {e}")
        try:
            self._render_messages()
        except Exception as e:
            self.game.push_message(f"[debug] messages render error: {e}")

        try:
            self.stdscr.noutrefresh()
            if self.status_win:
                self.status_win.noutrefresh()
            if self.map_win:
                self.map_win.noutrefresh()
            if self.desc_win:
                self.desc_win.noutrefresh()
            if self.msg_win:
                self.msg_win.noutrefresh()
            curses.doupdate()
        except Exception:
            try:
                self.stdscr.refresh()
            except Exception:
                pass

    def _render_status(self):
        win = self.status_win or self.stdscr
        try:
            win.erase()
            if self.status_win:
                win.box()
            p = self.player
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
                    10) if self.colors_available else 0
            elif pct > HEALTH_RED_THRESHOLD:
                color_pair = curses.color_pair(
                    11) if self.colors_available else 0
            else:
                color_pair = curses.color_pair(
                    12) if self.colors_available else 0

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
                if not getattr(self, "_status_draw_err_emitted", False):
                    self.game.push_message(f"[debug] status draw error: {e}")
                    self._status_draw_err_emitted = True
        except Exception as e:
            self.game.push_message(f"[debug] status render error: {e}")
        except Exception as e:
            if not getattr(self, "_status_outer_err_emitted", False):
                self.game.push_message(f"[debug] status outer error: {e}")
                self._status_outer_err_emitted = True
        

    def _render_description(self):
        """
        Vykreslí obsah pravého (description) okna včetně ambientní zprávy.
        Používá self.desc_win a self.game (Game instance).
        """
        if not getattr(self, "desc_win", None):
            return

        try:
            maxy, maxx = self.desc_win.getmaxyx()
        except Exception:
            return

        # vyčistit okno a vykreslit rámeček
        try:
            self.desc_win.erase()
            # pokud je dost místa, vykreslíme box, a posuneme obsah o 1 řádek/1 sloupec
            if maxy > 2 and maxx > 2:
                try:
                    self.desc_win.box()
                    inner_y = 1
                    inner_x = 1
                    inner_h = maxy - 2
                    inner_w = maxx - 2
                except Exception:
                    inner_y = 0
                    inner_x = 0
                    inner_h = maxy
                    inner_w = maxx
            else:
                inner_y = 0
                inner_x = 0
                inner_h = maxy
                inner_w = maxx
        except Exception:
            inner_y = 0
            inner_x = 0
            inner_h = maxy
            inner_w = maxx

        # získat aktuální sektor
        try:
            sector = self.game.map.get_sector(self.game.player.x, self.game.player.y)
        except Exception:
            sector = None

        y = inner_y
        x = inner_x
        # název sektoru (tučně)
        title = getattr(sector, "name", "Unknown") if sector else "Unknown"
        try:
            self.desc_win.addstr(y, x, title[:inner_w], curses.A_BOLD)
        except Exception:
            try:
                self.desc_win.addstr(y, x, title[:inner_w])
            except Exception:
                pass
        y += 1

        # popis sektoru (zalomení)
        desc = getattr(sector, "description", "") if sector else ""
        for line in wrap_text(desc, inner_w):
            if y >= inner_y + inner_h:
                break
            try:
                self.desc_win.addstr(y, x, line[:inner_w])
            except Exception:
                pass
            y += 1

        # seznam objektů
        objs = getattr(sector, "objects", []) if sector else []
        if objs and y < inner_y + inner_h:
            # prázdný řádek pokud je místo
            if y < inner_y + inner_h:
                y += 1
            if y < inner_y + inner_h:
                try:
                    self.desc_win.addstr(y, x, "Objects:", curses.A_UNDERLINE)
                except Exception:
                    try:
                        self.desc_win.addstr(y, x, "Objects:")
                    except Exception:
                        pass
                y += 1
            for obj in objs:
                if y >= inner_y + inner_h:
                    break
                title = obj.get("title", obj.get("name", "object")) if isinstance(obj, dict) else str(obj)
                try:
                    style = curses.A_NORMAL
                    if self.colors_available and isinstance(obj, dict):
                        if obj.get("type") == "item":
                            style = curses.color_pair(30)

                    self.desc_win.addstr(y, x, f"- {title}"[:inner_w], style)
                except Exception:
                    pass
                y += 1

        # ambientní blok (zobrazí se krátce)
        amb_msg = getattr(self.game, "last_ambient_message", None)
        if amb_msg and y < inner_y + inner_h:
            # rezervovat prázdný řádek pokud je místo
            if y < inner_y + inner_h:
                y += 1
            if y < inner_y + inner_h:
                try:
                    self.desc_win.addstr(y, x, "Ambient:", curses.A_BOLD | curses.A_UNDERLINE)
                except Exception:
                    try:
                        self.desc_win.addstr(y, x, "Ambient:")
                    except Exception:
                        pass
                y += 1
            # samotná zpráva (zalomení) s jemným stylem
            style = curses.A_DIM
            for line in wrap_text(amb_msg, inner_w):
                if y >= inner_y + inner_h:
                    break
                try:
                    self.desc_win.addstr(y, x, line[:inner_w], style)
                except Exception:
                    try:
                        self.desc_win.addstr(y, x, line[:inner_w])
                    except Exception:
                        pass
                y += 1

        # noutrefresh/refresh podle render loopu
        try:
            self.desc_win.noutrefresh()
        except Exception:
            try:
                self.desc_win.refresh()
            except Exception:
                pass

    def _render_messages(self):
        win = self.msg_win or self.stdscr
        try:
            if self.msg_win:
                win.erase()
                win.box()
            maxy, maxx = win.getmaxyx()
            lines = self.game.messages[-(maxy - 2)
                                         :] if maxy > 2 else self.game.messages[-1:]
            for i, line in enumerate(lines):
                try:
                    attr = curses.color_pair(4) | curses.A_BOLD if (self.colors_available and (
                        "WARNING" in line.upper() or "ANOMALY" in line.upper())) else curses.A_NORMAL
                    win.addstr(1 + i, 2, line[:maxx - 4], attr)
                except Exception:
                    continue
        except Exception as e:
            if not getattr(self, "_msg_draw_err_emitted", False):
                self.game.push_message(f"[debug] messages draw error: {e}")
                self._msg_draw_err_emitted = True

    def open_pager(self, lines):
        stdscr = self.stdscr
        maxy, maxx = stdscr.getmaxyx()
        pad_h = max(len(lines) + 2, maxy)
        pad_w = maxx - 2
        pad = curses.newpad(pad_h, pad_w)
        for i, ln in enumerate(lines):
            try:
                pad.addstr(i, 0, ln[:pad_w - 1])
            except Exception:
                pass
        top = 0
        view_h = maxy - 2
        title = " LOG VIEWER (q to close) "
        while True:
            try:
                stdscr.erase()
                stdscr.box()
                stdscr.addstr(0, max(1, (maxx - len(title)) // 2),
                              title, curses.A_REVERSE)
                stdscr.noutrefresh()
                pad.noutrefresh(top, 0, 1, 1, view_h, pad_w)
                curses.doupdate()
            except Exception:
                pass
            ch = stdscr.getch()
            if ch in (ord('q'), 27):
                break
            elif ch in (curses.KEY_DOWN, ord('j')):
                if top + view_h < pad_h:
                    top += 1
            elif ch in (curses.KEY_UP, ord('k')):
                if top > 0:
                    top -= 1
            elif ch == curses.KEY_NPAGE:
                top = min(top + view_h, pad_h - view_h)
            elif ch == curses.KEY_PPAGE:
                top = max(top - view_h, 0)
            elif ch == curses.KEY_HOME:
                top = 0
            elif ch == curses.KEY_END:
                top = max(0, pad_h - view_h)
        self.render()


def wrap_text(text, width):
    if not text:
        return [""]
    return textwrap.wrap(text, width=width) or [""]

# do třídy OutputRenderer (nebo kde máš metody renderování) přidej:


