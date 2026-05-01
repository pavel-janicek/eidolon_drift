# eidolon/mechanics/events.py
import time


class EventEngine:
    def __init__(self, game, event_defs=None):
        self.game = game
        self.event_defs = event_defs or {}
        self._last_trigger = {}  # event_id -> last tick index or timestamp

    def trigger(self, event_def, sector):
        """
        event_def: dict loaded from JSON (fields: id, type, damage, message, repeatable, cooldown, etc.)
        sector: Sector instance where event occurs
        """
        etype = event_def.get("type")
        if etype == "linger_damage":
            dmg = int(event_def.get("damage", 1))
            msg = event_def.get("message", "You take damage.").format(damage=dmg)
            self.game.player.take_damage(dmg, source=event_def.get("id"))
            self.game.push_message(msg)
            if self.game.player.health <= 0:
                # call game death handler
                self.game.handle_death(
                    event_def.get("death_message", "You succumbed to your injuries.")
                )
        elif etype == "spawn_anomaly":
            # create a simple anomaly object in the sector
            anomaly = {
                "type": "anomaly",
                "name": event_def.get("name", f"anomaly-{int(time.time())}"),
                "title": event_def.get("title", "Unstable Anomaly"),
                "description": event_def.get(
                    "description", "A newly formed anomaly pulses here."
                ),
                "linger_damage": event_def.get("linger_damage", 1),
            }
            sector.objects.append(anomaly)
            self.game.push_message(event_def.get("message", "An anomaly forms nearby."))
        # other event types can be added here
