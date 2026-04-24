# eidolon/world/player.py
class Player:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y
        self.inventory = []
        self.health = 100
        self.sanity = 100
