# eidolon/mechanics/commands.py
"""
Simple command handlers for Eidolon Drift.
Each command receives the `game` object (Game instance) and the raw command string.
Handlers may modify game state and should return a short text result (string).
"""

import random
from eidolon.mechanics.game_state import GameState


def handle_command(game, raw_cmd: str) -> str:
    cmd = raw_cmd.strip()
    if not cmd:
        return ""

    parts = cmd.split()
    verb = parts[0].lower()
    args = parts[1:]

    if verb in ("quit", "exit"):
        game.gameState = GameState.QUIT_CONFIRM
        game._handle_quit_confirm()
        return "Quit game? (y/n)"

    if verb in ("help", "?"):
        return _cmd_help(game)

    if verb == "logs":
        return _cmd_logs(game)

    if verb == "decrypt":
        if not args:
            return "Usage: decrypt <object>"
        target = " ".join(args)
        return _cmd_decrypt(game, target)

    if verb == "inspect-all":
        sector = game.map.get_sector(game.player.x, game.player.y)
        if sector is None:
            return "No sector."
        # show raw objects for debugging
        return repr(sector.objects)


    return f"Unknown command: {verb}. Type 'help' for a list of commands."


def _cmd_help(game):
    lines = [
        "Available commands:",
        "  help or ?: Show this help message.",
        " I or Enter: Interact with an object. With joystick, press primary action button to interact",
        " C or ESC: Cancel/Back. With joystick, press secondary action button to cancel.",
    ]
    for line in lines:
        game.push_message(line)



def _cmd_logs(game):
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return "No logs here."
    logs = [o for o in sector.objects if isinstance(o, dict) and o.get("type") == "log"]
    if not logs:
        return "No readable logs in this sector."

    # build lines for pager
    lines = ["Logs found:"]
    for i, l in enumerate(logs, 1):
        title = l.get("title", f"log-{i}")
        frag = l.get("fragmented", False)
        lines.append(f"  {i}. {title}" + (" (fragmented)" if frag else ""))
    lines.append("")
    lines.append("Use 'inspect <log name>' to read a log (e.g. inspect log-1).")
    # open pager if renderer available
    try:
        if hasattr(game, "renderer") and game.renderer:
            game.renderer.open_pager(lines)
            return None  # pager handled display
    except Exception:
        # fallback to returning text if pager fails
        pass
    return "\n".join(lines)



def _inspect_object(game, obj, full=False):

    def _describe_object_short(o):
        typ = o.get("type", "object")
        if typ == "log":
            content = o.get("content", "")
            if o.get("fragmented") and not full:
                snippet = content[:120]
                return f"{o.get('title','log')}: {snippet} ... (fragmented)"
            return f"{o.get('title','log')}: {content}"
        if typ == "enc":
            return o.get("description", "An encrypted fragment.")
        return o.get("description", o.get("title", o.get("name", "Nothing special.")))

    def _open_pager(lines):
        try:
            if hasattr(game, "renderer") and game.renderer:
                game.renderer.open_pager(lines)
                return True
        except Exception:
            pass
        return False

    # --- LOG ---
    if obj.get("type") == "log":
        content = obj.get("content", "")
        title = obj.get("title", "Log")

        # fragmented + not full → snippet
        if obj.get("fragmented") and not full:
            snippet = content[:120]
            game.push_message(f"{title}: {snippet} ... (fragmented)")
            return None

        # full log → pager
        lines = [title, "-" * 40] + content.splitlines()
        if _open_pager(lines):
            return None
        return "\n".join(lines)

    # --- ON_INSPECT EFFECT ---
    on_inspect = obj.get("on_inspect") or {}
    if on_inspect.get("action") == "sanity":
        amt = int(on_inspect.get("amount", 0))
        if amt > 0:
            game.player.gain_sanity(amt)
            return f"{obj.get('title')}: You feel calm. Sanity +{amt}."
        else:
            game.player.lose_sanity(-amt)
            return f"{obj.get('title')}: Something is wrong. Sanity {amt}."

    # --- DEFAULT ---
    return _describe_object_short(obj)


# Helper: normalized lowercase function (if not already present)
def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _cmd_decrypt(game, target):
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return "Nothing to decrypt."
    # find encrypted fragments (type == 'enc')
    for o in sector.objects:
        if isinstance(o, dict) and o.get("type") == "enc":
            name = o.get("name", "").lower()
            if target.lower() == name or target.lower() == o.get("title", "").lower():
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
                        "fragmented": False,
                    }
                    sector.objects.append(revealed)
                    sector.objects.remove(o)
                    return f"Decryption successful. Revealed log: {revealed['title']}"
                else:
                    # failure: small sanity/health penalty
                    game.player.sanity = max(0, game.player.sanity - 5)
                    return "Decryption failed. Neural feedback caused minor disorientation."
    return f"No encrypted object named '{target}' found here."

    
def _use_object(game, obj):
    on_use = obj.get("on_use") or {}
    action = on_use.get("action")

    # HEAL
    if action == "heal":
        amt = int(on_use.get("amount", 0))
        san = int(on_use.get("sanity", 0))
        game.player.heal(amt)
        if san:
            game.player.gain_sanity(san)
        return f"{obj.get('title')} used. Health +{amt}, Sanity +{san}."

    # SANITY
    if action == "sanity":
        amt = int(on_use.get("amount", 0))
        game.player.adjust_sanity(amt)
        if amt >= 0:
            return f"{obj.get('title')} used. Sanity +{amt}."
        else:
            return f"{obj.get('title')} used. Something is wrong. Sanity {amt}."

    # FLAG (moduly)
    if action == "flag":
        flag_name = on_use.get("flag")
        flag_value = on_use.get("value", True)
        flavor = obj.get("flavor_text") or "Module activated."

        setattr(game, flag_name, flag_value)
        return flavor

    # ESCAPE
    if action == "escape":
        game.gameState = GameState.ESCAPE
        game._handle_escape_confirm()
        return None

    return f"You interact with the {obj.get('title') or obj.get('name') or obj.get('type')}. Nothing obvious happens."

    

    # ESCAPE action
    if (
        action == "escape"
        or obj.get("name") == "escape-pod"
        or obj.get("id") == "escape-pod"
    ):
        # only set flag here; do NOT call dialog directly
        game.gameState = GameState.ESCAPE
        game._handle_escape_confirm()
        return None

    # fallback: no actionable on_use, but object matches target
    return f"You interact with the {obj.get('title') or obj.get('name') or obj.get('type')}. Nothing obvious happens."
