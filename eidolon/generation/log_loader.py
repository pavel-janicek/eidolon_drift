# eidolon/generation/log_loader.py
import json
from pathlib import Path
import sys

def load_logs():
    # hledáme project_root/data/logs/logs.json, fallback do package-local
    p1 = Path(__file__).resolve().parents[2] / "data" / "logs" / "logs.json"
    p2 = Path(__file__).resolve().parents[1] / "data" / "logs" / "logs.json"
    for p in (p1, p2):
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    arr = json.load(f)
                return arr
            except Exception as e:
                print(f"[log_loader] error loading {p}: {e}", file=sys.stderr)
                return []
    print(f"[log_loader] no logs.json found in candidates: {[str(p1), str(p2)]}", file=sys.stderr)
    return []
    