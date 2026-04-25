# object_loader.py
import json
import glob
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "objects"

def load_object_templates():
    templates = []
    for path in glob.glob(str(DATA_DIR / "*.json")):
        with open(path, "r", encoding="utf-8") as f:
            templates.extend(json.load(f))
    # index by id for convenience
    by_id = {t["id"]: t for t in templates}
    return templates, by_id
