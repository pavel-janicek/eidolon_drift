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
        return (
            f"Theme set to {name}"
            if ok
            else f"Unknown theme '{name}'. Available: {', '.join(game.renderer.THEMES.keys())}"
        )

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
        # --- joystick quick-inspect: pokud není zadán target a je připojen joystick,
    #     vyber první dict objekt, jinak první string objekt -----------------
    ih = getattr(game, "input_handler", None)
    joystick_connected = False
    if ih is not None:
        # preferujeme explicitní příznak používání controlleru, fallback na pygame joystick
        joystick_connected = bool(getattr(ih, "_using_controller", False) or getattr(ih, "_pygame_joystick", None))

    if not raw_target and joystick_connected:
        # preferuj první dict objekt
        if dict_objs:
            obj = dict_objs[0]
            # reuse logic from numeric index branch for logs and effects
            if obj.get("type") == "log":
                if obj.get("fragmented") and not full_flag:
                    snippet = obj.get("content", "")[:120]
                    game.push_message(f"{obj.get('title')}: {snippet} ... (fragmented)")
                    game.push_message("Use 'inspect <name> full' to read the entire entry.")
                    return None
                lines = [obj.get("title", "Log"), "-" * 40] + obj.get("content", "").splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            _apply_on_inspect_effect(obj, full_flag=full_flag)
            return _describe_object_short(obj)
        # fallback na první string objekt
        if str_objs:
            s = str_objs[0]
            return f"You inspect the {s}. It seems unremarkable."
        return "Nothing to inspect here."

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
            return o.get(
                "description", "An encrypted data fragment. Try 'decrypt <name>'."
            )
        return o.get(
            "description",
            o.get("title", o.get("name", "You see nothing special about it.")),
        )

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

    def _apply_on_inspect_effect(o, full_flag=False):
        on_inspect = o.get("on_inspect") or {}
        if not isinstance(on_inspect, dict):
            return False
        action = on_inspect.get("action")
        if action == "sanity":
            amt = int(on_inspect.get("amount", 0))
            try:
                if amt > 0 and hasattr(game.player, "gain_sanity"):
                    game.player.gain_sanity(amt)
                elif amt < 0 and hasattr(game.player, "lose_sanity"):
                    game.player.lose_sanity(-amt)
                elif hasattr(game.player, "adjust_sanity"):
                    game.player.adjust_sanity(amt)
                elif hasattr(game.player, "gain_sanity"):
                    game.player.gain_sanity(amt)
            except Exception:
                pass
            if amt >= 0:
                game.push_message(f"You feel calmer. Sanity +{amt}.")
            else:
                game.push_message(f"A chill runs down your spine. Sanity {amt}.")
            return True
        # další akce lze přidat zde
        return False

    # collect objects and simple strings
    dict_objs = [o for o in sector.objects if isinstance(o, dict)]
    str_objs = [o for o in sector.objects if isinstance(o, str)]

    # 0) match by internal ID (popup uses this)
    for o in dict_objs:
        if o.get("id") == target:
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

            _apply_on_inspect_effect(o, full_flag=full_flag)
            return _describe_object_short(o)
    


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
                    game.push_message(
                        "Use 'inspect <name> full' to read the entire entry."
                    )
                    return None
                # full content
                lines = [obj.get("title", "Log"), "-" * 40] + obj.get(
                    "content", ""
                ).splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            # non-log: short description
            _apply_on_inspect_effect(o, full_flag=full_flag)
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
                    game.push_message(
                        "Use 'inspect <name> full' to read the entire entry."
                    )
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get(
                    "content", ""
                ).splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            _apply_on_inspect_effect(o, full_flag=full_flag)

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
                    game.push_message(
                        "Use 'inspect <name> full' to read the entire entry."
                    )
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get(
                    "content", ""
                ).splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            _apply_on_inspect_effect(o, full_flag=full_flag)
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
                    game.push_message(
                        "Use 'inspect <name> full' to read the entire entry."
                    )
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get(
                    "content", ""
                ).splitlines()
                if _open_pager_if_possible(lines):
                    return None
                return "\n".join(lines)
            _apply_on_inspect_effect(o, full_flag=full_flag)
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
                    game.push_message(
                        "Use 'inspect <name> full' to read the entire entry."
                    )
                    return None
                lines = [o.get("title", "Log"), "-" * 40] + o.get(
                    "content", ""
                ).splitlines()
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


def _cmd_use(game, target):
    
    target_norm = _normalize(target)
        # --- joystick quick-use: pokud není zadán target a je připojen joystick,
    #     preferuj první položku v inventáři, jinak první dict objekt v sektoru
    ih = getattr(game, "input_handler", None)
    joystick_connected = False
    if ih is not None:
        joystick_connected = bool(getattr(ih, "_using_controller", False) or getattr(ih, "_pygame_joystick", None))

    if not target and joystick_connected:
        # 1) inventory first
        try:
            inv = list(getattr(game.player, "inventory", []) or [])
        except Exception:
            inv = []
        if inv:
            # najdeme první dict položku v inventáři
            for i, it in enumerate(inv):
                if isinstance(it, dict):
                    # znovu použijeme stávající logiku: nastavíme matches tak, aby vybral tuto položku
                    matches = [("inv", i, it)]
                    break
            else:
                matches = []
        else:
            matches = []

        # 2) pokud nic v inventáři, zkus první dict objekt v sektoru
        if not matches:
            sector = game.map.get_sector(game.player.x, game.player.y)
            if sector:
                for i, o in enumerate(list(getattr(sector, "objects", []) or [])):
                    if isinstance(o, dict):
                        matches = [("sec", i, o)]
                        break

        if not matches:
            return "No usable object found to use."

        # vyber první match (inventář má prioritu díky pořadí výše)
        source, idx, obj = matches[0]
        # pokračujeme níže v původní logice s tímto obj


    def _matches_obj(obj, target_norm):
        if not isinstance(obj, dict):
            return False
        name = _normalize(obj.get("name", ""))
        title = _normalize(obj.get("title", ""))
        typ = _normalize(obj.get("type", ""))
        obj_id = _normalize(obj.get("id", ""))
        if (
            target_norm == name
            or target_norm == title
            or target_norm == typ
            or target_norm == obj_id
        ):
            return True
        if target_norm in name or target_norm in title or target_norm in typ:
            return True
        return False

    # collect matches (inventory first, then sector)
    matches = []  # tuples: ("inv", index, obj) or ("sec", index, obj)
    for i, it in enumerate(list(game.player.inventory)):
        if isinstance(it, dict) and _matches_obj(it, target_norm):
            matches.append(("inv", i, it))

    sector = game.map.get_sector(game.player.x, game.player.y)
    if sector:
        for i, o in enumerate(list(getattr(sector, "objects", []) or [])):
            if isinstance(o, dict) and _matches_obj(o, target_norm):
                matches.append(("sec", i, o))

    if not matches:
        return f"No usable object named '{target}' found here."

    # pick first match (inventory preferred because collected first)
    source, idx, obj = matches[0]

    # helper to adjust sanity safely
    def _apply_sanity(delta):
        # prefer explicit methods if available
        if delta == 0:
            return
        # try gain_sanity for positive, lose_sanity for negative, fallback to gain_sanity with negative
        try:
            if delta > 0 and hasattr(game.player, "gain_sanity"):
                game.player.gain_sanity(int(delta))
                return
            if delta < 0 and hasattr(game.player, "lose_sanity"):
                game.player.lose_sanity(int(-delta))
                return
            # fallback: try adjust_sanity or gain_sanity with signed value
            if hasattr(game.player, "adjust_sanity"):
                game.player.adjust_sanity(int(delta))
                return
            if hasattr(game.player, "gain_sanity"):
                game.player.gain_sanity(int(delta))
                return
        except Exception:
            # best-effort: ignore if player API differs
            pass

    # process on_use
    on_use = obj.get("on_use") or {}
    action = on_use.get("action") if isinstance(on_use, dict) else None

    # HEAL
    if action == "heal":
        amt = int(on_use.get("amount", 0))
        san = int(on_use.get("sanity", 0))
        try:
            game.player.heal(amt)
        except Exception:
            pass
        _apply_sanity(san)
        # remove consumable
        if source == "inv":
            try:
                game.player.inventory.pop(idx)
            except Exception:
                pass
        else:
            try:
                sector.objects.pop(idx)
            except Exception:
                pass
        return f"You use the {obj.get('title','item')}. Restored {amt} health and gained {san} sanity."

    # SANITY action (positive or negative)
    if action == "sanity":
        amt = int(on_use.get("amount", 0))
        _apply_sanity(amt)
        # remove if consumable (optional; keep or remove depending on design)
        if source == "inv":
            try:
                game.player.inventory.pop(idx)
            except Exception:
                pass
        else:
            try:
                sector.objects.pop(idx)
            except Exception:
                pass
        if amt >= 0:
            return f"You use the {obj.get('title','item')}. Sanity +{amt}."
        else:
            return f"You use the {obj.get('title','item')}. A chill runs down your spine. Sanity {amt}."
        
        # FLAG action (generic key/value override)
    if action == "flag":
        flag_name = on_use.get("flag")
        flag_value = on_use.get("value", True)

        # nastav flag do game objektu
        try:
            setattr(game, flag_name, flag_value)
        except Exception:
            pass

        # modul se nespotřebovává (ale můžeš změnit)
        return f"You activate the {obj.get('title','module')}. Flag '{flag_name}' set to {flag_value}."
    

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
