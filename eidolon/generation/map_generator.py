# eidolon/generation/map_generator.py
import random
from eidolon.world.map import Map
from eidolon.world.sector import Sector
from eidolon.config import DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT, SEED

SECTOR_TYPES = ["BRIDGE", "ENGINEERING", "CREW", "MEDBAY", "CARGO", "AIRLOCK", "EMPTY"]

class MapGenerator:
    def __init__(self, width=DEFAULT_MAP_WIDTH, height=DEFAULT_MAP_HEIGHT, seed=SEED):
        self.width = width
        self.height = height
        if seed is not None:
            random.seed(seed)

    def generate(self):
        grid = {}
        for y in range(self.height):
            for x in range(self.width):
                t = random.choices(SECTOR_TYPES, weights=[1,1,2,1,2,1,5])[0]
                name = f"{t}-{x}-{y}"
                desc = self._make_description(t)
                sector = Sector(x, y, name, t, desc)
                sector.environment = self._random_environment(t)
                # populate objects (items, logs, encrypted fragments) with probabilities
                self._populate_objects(sector, t)
                grid[(x, y)] = sector

        # place bridge near top-left, airlock near edge
        if (0, 0) in grid:
            grid[(0,0)].type = "BRIDGE"
            grid[(0,0)].name = "Bridge"
            grid[(0,0)].description = self._make_description("BRIDGE")
        if (self.width-1, self.height-1) in grid:
            grid[(self.width-1, self.height-1)].type = "AIRLOCK"
            grid[(self.width-1, self.height-1)].name = "Outer Airlock"
            grid[(self.width-1, self.height-1)].description = self._make_description("AIRLOCK")

        return Map(self.width, self.height, grid)

    def _make_description(self, t):
        templates = {
            "BRIDGE": "The bridge is dark. Consoles flicker with corrupted telemetry.",
            "ENGINEERING": "Sparks and the smell of ozone. A coolant leak has frozen some panels.",
            "CREW": "Personal lockers are open. A jacket lies on the floor.",
            "MEDBAY": "Medical trays overturned. A faint stain on the floor.",
            "CARGO": "Crates are scattered. Some containers are sealed with hazard tape.",
            "AIRLOCK": "The airlock cycles are offline. The outer hatch is ajar.",
            "EMPTY": "A narrow corridor. The lights are dim.",
        }
        return templates.get(t, "An unremarkable section of the ship.")

    def _random_environment(self, sector_type):
        env = {}
        # small variety of environmental readings to show in scan
        if sector_type == "ENGINEERING":
            env["power"] = random.choice(["unstable", "low", "nominal"])
            env["smoke"] = random.choice(["none", "light", "heavy"])
        elif sector_type == "MEDBAY":
            env["biohazard"] = random.choice(["none", "trace", "present"])
            env["temperature"] = f"{random.randint(18,28)}C"
        elif sector_type == "AIRLOCK":
            env["pressure"] = random.choice(["depressurized", "low", "nominal"])
            env["hatch"] = random.choice(["ajar", "sealed", "damaged"])
        else:
            # generic corridor / crew / cargo
            if random.random() < 0.15:
                env["anomaly"] = "faint electromagnetic interference"
            if random.random() < 0.08:
                env["lights"] = "flickering"
        return env

    def _populate_objects(self, sector, sector_type):
        # helper factories
        def make_item(name, title, description):
            return {
                "type": "item",
                "name": name.lower(),
                "title": title,
                "description": description
            }

        def make_log(x, y, idx, fragmented=False):
            content = (
                "Log entry: We lost contact with the relay. Strange readings on the sensors. "
                "Crew morale is low. Something moved in the hydroponics last night."
            )
            # vary content slightly
            if random.random() < 0.4:
                content += " Last transmission corrupted; repeating fragments only."
            return {
                "type": "log",
                "name": f"log-{x}-{y}-{idx}",
                "title": f"Crew Log {x}-{y}-{idx}",
                "description": "A personal log terminal. Use 'inspect' to read.",
                "content": content,
                "fragmented": fragmented
            }

        def make_enc(x, y, idx, difficulty=1):
            payload = "Encrypted payload: <binary data fragment>. Requires decryption."
            return {
                "type": "enc",
                "name": f"enc-{x}-{y}-{idx}",
                "title": f"Encrypted Fragment {x}-{y}-{idx}",
                "description": "An encrypted data shard. Try 'decrypt <name>'.",
                "payload": payload,
                "difficulty": difficulty
            }

        x, y = sector.x, sector.y

        # chance to add plain flavor string (older code used plain strings)
        if random.random() < 0.06:
            sector.objects.append("a loose wrench")
        # crew sectors more likely to have personal items
        if sector_type == "CREW":
            if random.random() < 0.45:
                sector.objects.append(make_item("jacket", "Crew Jacket", "A worn crew jacket. The patch reads 'EIDOLON'."))
            if random.random() < 0.25:
                sector.objects.append(make_item("locker", "Personal Locker", "A locker with scattered personal effects."))
        # engineering: tools, logs, encrypted fragments
        if sector_type == "ENGINEERING":
            if random.random() < 0.35:
                sector.objects.append(make_item("toolkit", "Tool Kit", "A compact engineering toolkit."))
            if random.random() < 0.18:
                sector.objects.append(make_log(x, y, 1, fragmented=random.random() < 0.5))
            if random.random() < 0.10:
                sector.objects.append(make_enc(x, y, 1, difficulty=random.randint(1,3)))
        # medbay: medical logs, bio traces
        if sector_type == "MEDBAY":
            if random.random() < 0.28:
                sector.objects.append(make_log(x, y, 1, fragmented=random.random() < 0.3))
            if random.random() < 0.12:
                sector.objects.append(make_item("medkit", "Medkit", "A small medkit with limited supplies."))
        # cargo: crates, sealed containers, occasional encrypted manifest
        if sector_type == "CARGO":
            if random.random() < 0.4:
                sector.objects.append(make_item("crate", "Cargo Crate", "A sealed cargo crate with hazard tape."))
            if random.random() < 0.08:
                sector.objects.append(make_enc(x, y, 1, difficulty=2))
        # airlock: suit, log
        if sector_type == "AIRLOCK":
            if random.random() < 0.3:
                sector.objects.append(make_item("helmet", "EVA Helmet", "A scratched EVA helmet. The visor is cracked."))
            if random.random() < 0.15:
                sector.objects.append(make_log(x, y, 1, fragmented=False))
        # bridge: important logs and encrypted fragments
        if sector_type == "BRIDGE":
            if random.random() < 0.6:
                sector.objects.append(make_log(x, y, 1, fragmented=random.random() < 0.2))
            if random.random() < 0.25:
                sector.objects.append(make_enc(x, y, 1, difficulty=2))

        # small chance to add an "anomaly" object (for flavor / horror hints)
        if random.random() < 0.05:
            sector.objects.append({
                "type": "anomaly",
                "name": f"anomaly-{x}-{y}",
                "title": "Unidentified Anomaly",
                "description": "A faint, pulsing residue on the floor. Sensors cannot classify it."
            })
