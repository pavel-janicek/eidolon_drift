# eidolon/generation/map_generator.py
import random
import json
from pathlib import Path
from eidolon.world.map import Map
from eidolon.world.sector import Sector
from eidolon.config import DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT, SEED

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "objects"
SECTOR_TYPES = ["BRIDGE", "ENGINEERING", "CREW", "MEDBAY", "CARGO", "AIRLOCK", "EMPTY"]

def _load_templates():
    templates = []
    p = DATA_DIR / "objects.json"
    if not p.exists():
        return templates
    with open(p, "r", encoding="utf-8") as f:
        templates = json.load(f)
    # index by id and also group templates by kind
    by_id = {t["id"]: t for t in templates}
    return templates, by_id

class MapGenerator:
    def __init__(self, width=DEFAULT_MAP_WIDTH, height=DEFAULT_MAP_HEIGHT, seed=SEED):
        self.width = width
        self.height = height
        if seed is not None:
            random.seed(seed)
        self.templates, self.template_index = _load_templates()

    def generate(self):
        grid = {}
        # create empty grid
        for y in range(self.height):
            for x in range(self.width):
                grid[(x, y)] = Sector(x, y, f"EMPTY-{x}-{y}", "EMPTY", "A narrow corridor. The lights are dim.")
                # initialize linger fields
                grid[(x, y)].linger_counter = 0
                grid[(x, y)].linger_thresholds = {}

        # carve ship layout
        # Bridge region top-left
        for y in range(0, max(2, self.height // 4)):
            for x in range(0, max(3, self.width // 4)):
                stype = "BRIDGE" if (x == 0 and y == 0) else "CREW"
                grid[(x, y)].type = stype
                grid[(x, y)].name = f"{stype}-{x}-{y}"

        # engineering band
        mid_y = self.height // 2
        for x in range(self.width // 4, 3 * self.width // 4):
            grid[(x, mid_y)].type = "ENGINEERING"
            grid[(x, mid_y)].name = f"ENGINEERING-{x}-{mid_y}"

        # cargo aft
        for y in range(self.height - max(3, self.height // 4), self.height):
            for x in range(self.width - max(4, self.width // 4), self.width):
                grid[(x, y)].type = "CARGO"
                grid[(x, y)].name = f"CARGO-{x}-{y}"

        # airlocks
        grid[(self.width - 1, self.height // 2)].type = "AIRLOCK"
        grid[(self.width - 1, self.height // 2)].name = "Outer Airlock"
        grid[(0, self.height - 1)].type = "AIRLOCK"
        grid[(0, self.height - 1)].name = "Rear Airlock"

        # ensure command module
        bridge_pos = (0, 0)
        grid[bridge_pos].type = "BRIDGE"
        grid[bridge_pos].name = "Command Module"

        # apply descriptions from templates if present
        desc_map = {t["sector_type"]: t["text"] for t in self.templates if t.get("kind") == "description"}
        for (x, y), sector in grid.items():
            sector.description = desc_map.get(sector.type, sector.description)
            sector.environment = self._random_environment(sector.type)
            # populate objects using templates
            self._populate_objects(sector)

        # place escape pod near bridge
        ex_x, ex_y = 1, 0
        if (ex_x, ex_y) in grid:
            grid[(ex_x, ex_y)].objects.append({
                "type": "item",
                "name": "escape-pod",
                "title": "Escape Pod",
                "description": "A small escape pod interface. Use 'use escape-pod' to attempt launch."
            })

        return Map(self.width, self.height, grid)

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
        variations = [
            " The air is cool and still.",
            " A faint vibration runs through the floor.",
            " Emergency lighting casts an eerie glow.",
            " The sound of distant alarms echoes faintly.",
            " Scattered debris litters the floor."
        ]
        if random.random() < 0.3:
            env += random.choice(variations)
        return env

    def _choose_templates_for_sector(self, sector_type):
        # return list of templates with spawn_weight for this sector_type
        choices = []
        for t in self.templates:
            if t.get("kind") != "template":
                continue
            weights = t.get("spawn_weight", {})
            w = weights.get(sector_type, 0)
            if w > 0:
                choices.append((t, w))
        return choices

    def _populate_objects(self, sector):
        # deterministic-ish: iterate templates and roll by weight
        choices = self._choose_templates_for_sector(sector.type)
        for tpl, weight in choices:
            if random.random() < weight:
                # instantiate object from template
                obj = self._instantiate_from_template(tpl, sector)
                sector.objects.append(obj)
                # if object has linger properties, set sector thresholds
                if obj.get("type") == "anomaly" and obj.get("linger_damage"):
                    # set a simple threshold: linger 2 turns triggers linger effect
                    sector.linger_thresholds[2] = sector.linger_thresholds.get(2, []) + [obj.get("name")]
                    # store linger metadata on object for event engine
                    obj["_linger_threshold"] = 2

    def _instantiate_from_template(self, tpl, sector):
        # shallow copy and fill dynamic fields
        obj = dict(tpl)  # copy template dict
        # remove internal keys not needed on instance
        obj.pop("id", None)
        obj.pop("kind", None)
        obj.pop("spawn_weight", None)
        # normalize name lowercased
        if "name" in obj:
            obj["name"] = obj["name"].lower()
        # for logs, generate content
        if obj.get("type") == "log":
            # simple seeded text
            text = random.choice([
                "We lost contact with the relay. Strange readings on the sensors.",
                "Crew morale is low. Supplies are dwindling.",
                "Engineering reports intermittent power surges in sector 3.",
                "Unidentified impact on the hull. External cameras corrupted."
            ])
            content = obj.get("content_template", "{text}").format(text=text)
            obj["content"] = content
            obj["fragmented"] = random.random() < obj.get("fragmented_chance", 0.3)
        return obj
