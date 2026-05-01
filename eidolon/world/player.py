class Player:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y
        self.inventory = []
        self.health = 100
        self.max_health = 100
        self.sanity = 100
        self.alive = True

    def heal(self, amount):
        self.health = min(self.max_health, self.health + amount)

    def take_damage(self, amount, source=None):
        self.health = max(0, self.health - amount)
        if self.health == 0:
            self.alive = False

    def lose_sanity(self, amount):
        self.sanity = max(0, self.sanity - amount)

    def gain_sanity(self, amount):
        self.sanity = min(100, self.sanity + amount)
