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

    def generate(self):
        grid = {}
        # create empty grid with default sectors
        for y in range(self.height):
            for x in range(self.width):
                s = Sector(x, y, f"EMPTY-{x}-{y}", "EMPTY", "A narrow corridor. The lights are dim.")
                # ensure objects list and linger fields exist
                if not hasattr(s, "objects") or s.objects is None:
                    s.objects = []
                s.linger_counter = getattr(s, "linger_counter", 0)
                s.linger_thresholds = getattr(s, "linger_thresholds", {}) or {}
                grid[(x, y)] = s

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
        try:
            grid[(self.width - 1, self.height // 2)].type = "AIRLOCK"
            grid[(self.width - 1, self.height // 2)].name = "Outer Airlock"
        except Exception:
            pass
        try:
            grid[(0, self.height - 1)].type = "AIRLOCK"
            grid[(0, self.height - 1)].name = "Rear Airlock"
        except Exception:
            pass

        # ensure command module
        bridge_pos = (0, 0)
        if bridge_pos in grid:
            grid[bridge_pos].type = "BRIDGE"
            grid[bridge_pos].name = "Command Module"

        # apply descriptions from templates if present
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
            # populate objects using templates
            try:
                self._populate_objects(sector)
            except Exception as e:
                # nevyhazovat chybu generátoru kvůli jednomu sektoru
                print(f"[mapgen] populate error at {x},{y}: {e}", file=sys.stderr)

        # place escape pod near bridge (safe)
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
