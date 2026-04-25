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
        # create empty grid first
        for y in range(self.height):
            for x in range(self.width):
                grid[(x, y)] = Sector(x, y, f"EMPTY-{x}-{y}", "EMPTY", "A narrow corridor. The lights are dim.")
        # carve ship layout: front (bridge), mid (engineering), aft (cargo)
        # Bridge region (top-left quadrant)
        for y in range(0, max(2, self.height//4)):
            for x in range(0, max(3, self.width//4)):
                grid[(x, y)].type = "BRIDGE" if (x==0 and y==0) else "CREW"
                grid[(x, y)].name = f"{grid[(x,y)].type}-{x}-{y}"
                grid[(x, y)].description = self._make_description(grid[(x,y)].type)
        # Engineering central band
        mid_y = self.height//2
        for x in range(self.width//4, 3*self.width//4):
            grid[(x, mid_y)].type = "ENGINEERING"
            grid[(x, mid_y)].name = f"ENGINEERING-{x}-{mid_y}"
            grid[(x, mid_y)].description = self._make_description("ENGINEERING")
        # Cargo aft (bottom-right quadrant)
        for y in range(self.height - max(3, self.height//4), self.height):
            for x in range(self.width - max(4, self.width//4), self.width):
                grid[(x, y)].type = "CARGO"
                grid[(x, y)].name = f"CARGO-{x}-{y}"
                grid[(x, y)].description = self._make_description("CARGO")
        # place airlocks along edges
        grid[(self.width-1, self.height//2)].type = "AIRLOCK"
        grid[(self.width-1, self.height//2)].name = "Outer Airlock"
        grid[(0, self.height-1)].type = "AIRLOCK"
        grid[(0, self.height-1)].name = "Rear Airlock"
        # ensure a single Command Module / Bridge sector
        bridge_pos = (0, 0)
        grid[bridge_pos].type = "BRIDGE"
        grid[bridge_pos].name = "Command Module"
        grid[bridge_pos].description = self._make_description("BRIDGE")
        # populate objects and environment
        for (x, y), sector in grid.items():
            sector.environment = self._random_environment(sector.type)
            self._populate_objects(sector, sector.type)
        # ensure escape pod exists in a reachable sector near bridge (e.g., bridge adjacent)
        ex_x, ex_y = 1, 0
        if (ex_x, ex_y) in grid:
            grid[(ex_x, ex_y)].objects.append({
                "type": "item",
                "name": "escape-pod",
                "title": "Escape Pod",
                "description": "A small escape pod interface. Use 'use escape-pod' to attempt launch."
            })
        return Map(self.width, self.height, grid)

    # keep _make_description, _random_environment, _populate_objects as before
