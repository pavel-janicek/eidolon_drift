
import curses



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

        try:
            maxy, maxx = self.output_renderer.desc_win.getmaxyx()
        except Exception:
            return

        # vyčistit okno a vykreslit rámeček
        try:
            self.output_renderer.desc_win.erase()
            # pokud je dost místa, vykreslíme box, a posuneme obsah o 1 řádek/1 sloupec
            if maxy > 2 and maxx > 2:
                try:
                    self.output_renderer.desc_win.box()
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
            sector = self.output_renderer.game.map.get_sector(self.output_renderer.game.player.x, self.output_renderer.game.player.y)
        except Exception:
            sector = None

        y = inner_y
        x = inner_x
        # název sektoru (tučně)
        title = getattr(sector, "name", "Unknown") if sector else "Unknown"
        try:
            self.output_renderer.desc_win.addstr(y, x, title[:inner_w], curses.A_BOLD)
        except Exception:
            try:
                self.output_renderer.desc_win.addstr(y, x, title[:inner_w])
            except Exception:
                pass
        y += 1

        # popis sektoru (zalomení)
        desc = getattr(sector, "description", "") if sector else ""
        for line in self.output_renderer.wrap_text(desc, inner_w):
            if y >= inner_y + inner_h:
                break
            try:
                self.output_renderer.desc_win.addstr(y, x, line[:inner_w])
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
                    self.output_renderer.desc_win.addstr(y, x, "Objects:", curses.A_UNDERLINE)
                except Exception:
                    try:
                        self.output_renderer.desc_win.addstr(y, x, "Objects:")
                    except Exception:
                        pass
                y += 1
            for obj in objs:
                if y >= inner_y + inner_h:
                    break
                title = obj.get("title", obj.get("name", "object")) if isinstance(obj, dict) else str(obj)
                try:
                    style = curses.A_NORMAL
                    if self.output_renderer.colors_available and isinstance(obj, dict):
                        if obj.get("type") == "item":
                            style = curses.color_pair(30)

                    self.output_renderer.desc_win.addstr(y, x, f"- {title}"[:inner_w], style)
                except Exception:
                    pass
                y += 1

        # ambientní blok (zobrazí se krátce)
        amb_msg = getattr(self.output_renderer.game, "last_ambient_message", None)
        if amb_msg and y < inner_y + inner_h:
            # rezervovat prázdný řádek pokud je místo
            if y < inner_y + inner_h:
                y += 1
            if y < inner_y + inner_h:
                try:
                    self.output_renderer.desc_win.addstr(y, x, "Ambient:", curses.A_BOLD | curses.A_UNDERLINE)
                except Exception:
                    try:
                        self.output_renderer.desc_win.addstr(y, x, "Ambient:")
                    except Exception:
                        pass
                y += 1
            # samotná zpráva (zalomení) s jemným stylem
            style = curses.A_DIM
            for line in self.output_renderer.wrap_text(amb_msg, inner_w):
                if y >= inner_y + inner_h:
                    break
                try:
                    self.output_renderer.desc_win.addstr(y, x, line[:inner_w], style)
                except Exception:
                    try:
                        self.output_renderer.desc_win.addstr(y, x, line[:inner_w])
                    except Exception:
                        pass
                y += 1

        # noutrefresh/refresh podle render loopu
        try:
            self.output_renderer.desc_win.noutrefresh()
        except Exception:
            try:
                self.output_renderer.desc_win.refresh()
            except Exception:
                pass
