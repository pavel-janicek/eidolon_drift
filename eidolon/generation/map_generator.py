# eidolon/generation/map_generator.py
import random
from eidolon.world.map import Map
from eidolon.world.sector import Sector
from eidolon.config import DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT, SEED

SECTOR_TYPES = ["BRIDGE", "ENGINEERING", "CREW", "MEDBAY", "CARGO", "AIRLOCK", "EMPTY"]

class MapGenerator:
    def __init__(self, width=DEFAULT_MAP_WIDTH, height=DEFAULT_MAP_HEIGHT, seed=SEED):
        self.width = width
        self.height = height
        if seed is not None:
            random.seed(seed)

    def generate(self):
        grid = {}
        for y in range(self.height):
            for x in range(self.width):
                t = random.choices(SECTOR_TYPES, weights=[1,1,2,1,2,1,5])[0]
                name = f"{t}-{x}-{y}"
                desc = self._make_description(t)
                grid[(x, y)] = Sector(x, y, name, t, desc)
        # place bridge near top-left, airlock near edge
        grid[(0,0)].type = "BRIDGE"
        grid[(0,0)].name = "Bridge"
        grid[(self.width-1, self.height-1)].type = "AIRLOCK"
        grid[(self.width-1, self.height-1)].name = "Outer Airlock"
        return Map(self.width, self.height, grid)

    def _make_description(self, t):
        templates = {
            "BRIDGE": "The bridge is dark. Consoles flicker with corrupted telemetry.",
            "ENGINEERING": "Sparks and the smell of ozone. A coolant leak has frozen some panels.",
            "CREW": "Personal lockers are open. A jacket lies on the floor.",
            "MEDBAY": "Medical trays overturned. A faint stain on the floor.",
            "CARGO": "Crates are scattered. Some containers are sealed with hazard tape.",
            "AIRLOCK": "The airlock cycles are offline. The outer hatch is ajar.",
            "EMPTY": "A narrow corridor. The lights are dim.",
        }
        return templates.get(t, "An unremarkable section of the ship.")
