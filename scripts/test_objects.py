# scripts/test_objects.py
import sys
from pathlib import Path
# přidej root do sys.path pokud spouštíš z scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eidolon.generation.map_generator import _load_templates, _find_data_dir

data_dir = _find_data_dir()
print("Using data_dir:", data_dir)
templates, by_id, config = _load_templates(data_dir)
print("templates:", len(templates))
print("item_photo in by_id:", "item_photo" in by_id)
if "item_photo" in by_id:
    import json
    print(json.dumps(by_id["item_photo"], indent=2, ensure_ascii=False))
else:
    found = [t for t in templates if t.get("name")=="crew-photo" or t.get("id")=="item_photo"]
    print("found by name count:", len(found))
    for f in found:
        print(f.get("id"), f.get("type"), f.get("spawn_weight"))
