# eidolon/mechanics/event_loader.py
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "events"

def load_event_defs():
    p = DATA_DIR / "events.json"
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        arr = json.load(f)
    return {e.get("id"): e for e in arr}
