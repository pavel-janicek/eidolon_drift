# eidolon/mechanics/event_loader.py
import json
from pathlib import Path
import sys

def _candidate_paths():
    # 1) project_root/data/events/events.json
    p1 = Path(__file__).resolve().parents[2] / "data" / "events" / "events.json"
    # 2) package-local eidolon/data/events/events.json (fallback)
    p2 = Path(__file__).resolve().parents[1] / "data" / "events" / "events.json"
    return [p1, p2]

def load_event_defs():
    paths = _candidate_paths()
    for p in paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    arr = json.load(f)
                # index by id
                return {e.get("id"): e for e in arr}
            except json.JSONDecodeError as e:
                print(f"[event_loader] JSON parse error in {p}: {e}", file=sys.stderr)
                return {}
            except Exception as e:
                print(f"[event_loader] Error loading {p}: {e}", file=sys.stderr)
                return {}
    # nothing found
    print(f"[event_loader] no events.json found in candidates: {[str(x) for x in paths]}", file=sys.stderr)
    return {}
