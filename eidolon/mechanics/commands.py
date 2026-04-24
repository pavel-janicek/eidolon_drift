# eidolon/mechanics/commands.py
"""
Simple command handlers for Eidolon Drift.
Each command receives the `game` object (Game instance) and the raw command string.
Handlers may modify game state and should return a short text result (string).
"""

import random

def handle_command(game, raw_cmd: str) -> str:
    cmd = raw_cmd.strip()
    if not cmd:
        return ""

    parts = cmd.split()
    verb = parts[0].lower()
    args = parts[1:]

    if verb in ("quit", "exit"):
        game.running = False
        return "Quitting session..."

    if verb in ("help", "?"):
        return _cmd_help()

    if verb == "scan":
        return _cmd_scan(game)

    if verb == "logs":
        return _cmd_logs(game)

    if verb == "inspect":
        if not args:
            return "Usage: inspect <object>"
        target = " ".join(args)
        return _cmd_inspect(game, target)

    if verb == "decrypt":
        if not args:
            return "Usage: decrypt <object>"
        target = " ".join(args)
        return _cmd_decrypt(game, target)

    if verb == "map":
        # renderer already shows minimap; return full map text snapshot
        return _cmd_map(game)

    if verb == "status":
        return _cmd_status(game)
    
    if verb == "inspect-all":
        sector = game.map.get_sector(game.player.x, game.player.y)
        if sector is None:
            return "No sector."
        # show raw objects for debugging
        return repr(sector.objects)


    return f"Unknown command: {verb}. Type 'help' for a list of commands."

def _cmd_help():
    lines = [
        "Available commands:",
        "  scan               - run diagnostics on current sector",
        "  logs               - list readable logs in this sector",
        "  inspect <object>   - inspect an object in the sector",
        "  decrypt <object>   - attempt to decrypt a data fragment",
        "  map                - show a textual snapshot of the ship map",
        "  status             - show your status (health, sanity, inventory)",
        "  help               - show this help",
        "  quit               - exit the session",
    ]
    return "\n".join(lines)

def _cmd_scan(game):
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return "Scan: no sector data."
    env = sector.environment or {}
    lines = []
    lines.append(f"Scan results for {sector.name}:")
    # environment keys
    if env:
        for k, v in env.items():
            lines.append(f"  {k}: {v}")
    else:
        lines.append("  No special environmental readings.")
    # objects summary
    if sector.objects:
        lines.append(f"  Objects detected: {len(sector.objects)}")
        # show types if objects are dicts or strings
        sample = []
        for o in sector.objects[:5]:
            if isinstance(o, dict):
                sample.append(o.get("name", "object"))
            else:
                sample.append(str(o))
        lines.append("  " + ", ".join(sample))
    else:
        lines.append("  No objects detected.")
    # random noise / hint
    if random.random() < 0.12:
        lines.append("  [ANOMALY] faint electromagnetic interference detected.")
    return "\n".join(lines)

def _cmd_logs(game):
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return "No logs here."
    logs = [o for o in sector.objects if isinstance(o, dict) and o.get("type") == "log"]
    if not logs:
        return "No readable logs in this sector."
    lines = ["Logs found:"]
    for i, l in enumerate(logs, 1):
        title = l.get("title", f"log-{i}")
        frag = l.get("fragmented", False)
        lines.append(f"  {i}. {title}" + (" (fragmented)" if frag else ""))
    lines.append("Use 'inspect <log name>' to read a log (e.g. inspect log-1).")
    return "\n".join(lines)

def _cmd_inspect(game, target):
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return "Nothing to inspect."

    target_l = target.strip().lower()
    # 1) exact match on dict name/title
    for o in sector.objects:
        if isinstance(o, dict):
            name = o.get("name", "").lower()
            title = o.get("title", "").lower()
            if target_l == name or target_l == title:
                return _describe_object(o)
    # 2) case-insensitive substring match on dict fields
    for o in sector.objects:
        if isinstance(o, dict):
            name = o.get("name", "").lower()
            title = o.get("title", "").lower()
            if target_l in name or target_l in title:
                return _describe_object(o)
    # 3) plain string objects: exact or substring
    for o in sector.objects:
        if isinstance(o, str):
            ol = o.lower()
            if target_l == ol or target_l in ol:
                return f"You inspect the {o}. It seems unremarkable."

    return f"No object named '{target}' found here."

def _describe_object(o: dict) -> str:
    # returns a human-friendly description for dict objects
    typ = o.get("type", "object")
    if typ == "log":
        content = o.get("content", "")
        if o.get("fragmented"):
            snippet = content[: min(120, len(content))]
            return f"{o.get('title','log')}: {snippet} ... (fragmented)"
        return f"{o.get('title','log')}: {content}"
    if typ == "enc":
        return o.get("description", "An encrypted data fragment. Try 'decrypt <name>'.")
    # generic object
    return o.get("description", o.get("title", o.get("name", "You see nothing special about it.")))


def _cmd_decrypt(game, target):
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return "Nothing to decrypt."
    # find encrypted fragments (type == 'enc')
    for o in sector.objects:
        if isinstance(o, dict) and o.get("type") == "enc":
            name = o.get("name", "").lower()
            if target.lower() == name or target.lower() == o.get("title","").lower():
                # simple decrypt mini-game: random chance + sanity cost
                difficulty = o.get("difficulty", 1)
                roll = random.random()
                success_chance = max(0.15, 0.8 - 0.15 * difficulty)
                if roll < success_chance:
                    # reveal content as a new log object
                    revealed = {
                        "type": "log",
                        "name": f"log-{random.randint(1000,9999)}",
                        "title": o.get("title", "Recovered Log"),
                        "description": "Recovered data fragment.",
                        "content": o.get("payload", "Fragment content."),
                        "fragmented": False
                    }
                    sector.objects.append(revealed)
                    sector.objects.remove(o)
                    return f"Decryption successful. Revealed log: {revealed['title']}"
                else:
                    # failure: small sanity/health penalty
                    game.player.sanity = max(0, game.player.sanity - 5)
                    return "Decryption failed. Neural feedback caused minor disorientation."
    return f"No encrypted object named '{target}' found here."

def _cmd_map(game):
    # produce a textual snapshot of the map
    lines = []
    m = game.map
    for y in range(m.height):
        row = ""
        for x in range(m.width):
            if game.player.x == x and game.player.y == y:
                row += "@"
            else:
                row += m.get_tile_char(x, y)
        lines.append(row)
    return "Ship map snapshot:\n" + "\n".join(lines)

def _cmd_status(game):
    p = game.player
    inv = ", ".join(p.inventory) if p.inventory else "empty"
    lines = [
        f"Health: {p.health}",
        f"Sanity: {p.sanity}",
        f"Inventory: {inv}",
        f"Position: ({p.x}, {p.y})",
    ]
    return "\n".join(lines)
