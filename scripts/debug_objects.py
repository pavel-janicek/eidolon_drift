# 1) Základní info o generátoru a šablonách
from eidolon.generation.map_generator import MapGenerator

g = MapGenerator(seed=12345)
print("templates:", len(g.templates))
print("template_index keys sample:", list(g.template_index.keys())[:30])
print("log_pool size:", len(g.log_pool))
print("base_density:", g.base_density, "min_distance:", g.min_distance)

# 2) Vygeneruj mapu a vypiš sektory s objekty
m = g.generate()
count = 0
for (x, y), s in sorted(m.grid.items()):
    objs = getattr(s, "objects", []) or []
    if objs:
        print(f"{x},{y} {s.type} objects={len(objs)} sample={objs[:2]}")
        count += 1
print("sectors with objects:", count)
