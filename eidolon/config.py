# eidolon/config.py

SEED = None  # set to int for reproducible runs
MIN_MAP_WIDTH = 10
MIN_MAP_HEIGHT = 5
DEFAULT_THEME = "dark"  # available: "dark", "retro", "high_contrast"
# eidolon/config.py additions
HEALTH_YELLOW_THRESHOLD = 0.5
HEALTH_RED_THRESHOLD = 0.25
# nové volitelné výchozí hodnoty pro generátor
DEFAULT_BASE_DENSITY = 0.05   # doporučené rozmezí 0.03..0.12
DEFAULT_MIN_DISTANCE = 3      # doporučené rozmezí 2..6
GAME_VERSION = "0.9.5"

# sector type weights for map generation (normalized to sum to 1.0)
SECTOR_TYPE_WEIGHTS = {
    "BRIDGE": 0.02,
    "ENGINEERING": 0.03,
    "CREW": 0.02,
    "MEDBAY": 0.03,
    "CARGO": 0.02,
    "AIRLOCK": 0.01,
    "EMPTY": 0.87
}
