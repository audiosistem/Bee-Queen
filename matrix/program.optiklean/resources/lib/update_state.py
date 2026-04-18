import json
import os
import time

import xbmc
import xbmcaddon
import xbmcvfs


ADDON = xbmcaddon.Addon()
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
RESTART_PENDING_PATH = os.path.join(PROFILE_PATH, "update_pending_restart.json")


def _log(message, level=xbmc.LOGINFO):
    xbmc.log(f"OptiKlean: {message}", level)


def _ensure_profile_path():
    if not xbmcvfs.exists(PROFILE_PATH):
        xbmcvfs.mkdirs(PROFILE_PATH)


def _current_pid():
    try:
        return int(os.getpid())
    except Exception:
        return 0


def clear_restart_pending():
    try:
        if xbmcvfs.exists(RESTART_PENDING_PATH):
            return bool(xbmcvfs.delete(RESTART_PENDING_PATH))
    except Exception as exc:
        _log(f"Failed clearing restart-pending marker: {exc}", xbmc.LOGWARNING)
    return False


def set_restart_pending(commit_id="", version="", message=""):
    _ensure_profile_path()

    payload = {
        "pid": _current_pid(),
        "timestamp": int(time.time()),
        "commit_id": commit_id or "",
        "version": version or "",
        "message": message or "",
    }
    temp_path = f"{RESTART_PENDING_PATH}.tmp"

    try:
        with xbmcvfs.File(temp_path, "w") as handle:
            written = handle.write(json.dumps(payload, ensure_ascii=False))
            if not written:
                _log("Failed to write restart-pending marker (write returned falsy)", xbmc.LOGWARNING)
                return False

        if xbmcvfs.exists(RESTART_PENDING_PATH):
            xbmcvfs.delete(RESTART_PENDING_PATH)

        if not xbmcvfs.rename(temp_path, RESTART_PENDING_PATH):
            _log("Failed to move restart-pending marker into place", xbmc.LOGWARNING)
            return False

        _log("Persisted restart-pending marker", xbmc.LOGINFO)
        return True
    except Exception as exc:
        _log(f"Failed persisting restart-pending marker: {exc}", xbmc.LOGWARNING)
        try:
            if xbmcvfs.exists(temp_path):
                xbmcvfs.delete(temp_path)
        except Exception:
            pass
    return False


def get_restart_pending_state():
    if not xbmcvfs.exists(RESTART_PENDING_PATH):
        return {}

    try:
        with xbmcvfs.File(RESTART_PENDING_PATH, "r") as handle:
            raw = handle.read()
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        _log(f"Failed reading restart-pending marker: {exc}", xbmc.LOGWARNING)
        return {}

    if not isinstance(payload, dict):
        clear_restart_pending()
        return {}

    marker_pid = int(payload.get("pid", 0) or 0)
    current_pid = _current_pid()
    if marker_pid and current_pid and marker_pid != current_pid:
        _log("Detected Kodi process restart; clearing restart-pending marker", xbmc.LOGINFO)
        clear_restart_pending()
        return {}

    return payload
