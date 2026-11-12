# -*- coding: utf-8 -*-
"""Local TVOnline123 adapter for the existing RomyLive Kodi addon."""
import ast
import base64
import json
import os
import re
import sys
from urllib.parse import parse_qs, urlencode, urlparse

from romy_tvonline_data import SITE, parse_catalog, parse_sources

ADDON_ID = 'plugin.video.RomyLive'
BASE = 'plugin://' + ADDON_ID + '/tvonline123/'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'


def text(value):
    return value.decode('utf-8', 'replace') if isinstance(value, bytes) else str(value or '')


def _addon():
    import xbmcaddon
    return xbmcaddon.Addon(ADDON_ID)


def _art(image=''):
    addon = _addon()
    return {'thumb': image or addon.getAddonInfo('icon'), 'icon': addon.getAddonInfo('icon'),
            'fanart': addon.getAddonInfo('fanart')}


def add_entry(handle, label, action='categories', image='', plot='', **params):
    import xbmcgui
    import xbmcplugin
    item = xbmcgui.ListItem(label)
    item.setArt(_art(image))
    item.setInfo('video', {'title': label, 'plot': plot or 'TVOnline123 - canale pe categorii.'})
    playable = action == 'play'
    if playable:
        item.setProperty('IsPlayable', 'true')
    params['action'] = action
    xbmcplugin.addDirectoryItem(handle, BASE + '?' + urlencode(params), item, isFolder=not playable)


def patch_source(source):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'params' for t in node.targets):
            if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', '') == 'get_params':
                lines = source.splitlines(True)
                lines.insert(node.lineno - 1, '\nimport romy_tvonline123 as _romy_tv123\n_romy_tv123.install(globals())\n\n')
                return ''.join(lines)
    raise ValueError('Nu am gasit punctul de rutare pentru TVOnline123')


def install(ns):
    """Replace only Romania 2; local wrapper is applied after upstream definitions."""
    if ns.get('_romy_tvonline123_installed'):
        return
    if not callable(ns.get('getData')) or not callable(ns.get('addDir')):
        raise ValueError('Structura meniului RomyLive s-a schimbat')
    ns['_romy_tvonline123_installed'] = True
    original_get = ns['getData']

    def get_data(url, *args, **kwargs):
        if text(url).startswith('rdslive://'):
            categories(int(ns['addon_handle']))
            return
        return original_get(url, *args, **kwargs)

    ns['getData'] = get_data
    for function_name in ('addDir', 'addDir2'):
        original = ns.get(function_name)
        if not callable(original):
            continue

        def wrap(original):
            def add_dir(*args, **kwargs):
                url = text(args[1] if len(args) > 1 else kwargs.get('url'))
                name = text(args[0] if args else kwargs.get('name'))
                plain = re.sub(r'\[[^\]]*\]', '', name).lower()
                if url.startswith('rdslive://') or ('romania 2' in plain and 'canale' in plain):
                    return add_entry(int(ns['addon_handle']), '[COLOR aqua][B]Canale TV[/COLOR] [COLOR yellow]Romania 2[/B][/COLOR]',
                                     plot='TVOnline123 in loc de RDS.live: categoriile originale si surse actualizate la redare.')
                return original(*args, **kwargs)
            return add_dir
        ns[function_name] = wrap(original)


def handles(argv=None):
    argv = sys.argv if argv is None else argv
    path = urlparse(argv[0]).path if argv else ''
    return path == '/tvonline123' or path.startswith('/tvonline123/') or bool(_legacy_url(argv))


def _legacy_url(argv):
    if len(argv) < 3:
        return ''
    value = parse_qs(argv[2].lstrip('?')).get('url', [''])[0]
    if value.startswith('rdslive://'):
        return value
    try:
        decoded = base64.b64decode(bytes.fromhex(value), validate=True).decode('utf-8')
        return decoded if decoded.startswith('rdslive://') else ''
    except (ValueError, UnicodeError):
        return ''


def _session():
    import requests
    session = requests.Session()
    session.headers.update({'User-Agent': UA, 'Referer': SITE + '/',
                            'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    return session


def _get(session, url, headers=None):
    response = session.get(url, headers=headers, timeout=(8, 18))
    if response.status_code == 403 or 'Sorry, you have been blocked' in response.text:
        raise RuntimeError('TVOnline123 blocheaza accesul prin Cloudflare (HTTP 403).')
    response.raise_for_status()
    if 'cf-chl-' in response.text or 'Just a moment...' in response.text:
        raise RuntimeError('TVOnline123 solicita verificare Cloudflare in browser.')
    return response


def _cache_path():
    import xbmcvfs
    profile = xbmcvfs.translatePath(_addon().getAddonInfo('profile'))
    os.makedirs(profile, exist_ok=True)
    return os.path.join(profile, 'tvonline123_catalog.json')


def _snapshot():
    path = os.path.join(os.path.dirname(__file__), 'resources', 'tvonline123_snapshot.json')
    with open(path, encoding='utf-8') as file:
        return json.load(file)


def _saved():
    try:
        with open(_cache_path(), encoding='utf-8') as file:
            value = json.load(file)
        if value.get('categories'):
            return value
    except (OSError, ValueError):
        pass
    return _snapshot()


def _save(value):
    try:
        path = _cache_path()
        with open(path + '.tmp', 'w', encoding='utf-8') as file:
            json.dump(value, file, ensure_ascii=False)
        os.replace(path + '.tmp', path)
    except OSError:
        pass


def _notice(message):
    import xbmcgui
    xbmcgui.Dialog().notification('TVOnline123', message, xbmcgui.NOTIFICATION_WARNING, 6000)


def categories(handle):
    import xbmcplugin
    saved = _saved()
    try:
        with _session() as session:
            cats, channels = parse_catalog(_get(session, SITE + '/').text)
        if not cats:
            raise RuntimeError('Nu am gasit categoriile pe site.')
        saved['categories'] = cats
        saved['channels'] = [c for c in saved.get('channels', []) if c.get('category')]
        known = {(c['category'], c['slug']) for c in saved['channels']}
        for channel in channels:
            key = (channel.get('category'), channel['slug'])
            if channel.get('category') and key not in known:
                saved['channels'].append(channel)
                known.add(key)
        _save(saved)
    except Exception as exc:
        _notice(str(exc) + ' Se afiseaza catalogul salvat.')
    xbmcplugin.setContent(handle, 'files')
    for category in saved['categories']:
        add_entry(handle, category['name'], 'channels', name=category['name'], url=category['url'])
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def channels(handle, name, url):
    import xbmcplugin
    parsed = urlparse(url)
    if parsed.hostname != 'www.tvonline123.eu' or not parsed.path.startswith('/categoria/'):
        raise ValueError('Adresa categoriei nu este valida')
    saved = _saved()
    partial = False
    try:
        with _session() as session:
            _, values = parse_catalog(_get(session, url).text, url, name)
        if not values:
            raise RuntimeError('Nu am gasit canale in aceasta categorie.')
        for value in values:
            value['category'] = name
        saved['channels'] = [c for c in saved.get('channels', []) if c.get('category') != name] + values
        saved.setdefault('complete_categories', []).append(name)
        saved['complete_categories'] = sorted(set(saved['complete_categories']))
        _save(saved)
    except Exception as exc:
        values = [c for c in saved.get('channels', []) if c.get('category') == name]
        partial = name not in saved.get('complete_categories', [])
        _notice(str(exc) + (' Lista salvata este partiala.' if partial else ' Se foloseste lista salvata.'))
    xbmcplugin.setContent(handle, 'videos')
    for channel in values:
        add_entry(handle, channel['name'], 'play', channel.get('image', ''),
                  plot=('%s - %s. %s' % (channel['name'], name,
                        'Catalog partial salvat; redarea necesita acces la site.' if partial else 'Sursa este extrasa la fiecare pornire.')),
                  slug=channel['slug'], name=channel['name'])
    xbmcplugin.endOfDirectory(handle, succeeded=bool(values), cacheToDisc=False)


def _stream_headers(session, source, referer):
    import requests
    meta = source.get('meta_config') or {}
    headers = {'User-Agent': UA}
    if not meta.get('meta_referrer_none'):
        headers['Referer'] = referer
    if not meta.get('meta_origin_none'):
        headers['Origin'] = SITE
    prepared = session.prepare_request(requests.Request('GET', source['source_url']))
    if prepared.headers.get('Cookie'):
        headers['Cookie'] = prepared.headers['Cookie']
    return headers


def play(handle, slug, name=''):
    import xbmcgui
    import xbmcplugin
    if not re.fullmatch('[a-zA-Z0-9_-]+', slug):
        raise ValueError('Identificator de canal invalid')
    page = SITE + '/tvlive/?' + urlencode({'url': slug})
    with _session() as session:
        response = _get(session, page)
        sources = parse_sources(response.text)
        if not sources:
            raise RuntimeError('Playerul nu ofera surse compatibile sau necesita deblocare in browser.')
        selected = None
        errors = []
        for source in sources:
            if source.get('keys'):
                errors.append('sursa protejata; nu este implementata redarea DRM')
                continue
            try:
                source = dict(source)
                if source.get('source_type') == 'iframe':
                    import resolveurl
                    resolver = resolveurl.HostedMediaFile(url=source['source_url'])
                    if not resolver.valid_url():
                        raise RuntimeError('player iframe nesuportat de ResolveURL')
                    source['source_url'] = resolver.resolve()
                    if not source['source_url']:
                        raise RuntimeError('playerul iframe nu a returnat un stream')
                    source['source_type'] = 'resolved'
                headers = _stream_headers(session, source, page)
                kind = source.get('source_type', '')
                if kind in ('m3u8', 'mpd'):
                    # requests.Session would otherwise retain Referer even when meta asks for none.
                    request_headers = dict(headers)
                    for key in ('Referer', 'Origin'):
                        if key not in request_headers:
                            request_headers[key] = None
                    manifest = _get(session, source['source_url'], request_headers).text
                    if kind == 'm3u8' and not manifest.lstrip().startswith('#EXTM3U'):
                        raise RuntimeError('serverul nu a returnat un manifest HLS')
                    if kind == 'mpd' and '<MPD' not in manifest:
                        raise RuntimeError('serverul nu a returnat un manifest MPEG-DASH')
                elif kind != 'resolved':
                    raise RuntimeError('tip de sursa nesuportat: ' + kind)
                selected = source, headers
                break
            except Exception as exc:
                # Avoid logging signed URLs from requests error messages.
                message = str(exc)
                errors.append(message if isinstance(exc, RuntimeError) and 'http' not in message
                              else type(exc).__name__)
        if not selected:
            raise RuntimeError('Nicio sursa nu a putut fi deschisa. ' + ', '.join(errors))
    source, headers = selected
    header_string = urlencode(headers)
    stream = source['source_url']
    path = stream if '|' in stream else stream + '|' + header_string
    item = xbmcgui.ListItem(name or slug, path=path)
    item.setArt(_art())
    item.setProperty('IsPlayable', 'true')
    kind = source.get('source_type')
    if kind == 'm3u8':
        item.setMimeType('application/vnd.apple.mpegurl')
        item.setContentLookup(False)
    elif kind == 'mpd':
        try:
            import inputstreamhelper
        except ImportError:
            raise RuntimeError('Instalati addonul InputStream Helper pentru canalele MPEG-DASH.')
        if not inputstreamhelper.Helper('mpd').check_inputstream():
            raise RuntimeError('Este necesar InputStream Adaptive pentru acest canal.')
        item.setMimeType('application/dash+xml')
        item.setContentLookup(False)
        item.setProperty('inputstream', 'inputstream.adaptive')
        item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        item.setProperty('inputstream.adaptive.manifest_headers', header_string)
        item.setProperty('inputstream.adaptive.stream_headers', header_string)
    xbmcplugin.setResolvedUrl(handle, True, item)


def run():
    import xbmc
    import xbmcgui
    import xbmcplugin
    handle = int(sys.argv[1])
    params = {k: v[0] for k, v in parse_qs(sys.argv[2].lstrip('?')).items()}
    action = params.get('action', 'categories')
    # Old RDS favourites lead back to the replacement catalog; channel slugs differ.
    if _legacy_url(sys.argv):
        action = 'categories'
    try:
        if action == 'play':
            play(handle, params.get('slug', ''), params.get('name', ''))
        elif action == 'channels':
            channels(handle, params.get('name', ''), params.get('url', ''))
        else:
            categories(handle)
    except Exception as exc:
        message = str(exc)
        if 'https://' in message or 'http://' in message:
            message = 'Conexiunea cu TVOnline123 a esuat (' + type(exc).__name__ + ').'
        xbmc.log('[RomyLive TVOnline123] ' + message, xbmc.LOGWARNING)
        if action == 'play':
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            xbmcgui.Dialog().ok('TVOnline123', message)
        else:
            _notice(message)
            xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)