"""debrid_hub

Unified Debrid account panel (Debrid Hub).

This is a lightweight directory UI that aggregates all Debrid account actions
in one place.
"""

from __future__ import annotations

from sys import argv

from resources.lib.modules import control


def _bool(v: str) -> bool:
    return str(v).lower() == 'true'


def _status_label(name: str, enabled: bool, authorized: bool, username: str = '') -> str:
    if not enabled:
        return f"{name}: [COLOR red][B]Disabled[/B][/COLOR]"
    if authorized:
        user = f" ({username})" if username else ''
        return f"{name}: [COLOR lime][B]Authorized[/B][/COLOR]{user}"
    return f"{name}: [COLOR orange][B]Not authorized[/B][/COLOR]"


def _add_item(label: str, query: str, icon: str, is_folder: bool, is_action: bool = True):
    """Add an item to the current directory."""
    syshandle = int(argv[1])
    if is_action:
        url = f"plugin://plugin.video.luc_kodi/?action={query}"
    else:
        url = query
    art = control.artPath()
    icon_path = control.joinPath(art, icon) if not icon.startswith('Default') else icon
    li = control.item(label=label, offscreen=True)
    li.setArt({'icon': icon_path, 'thumb': icon_path, 'poster': icon_path, 'fanart': control.addonFanart()})
    control.addItem(handle=syshandle, url=url, listitem=li, isFolder=is_folder)


def open_hub():
    """Debrid Hub root directory."""
    from resources.lib.modules.debrid_state import sync_state

    try:
        sync_state()
    except Exception:
        pass

    get = control.setting

    _add_item('My Accounts (Settings)', 'tools_openSettings&query=7.0', 'tools.png', is_folder=False)

    services = [
        ('realdebrid', 'Real-Debrid', 'realdebrid.enable', 'realdebrid.token', 'realdebrid.username', 'realdebrid.png'),
        ('premiumize', 'Premiumize', 'premiumize.enable', 'premiumize.token', 'premiumize.username', 'premiumize.png'),
        ('alldebrid', 'AllDebrid', 'alldebrid.enable', 'alldebrid.token', 'alldebrid.username', 'alldebrid.png'),
        ('torbox', 'TorBox', 'torbox.enable', 'torbox.token', 'torbox.username', 'torbox.png'),
    ]

    for key, name, en_key, tk_key, un_key, icon in services:
        enabled = _bool(get(en_key))
        authorized = bool(get(tk_key))
        username = get(un_key) or ''
        label = _status_label(name, enabled, authorized, username)
        _add_item(label, f"debridHub_Service&service={key}", icon, is_folder=True)

    control.content(int(argv[1]), 'addons')
    control.directory(int(argv[1]), cacheToDisc=False)


def service_menu(service: str):
    """Per-service submenu."""
    from resources.lib.modules.debrid_state import sync_state

    get = control.setting

    mapping = {
        'realdebrid': ('Real-Debrid', 'realdebrid.enable', 'realdebrid.token', 'realdebrid.username', 'realdebrid.png', 'rd_Authorize', 'rd_Deauthorize', 'rd_AccountInfo'),
        'premiumize': ('Premiumize', 'premiumize.enable', 'premiumize.token', 'premiumize.username', 'premiumize.png', 'pm_Authorize', 'pm_Deauthorize', 'pm_AccountInfo'),
        'alldebrid': ('AllDebrid', 'alldebrid.enable', 'alldebrid.token', 'alldebrid.username', 'alldebrid.png', 'ad_Authorize', 'ad_Deauthorize', 'ad_AccountInfo'),
        'torbox': ('TorBox', 'torbox.enable', 'torbox.token', 'torbox.username', 'torbox.png', 'tb_Authorize', 'tb_Deauthorize', 'tb_AccountInfo'),
    }
    if service not in mapping:
        return

    name, en_key, tk_key, un_key, icon, auth_action, deauth_action, acc_action = mapping[service]
    enabled = _bool(get(en_key))
    authorized = bool(get(tk_key))
    username = get(un_key) or ''

    try:
        sync_state()
    except Exception:
        pass

    _add_item(_status_label(name, enabled, authorized, username), '', icon, is_folder=False, is_action=False)

    if enabled:
        if authorized:
            _add_item('Account Info', acc_action, icon, is_folder=False)
            _add_item('Deauthorize', deauth_action, icon, is_folder=False)
        else:
            _add_item('Authorize', auth_action, icon, is_folder=False)

    _add_item('Open My Accounts settings', 'tools_openSettings&query=7.0', 'tools.png', is_folder=False)

    control.content(int(argv[1]), 'addons')
    control.directory(int(argv[1]), cacheToDisc=False)
