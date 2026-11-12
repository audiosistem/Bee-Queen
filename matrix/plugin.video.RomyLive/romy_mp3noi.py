# -*- coding: utf-8 -*-
"""Sursa MP3noi.net (mp3noi.ro) pentru RomyLive.

Apare ca intrare separata in meniul principal. Integrarea e locala: wrapper peste
getData (intrarea din meniul principal) si muzicax_list_songs (cai mp3noi://).
Melodiile merg direct ca fisiere mp3 (fara mode nou). MuzicaX.Net ramane neschimbat.
"""
import ast
import html as _html
import re
import sys
import time
import urllib.request
from urllib.parse import quote, urlencode

import xbmc
import xbmcgui
import xbmcplugin

BASE = 'https://mp3noi.ro'
SEARCH_URL = BASE + '/index.php/index.php'
PREFIX = 'mp3noi://'


def _icon():
    """Iconul pluginului RomyLive (icon.png din addon), folosit pe toate intrarile MP3noi."""
    try:
        import xbmcaddon
        path = xbmcaddon.Addon('plugin.video.RomyLive').getAddonInfo('icon')
        if path:
            return path
    except Exception:
        pass
    return ''


MAIN_TITLE = '[COLOR aqua][B]MP3noi.net[/B][/COLOR]'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
TIMEOUT = 20

CATEGORIES = [
    ('Manele 2026', 294580),
    ('Manele', 294581),
    ('Romaneasca 2026', 294582),
    ('Romaneasca', 294583),
    ('Clubbing', 294584),
    ('Trap', 294585),
    ('Petrecere', 294587),
    ('Straina', 294588),
    ('Crestina', 294589),
    ('Colinde', 294590),
    ('Ringtones', 294591),
    ('Diverse Mp3', 294594),
    ('Instrumental', 294595),
]

_TAG_RE = re.compile(r'<[^>]*data-track="([^"]+)"[^>]*>')
_TITLE_RE = re.compile(r'data-title="([^"]*)"')
_IMG_RE = re.compile(r'data-img="([^"]*)"')


def install(ns):
    """Leaga MP3noi.net in meniul principal; apelat o singura data."""
    if ns.get('_romy_mp3noi_installed'):
        return
    if not callable(ns.get('getData')) or not callable(ns.get('muzicax_list_songs')):
        raise ValueError('Structura meniului RomyLive s-a schimbat')
    ns['_romy_mp3noi_installed'] = True

    original_songs = ns['muzicax_list_songs']

    def list_songs(page_url, *args, **kwargs):
        if str(page_url).startswith(PREFIX):
            return _list(ns, str(page_url)[len(PREFIX):])
        return original_songs(page_url, *args, **kwargs)

    original_get = ns['getData']

    def get_data(url, *args, **kwargs):
        if isinstance(url, str) and url.startswith(PREFIX):
            return _list(ns, url[len(PREFIX):])
        if url == ns.get('url_principal'):
            return _main_menu_with_mp3noi(ns, original_get, url, *args, **kwargs)
        return original_get(url, *args, **kwargs)

    ns['muzicax_list_songs'] = list_songs
    ns['getData'] = get_data


def patch_source(source):
    """Insereaza install() inainte de rutarea principala (dupa definitiile remote)."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'params' for t in node.targets):
            if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', '') == 'get_params':
                lines = source.splitlines(True)
                lines.insert(node.lineno - 1, '\nimport romy_mp3noi as _romy_mp3noi\n_romy_mp3noi.install(globals())\n\n')
                return ''.join(lines)
    raise ValueError('Nu am gasit punctul de rutare pentru MP3noi.net')


def _ns_get(ns, key, default=''):
    return ns.get(key, default)


def _plugin_url(ns, url, name):
    return sys.argv[0] + '?' + urlencode({
        'url': url,
        'mode': '70',
        'name': name,
        'fanart': _ns_get(ns, 'fanart_muzicax'),
    })


def _add_folder(ns, handle, label, url, plot=''):
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': _icon(), 'thumb': _icon(), 'fanart': _ns_get(ns, 'fanart_muzicax')})
    li.setInfo('video', {'title': label, 'plot': plot})
    xbmcplugin.addDirectoryItem(handle, _plugin_url(ns, url, label), li, isFolder=True)


def _main_menu_with_mp3noi(ns, original_get, url, *args, **kwargs):
    """Meniul principal: MuzicaX.Net scos, MP3noi.net pus in locul lui (cu logo)."""
    original_add_dir = ns['addDir']

    def add_dir(name, url_item, mode, iconimage, fanart, *args, **kwargs):
        if url_item == ns.get('url_muzicax'):
            # Apelul din canale trimite exact 17 argumente dupa fanart (descriere + 16 campuri).
            # Nu adaugam nimic in plus: al 23-lea argument ajunge la isFolder si Kodi
            # ridica exceptie, iar bucla canalelor afiseaza "Eroare la incarcare".
            rest = list(args)
            if rest:
                rest[0] = 'Melodii si categorii de pe mp3noi.ro'
            return original_add_dir(MAIN_TITLE, PREFIX + 'root', mode, _icon(), fanart, *rest, **kwargs)
        return original_add_dir(name, url_item, mode, iconimage, fanart, *args, **kwargs)

    ns['addDir'] = add_dir
    try:
        return original_get(url, *args, **kwargs)
    finally:
        ns['addDir'] = original_add_dir


def _list_root(ns, handle):
    _add_folder(ns, handle, '[COLOR aqua][B]Cauta melodii[/B][/COLOR]', PREFIX + 'search',
                plot='Cauta melodii pe mp3noi.ro')
    for name, cat_id in CATEGORIES:
        _add_folder(ns, handle, '[COLOR aqua][B]%s[/B][/COLOR]' % name,
                    '%scat/%d/1' % (PREFIX, cat_id), plot='mp3noi.ro - ' + name)


def _fetch(url, data=None):
    headers = {'User-Agent': UA, 'Accept': 'text/html', 'Referer': BASE + '/'}
    body = None
    if data is not None:
        body = urlencode(data).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode('utf-8', errors='replace')


def _parse_tracks(text):
    tracks = []
    for tag in _TAG_RE.finditer(text):
        whole = tag.group(0)
        track = _html.unescape(tag.group(1))
        title_m = _TITLE_RE.search(whole)
        img_m = _IMG_RE.search(whole)
        title = _html.unescape(title_m.group(1)).strip() if title_m else ''
        if not title or not track.startswith(BASE + '/descarca/'):
            continue
        img = _html.unescape(img_m.group(1)) if img_m else ''
        tracks.append((title, track, img))
    return tracks


def _play_url(track):
    return track + '|User-Agent=' + quote(UA, safe='')


_YT_EMBED_RE = re.compile(r'youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})')


def _youtube_id(track):
    """ID-ul video YouTube din pagina melodiei (iframe embed).
    '' = pagina fara clip; None = pagina nu s-a putut citi (nu se memoreaza)."""
    # Linkurile din categorii sunt fisierele .mp3; pagina melodiei are acelasi nume in .html.
    page = track[:-4] + '.html' if track.endswith('.mp3') else track
    last = None
    for attempt in range(1, 4):
        try:
            m = _YT_EMBED_RE.search(_fetch(page))
            return m.group(1) if m else ''
        except Exception as exc:
            last = exc
            time.sleep(0.5 * attempt)
    xbmc.log('[MP3noi] pagina %s: %s' % (track, last), level=xbmc.LOGWARNING)
    return None


_ID_CACHE_FILE = 'mp3noi_yt_ids_v2.json'
_ID_CACHE_TTL = 7 * 24 * 3600


def _cache_path():
    """Fisierul cu ID-urile YouTube memorate, in profilul addonului. '' daca nu e disponibil."""
    try:
        import os
        import xbmcaddon
        import xbmcvfs
        profile = xbmcvfs.translatePath(xbmcaddon.Addon('plugin.video.RomyLive').getAddonInfo('profile'))
        os.makedirs(profile, exist_ok=True)
        return os.path.join(profile, _ID_CACHE_FILE)
    except Exception:
        return ''


def _load_id_cache():
    path = _cache_path()
    if not path:
        return {}
    try:
        import json
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_id_cache(cache):
    path = _cache_path()
    if not path:
        return
    try:
        import json
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(cache, fh)
    except Exception as exc:
        xbmc.log('[MP3noi] cache ID: %s' % exc, level=xbmc.LOGWARNING)


def _resolve_youtube_ids(tracks):
    """ID-urile pentru melodii. Cele memorate (sub 7 zile) nu mai cer pagina din nou."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    cache = _load_id_cache()
    now = time.time()
    result = [None] * len(tracks)
    missing = []
    for i, (_, track, _) in enumerate(tracks):
        hit = cache.get(track)
        if isinstance(hit, list) and len(hit) == 2 and now - hit[1] < _ID_CACHE_TTL:
            result[i] = hit[0]
        else:
            missing.append(i)
    if missing:
        with ThreadPoolExecutor(max_workers=8) as pool:
            fetched = list(pool.map(lambda i: _youtube_id(tracks[i][1]), missing))
        for i, vid in zip(missing, fetched):
            if vid is not None:
                result[i] = vid
                cache[tracks[i][1]] = [vid, now]
        _save_id_cache(cache)
    return [vid or '' for vid in result]


def _add_tracks(ns, handle, tracks):
    """Melodiile se deschid pe YouTube (clipul din pagina melodiei); fara clip -> mp3."""
    from romy_youtube import BASE as YT_BASE
    from romy_youtube_autoplay import enabled, snapshot, uri as autoplay_uri
    ids = _resolve_youtube_ids(tracks)
    autoplay = enabled()
    queue_entries = [{'title': title, 'url': YT_BASE + 'play/?' + urlencode({'video_id': vid}),
                      'thumb': img, 'plot': 'mp3noi.ro', 'folder': False}
                     for (title, _, img), vid in zip(tracks, ids) if vid]
    queue = snapshot(queue_entries) if (autoplay and queue_entries) else ''
    position = 0
    for (title, track, img), vid in zip(tracks, ids):
        li = xbmcgui.ListItem(title)
        li.setArt({'icon': _icon(), 'thumb': img or _icon()})
        if vid:
            if autoplay:
                uri = autoplay_uri(queue, position)
                li.setProperty('IsPlayable', 'false')
            else:
                uri = YT_BASE + 'play/?' + urlencode({'video_id': vid})
                li.setProperty('IsPlayable', 'true')
            position += 1
            li.setInfo('video', {'title': title, 'plot': 'mp3noi.ro'})
            li.setContentLookup(False)
        else:
            uri = _play_url(track)
            li.setProperty('IsPlayable', 'true')
            li.setInfo('music', {'title': title})
        xbmcplugin.addDirectoryItem(handle, uri, li, isFolder=False)


def _list(ns, path):
    handle = int(ns['addon_handle'])
    try:
        if path == 'root':
            _list_root(ns, handle)
        elif path == 'search':
            kb = xbmc.Keyboard('', 'Cauta melodii')
            kb.doModal()
            query = kb.getText().strip() if kb.isConfirmed() else ''
            if query:
                tracks = _parse_tracks(_fetch(SEARCH_URL, {'cuvant': query, 'actiune': ''}))
                if not tracks:
                    xbmcgui.Dialog().notification('MP3noi.net', 'Nu am gasit melodii pentru: ' + query,
                                                  xbmcgui.NOTIFICATION_INFO, 4000)
                _add_tracks(ns, handle, tracks)
        elif path.startswith('cat/'):
            _, cat_id, page = path.split('/')
            cat_id, page = int(cat_id), int(page)
            if page == 1:
                page_url = '%s/categorie_%d.html' % (BASE, cat_id)
            else:
                page_url = '%s/index.php?actiune=categorie&id=%d&pagina=%d' % (BASE, cat_id, page)
            text = _fetch(page_url)
            tracks = _parse_tracks(text)
            _add_tracks(ns, handle, tracks)
            if tracks and ('pagina=%d"' % (page + 1)) in text:
                _add_folder(ns, handle, '[COLOR aqua][B]Pagina urmatoare (%d)[/B][/COLOR]' % (page + 1),
                            '%scat/%d/%d' % (PREFIX, cat_id, page + 1))
        else:
            xbmc.log('[MP3noi] cale necunoscuta: %s' % path, level=xbmc.LOGWARNING)
    except Exception as exc:
        xbmc.log('[MP3noi] eroare: %s' % exc, level=xbmc.LOGERROR)
        xbmcgui.Dialog().notification('MP3noi.net', 'Eroare la incarcare: %s' % exc, xbmcgui.NOTIFICATION_ERROR, 5000)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
