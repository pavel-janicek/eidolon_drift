#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eidolon.generation.map_generator import MapGenerator, _find_data_dir
from collections import Counter, defaultdict

def count_photos_in_map(gen, seed=None):
    mg = MapGenerator(seed=seed)
    m = mg.generate()
    counts = Counter()
    positions = defaultdict(list)
    for (x,y), sec in m.grid.items():
        for obj in getattr(sec, "objects", []) or []:
            if not isinstance(obj, dict):
                continue
            oid = obj.get("id") or obj.get("name")
            if oid in ("item_photo", "item_photo_cursed") or obj.get("name") == "crew-photo":
                counts[oid] += 1
                positions[oid].append((x,y))
    return counts, positions

def run_trials(trials=100, seed_base=None):
    total = Counter()
    pos_samples = defaultdict(list)
    for i in range(trials):
        seed = (seed_base + i) if seed_base is not None else None
        counts, positions = count_photos_in_map(MapGenerator, seed=seed)
        total.update(counts)
        for k, v in positions.items():
            if v:
                pos_samples[k].extend(v[:5])  # keep a few samples
    return total, pos_samples

if __name__ == "__main__":
    TRIALS = 200
    # pokud chceš reprodukovat, nastav seed_base na číslo, např. 12345
    seed_base = None
    total, samples = run_trials(TRIALS, seed_base=seed_base)
    print(f"Ran {TRIALS} maps")
    print("Totals:", dict(total))
    for k, v in samples.items():
        print(f"Sample positions for {k}: {v[:10]}")
