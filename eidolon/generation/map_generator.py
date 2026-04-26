# eidolon/generation/map_generator.py
import random
import json
import sys
from pathlib import Path
from eidolon.world.map import Map
from eidolon.world.sector import Sector
from eidolon.config import MIN_MAP_WIDTH, MIN_MAP_HEIGHT, SEED, DEFAULT_BASE_DENSITY, DEFAULT_MIN_DISTANCE
from eidolon.generation.log_loader import load_logs

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
    config = {}
    if not data_dir:
        return templates, by_id, config
    p = data_dir / "objects.json"
    if not p.exists():
        return templates, by_id, config
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                if isinstance(item, dict):
                    kind = item.get("kind")
                    if kind == "config":
                        config.update(item)
                    elif kind in ("template", "description"):
                        templates.append(item)
                        if "id" in item:
                            by_id[item["id"]] = item
    except Exception as e:
        print(f"[mapgen] failed to load templates: {e}", file=sys.stderr)
        return [], {}, {}
    return templates, by_id, config


class MapGenerator:
    """
    Robustní generátor mapy.
    - width/height volitelné; pokud nejsou předány, použijí se MIN_MAP_*.
    - používá vlastní RNG instance (seed=None => náhodný).
    - base_density a min_distance laditelné.
    """
    def __init__(self, width=None, height=None, seed=None, base_density=None, min_distance=None):
        self.width = int(width) if width is not None else int(MIN_MAP_WIDTH)
        self.height = int(height) if height is not None else int(MIN_MAP_HEIGHT)
        if self.width < MIN_MAP_WIDTH:
            self.width = MIN_MAP_WIDTH
        if self.height < MIN_MAP_HEIGHT:
            self.height = MIN_MAP_HEIGHT

        # determine seed: explicit > config.SEED > system entropy
        use_seed = seed if seed is not None else SEED
        if use_seed is None:
            # system entropy seed for true randomness
            sys_seed = random.SystemRandom().randint(0, 2**30)
            self.rng = random.Random(sys_seed)
            print(f"[mapgen][debug] using system-random seed={sys_seed}", file=sys.stderr)
        else:
            self.rng = random.Random(int(use_seed))
            print(f"[mapgen][debug] using seed={int(use_seed)}", file=sys.stderr)

        self.base_density = float(base_density) if base_density is not None else float(DEFAULT_BASE_DENSITY)
        self.min_distance = int(min_distance) if min_distance is not None else int(DEFAULT_MIN_DISTANCE)

        self.data_dir = _find_data_dir()
        self.templates, self.template_index, self.config = _load_templates(self.data_dir)
        self.log_pool = load_logs()
        data_path = (self.data_dir / "objects.json") if self.data_dir else Path("data/objects/objects.json")
        print(f"[mapgen][debug] loaded {len(self.templates)} templates from {data_path}", file=sys.stderr)
        print(f"[mapgen][debug] loaded {len(self.log_pool)} logs from logs.json", file=sys.stderr)

        self.sector_types = self.config.get("sector_types", ["BRIDGE", "ENGINEERING", "CREW", "MEDBAY", "CARGO", "AIRLOCK", "EMPTY"])

    # --- helper methods for region placement ---------------------------------
    def _rects_overlap(self, a, b, gap=0):
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        return not (ax1 + gap < bx0 or bx1 + gap < ax0 or ay1 + gap < by0 or by1 + gap < ay0)

    def _place_region(self, map_w, map_h, width, height, prefer_area=None, existing=None, attempts=80, min_gap=None):
        """
        Try to place a rectangle (width x height) somewhere on the map so it doesn't
        overlap existing rectangles (with min_gap). prefer_area is (x0,y0,x1,y1) to bias placement.
        Returns (x0,y0,x1,y1) or None.
        """
        if min_gap is None:
            min_gap = max(1, getattr(self, "min_distance", 3))
        existing = existing or []

        for _ in range(attempts):
            if prefer_area:
                px0, py0, px1, py1 = prefer_area
                # clamp prefer_area to map bounds
                px0 = max(0, px0)
                py0 = max(0, py0)
                px1 = min(map_w - 1, px1)
                py1 = min(map_h - 1, py1)
                if px1 - px0 + 1 < width or py1 - py0 + 1 < height:
                    # fallback to full map
                    rx = self.rng.randint(0, max(0, map_w - width))
                    ry = self.rng.randint(0, max(0, map_h - height))
                else:
                    rx = self.rng.randint(px0, max(px0, min(px1 - width + 1, map_w - width)))
                    ry = self.rng.randint(py0, max(py0, min(py1 - height + 1, map_h - height)))
            else:
                rx = self.rng.randint(0, max(0, map_w - width))
                ry = self.rng.randint(0, max(0, map_h - height))
            rect = (rx, ry, rx + width - 1, ry + height - 1)
            ok = True
            for ex in existing:
                if self._rects_overlap(rect, ex, gap=min_gap):
                    ok = False
                    break
            if ok:
                return rect
        return None

    def _fill_region(self, grid, x0, y0, x1, y1, stype, name_prefix=None, density=0.6):
        """
        Fill a rectangular region with given density (0..1). Uses self.rng.
        """
        for yy in range(max(0, y0), min(self.height, y1 + 1)):
            for xx in range(max(0, x0), min(self.width, x1 + 1)):
                if self.rng.random() <= density:
                    sector = grid[(xx, yy)]
                    sector.type = stype
                    sector.name = f"{(name_prefix or stype)}-{xx}-{yy}"

    # --- main generation -----------------------------------------------------
    def generate(self, width=None, height=None):
        w = int(width) if width is not None else int(self.width)
        h = int(height) if height is not None else int(self.height)

        if w < MIN_MAP_WIDTH:
            w = MIN_MAP_WIDTH
        if h < MIN_MAP_HEIGHT:
            h = MIN_MAP_HEIGHT

        # ensure self.width/self.height reflect actual generation size for helpers
        self.width = w
        self.height = h

        grid = {}
        for y in range(h):
            for x in range(w):
                s = Sector(x, y, f"EMPTY-{x}-{y}", "EMPTY", "A narrow corridor. The lights are dim.")
                s.linger_counter = getattr(s, "linger_counter", 0)
                s.linger_thresholds = getattr(s, "linger_thresholds", {}) or {}
                if not hasattr(s, "objects") or s.objects is None:
                    s.objects = []
                grid[(x, y)] = s

        # randomly assign sector types across the map
        # weights are normalized to sum to 1.0
        sector_type_weights = {
            "BRIDGE": 0.02,
            "ENGINEERING": 0.03,
            "CREW": 0.05,
            "MEDBAY": 0.03,
            "CARGO": 0.02,
            "AIRLOCK": 0.01,
            "EMPTY": 0.84
        }
        
        bridge_placed = False
        for y in range(h):
            for x in range(w):
                sector = grid[(x, y)]
                rand = self.rng.random()
                cumulative = 0.0
                
                # randomly select a sector type based on weights
                for stype, weight in sector_type_weights.items():
                    cumulative += weight
                    if rand < cumulative:
                        sector.type = stype
                        sector.name = f"{stype}-{x}-{y}"
                        if stype == "BRIDGE":
                            bridge_placed = True
                        break

        # fallback: ensure at least one bridge tile exists
        if not bridge_placed:
            bridge_x = self.rng.randint(0, w - 1)
            bridge_y = self.rng.randint(0, h - 1)
            grid[(bridge_x, bridge_y)].type = "BRIDGE"
            grid[(bridge_x, bridge_y)].name = "Command Module"

        # descriptions map
        desc_map = {}
        try:
            desc_map = {t["sector_type"]: t["text"] for t in self.templates if isinstance(t, dict) and t.get("kind") == "description"}
        except Exception:
            desc_map = {}

        # make grid available for placement checks
        self.current_grid = grid

        # populate sectors in random order to avoid bias
        keys = list(grid.keys())
        self.rng.shuffle(keys)
        for (x, y) in keys:
            sector = grid[(x, y)]
            sector.description = desc_map.get(sector.type, getattr(sector, "description", ""))
            sector.environment = self._random_environment(sector.type)
            if not hasattr(sector, "objects") or sector.objects is None:
                sector.objects = []
            try:
                self._populate_objects(sector)
            except Exception as e:
                print(f"[mapgen] populate error at {x},{y}: {e}", file=sys.stderr)

        # place escape pod near a bridge sector
        ex_x, ex_y = None, None
        # find all bridge sectors
        bridge_sectors = [(x, y) for (x, y) in grid if grid[(x, y)].type == "BRIDGE"]
        if bridge_sectors:
            # pick a random bridge sector
            bridge_x, bridge_y = self.rng.choice(bridge_sectors)
            # try to find an adjacent empty or crew tile for escape pod
            candidates = [
                (bridge_x + 1, bridge_y),
                (bridge_x - 1, bridge_y),
                (bridge_x, bridge_y + 1),
                (bridge_x, bridge_y - 1),
            ]
            for cx, cy in candidates:
                if (cx, cy) in grid:
                    ex_x, ex_y = cx, cy
                    break
            # fallback to bridge sector itself if no adjacent tile
            if ex_x is None:
                ex_x, ex_y = bridge_x, bridge_y
        else:
            # this shouldn't happen due to fallback, but just in case
            ex_x, ex_y = 0, 0

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

        # debug summary of placed objects
        total = 0
        per_type = {}
        for sec in grid.values():
            n = len(getattr(sec, "objects", []) or [])
            total += n
            for o in getattr(sec, "objects", []) or []:
                t = o.get("type", "unknown") if isinstance(o, dict) else "unknown"
                per_type[t] = per_type.get(t, 0) + 1
        print(f"[mapgen][debug] placed total objects={total}, by_type={per_type}", file=sys.stderr)

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
                density_mod = 1.0
                try:
                    density_mod = float(tpl.get("density_modifier", 1.0))
                except Exception:
                    density_mod = 1.0

                p = self.base_density * float(weight) * density_mod * local_noise
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
