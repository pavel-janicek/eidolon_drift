# eidolon/config.py

SEED = None  # set to int for reproducible runs
MIN_MAP_WIDTH = 10
MIN_MAP_HEIGHT = 5
DEFAULT_THEME = "dark"  # available: "dark", "retro", "high_contrast"
# eidolon/config.py additions
HEALTH_YELLOW_THRESHOLD = 0.5
HEALTH_RED_THRESHOLD = 0.25
# nové volitelné výchozí hodnoty pro generátor
DEFAULT_BASE_DENSITY = 0.1   # doporučené rozmezí 0.03..0.12
DEFAULT_MIN_DISTANCE = 3      # doporučené rozmezí 2..6
GAME_VERSION = "0.8.0"