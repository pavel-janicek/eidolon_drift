# eidolon/mechanics/commands.py
# placeholder for command handlers
def handle_command(game_state, cmd):
    cmd = cmd.strip().lower()
    if cmd == "scan":
        return "Scan: nothing immediate detected."
    if cmd.startswith("inspect"):
        return f"Inspect: {cmd[7:].strip()}"
    return f"Unknown command: {cmd}"
