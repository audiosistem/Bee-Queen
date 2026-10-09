# -*- coding: utf-8 -*-
"""Local DeseneFaine playback fixes, independent of remote addon updates.

Only public players supported by ResolveURL or exposing media sources are
handled. This module does not execute page scripts or bypass DRM/Cloudflare.
"""
import ast
import base64
import html
import re
from urllib.parse import parse_qs, urljoin, urlparse, urlencode

PATCH_VERSION = '1.2.0'
MEDIA = re.compile(r'\.(?:m3u8|mp4|mkv|webm|avi|mpd)(?:[?#|]|$)', re.I)


def _clean(value):
    return html.unescape(value or '').replace('\\/', '/').strip()


def _site(url):
    host = (urlparse(url).hostname or '').lower()
    return host == 'desenefaine.com' or host.endswith('.desenefaine.com')


def _direct(url):
    return bool(url and (url.startswith('plugin://') or
                         (url.startswith(('http://', 'https://')) and MEDIA.search(url))))


def _hidden(url):
    """Decode the site's reversed-hex embed URL; never execute page code."""
    query = parse_qs(urlparse(url).query)
    if query.get('trhide') != ['1']:
        return url
    try:
        decoded = bytes.fromhex(query.get('tid', [''])[0][::-1]).decode('utf-8')
        return decoded if decoded.startswith(('https://', 'http://')) else ''
    except (ValueError, UnicodeError):
        return ''


def _source(page, base):
    # Explicit video/source tags and common JWPlayer/VideoJS source fields.
    patterns = [
        r'<(?:video|source)\b[^>]*\b(?:src|data-src)=["\']([^"\']+)["\']',
        r'["\']?(?:file|src|hls|hlsUrl|manifestUrl)["\']?\s*:\s*["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        for candidate in re.findall(pattern, page or '', re.I):
            candidate = urljoin(base, _clean(candidate))
            if _direct(candidate):
                return candidate
    return ''


def _frames(page, base):
    frames = []
    for candidate in re.findall(
            r'<iframe\b[^>]*\b(?:src|data-src)=["\']([^"\']+)["\']', page or '', re.I):
        candidate = _hidden(urljoin(base, _clean(candidate)))
        if candidate.startswith(('https://', 'http://')) and candidate not in frames:
            frames.append(candidate)
    return frames


def _family_stream(url):
    # The upstream KinoGer resolver lists individual tenants, not every
    # subdomain. Reuse its implementation for the same known host families.
    # No URL is redirected to another tenant and no guessed media ID is used.
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    families = ('strp2p.site', 'p2pplay.pro', 'embed4me.vip',
                '4meplayer.pro', 'seekplays.pro')
    if not any(host == family or host.endswith('.' + family) for family in families):
        return ''
    if not re.fullmatch(r'[A-Za-z0-9]+', parsed.fragment or ''):
        return ''
    from resolveurl.plugins.kinoger import KinoGerResolver
    return KinoGerResolver().get_media_url(host, parsed.fragment) or ''


def patch_source(source):
    """Install overrides immediately before the remote script's route dispatch."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == 'params'
                for target in node.targets) and isinstance(node.value, ast.Call) and (
                isinstance(node.value.func, ast.Name) and node.value.func.id == 'get_params'):
            lines = source.splitlines(True)
            lines.insert(node.lineno - 1,
                         '\nimport desenefaine_fix as _romy_df_fix\n'
                         '_romy_df_fix.install(globals())\n\n')
            return ''.join(lines)
    raise ValueError('Structura codului remote s-a schimbat; patch-ul nu poate fi aplicat.')


def install(ns):
    """Override only the DeseneFaine playback path in the remote namespace."""
    import requests
    import xbmc
    import xbmcgui
    import xbmcplugin
    import resolveurl
    from romy_audio import mark_playback, install_hooks
    from romy_tenant import HOSTS, resolve_tenant
    from romy_byse import resolve_byse, UserCancelled, ByseFailed
    from romy_startup import Counter, wait_and_select

    session = requests.Session()
    stream_params = {}
    failure = {'message': ''}
    ua = ns.get('useragent') or 'Mozilla/5.0'
    originals = {key: ns.get(key) for key in
                 ('_desenefaine_fetch', '_desenefaine_unwrap_player', 'desenefaine_play')}

    def log(message, level=None):
        xbmc.log('[RomyLive Desenefaine fix %s] %s' % (PATCH_VERSION, message),
                 xbmc.LOGINFO if level is None else level)

    def fetch(url, referer='https://desenefaine.com/'):
        try:
            response = session.get(url, headers={
                'User-Agent': ua, 'Referer': referer,
                'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            }, timeout=(10, 20))
            if response.status_code != 200:
                log('HTTP %s de la %s' % (response.status_code, urlparse(url).hostname),
                    xbmc.LOGWARNING)
                return ''
            response.encoding = 'utf-8'
            return response.text
        except requests.RequestException as exc:
            log('Cerere esuata (%s): %s' % (urlparse(url).hostname, type(exc).__name__),
                xbmc.LOGWARNING)
            return ''

    def unwrap(url):
        url = _clean(url)
        seen = set()
        for _ in range(5):
            if not url or url in seen:
                return ''
            seen.add(url)
            if _direct(url) or not _site(url):
                return url
            page = fetch(url)
            if not page:
                return ''
            direct = _source(page, url)
            if direct:
                return direct
            frames = _frames(page, url)
            if not frames:
                return ''
            url = frames[0]
        return ''

    def add_headers(stream, referer):
        if not stream.startswith(('https://', 'http://')):
            return stream
        base, separator, tail = stream.partition('|')
        headers = dict(parse_qs(tail, keep_blank_values=True))
        # Preserve all resolver headers, especially signed Referer/Origin/Cookie.
        for key, value in [('Referer', referer), ('User-Agent', ua)]:
            if key.lower() not in [item.lower() for item in headers]:
                headers[key] = [value]
        if 'cookie' not in [item.lower() for item in headers]:
            request = session.prepare_request(requests.Request('GET', base))
            cookie = request.headers.get('Cookie')
            if cookie:
                headers['Cookie'] = [cookie]
        return base + '|' + urlencode(headers, doseq=True)

    def resolve(provider, depth=0, seen=None, referer='https://desenefaine.com/'):
        seen = seen if seen is not None else set()
        if depth > 3 or provider in seen:
            return '', ''
        seen.add(provider)
        if _direct(provider):
            return provider, referer
        if urlparse(provider).hostname in HOSTS:
            try:
                stream, params = resolve_tenant(provider, session, referer, ua)
                if stream:
                    stream_params[stream.split('|', 1)[0]] = params
                    root = 'https://' + urlparse(provider).hostname
                    stream += '|Origin=' + urlencode({'value': root}).split('=', 1)[1]
                    log('API player nativ: sursa HTTP extrasa.')
                    return stream, root + '/'
            except Exception as exc:
                detail = re.sub(r'https?://\S+', '[URL]', str(exc))[:160]
                failure['message'] = 'Player API: ' + detail
                log(failure['message'], xbmc.LOGWARNING)
        byse_attempted = False
        try:
            byse_attempted, stream = resolve_byse(provider, quiet=True)
            if stream:
                return stream, provider
        except ImportError:
            pass
        except UserCancelled:
            raise
        except ByseFailed as exc:
            byse_attempted = True
            failure['message'] = 'Byse: ' + re.sub(r'https?://\S+', '[URL]', str(exc))[:160]
            log(failure['message'], xbmc.LOGWARNING)
        # ResolveURL already implements host-specific signing/decryption.
        try:
            stream = '' if byse_attempted else resolveurl.resolve(provider)
            if isinstance(stream, str) and stream and (stream != provider or _direct(stream)):
                return stream, provider
        except Exception as exc:
            log('ResolveURL: %s pentru %s' % (type(exc).__name__, urlparse(provider).hostname),
                xbmc.LOGWARNING)
        try:
            stream = _family_stream(provider)
            if isinstance(stream, str) and stream and stream != provider:
                return stream, provider
        except Exception as exc:
            log('Familie player: %s pentru %s' % (type(exc).__name__, urlparse(provider).hostname),
                xbmc.LOGWARNING)
        # Best effort for non-registered hosts exposing standard media sources.
        page = fetch(provider, referer)
        if not page:
            return '', ''
        unpacked = page
        if 'eval(function(p,a,c,k,e,' in page:
            try:
                from resolveurl.lib import helpers
                unpacked += '\n' + helpers.get_packed_data(page)
            except Exception:
                pass
        stream = _source(unpacked, provider)
        if stream:
            return stream, provider
        for frame in _frames(page, provider)[:3]:
            stream, context = resolve(frame, depth + 1, seen, provider)
            if stream:
                return stream, context
        return '', ''

    def failed(message):
        log(message, xbmc.LOGWARNING)
        try:
            xbmcgui.Dialog().notification('Desenefaine.com', 'Incearca mai tarziu :))',
                                          xbmcgui.NOTIFICATION_WARNING, 7000)
        finally:
            xbmcplugin.setResolvedUrl(ns['addon_handle'], False, xbmcgui.ListItem())

    def play(name, url, iconimage=None, description=None, subtitle=None):
        counter = None
        try:
            counter = Counter()
            failure['message'] = ''
            stream_params.clear()
            log('Redare server: %s' % (name or 'necunoscut'))
            if _site(url) and '/film/' in urlparse(url).path:
                page = fetch(url)
                selected = ''
                for attributes, encoded, label in re.findall(
                        r'<a\b([^>]*\bdata-src=["\']([^"\']+)["\'][^>]*)>([\s\S]*?)</a>',
                        page or '', re.I):
                    if not re.search(r'byse(?:wihe)?', label, re.I):
                        continue
                    try:
                        option = encoded + '=' * (-len(encoded) % 4)
                        candidate = base64.urlsafe_b64decode(option).decode('utf-8')
                    except (ValueError, UnicodeError):
                        candidate = _clean(encoded)
                    if candidate.startswith(('http://', 'https://', '/')):
                        selected = urljoin(url, candidate)
                        break
                if not selected:
                    failed('ByseWihe nu este disponibil pentru acest film.')
                    return
                url = selected
            provider = unwrap(url)
            if not provider:
                failed('Sursa nu este accesibila. Verifica kodi.log (HTTP/Cloudflare).')
                return
            log('Host player: %s' % (urlparse(provider).hostname or 'plugin'))
            media_id = urlparse(provider).fragment.split('&', 1)[0]
            if re.fullmatch(r'[A-Za-z0-9]+', media_id or ''):
                log('Identificator player: %s' % media_id)
            stream, referer = resolve(provider, referer=url if _site(url) else 'https://desenefaine.com/')
            if not stream:
                failed(failure['message'] or 'Server nerezolvat. Incearca alt server si trimite kodi.log.')
                return
            stream = add_headers(stream, referer)
            item = xbmcgui.ListItem(label=name or 'Desenefaine.com', path=stream)
            item.setArt({'icon': iconimage or ns.get('DESENEFAINE_ICON', ''),
                         'thumb': iconimage or ns.get('DESENEFAINE_ICON', '')})
            try:
                info = item.getVideoInfoTag()
                info.setTitle(name or 'Desenefaine.com')
                info.setPlot(description or '')
            except AttributeError:
                item.setInfo('video', {'title': name or '', 'plot': description or ''})
            item.setProperty('IsPlayable', 'true')
            item.setContentLookup(False)
            if subtitle:
                item.setSubtitles([subtitle] if isinstance(subtitle, str) else subtitle)
            base, _, headers = stream.partition('|')
            if re.search(r'\.m3u8(?:[?#]|$)', base, re.I):
                item.setMimeType('application/vnd.apple.mpegurl')
                mime = 'hls'
            elif re.search(r'\.mpd(?:[?#]|$)', base, re.I):
                item.setMimeType('application/dash+xml')
                mime = 'mpd'
            else:
                mime = ''
                if re.search(r'\.mp4(?:[?#]|$)', base, re.I):
                    item.setMimeType('video/mp4')
            if mime:
                try:
                    import xbmcaddon
                    xbmcaddon.Addon('inputstream.adaptive')
                    item.setProperty('inputstream', 'inputstream.adaptive')
                    item.setProperty('inputstream.adaptive.manifest_headers', headers)
                    item.setProperty('inputstream.adaptive.stream_headers', headers)
                    params = stream_params.get(base, '')
                    if params:
                        item.setProperty('inputstream.adaptive.manifest_params', params)
                        item.setProperty('inputstream.adaptive.stream_params', params)
                except Exception:
                    if mime == 'mpd':
                        failed('Activeaza InputStream Adaptive pentru aceasta sursa DASH.')
                        return
            log('Sursa rezolvata; predare catre playerul Kodi (%s).' % (mime or 'video'))
            mark_playback(stream, name)
            active_counter = counter
            counter = None
            started = wait_and_select(active_counter, stream,
                lambda: xbmcplugin.setResolvedUrl(ns['addon_handle'], True, item))
            if not started:
                log('Playerul nu a pornit in intervalul de asteptare.', xbmc.LOGWARNING)
                xbmcgui.Dialog().notification('Desenefaine.com', 'Incearca mai tarziu :))',
                                              xbmcgui.NOTIFICATION_WARNING, 7000)
        except UserCancelled:
            failed('Verificare Byse anulata. Alege alt server.')
        except Exception as exc:
            log('Eroare de redare: %s' % type(exc).__name__, xbmc.LOGERROR)
            failed('Eroare de redare. Trimite liniile RomyLive Desenefaine din kodi.log.')
        finally:
            if counter is not None:
                counter.close()

    original_add = ns.get('_desenefaine_add')
    if original_add:
        def direct_movie(name, url, thumb=None, description='', folder=True, mode=1):
            if url.startswith('desenefaine://detail/'):
                try:
                    token = url.split('desenefaine://detail/', 1)[1]
                    target = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)).decode('utf-8')
                    if _site(target) and '/film/' in urlparse(target).path:
                        return original_add(name, target, thumb, description, folder=False, mode=75)
                except (ValueError, UnicodeError):
                    pass
            return original_add(name, url, thumb, description, folder, mode)
        ns['_desenefaine_add'] = direct_movie
    ns['_desenefaine_fetch'] = fetch
    ns['_desenefaine_unwrap_player'] = unwrap
    ns['desenefaine_play'] = play
    install_hooks(ns)
    log('Patch local activ: API tenant, Byse cu timp extins, audio romana automat.')
    return originals