# eidolon/generation/log_loader.py
import json
from pathlib import Path
import sys


def load_logs():
    here = Path(__file__).resolve()
    for up in range(1, 5):
        candidate = here.parents[up] / "data" / "logs" / "logs.json"
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    arr = json.load(f)
                return arr
            except Exception as e:
                print(f"[log_loader] error loading {candidate}: {e}", file=sys.stderr)
                return []
    candidate = Path.cwd() / "data" / "logs" / "logs.json"
    if candidate.exists():
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                arr = json.load(f)
            return arr
        except Exception as e:
            print(f"[log_loader] error loading {candidate}: {e}", file=sys.stderr)
            return []
    print(f"[log_loader] no logs.json found", file=sys.stderr)
    return []
