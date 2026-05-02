# eidolon/mechanics/movement.py
def move_player(ship_map, player, direction):
    dx, dy = 0, 0
    if direction == "UP":
        dy = -1
    elif direction == "DOWN":
        dy = 1
    elif direction == "LEFT":
        dx = -1
    elif direction == "RIGHT":
        dx = 1
    else:
        return False
    nx = player.x + dx
    ny = player.y + dy
    if 0 <= nx < ship_map.width and 0 <= ny < ship_map.height:
        player.x = nx
        player.y = ny
        return True
    return False
