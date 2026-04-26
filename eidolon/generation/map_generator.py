# eidolon/generation/map_generator.py
import random
import json
import sys
from pathlib import Path
from eidolon.world.map import Map
from eidolon.world.sector import Sector
from eidolon.config import MIN_MAP_WIDTH, MIN_MAP_HEIGHT
from eidolon.generation.log_loader import load_logs

SECTOR_TYPES = ["BRIDGE", "ENGINEERING", "CREW", "MEDBAY", "CARGO", "AIRLOCK", "EMPTY"]


def _find_data_dir():
    """
    Pokusí se najít adresář data/objects v několika běžných umístěních:
    - relativně k tomuto modulu (parents 1..4)
    - aktuální pracovní adresář
    Vrací Path k adresáři (ne k souboru), nebo None pokud nenalezen.
    """
    here = Path(__file__).resolve()
    for up in range(1, 5):
        candidate = here.parents[up] / "data" / "objects"
        if candidate.exists() and candidate.is_dir():
            return candidate
    # fallback: cwd/data/objects
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
    Generátor mapy. width/height jsou volitelné; pokud nejsou předány,
    použijí se minimální rozměry z configu (MIN_MAP_WIDTH / MIN_MAP_HEIGHT).
    seed je volitelný; pokud je None, náhodí se standardní random.
    """
    def __init__(self, width=None, height=None, seed=None):
        # pokud nejsou předány, použij minimální rozměry
        self.width = int(width) if width is not None else int(MIN_MAP_WIDTH)
        self.height = int(height) if height is not None else int(MIN_MAP_HEIGHT)
        if self.width < MIN_MAP_WIDTH:
            self.width = MIN_MAP_WIDTH
        if self.height < MIN_MAP_HEIGHT:
            self.height = MIN_MAP_HEIGHT

        if seed is not None:
            random.seed(seed)

        # najdi data dir robustně
        self.data_dir = _find_data_dir()
        self.templates, self.template_index = _load_templates(self.data_dir)
        self.log_pool = load_logs()

        # informativní výpis (stderr)
        data_path = (self.data_dir / "objects.json") if self.data_dir else Path("data/objects/objects.json")
        print(f"[mapgen] loaded {len(self.templates)} templates from {data_path}", file=sys.stderr)

    def generate(self, width=None, height=None):
        """
        Generate map. If width/height provided, use them (they represent tile counts).
        Otherwise fall back to self.width/self.height (which were set in __init__).
        """
        # prefer explicit args
        w = int(width) if width is not None else int(self.width)
        h = int(height) if height is not None else int(self.height)

        # ensure minima
        if w < MIN_MAP_WIDTH:
            w = MIN_MAP_WIDTH
        if h < MIN_MAP_HEIGHT:
            h = MIN_MAP_HEIGHT

        grid = {}
        # create empty grid
        for y in range(h):
            for x in range(w):
                grid[(x, y)] = Sector(x, y, f"EMPTY-{x}-{y}", "EMPTY", "A narrow corridor. The lights are dim.")
                # initialize linger fields
                grid[(x, y)].linger_counter = 0
                grid[(x, y)].linger_thresholds = {}
                if not hasattr(grid[(x, y)], "objects") or grid[(x, y)].objects is None:
                    grid[(x, y)].objects = []

        # rest of generation logic must use w,h instead of self.width/self.height
        # Bridge region top-left
        for yy in range(0, max(2, h // 4)):
            for xx in range(0, max(3, w // 4)):
                stype = "BRIDGE" if (xx == 0 and yy == 0) else "CREW"
                grid[(xx, yy)].type = stype
                grid[(xx, yy)].name = f"{stype}-{xx}-{yy}"

        # engineering band
        mid_y = h // 2
        for xx in range(w // 4, 3 * w // 4):
            grid[(xx, mid_y)].type = "ENGINEERING"
            grid[(xx, mid_y)].name = f"ENGINEERING-{xx}-{mid_y}"

        # cargo aft
        for yy in range(h - max(3, h // 4), h):
            for xx in range(w - max(4, w // 4), w):
                grid[(xx, yy)].type = "CARGO"
                grid[(xx, yy)].name = f"CARGO-{xx}-{yy}"

        # airlocks (guarded)
        try:
            grid[(w - 1, h // 2)].type = "AIRLOCK"
            grid[(w - 1, h // 2)].name = "Outer Airlock"
        except Exception:
            pass
        try:
            grid[(0, h - 1)].type = "AIRLOCK"
            grid[(0, h - 1)].name = "Rear Airlock"
        except Exception:
            pass

        # ensure command module
        bridge_pos = (0, 0)
        if bridge_pos in grid:
            grid[bridge_pos].type = "BRIDGE"
            grid[bridge_pos].name = "Command Module"

        # apply descriptions and populate objects (use same code but iterate over grid items)
        desc_map = {}
        try:
            desc_map = {t["sector_type"]: t["text"] for t in self.templates if isinstance(t, dict) and t.get("kind") == "description"}
        except Exception:
            desc_map = {}

        for (x, y), sector in grid.items():
            sector.description = desc_map.get(sector.type, getattr(sector, "description", ""))
            sector.environment = self._random_environment(sector.type)
            # ensure objects list exists
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
        if random.random() < 0.3:
            env += random.choice(variations)
        return env

    def _choose_templates_for_sector(self, sector_type):
        # return list of templates with spawn_weight for this sector_type
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
            # treat weight as probability cap at 1.0
            w = max(0.0, min(1.0, w))
            if w > 0:
                choices.append((t, w))
        return choices

    def _populate_objects(self, sector):
        choices = self._choose_templates_for_sector(sector.type)
        for tpl, weight in choices:
            try:
                if random.random() < weight:
                    obj = self._instantiate_from_template(tpl, sector)
                    if not hasattr(sector, "objects") or sector.objects is None:
                        sector.objects = []
                    sector.objects.append(obj)
                    # linger behavior
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
                selected_log = random.choice(self.log_pool)

            if selected_log:
                template_str = obj.get("content_template", "{text}")
                content = template_str.format(
                    text=selected_log.get("text", ""),
                    title=selected_log.get("title", ""),
                )
                obj["content"] = content
                if not obj.get("title"):
                    obj["title"] = selected_log.get("title", obj.get("name", "log"))
                obj["fragmented"] = random.random() < obj.get("fragmented_chance", 0.3)
            else:
                obj["content"] = obj.get("content_template", "{text}").format(text="An unreadable log entry.")
                obj["fragmented"] = False

        return obj
