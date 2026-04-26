# eidolon/generation/map_generator.py
import random
import json
import sys
from pathlib import Path
from eidolon.world.map import Map
from eidolon.world.sector import Sector
from eidolon.config import MIN_MAP_WIDTH, MIN_MAP_HEIGHT
from eidolon.generation.log_loader import load_logs
from eidolon.config import DEFAULT_BASE_DENSITY, DEFAULT_MIN_DISTANCE

SECTOR_TYPES = ["BRIDGE", "ENGINEERING", "CREW", "MEDBAY", "CARGO", "AIRLOCK", "EMPTY"]


def _find_data_dir():
    here = Path(__file__).resolve()
    for up in range(1, 5):
        candidate = here.parents[up] / "data" / "objects"
        if candidate.exists() and candidate.is_dir():
            return candidate
    candidate = Path.cwd() / "data" / "objects"
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None


def _load_templates(data_dir):
    templates = []
    by_id = {}
    if not data_dir:
        return templates, by_id
    p = data_dir / "objects.json"
    if not p.exists():
        return templates, by_id
    try:
        with open(p, "r", encoding="utf-8") as f:
            templates = json.load(f)
    except Exception as e:
        print(f"[mapgen] failed to load templates: {e}", file=sys.stderr)
        return [], {}
    try:
        by_id = {t["id"]: t for t in templates if isinstance(t, dict) and "id" in t}
    except Exception:
        by_id = {}
    return templates, by_id


class MapGenerator:
    """
    Robustní generátor mapy.
    - width/height volitelné; pokud nejsou předány, použijí se MIN_MAP_*.
    - používá vlastní RNG instance (seed=None => náhodný).
    - base_density a min_distance laditelné.
    """
    def __init__(self, width=None, height=None, seed=None, base_density=0.06, min_distance=3):
        self.width = int(width) if width is not None else int(MIN_MAP_WIDTH)
        self.height = int(height) if height is not None else int(MIN_MAP_HEIGHT)
        if self.width < MIN_MAP_WIDTH:
            self.width = MIN_MAP_WIDTH
        if self.height < MIN_MAP_HEIGHT:
            self.height = MIN_MAP_HEIGHT

        # dedicated RNG
        if seed is None:
            self.rng = random.Random()
        else:
            self.rng = random.Random(seed)

        self.base_density = float(base_density) if base_density is not None else DEFAULT_BASE_DENSITY
        self.min_distance = int(min_distance) if min_distance is not None else DEFAULT_MIN_DISTANCE

        self.data_dir = _find_data_dir()
        self.templates, self.template_index = _load_templates(self.data_dir)
        self.log_pool = load_logs()
        data_path = (self.data_dir / "objects.json") if self.data_dir else Path("data/objects/objects.json")
        print(f"[mapgen][debug] loaded {len(self.templates)} templates from {data_path}", file=sys.stderr)

        # current_grid bude nastaven v generate() pro kontrolu okolí při spawnování
        self.current_grid = None

    def generate(self, width=None, height=None):
        w = int(width) if width is not None else int(self.width)
        h = int(height) if height is not None else int(self.height)

        if w < MIN_MAP_WIDTH:
            w = MIN_MAP_WIDTH
        if h < MIN_MAP_HEIGHT:
            h = MIN_MAP_HEIGHT

        grid = {}
        for y in range(h):
            for x in range(w):
                s = Sector(x, y, f"EMPTY-{x}-{y}", "EMPTY", "A narrow corridor. The lights are dim.")
                s.linger_counter = getattr(s, "linger_counter", 0)
                s.linger_thresholds = getattr(s, "linger_thresholds", {}) or {}
                if not hasattr(s, "objects") or s.objects is None:
                    s.objects = []
                grid[(x, y)] = s

        def fill_region(x0, y0, x1, y1, stype, name_prefix=None, density=1.0):
            for yy in range(max(0, y0), min(h, y1 + 1)):
                for xx in range(max(0, x0), min(w, x1 + 1)):
                    if self.rng.random() <= density:
                        sector = grid[(xx, yy)]
                        sector.type = stype
                        sector.name = f"{name_prefix or stype}-{xx}-{yy}"

        # bridge + crew cluster
        bridge_w = self.rng.randint(2, max(3, w // 5))
        bridge_h = self.rng.randint(2, max(2, h // 5))
        fill_region(0, 0, bridge_w - 1, bridge_h - 1, "BRIDGE", "Bridge")

        crew_w = max(2, min(w // 4, w - bridge_w - 1))
        crew_h = max(2, min(h // 4, h - bridge_h - 1))
        fill_region(bridge_w, 0, bridge_w + crew_w - 1, crew_h - 1, "CREW", "Crew", density=0.75)
        fill_region(0, bridge_h, crew_w - 1, bridge_h + crew_h - 1, "CREW", "Crew", density=0.75)

        # medbay region somewhere near the upper half, not overlapping the bridge cluster
        medbay_w = min(max(2, w // 6), max(2, w // 4))
        medbay_h = min(max(2, h // 6), max(2, h // 4))
        medbay_x = self.rng.randint(bridge_w, max(bridge_w, w - medbay_w - 2)) if w - medbay_w - bridge_w > 1 else bridge_w
        medbay_y = self.rng.randint(1, max(1, h // 2 - medbay_h)) if h // 2 - medbay_h > 1 else 1
        fill_region(medbay_x, medbay_y, medbay_x + medbay_w - 1, medbay_y + medbay_h - 1, "MEDBAY", "MEDBAY")

        # engineering band through the middle with small random offset
        eng_y = min(max(1, h // 2 + self.rng.randint(-1, 1)), h - 2)
        eng_x0 = self.rng.randint(0, max(0, w // 5))
        eng_x1 = self.rng.randint(min(w - 1, 3 * w // 4), w - 1)
        fill_region(eng_x0, eng_y, eng_x1, min(h - 1, eng_y + self.rng.randint(0, 1)), "ENGINEERING", "ENGINEERING", density=0.95)

        # cargo cluster with holes to reduce density
        cargo_w = max(4, min(w // 3, w - 2))
        cargo_h = max(3, min(h // 3, h - 2))
        cargo_x0 = max(0, w - cargo_w - self.rng.randint(0, max(0, (w - cargo_w) // 2)))
        cargo_y0 = max(h // 2, h - cargo_h - self.rng.randint(0, max(0, (h - cargo_h) // 2)))
        fill_region(cargo_x0, cargo_y0, cargo_x0 + cargo_w - 1, cargo_y0 + cargo_h - 1, "CARGO", "CARGO", density=0.7)

        airlocks = []
        if w > 1:
            airlocks.append((w - 1, self.rng.randint(0, h - 1)))
            airlocks.append((0, self.rng.randint(0, h - 1)))
        if h > 1:
            airlocks.append((self.rng.randint(0, w - 1), 0))
            airlocks.append((self.rng.randint(0, w - 1), h - 1))
        self.rng.shuffle(airlocks)
        seen = set()
        for x, y in airlocks:
            if len(seen) >= 2:
                break
            if (x, y) in seen:
                continue
            seen.add((x, y))
            try:
                grid[(x, y)].type = "AIRLOCK"
                name = "Outer Airlock" if x == w - 1 else "Rear Airlock"
                grid[(x, y)].name = name
            except Exception:
                pass

        bridge_pos = (0, 0)
        if bridge_pos in grid:
            grid[bridge_pos].type = "BRIDGE"
            grid[bridge_pos].name = "Command Module"

        # descriptions map
        desc_map = {}
        try:
            desc_map = {t["sector_type"]: t["text"] for t in self.templates if isinstance(t, dict) and t.get("kind") == "description"}
        except Exception:
            desc_map = {}

        # make grid available for placement checks
        self.current_grid = grid

        # populate sectors
        for (x, y), sector in list(grid.items()):
            sector.description = desc_map.get(sector.type, getattr(sector, "description", ""))
            sector.environment = self._random_environment(sector.type)
            if not hasattr(sector, "objects") or sector.objects is None:
                sector.objects = []
            try:
                self._populate_objects(sector)
            except Exception as e:
                print(f"[mapgen] populate error at {x},{y}: {e}", file=sys.stderr)

        # place escape pod near bridge
        ex_x, ex_y = 1, 0
        if (ex_x, ex_y) in grid:
            sec = grid[(ex_x, ex_y)]
            if not hasattr(sec, "objects") or sec.objects is None:
                sec.objects = []
            sec.objects.append({
                "type": "item",
                "name": "escape-pod",
                "title": "Escape Pod",
                "description": "A small escape pod interface. Use 'use escape-pod' to attempt launch."
            })

        # cleanup
        self.current_grid = None

        return Map(w, h, grid)

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
        if self.rng.random() < 0.3:
            env += self.rng.choice(variations)
        return env

    def _choose_templates_for_sector(self, sector_type):
        choices = []
        for t in self.templates:
            if not isinstance(t, dict) or t.get("kind") != "template":
                continue
            weights = t.get("spawn_weight", {})
            w = weights.get(sector_type, 0)
            try:
                w = float(w)
            except Exception:
                w = 0.0
            if w > 0:
                choices.append((t, w))
        return choices

    def _populate_objects(self, sector):
        choices = self._choose_templates_for_sector(sector.type)
        if not choices:
            return

        local_noise = self.rng.uniform(0.7, 1.3)
        # shuffle in-place using RNG
        self.rng.shuffle(choices)

        for tpl, weight in choices:
            try:
                p = self.base_density * float(weight) * local_noise
                p = max(0.0, min(0.9, p))
                if self.rng.random() < p:
                    if not self._can_place_in_sector(sector):
                        continue
                    obj = self._instantiate_from_template(tpl, sector)
                    if not hasattr(sector, "objects") or sector.objects is None:
                        sector.objects = []
                    sector.objects.append(obj)

                    if tpl.get("kind") == "template" and tpl.get("type") == "anomaly":
                        event_id = tpl.get("linger_event", tpl.get("id"))
                        if event_id:
                            th = tpl.get("linger_threshold", 2)
                            sector.linger_thresholds[th] = sector.linger_thresholds.get(th, []) + [event_id]
                            obj["_linger_threshold"] = th
                            obj["_linger_event"] = event_id
            except Exception as e:
                print(f"[mapgen] error instantiating template {tpl.get('id','?')}: {e}", file=sys.stderr)
                continue

    def _instantiate_from_template(self, tpl, sector):
        obj = dict(tpl) if isinstance(tpl, dict) else {"name": str(tpl)}
        obj.pop("spawn_weight", None)
        obj.pop("kind", None)

        if "name" in obj and isinstance(obj["name"], str):
            obj["name"] = obj["name"].lower()

        if obj.get("type") == "log":
            selected_log = None
            log_ids = tpl.get("log_pool")
            if log_ids and isinstance(log_ids, list):
                for lid in log_ids:
                    for l in self.log_pool:
                        if l.get("id") == lid:
                            selected_log = l
                            break
                    if selected_log:
                        break

            if selected_log is None and self.log_pool:
                selected_log = self.rng.choice(self.log_pool)

            if selected_log:
                template_str = obj.get("content_template", "{text}")
                content = template_str.format(
                    text=selected_log.get("text", ""),
                    title=selected_log.get("title", ""),
                )
                obj["content"] = content
                if not obj.get("title"):
                    obj["title"] = selected_log.get("title", obj.get("name", "log"))
                obj["fragmented"] = self.rng.random() < obj.get("fragmented_chance", 0.3)
            else:
                obj["content"] = obj.get("content_template", "{text}").format(text="An unreadable log entry.")
                obj["fragmented"] = False

        return obj

    def _can_place_in_sector(self, sector):
        if getattr(sector, "objects", None):
            if len(sector.objects) >= 2:
                return False

        sx, sy = sector.x, sector.y
        grid = getattr(self, "current_grid", None)
        if not grid:
            return True

        for dx in range(-self.min_distance, self.min_distance + 1):
            for dy in range(-self.min_distance, self.min_distance + 1):
                if abs(dx) + abs(dy) > self.min_distance:
                    continue
                nx, ny = sx + dx, sy + dy
                if (nx, ny) == (sx, sy):
                    continue
                neighbor = grid.get((nx, ny))
                if neighbor and getattr(neighbor, "objects", None):
                    if self.rng.random() < 0.8:
                        return False
        return True
