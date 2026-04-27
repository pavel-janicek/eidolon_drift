import curses
import math


class MapRenderer:
    def __init__(self, parent):
        self.parent = parent

    def render(self):
        win = self.parent.map_win or self.parent.stdscr
        try:
            if self.parent.map_win:
                win.erase()
                win.box()
            h, w = win.getmaxyx()
            inner_h = max(0, h - 2)
            inner_w = max(0, w - 2)

            for y in range(min(self.parent.map.height, inner_h)):
                for x in range(min(self.parent.map.width, inner_w)):
                    # Check visibility first
                    if self._is_outside_visibility(x, y):
                        ch = " "
                        attr = curses.A_NORMAL
                    else:
                        ch = self.parent.map.get_tile_char(x, y) or "."
                        sector = self.parent.map.get_sector(x, y)
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
                        if self.parent.player.x == x and self.parent.player.y == y:
                            ch = "@"
                            attr = curses.A_BOLD | (curses.color_pair(
                                2) if self.parent.colors_available else 0)
                        else:
                            # object has priority
                            if obj_marker and self.parent.colors_available:
                                try:
                                    first = sector.objects[0]
                                    otype = first.get("type")
                                    pair = self.parent.obj_color_map.get(otype)
                                    if pair:
                                        attr = curses.color_pair(pair) | curses.A_BOLD
                                    else:
                                        attr = curses.A_NORMAL
                                except Exception:
                                    attr = curses.A_NORMAL
                                ch = obj_marker

                        # sector color (only if no object)
                            elif self.parent.colors_available:
                                stype = sector.type
                                pair = self.parent.sector_color_map.get(stype)
                                if pair:
                                    attr = curses.color_pair(pair)
                                else:
                                    attr = curses.A_NORMAL

                            else:
                                attr = curses.A_NORMAL

                    try:
                        win.addstr(1 + y, 1 + x, str(ch), attr)
                    except Exception as e:
                        # avoid flooding messages: emit once per cell error type
                        if not getattr(self.parent, "_map_cell_err_emitted", False):
                            self.parent.game.push_message(
                                f"[debug] map draw cell error: {e} x={x} y={y} ch={ch}")
                            self.parent._map_cell_err_emitted = True
                        continue
        except Exception as e:
            self.parent.game.push_message(f"[debug] map draw error: {e}")

    def _is_outside_visibility(self, x, y):
        p = self.parent.player
        sanity = getattr(p, "sanity", 100)       
        pct = max(0.20, sanity / 100.0)  # minimum 20%
        # Use map dimensions for max radius calculation
        max_radius = max(self.parent.map.width, self.parent.map.height) // 2
        radius = int(max_radius * pct)
        dx = x - p.x
        dy = y - p.y
        dist = math.sqrt(dx*dx + dy*dy)
        return dist > radius   