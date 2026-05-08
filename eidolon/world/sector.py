# eidolon/world/sector.py
class Sector:
    def __init__(self, x, y, name, type_, description):
        self.x = x
        self.y = y
        self.name = name
        self.type = type_
        self.description = description
        self.objects = []
        self.environment = {}
        self.scanned = False
