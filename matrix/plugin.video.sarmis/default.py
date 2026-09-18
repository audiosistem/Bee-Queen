import sys
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs
from urllib.parse import parse_qs, urlparse, quote

from resources.lib.sites import menu as sites_menu

_addon  = xbmcaddon.Addon()
handle  = int(sys.argv[1])
params  = parse_qs(urlparse(sys.argv[2]).query)
xbmc.log(f"[Sarmis] Params: {params}", xbmc.LOGINFO)
action = params.get('action', [''])[0]
page   = int(params.get('page', [1])[0])

# Lista site-uri — aliasuri externe (mapping real păstrat server-side)
_SITES = [
    {"id": "alfa",    "name": "Alfa"},
    {"id": "beta",    "name": "Beta"},
    {"id": "gamma",   "name": "Gamma"},
    {"id": "delta",   "name": "Delta"},
    {"id": "epsilon", "name": "Epsilon"},
    {"id": "zeta",    "name": "Zeta"},
    {"id": "eta",     "name": "Eta"},
    {"id": "theta",   "name": "Theta"},
    {"id": "iota",    "name": "Iota"},
    {"id": "kappa",   "name": "Kappa"},
    {"id": "lambda",  "name": "Lambda"},
    {"id": "mu",      "name": "Mu"},
    {"id": "nu",      "name": "Nu"},
    {"id": "xi",      "name": "Xi"},
    {"id": "omicron", "name": "Omicron"},
    {"id": "pi",      "name": "Pi"},
    {"id": "rho",     "name": "Rho"},
    {"id": "sigma",   "name": "Sigma"},
    {"id": "tau",     "name": "Tau"},
    {"id": "upsilon", "name": "Upsilon"},
    {"id": "phi",     "name": "Phi"},
]

_SETTING_KEY = {s["id"]: f"use_{s['id']}" for s in _SITES}


def _site_enabled(site_id):
    key = _SETTING_KEY.get(site_id)
    try:
        return _addon.getSettingBool(key) if key else True
    except Exception:
        return True


if action == 'site_menu':
    site      = params.get('site', [''])[0]
    site_name = params.get('site_name', [site])[0]
    sites_menu.show_site_menu(site, site_name)

elif action == 'site_browse':
    site      = params.get('site', [''])[0]
    url       = params.get('url', [''])[0]
    site_name = params.get('site_name', [site])[0]
    sites_menu.show_browse(site, url, page, site_name)

elif action == 'site_search':
    site      = params.get('site', [''])[0]
    site_name = params.get('site_name', [site])[0]
    sites_menu.show_search(site, site_name)

elif action == 'site_search_new':
    site      = params.get('site', [''])[0]
    site_name = params.get('site_name', [site])[0]
    sites_menu.show_search_new(site, site_name)

elif action == 'site_search_page':
    site      = params.get('site', [''])[0]
    q         = params.get('q', [''])[0]
    site_name = params.get('site_name', [site])[0]
    sites_menu.show_search_page(site, q, page, site_name)

elif action == 'site_item_serial':
    site      = params.get('site', [''])[0]
    url       = params.get('url', [''])[0]
    title     = params.get('title', [''])[0]
    poster    = params.get('poster', [''])[0]
    site_name = params.get('site_name', [site])[0]
    sites_menu.show_item_serial(site, url, title, poster, site_name)

elif action == 'site_seasons':
    site      = params.get('site', [''])[0]
    url       = params.get('url', [''])[0]
    title     = params.get('title', [''])[0]
    poster    = params.get('poster', [''])[0]
    site_name = params.get('site_name', [site])[0]
    sites_menu.show_seasons(site, url, title, poster, site_name)

elif action == 'site_episodes':
    site      = params.get('site', [''])[0]
    url       = params.get('url', [''])[0]
    title     = params.get('title', [''])[0]
    poster    = params.get('poster', [''])[0]
    site_name = params.get('site_name', [site])[0]
    ep_page   = int(params.get('ep_page', [1])[0])
    sites_menu.show_episodes(site, url, title, poster, site_name, ep_page=ep_page)

elif action == 'site_play':
    site  = params.get('site', [''])[0]
    url   = params.get('url', [''])[0]
    title = params.get('title', [''])[0]
    sites_menu.play_item(site, url, title)

elif action == 'site_play_ep':
    site  = params.get('site', [''])[0]
    url   = params.get('url', [''])[0]
    title = params.get('title', [''])[0]
    sites_menu.play_episode(site, url, title)

elif action == 'search_all':
    enabled = [s['id'] for s in _SITES if _site_enabled(s['id'])]
    sites_menu.show_search_all(enabled)

elif action == 'search_all_new':
    enabled = [s['id'] for s in _SITES if _site_enabled(s['id'])]
    sites_menu.show_search_all_new(enabled)

else:
    # Meniu principal — [Caută] primul, apoi câte o intrare per site activ
    xbmcplugin.setPluginCategory(handle, 'Sarmis')
    _icons_base  = xbmcvfs.translatePath('special://home/addons/plugin.video.sarmis/resources/icons/sites/')
    _icon_search = xbmcvfs.translatePath('special://home/addons/plugin.video.sarmis/resources/icons/search.png')

    li_search = xbmcgui.ListItem(label="[Caută]")
    li_search.setArt({'icon': _icon_search, 'thumb': _icon_search})
    xbmcplugin.addDirectoryItem(handle, f'{sys.argv[0]}?action=search_all', listitem=li_search, isFolder=True)

    for site_info in _SITES:
        if not _site_enabled(site_info['id']):
            continue
        li   = xbmcgui.ListItem(label=site_info['name'])
        icon = _icons_base + f'{site_info["id"]}.png'
        li.setArt({'icon': icon, 'thumb': icon})
        url  = f'{sys.argv[0]}?action=site_menu&site={site_info["id"]}&site_name={quote(site_info["name"])}'
        xbmcplugin.addDirectoryItem(handle, url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(handle)
