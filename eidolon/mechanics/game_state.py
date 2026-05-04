from enum import Enum, unique

@unique
class GameState(Enum):
    RUNNING = 1
    INTERACT = 2        # player is choosing Inspect/Use/Cancel
    CONFIRM = 3         # confirm dialog (yes/no)
    PAUSED = 4
    ESCAPE = 5
    QUIT = 6
    DEATH = 7
