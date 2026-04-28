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
        game.awaiting_quit_confirm = True
        game._handle_quit_confirm()
        return "Quit game? (y/n)"

    if verb in ("help", "?"):
        return _cmd_help(game)

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
    
    if verb == "inspect-all":
        sector = game.map.get_sector(game.player.x, game.player.y)
        if sector is None:
            return "No sector."
        # show raw objects for debugging
        return repr(sector.objects)
    if verb == "use":
        if not args:
            return "Usage: use <object>"
        target = " ".join(args)
        return _cmd_use(game, target)
    if verb == "theme":
        name = args[0] if args else "dark"
        if not hasattr(game, "renderer") or game.renderer is None:
            return "No renderer available to apply a theme."
        ok = game.renderer.apply_theme(name)
        return f"Theme set to {name}" if ok else f"Unknown theme '{name}'. Available: {', '.join(game.renderer.THEMES.keys())}"

    
    return f"Unknown command: {verb}. Type 'help' for a list of commands."

def _cmd_help(game):
    lines = [
        "Available commands:",
        "  scan               - run diagnostics on current sector",
        "  logs               - list readable logs in this sector",
        "  inspect <object>   - inspect an object in the sector",
        "  decrypt <object>   - attempt to decrypt a data fragment",
        "  use <object>       - use an item from your inventory or the sector",
        "  theme <name>        - change display theme (e.g. theme dark)",
        "  help               - show this help",
        "  quit               - exit the session",
    ]
    for line in lines:
        game.push_message(line)

def _cmd_scan(game):
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return ["Scan: no sector data."]

    env = sector.environment or {}

    lines = []
    lines.append(f"Scan results for {sector.name}:")

    # environment keys
    if isinstance(env, dict) and env:
        for k, v in env.items():
            lines.append(f"  {k}: {v}")
    else:
        lines.append("  No special environmental readings.")

    # objects summary
    if sector.objects:
        lines.append(f"  Objects detected: {len(sector.objects)}")
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


def _normalize(s: str) -> str:
    # lower, strip punctuation, remove simple articles
    import re
    s = s.lower().strip()
    s = re.sub(r"[^\w\s\-]", "", s)  # remove punctuation except dash
    # remove common articles
    s = re.sub(r"\b(a|an|the)\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _cmd_inspect(game, raw_target):
    """
    Inspect an object in the current sector.
    - raw_target: string provided by player, may include 'full' flag (e.g. "log-1 full")
    Returns:
      - None if display was handled by renderer (pager),
      - string message otherwise.
    """
    if not raw_target:
        return "Inspect what?"

    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector is None:
        return "Nothing to inspect here."

    # parse target and optional flags
    parts = raw_target.split()
    full_flag = False
    # accept trailing 'full' or '--full'
    if parts and parts[-1].lower() in ("full", "--full"):
        full_flag = True
        parts = parts[:-1]
    target = " ".join(parts).strip()
    if not target:
        return "Inspect what?"

    target_norm = _normalize(target)

    # helper: describe object for non-pager fallback
    def _describe_object_short(o: dict) -> str:
        typ = o.get("type", "object")
        if typ == "log":
            content = o.get("content", "")
            if o.get("fragmented"):
                snippet = content[: min(120, len(content))]
                return f"{o.get('title','log')}: {snippet} ... (fragmented)"
            return f"{o.get('title','log')}: {content}"
        if typ == "enc":
            return o.get("description", "An encrypted data fragment. Try 'decrypt <name>'.")
        return o.get("description", o.get("title", o.get("name", "You see nothing special about it.")))

    # helper: open pager if available, returns True if pager used
    def _open_pager_if_possible(lines):
        try:
            if hasattr(game, "renderer") and game.renderer:
                game.renderer.open_pager(lines)
                return True
        except Exception:
            # swallow pager errors and fallback to text return
            pass
        return False

    # collect objects and simple strings
    dict_objs = [o for o in sector.objects if isinstance(o, dict)]
    str_objs = [o for o in sector.objects if isinstance(o, str)]

    # 0) numeric index match (1-based) for dict objects: "1" -> first dict object
    if target_norm.isdigit():
        idx = int(target_norm) - 1
        if 0 <= idx < len(dict_objs):
            obj = dict_objs[idx]
            # if log and full requested -> open pager
            if obj.get("type") == "log":
                if obj.get("fragmented") and not full_flag:
                    # show snippet in messages and hint
                    snippet = obj.get("content", "")[:120]
                    game.push_message(f"{obj.get('title')}: {snippet} ... (fragmented)")
                    game.push_message("Use 'inspect <name> full' to read the entire entry.")
                    return None
                # full content
                lines = [obj.get("title", "Log"), "-" * 40] + obj.get("content", "").splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            # non-log: short description
            return _describe_object_short(obj)

    # 1) exact match on name/title (normalized)
    for o in dict_objs:
        name = _normalize(o.get("name", ""))
        title = _normalize(o.get("title", ""))
        if target_norm == name or target_norm == title:
            # handle log specially
            if o.get("type") == "log":
                if o.get("fragmented") and not full_flag:
                    snippet = o.get("content", "")[:120]
                    game.push_message(f"{o.get('title')}: {snippet} ... (fragmented)")
                    game.push_message("Use 'inspect <name> full' to read the entire entry.")
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get("content", "").splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            return _describe_object_short(o)

    # 2) substring match on name/title
    for o in dict_objs:
        name = _normalize(o.get("name", ""))
        title = _normalize(o.get("title", ""))
        if target_norm in name or target_norm in title:
            if o.get("type") == "log":
                if o.get("fragmented") and not full_flag:
                    snippet = o.get("content", "")[:120]
                    game.push_message(f"{o.get('title')}: {snippet} ... (fragmented)")
                    game.push_message("Use 'inspect <name> full' to read the entire entry.")
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get("content", "").splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            return _describe_object_short(o)

    # 3) token overlap match (e.g., "crew jacket" vs "jacket")
    target_tokens = set(target_norm.split())
    for o in dict_objs:
        combined = " ".join(filter(None, [o.get("name", ""), o.get("title", "")]))
        combined_norm = _normalize(combined)
        tokens = set(combined_norm.split())
        if tokens and (target_tokens & tokens):
            if o.get("type") == "log":
                if o.get("fragmented") and not full_flag:
                    snippet = o.get("content", "")[:120]
                    game.push_message(f"{o.get('title')}: {snippet} ... (fragmented)")
                    game.push_message("Use 'inspect <name> full' to read the entire entry.")
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get("content", "").splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            return _describe_object_short(o)

    # 4) plain string objects: exact or substring normalized
    for o in str_objs:
        o_norm = _normalize(o)
        if target_norm == o_norm or target_norm in o_norm:
            return f"You inspect the {o}. It seems unremarkable."

    # 5) if target looks like "log-<n>" or "log n", try to map to nth log specifically
    # collect logs in sector
    logs = [o for o in dict_objs if o.get("type") == "log"]
    if logs:
        # try patterns like "log-1", "log1", "log 1"
        import re
        m = re.search(r"(\d+)$", target)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(logs):
                o = logs[idx]
                if o.get("fragmented") and not full_flag:
                    snippet = o.get("content", "")[:120]
                    game.push_message(f"{o.get('title')}: {snippet} ... (fragmented)")
                    game.push_message("Use 'inspect <name> full' to read the entire entry.")
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get("content", "").splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)

    return f"No object named '{target}' found here."


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


def _cmd_use(game, target):
    target_norm = _normalize(target)
    # search inventory first
    for i, it in enumerate(game.player.inventory):
        if isinstance(it, dict):
            name = _normalize(it.get("name",""))
            title = _normalize(it.get("title",""))
            if target_norm == name or target_norm == title or target_norm in name or target_norm in title:
                # handle on_use
                on_use = it.get("on_use")
                if on_use and on_use.get("action") == "heal":
                    amt = int(on_use.get("amount", 0))
                    game.player.heal(amt)
                    game.player.inventory.pop(i)
                    return f"You use the {it.get('title','item')}. Restored {amt} health."
                return f"You use the {it.get('title','item')}. Nothing obvious happens."
    # search sector objects (similar logic)
    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector:
        for i, o in enumerate(sector.objects):
            if isinstance(o, dict):
                name = _normalize(o.get("name",""))
                title = _normalize(o.get("title",""))
                if target_norm == name or target_norm == title or target_norm in name or target_norm in title:
                    on_use = o.get("on_use")
                    if on_use and on_use.get("action") == "heal":
                        amt = int(on_use.get("amount", 0))
                        game.player.heal(amt)
                        # remove if consumable
                        sector.objects.pop(i)
                        return f"You use the {o.get('title','item')}. Restored {amt} health."
                    return f"You interact with the {o.get('title')}. Nothing obvious happens."
    return f"No usable object named '{target}' found here."

