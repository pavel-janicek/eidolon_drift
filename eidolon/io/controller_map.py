import json
import os
import logging
from eidolon.config import LOG_LEVEL

logger = logging.getLogger(__name__)
logging.basicConfig(filename='eidolon.log', encoding='utf-8', level=LOG_LEVEL)

CONTROLLERS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "controllers")

def _load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load controller map: %s", path)
        return None

def find_controller_map_by_name(joy_name: str):
    """
    Najde nejvhodnější mapu podle jména joysticku.
    - Projde všechny json soubory v CONTROLLERS_DIR.
    - Porovná aliases a name (case-insensitive substring).
    - Vrátí dict nebo None.
    """
    if not joy_name:
        return None
    joy_name_l = joy_name.lower()
    for fname in os.listdir(CONTROLLERS_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CONTROLLERS_DIR, fname)
        data = _load_json_file(path)
        if not data:
            continue
        name = (data.get("name") or "").lower()
        aliases = [a.lower() for a in data.get("aliases", [])]
        if name and name in joy_name_l:
            return data
        for a in aliases:
            if a and a in joy_name_l:
                return data
    return None

def merge_with_defaults(map_data: dict, default_data: dict):
    """
    Jednoduchý merge: pokud chybí klíč v map_data, vezmi z default_data.
    Vrací nový dict.
    """
    out = dict(default_data or {})
    if not map_data:
        return out
    # shallow merge for top-level keys
    for k, v in map_data.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out.get(k))
            merged.update(v)
            out[k] = merged
        else:
            out[k] = v
    return out
