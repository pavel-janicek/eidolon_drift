# eidolon/world/map.py
from eidolon.world.sector import Sector


class Map:
    def __init__(self, width, height, grid):
        self.width = width
        self.height = height
        self.grid = grid  # dict (x,y) -> Sector

    def get_sector(self, x, y):
        return self.grid.get((x, y))

    def get_tile_char(self, x, y):
        s = self.get_sector(x, y)
        if s is None:
            return " "
        t = s.type
        mapping = {
            "BRIDGE": "B",
            "ENGINEERING": "E",
            "CREW": "C",
            "MEDBAY": "M",
            "CARGO": "G",
            "AIRLOCK": "L",
            "EMPTY": ".",
        }
        return mapping.get(t, "?")
