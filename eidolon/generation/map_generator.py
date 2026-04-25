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

    def _make_description(self, sector_type):
        descriptions = {
            "BRIDGE": "The command center of the Eidolon. Consoles flicker with emergency lights. The captain's chair sits empty.",
            "ENGINEERING": "A maze of conduits and machinery. Humming engines provide power to the ship. Warning lights blink sporadically.",
            "CREW": "Crew quarters. Bunks line the walls, personal effects scattered about. The air smells of recycled oxygen.",
            "MEDBAY": "Medical bay. Examination tables and diagnostic equipment. Emergency supplies are stored in cabinets.",
            "CARGO": "Cargo hold. Crates and containers are secured to the floor. The space echoes with the hum of life support.",
            "AIRLOCK": "Airlock chamber. Heavy doors seal the entrance to space. Suits hang on racks, ready for EVA.",
            "EMPTY": "An empty corridor. Dim lights cast long shadows. The silence is broken only by distant machinery."
        }
        return descriptions.get(sector_type, "An unremarkable sector.")

    def _random_environment(self, sector_type):
        base_env = {
            "BRIDGE": "Control panels and navigation displays dominate the room.",
            "ENGINEERING": "Pipes and cables snake across the walls and ceiling.",
            "CREW": "Personal lockers and sleeping pods line the walls.",
            "MEDBAY": "Medical scanners and treatment equipment are visible.",
            "CARGO": "Storage containers and cargo nets fill the space.",
            "AIRLOCK": "Pressure suits and emergency equipment are stored here.",
            "EMPTY": "Bare walls and minimal lighting characterize this area."
        }
        env = base_env.get(sector_type, "The environment is sparse and functional.")
        # Add random variation
        variations = [
            " The air is cool and still.",
            " A faint vibration runs through the floor.",
            " Emergency lighting casts an eerie glow.",
            " The sound of distant alarms echoes faintly.",
            " Scattered debris litters the floor."
        ]
        if random.random() < 0.3:  # 30% chance
            env += random.choice(variations)
        return env

    def _populate_objects(self, sector, sector_type):
        # Add objects based on sector type
        if sector_type == "BRIDGE":
            if random.random() < 0.5:
                sector.objects.append({
                    "type": "log",
                    "name": "captains-log",
                    "title": "Captain's Log Terminal",
                    "description": "A terminal displaying the captain's final log entries."
                })
        elif sector_type == "ENGINEERING":
            if random.random() < 0.4:
                sector.objects.append({
                    "type": "item",
                    "name": "wrench",
                    "title": "Engineering Wrench",
                    "description": "A heavy wrench, useful for repairs."
                })
        elif sector_type == "MEDBAY":
            if random.random() < 0.6:
                sector.objects.append({
                    "type": "item",
                    "name": "medkit",
                    "title": "Medical Kit",
                    "description": "A kit containing bandages and painkillers."
                })
        elif sector_type == "CARGO":
            if random.random() < 0.3:
                sector.objects.append({
                    "type": "item",
                    "name": "ration",
                    "title": "Emergency Ration",
                    "description": "A sealed packet of food and water."
                })
        # Random anomalies in any sector
        if random.random() < 0.1:  # 10% chance
            sector.objects.append({
                "type": "anomaly",
                "name": "strange-signal",
                "title": "Strange Signal",
                "description": "An anomalous reading on your scanner."
            })

