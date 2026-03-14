"""debrid_state

Lightweight, addon-local state sync for Debrid accounts.

This writes a small JSON file into addon_data so other components in the
luc_kodi ecosystem (e.g. script modules, wizards) can reliably know whether a
Debrid service is currently authorized in plugin.video.luc_kodi.

The source of truth is still Kodi add-on settings. This module just mirrors a
minimal, non-sensitive subset + booleans.
"""

from __future__ import annotations

from json import dumps as _dumps

from resources.lib.modules import control


def _state_path() -> str:
    # addon_data/plugin.video.luc_kodi/debrid_state.json
    try:
        data_dir = control.dataPath
    except Exception:
        data_dir = control.translatePath('special://profile/addon_data/plugin.video.luc_kodi')
    try:
        control.makeFile(data_dir)
    except Exception:
        pass
    return control.joinPath(data_dir, 'debrid_state.json')


def build_state() -> dict:
    """Build a minimal state dict from current settings."""

    get = control.setting
    def _truthy(v: str) -> bool:
        return str(v).lower() == 'true'

    state = {
        'version': 1,
        'services': {
            'realdebrid': {
                'enabled': _truthy(get('realdebrid.enable')),
                'authorized': bool(get('realdebrid.token')),
                'username': get('realdebrid.username') or '',
            },
            'premiumize': {
                'enabled': _truthy(get('premiumize.enable')),
                'authorized': bool(get('premiumize.token')),
                'username': get('premiumize.username') or '',
            },
            'alldebrid': {
                'enabled': _truthy(get('alldebrid.enable')),
                'authorized': bool(get('alldebrid.token')),
                'username': get('alldebrid.username') or '',
            },
            'torbox': {
                'enabled': _truthy(get('torbox.enable')),
                'authorized': bool(get('torbox.token')),
                'username': get('torbox.username') or '',
            },
        }
    }
    return state


def sync_state() -> bool:
    """Write state file. Returns True on success."""
    try:
        path = _state_path()
        payload = _dumps(build_state(), ensure_ascii=False, indent=2)
        control.writeFile(path, payload)
        return True
    except Exception:
        return False
