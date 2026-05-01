"""
eidolon.io.detect_input

Cross-platform helper to detect presence of game controllers / joysticks.
Provides a small internal API used by InputHandler.

Backends (in order of preference):
 - pygame (SDL)    : cross-platform, integrates with event loop
 - evdev (Linux)   : direct /dev/input access, robust for Linux
 - hid (hidapi)    : optional, for vendor/product details

API:
 - has_controller() -> bool
 - list_controllers() -> list of dicts {id, name, backend, path, info}
 - start_monitoring(callback) -> None
 - stop_monitoring() -> None
 - backend_name() -> str or None
"""

from __future__ import annotations
import threading
import time
import logging
from typing import Callable, List, Dict, Optional

logger = logging.getLogger("eidolon.detect_input")
logger.addHandler(logging.NullHandler())

# backend flags and modules (populated at import time)
_BACKEND = None  # "pygame", "evdev", "hid", or None
_PYGAME = None
_EVDEV = None
_HID = None

# monitoring thread state
_monitor_thread: Optional[threading.Thread] = None
_monitor_stop = threading.Event()
_monitor_callback: Optional[Callable[[str, Dict], None]] = None
_monitor_poll_interval = 1.0  # seconds


# --- backend detection at import time --------------------------------------
try:
    import pygame as _pg
    _pg.init()
    _pg.joystick.init()
    _PYGAME = _pg
    _BACKEND = "pygame"
    logger.debug("detect_input: using pygame backend")
except Exception:
    _PYGAME = None
    # try evdev (Linux)
    try:
        import evdev as _ev
        _EVDEV = _ev
        _BACKEND = "evdev"
        logger.debug("detect_input: using evdev backend")
    except Exception:
        _EVDEV = None
        # try hid (hidapi)
        try:
            import hid as _hid  # hidapi python binding
            _HID = _hid
            _BACKEND = "hid"
            logger.debug("detect_input: using hid backend")
        except Exception:
            _HID = None
            _BACKEND = None
            logger.debug("detect_input: no input backend available")


# --- helpers per backend ---------------------------------------------------
def _list_pygame() -> List[Dict]:
    """Return list of joysticks via pygame."""
    res = []
    pg = _PYGAME
    if not pg:
        return res
    try:
        count = pg.joystick.get_count()
        for i in range(count):
            try:
                j = pg.joystick.Joystick(i)
                j.init()
                info = {
                    "id": f"pygame-{i}",
                    "name": j.get_name(),
                    "backend": "pygame",
                    "index": i,
                    "num_axes": j.get_numaxes(),
                    "num_buttons": j.get_numbuttons(),
                }
                res.append(info)
            except Exception:
                logger.exception("detect_input: pygame joystick init failed for index %s", i)
    except Exception:
        logger.exception("detect_input: pygame get_count failed")
    return res


def _list_evdev() -> List[Dict]:
    """Return list of input devices that look like gamepads (Linux)."""
    res = []
    ev = _EVDEV
    if not ev:
        return res
    try:
        from evdev import list_devices, InputDevice, ecodes
        for path in list_devices():
            try:
                dev = InputDevice(path)
                caps = dev.capabilities(verbose=True)
                # heuristic: presence of ABS (axes) or BTN_GAMEPAD/BTN_JOYSTICK
                is_gamepad = False
                for code, _ in caps.items():
                    if isinstance(code, tuple):
                        code_name = code[0]
                    else:
                        code_name = code
                    if "ABS" in str(code_name) or "BTN_GAMEPAD" in str(code_name) or "BTN_JOYSTICK" in str(code_name):
                        is_gamepad = True
                        break
                if is_gamepad:
                    res.append({
                        "id": f"evdev:{path}",
                        "name": dev.name,
                        "backend": "evdev",
                        "path": path,
                        "info": {"phys": getattr(dev, "phys", None), "uniq": getattr(dev, "uniq", None)}
                    })
            except Exception:
                logger.debug("detect_input: skipping evdev device %s", path, exc_info=True)
    except Exception:
        logger.exception("detect_input: evdev listing failed")
    return res


def _list_hid() -> List[Dict]:
    """Return list of HID devices (generic)."""
    res = []
    hid = _HID
    if not hid:
        return res
    try:
        for d in hid.enumerate():
            try:
                res.append({
                    "id": f"hid:{d.get('vendor_id')}:{d.get('product_id')}:{d.get('path')}",
                    "name": d.get("product_string") or d.get("manufacturer_string") or "HID Device",
                    "backend": "hid",
                    "path": d.get("path"),
                    "info": {"vendor_id": d.get("vendor_id"), "product_id": d.get("product_id")}
                })
            except Exception:
                logger.debug("detect_input: hid enumerate item failed", exc_info=True)
    except Exception:
        logger.exception("detect_input: hid enumerate failed")
    return res


# --- public API ------------------------------------------------------------
def backend_name() -> Optional[str]:
    """Return the name of the active backend or None."""
    return _BACKEND


def list_controllers() -> List[Dict]:
    """
    Return a list of detected controller descriptors.
    Each descriptor is a dict with keys: id, name, backend, path/index, info.
    """
    if _BACKEND == "pygame":
        return _list_pygame()
    if _BACKEND == "evdev":
        return _list_evdev()
    if _BACKEND == "hid":
        return _list_hid()
    return []


def has_controller() -> bool:
    """Return True if at least one controller is present."""
    return len(list_controllers()) > 0


# --- monitoring (hotplug) -------------------------------------------------
def _poll_once_and_notify(prev_ids: set):
    """Poll current devices and notify callback about adds/removes."""
    current = list_controllers()
    cur_ids = set(d.get("id") for d in current if d.get("id"))
    added = cur_ids - prev_ids
    removed = prev_ids - cur_ids
    if added or removed:
        # build info maps
        id_map = {d.get("id"): d for d in current}
        for aid in added:
            info = id_map.get(aid, {"id": aid})
            try:
                if _monitor_callback:
                    _monitor_callback("added", info)
            except Exception:
                logger.exception("detect_input: monitor callback raised on add")
        for rid in removed:
            try:
                if _monitor_callback:
                    _monitor_callback("removed", {"id": rid})
            except Exception:
                logger.exception("detect_input: monitor callback raised on remove")
    return cur_ids


def _monitor_loop(poll_interval: float):
    prev = set(d.get("id") for d in list_controllers())
    logger.debug("detect_input: monitor loop starting, initial devices=%s", prev)
    while not _monitor_stop.wait(poll_interval):
        try:
            prev = _poll_once_and_notify(prev)
        except Exception:
            logger.exception("detect_input: exception in monitor loop")
    logger.debug("detect_input: monitor loop exiting")


def start_monitoring(callback: Callable[[str, Dict], None], poll_interval: float = 1.0) -> None:
    """
    Start background monitoring for device add/remove events.
    callback(event_type, info) will be called with event_type in ("added","removed").
    """
    global _monitor_thread, _monitor_stop, _monitor_callback, _monitor_poll_interval
    if _monitor_thread and _monitor_thread.is_alive():
        logger.debug("detect_input: monitor already running")
        return
    _monitor_callback = callback
    _monitor_poll_interval = float(poll_interval)
    _monitor_stop.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, args=(poll_interval,), daemon=True)
    _monitor_thread.start()
    logger.debug("detect_input: monitoring started")


def stop_monitoring() -> None:
    """Stop background monitoring if running."""
    global _monitor_thread
    _monitor_stop.set()
    if _monitor_thread:
        _monitor_thread.join(timeout=2.0)
    _monitor_thread = None
    logger.debug("detect_input: monitoring stopped")


# --- simple CLI test when run as script -----------------------------------
if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="Detect input controllers (debug)")
    parser.add_argument("--monitor", action="store_true", help="Run monitor loop and print events")
    args = parser.parse_args()

    print("detect_input backend:", backend_name())
    devices = list_controllers()
    print("found devices:", len(devices))
    print(json.dumps(devices, indent=2, ensure_ascii=False))

    if args.monitor:
        def cb(ev, info):
            print(f"[monitor] {ev}: {info}")
        start_monitoring(cb, poll_interval=1.0)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            stop_monitoring()
            print("monitor stopped")
