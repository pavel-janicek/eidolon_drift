#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

SRC = Path("eidolon/data/objects/objects.json")
OUT = Path("eidolon/data")
if not SRC.exists():
    print("eidolon/data/objects/objects.json not found")
    raise SystemExit(1)

with SRC.open("r", encoding="utf-8") as fh:
    all_items = json.load(fh)

groups = defaultdict(list)
for obj in all_items:
    kind = obj.get("kind", "template")
    groups[kind].append(obj)

# write descriptions
if groups.get("description"):
    with (OUT / "descriptions.json").open("w", encoding="utf-8") as fh:
        json.dump(groups["description"], fh, ensure_ascii=False, indent=2)

# templates -> items.json (you can split further by obj['type'] if desired)
templates = groups.get("template", [])
with (OUT / "items.json").open("w", encoding="utf-8") as fh:
    json.dump(templates, fh, ensure_ascii=False, indent=2)

# environment
if groups.get("environment"):
    with (OUT / "environment.json").open("w", encoding="utf-8") as fh:
        json.dump(groups["environment"], fh, ensure_ascii=False, indent=2)

# config
if groups.get("config"):
    with (OUT / "config.json").open("w", encoding="utf-8") as fh:
        json.dump(groups["config"], fh, ensure_ascii=False, indent=2)

print("Migration done. Created files:", ", ".join([f.name for f in OUT.glob("*.json") if f.name in ("descriptions.json","items.json","environment.json","config.json")]))
