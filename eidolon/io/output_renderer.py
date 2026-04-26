# eidolon/io/output_renderer.py
import curses
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
        # reserve a description column width if space allows
        preferred_desc_w = 30
        # compute map area width first
        map_w = min(self.map.width + 2, maxx - 6 - preferred_desc_w)
        # if not enough space for side description, map takes full width and desc goes below
        side_desc = True
        if map_w < MIN_MAP_W:
            map_w = min(self.map.width + 2, maxx - 4)
            side_desc = False

        map_h = maxy - status_h - msg_h - 4
        if map_h < MIN_MAP_H:
            map_h = MIN_MAP_H

        # positions
        map_x = max(1, 1)
        map_y = status_h

        # if side_desc possible, desc on right; else desc below map
        if side_desc and (map_w + preferred_desc_w + 6 <= maxx):
            desc_w = preferred_desc_w
            desc_h = map_h
            desc_x = map_x + map_w + 2
            desc_y = map_y
        else:
            # desc below map, full width
            desc_w = max(20, maxx - 4)
            desc_h = max(4, (maxy - status_h - msg_h - 6) // 3)
            desc_x = 1
            desc_y = map_y + map_h + 1

        # create or resize windows safely
        try:
            if self.map_win is None:
                self.map_win = curses.newwin(map_h, map_w, map_y, map_x)
            else:
                self.map_win.resize(map_h, map_w)
                self.map_win.mvwin(map_y, map_x)
        except Exception as e:
            self.map_win = None
            # one-time debug only
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
                self.msg_win = curses.newwin(
                    msg_h, maxx - 2, maxy - msg_h - 1, 1)
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

        # one-time layout info
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
            self._render_map()
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
                color_pair = curses.color_pair(10) if self.colors_available else 0
            elif pct > HEALTH_RED_THRESHOLD:
                color_pair = curses.color_pair(11) if self.colors_available else 0
            else:
                color_pair = curses.color_pair(12) if self.colors_available else 0

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

    def _render_map(self):
        win = self.map_win or self.stdscr
        try:
            if self.map_win:
                win.erase()
                win.box()
            h, w = win.getmaxyx()
            inner_h = max(0, h - 2)
            inner_w = max(0, w - 2)

            for y in range(min(self.map.height, inner_h)):
                for x in range(min(self.map.width, inner_w)):
                    ch = self.map.get_tile_char(x, y) or "."
                    sector = self.map.get_sector(x, y)
                    obj_marker = None
                    if sector and sector.objects:
                        for o in sector.objects:
                            if isinstance(o, dict) and o.get("type") == "log":
                                obj_marker = "l"
                                break
                            if isinstance(o, dict) and o.get("type") == "anomaly":
                                obj_marker = "x"
                                break
                            if isinstance(o, dict) and o.get("type") == "item":
                                obj_marker = "i"
                                break
                    if self.player.x == x and self.player.y == y:
                        ch = "@"
                        attr = curses.A_BOLD | (curses.color_pair(
                            2) if self.colors_available else 0)
                    else:
                        ch = obj_marker if obj_marker else ch
                        attr = curses.color_pair(3) if (
                            self.colors_available and obj_marker) else curses.A_NORMAL
                    try:
                        win.addstr(1 + y, 1 + x, str(ch), attr)
                    except Exception as e:
                        # avoid flooding messages: emit once per cell error type
                        if not getattr(self, "_map_cell_err_emitted", False):
                            self.game.push_message(
                                f"[debug] map draw cell error: {e} x={x} y={y} ch={ch}")
                            self._map_cell_err_emitted = True
                        continue
        except Exception as e:
            self.game.push_message(f"[debug] map draw error: {e}")

    def _render_description(self):
        win = self.desc_win or self.stdscr
        try:
            win.erase()
            if self.desc_win:
                win.box()
            # get current sector
            sector = None
            try:
                sector = self.map.get_sector(self.player.x, self.player.y)
            except Exception:
                sector = None
            title = "Sector"
            desc = "You see nothing special."
            objects = []
            if sector:
                title = getattr(sector, "title", None) or getattr(
                    sector, "name", None) or f"Sector {self.player.x},{self.player.y}"
                # sector may have description field or short_desc
                desc = getattr(sector, "description", None) or getattr(
                    sector, "short_desc", None) or ""
                # collect object names/titles
                for o in getattr(sector, "objects", []) or []:
                    if isinstance(o, dict):
                        objects.append(o.get("title") or o.get(
                            "name") or "<object>")
                    elif isinstance(o, str):
                        objects.append(o)
            # draw title
            try:
                win.addstr(1, 2, title[:(win.getmaxyx()[1]-4)], curses.A_BOLD)
            except Exception:
                pass
            # draw description (wrap na řádky)
            maxy, maxx = win.getmaxyx()
            desc_lines = []
            if desc:
                # simple wrap
                line = ""
                for word in desc.split():
                    if len(line) + 1 + len(word) < maxx - 4:
                        line = (line + " " + word).strip()
                    else:
                        desc_lines.append(line)
                        line = word
                if line:
                    desc_lines.append(line)
            # print desc lines
            for i, ln in enumerate(desc_lines[: maxy - 6]):
                try:
                    win.addstr(3 + i, 2, ln)
                except Exception:
                    pass
            # print objects header and list
            obj_start = 3 + len(desc_lines)
            if obj_start < maxy - 2:
                try:
                    win.addstr(obj_start, 2, "Objects:", curses.A_UNDERLINE)
                except Exception:
                    pass
                for j, name in enumerate(objects[: maxy - obj_start - 3]):
                    try:
                        win.addstr(obj_start + 1 + j, 3,
                                   f"- {name}"[: maxx - 6])
                    except Exception:
                        pass
        except Exception as e:
            # do not flood messages
            if not getattr(self, "_desc_err_emitted", False):
                self.game.push_message(f"[debug] description draw error: {e}")
                self._desc_err_emitted = True

    def _render_messages(self):
        win = self.msg_win or self.stdscr
        try:
            if self.msg_win:
                win.erase()
                win.box()
            maxy, maxx = win.getmaxyx()
            lines = self.game.messages[-(maxy - 2)                                       :] if maxy > 2 else self.game.messages[-1:]
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
