from enum import Enum, unique, auto

@unique
class GameState(Enum):  
    RUNNING = auto()
    INTERACT = auto()        # player is choosing Inspect/Use/Cancel
    SCANNING = auto()
    CONFIRM = auto()        # confirm dialog (yes/no)
    PAUSED = auto()
    ESCAPE = auto()
    QUIT = auto()
    DEATH = auto()
