# -*- coding: utf-8 -*-
"""User-maintained genre folders and video lists, independent of remote code."""
import html
import os
import re
from urllib.parse import parse_qs, urljoin, urlparse, urlencode

INDEX_URL = 'https://documentarys.do.am/2026/kodinou/muzica/muzica.txt'
MAX_BYTES = 4 * 1024 * 1024
PAGE_SIZE = 40


def field(block, tag):
    match = re.search(r'<' + tag + r'\s*>(.*?)</' + tag + r'\s*>', block, re.S | re.I)
    return html.unescape(match.group(1).strip()) if match else ''


def http_url(value, base):
    value = urljoin(base, value)
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Adresa listei trebuie sa fie HTTP sau HTTPS.')
    return value


def video_url(value):
    from romy_youtube import BASE, parse_public_link
    parsed = urlparse(value)
    if parsed.scheme == 'plugin':
        if parsed.netloc not in ('plugin.video.RomyLive', 'plugin.video.youtube'):
            raise ValueError('Lista Muzica accepta numai videoclipuri YouTube.')
        if parsed.path not in ('/youtube/play/', '/play/', '/youtube/play', '/play'):
            raise ValueError('Ruta YouTube invalida.')
        value = parse_qs(parsed.query).get('video_id', [''])[0]
    key, ident = parse_public_link(value)
    if key != 'video_id':
        raise ValueError('Foloseste un videoclip, nu un playlist, in <link>.')
    return BASE + 'play/?' + urlencode({'video_id': ident}), ident


def playlist_url(value):
    """Accept a playlist ID or a YouTube link, including watch?v=...&list=...."""
    from romy_youtube import BASE
    value = value.strip()
    if re.fullmatch(r'UC[A-Za-z0-9_-]{22}', value):
        return youtube_channel_url(value)
    if re.fullmatch(r'[A-Za-z0-9_-]{10,150}', value):
        ident = value
    else:
        parsed = urlparse(value if '://' in value else 'https://' + value)
        if (parsed.scheme not in ('http', 'https')
                or parsed.hostname not in ('youtube.com', 'www.youtube.com',
                                           'm.youtube.com', 'music.youtube.com',
                                           'youtu.be', 'www.youtu.be')
                or parsed.username or parsed.password):
            raise ValueError('Introdu un link playlist YouTube sau ID-ul lui in <playlist>.')
        ident = parse_qs(parsed.query).get('list', [''])[0]
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,150}', ident):
            raise ValueError('Lipseste un ID playlist valid (parametrul list) in <playlist>.')
    return BASE + 'public_playlist/?' + urlencode({'list': ident}), ident


def youtube_channel_url(value):
    """Accept a YouTube channel ID or /channel/UC... URL."""
    from romy_youtube import BASE
    value = value.strip()
    if re.fullmatch(r'UC[A-Za-z0-9_-]{22}', value):
        ident = value
    else:
        parsed = urlparse(value if '://' in value else 'https://' + value)
        if (parsed.scheme not in ('http', 'https')
                or parsed.hostname not in ('youtube.com', 'www.youtube.com',
                                           'm.youtube.com', 'music.youtube.com')
                or parsed.username or parsed.password):
            raise ValueError('Introdu un ID de canal YouTube sau link /channel/UC... .')
        match = re.match(r'^/channel/(UC[A-Za-z0-9_-]{22})(?:/|$)', parsed.path)
        if not match:
            raise ValueError('Linkul canalului trebuie sa contina un ID /channel/UC... .')
        ident = match.group(1)
    return BASE + 'public_channel/?' + urlencode({'channel': ident}), ident


def parse_list(text, source):
    entries = []
    for match in re.finditer(r'<(channel|item)\s*>(.*?)</\1\s*>', text, re.S | re.I):
        kind, block = match.group(1).lower(), match.group(2)
        name = field(block, 'name') if kind == 'channel' else field(block, 'title')
        external = field(block, 'externallink')
        playlist = field(block, 'playlist')
        youtube_channel = field(block, 'youtubechannel')
        thumb, fanart = field(block, 'thumbnail'), field(block, 'fanart')
        if not name:
            raise ValueError('Lipseste <name> sau <title> din lista Muzica.')
        if youtube_channel:
            if external or playlist:
                raise ValueError('Foloseste fie <youtubechannel>, fie <playlist>/<externallink> pentru ' + name)
            url, ident = youtube_channel_url(youtube_channel)
            entries.append(dict(title=name, url=url, folder=True,
                                youtube_channel_id=ident, thumb=thumb,
                                fanart=fanart, plot=field(block, 'info')))
        elif playlist:
            if external:
                raise ValueError('Foloseste fie <playlist>, fie <externallink> pentru ' + name)
            url, ident = playlist_url(playlist)
            entries.append(dict(title=name, url=url, folder=True, playlist_id=ident,
                                thumb=thumb, fanart=fanart, plot=field(block, 'info')))
        elif kind == 'channel' or external:
            if not external:
                raise ValueError('Lipseste <externallink> pentru categoria ' + name)
            entries.append(dict(title=name, url=http_url(external, source), folder=True,
                                thumb=thumb, fanart=fanart, plot=field(block, 'info')))
        else:
            url, ident = video_url(field(block, 'link') or field(block, 'utube'))
            entries.append(dict(title=name, url=url, folder=False,
                                thumb=thumb or 'https://i.ytimg.com/vi/' + ident + '/hqdefault.jpg',
                                fanart=fanart, plot=field(block, 'info')))
    if not entries and text.strip():
        raise ValueError('Format nerecunoscut: foloseste blocuri <channel> sau <item>.')
    return entries


def fetch_text(url):
    import requests
    url = http_url(url, url)
    with requests.get(url, timeout=(10, 25), stream=True,
                      headers={'User-Agent': 'RomyLive/YouTube-Catalog', 'Cache-Control': 'no-cache'}) as response:
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('Lista Muzica depaseste 4 MB.')
            chunks.append(chunk)
        return b''.join(chunks).decode('utf-8-sig')


def list_catalog(handle, url='', root=False, page='1'):
    import xbmc
    import xbmcgui
    import xbmcplugin
    from romy_youtube import BASE, _addon, _art, _path
    index = _addon().getSetting('romy.youtube.music.index').strip() or INDEX_URL
    source = index if root else http_url(url, index)
    try:
        text = fetch_text(source)
    except Exception as exc:
        if not root or source != INDEX_URL:
            raise
        # Initial genres work before the owner uploads their index file.
        xbmc.log('[RomyLive Muzica] Index indisponibil; lista initiala: %s' % exc, xbmc.LOGWARNING)
        with open(os.path.join(_path(), 'resources', 'youtube', 'muzica.txt'), encoding='utf-8') as stream:
            text = stream.read()
    entries = parse_list(text, source)
    # Genre index pages contain folders; only paginate a leaf category that
    # consists of videos, leaving the genre/subcategory navigation intact.
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    paginated = not root and bool(entries) and not any(e['folder'] for e in entries)
    all_entries = entries
    total_videos = len(all_entries)
    if paginated:
        start = (page - 1) * PAGE_SIZE
        entries = entries[start:start + PAGE_SIZE]
    from romy_youtube_autoplay import enabled, snapshot, uri
    autoplay = enabled()
    # Paginated video lists queue only the videos on the current page.
    queue = snapshot(entries) if autoplay and any(not e['folder'] for e in entries) else ''
    video_index = 0
    xbmcplugin.setContent(handle, 'files' if any(e['folder'] for e in entries) else 'musicvideos')
    for entry in entries:
        item = xbmcgui.ListItem(entry['title'])
        art = _art()
        if entry['thumb']:
            art.update(icon=entry['thumb'], thumb=entry['thumb'])
        if entry['fanart']:
            art['fanart'] = entry['fanart']
        item.setArt(art)
        item.setInfo('video', {'title': entry['title'], 'plot': entry['plot']})
        target = entry['url']
        if entry['folder']:
            if not entry.get('playlist_id') and not entry.get('youtube_channel_id'):
                target = BASE + 'catalog/?' + urlencode({'url': target})
        else:
            item.setProperty('IsPlayable', 'true')
            item.setContentLookup(False)
            if autoplay:
                target = uri(queue, video_index)
                item.setProperty('IsPlayable', 'false')
            video_index += 1
        # Queue entries still represent playable videos. Marking every item as
        # a folder makes Kodi expand the plugin URLs concurrently, which can
        # launch the whole queue and trigger the engine's busy-dialog retry.
        xbmcplugin.addDirectoryItem(handle, target, item, isFolder=entry['folder'])
    if paginated and page * PAGE_SIZE < total_videos:
        item = xbmcgui.ListItem('Pagina urmatoare (%d–%d din %d)' %
                                (page * PAGE_SIZE + 1, min((page + 1) * PAGE_SIZE, total_videos), total_videos))
        item.setArt(_art())
        target = BASE + 'catalog/?' + urlencode({'url': source, 'page': page + 1})
        xbmcplugin.addDirectoryItem(handle, target, item, isFolder=True)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
