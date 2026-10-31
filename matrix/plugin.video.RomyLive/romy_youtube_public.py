# -*- coding: utf-8 -*-
"""Public YouTube search/playlist browsing, without Google Data API keys.

Playback is handled by the bundled upstream engine, not by web scraping.
Only anonymous public responses are read; no login or age-restriction bypass.
Session-only preference cookies are not Google account credentials.
"""
import json
import re
from urllib.parse import urlencode, urlsplit

ORIGIN = 'https://www.youtube.com'
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
           'Accept-Language': 'ro-RO,ro;q=0.9,en;q=0.8'}


def extract_json(page, patterns):
    decoder = json.JSONDecoder()
    for pattern in patterns:
        for match in re.finditer(pattern, page):
            try:
                value, _ = decoder.raw_decode(page[match.end():].lstrip())
                if isinstance(value, dict):
                    return value
            except ValueError:
                continue
    return {}


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def text(value):
    if not isinstance(value, dict):
        return ''
    return value.get('simpleText') or value.get('content') or ''.join(run.get('text', '') for run in value.get('runs', []))


def videos_and_token(data):
    videos = []
    seen = set()
    token = ''
    for node in walk(data):
        renderer = node.get('videoRenderer') or node.get('playlistVideoRenderer') or node.get('gridVideoRenderer')
        if renderer:
            video = renderer.get('videoId', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video) or video in seen:
                continue
            if renderer.get('isPlayable') is False:
                continue
            seen.add(video)
            thumbs = renderer.get('thumbnail', {}).get('thumbnails') or []
            videos.append({'id': video, 'title': text(renderer.get('title')) or video,
                           'author': text(renderer.get('ownerText') or renderer.get('shortBylineText')),
                           'duration': text(renderer.get('lengthText')),
                           'thumbnail': thumbs[-1].get('url', '') if thumbs else ''})
        lockup = node.get('lockupViewModel')
        if lockup and lockup.get('contentType') == 'LOCKUP_CONTENT_TYPE_VIDEO':
            video = lockup.get('contentId', '')
            if re.fullmatch(r'[A-Za-z0-9_-]{11}', video) and video not in seen:
                seen.add(video)
                metadata = lockup.get('metadata', {}).get('lockupMetadataViewModel', {})
                rows = metadata.get('metadata', {}).get('contentMetadataViewModel', {}).get('metadataRows', [])
                author = ' '.join(text(part.get('text')) for part in rows[0].get('metadataParts', [])) if rows else ''
                image = lockup.get('contentImage', {}).get('thumbnailViewModel', {})
                thumbs = image.get('image', {}).get('sources') or []
                duration = next((n.get('thumbnailBadgeViewModel', {}).get('text', '') for n in walk(image)
                                 if re.fullmatch(r'\d+(?::\d{2}){1,2}', n.get('thumbnailBadgeViewModel', {}).get('text', ''))), '')
                videos.append({'id': video, 'title': text(metadata.get('title')) or video,
                               'author': author, 'duration': duration,
                               'thumbnail': thumbs[-1].get('url', '') if thumbs else ''})
        continuation = node.get('continuationItemRenderer') or node.get('continuationItemViewModel')
        if continuation and not token:
            for inner in walk(continuation):
                if inner.get('continuationCommand', {}).get('token'):
                    token = inner['continuationCommand']['token']
                    break
    return videos, token


def anonymous_preferences(session):
    # SOCS=CAE records the basic/no-additional-consent choice, not an account.
    # Never import browser cookies or accept all optional tracking (CAI).
    # These live only in this requests session, scoped to HTTPS YouTube.
    session.cookies.set('SOCS', 'CAE', domain='.youtube.com', path='/', secure=True)
    session.cookies.set('PREF', 'hl=ro&tz=UTC', domain='.youtube.com', path='/', secure=True)


def public_response_gate(response):
    response.raise_for_status()
    host = (urlsplit(response.url).hostname or '').lower()
    if host == 'accounts.google.com':
        raise ValueError('YouTube a refuzat accesul anonim pentru aceasta cerere. '
                         'RomyLive nu foloseste autentificare Google; continutul '
                         'privat sau restrictionat nu este disponibil fara cont.')
    return host in ('consent.youtube.com', 'consent.google.com')


def fetch_public(params, kind):
    import requests
    if kind not in ('search', 'playlist', 'channel'):
        raise ValueError('Categorie YouTube necunoscuta')
    with requests.Session() as session:
        anonymous_preferences(session)
        if params.get('token'):
            version = params.get('version', '')
            if not version:
                raise ValueError('Versiunea clientului YouTube lipseste; repeta cautarea.')
            endpoint = 'search' if kind == 'search' else 'browse'
            payload = {'context': {'client': {'clientName': 'WEB', 'clientVersion': version,
                                              'hl': 'ro', 'gl': 'RO'}},
                       'continuation': params['token']}
            response = session.post(ORIGIN + '/youtubei/v1/' + endpoint,
                                    params={'prettyPrint': 'false'}, json=payload,
                                    headers=HEADERS, timeout=(8, 25))
            if public_response_gate(response):
                raise ValueError('Pagina YouTube de preferinte cookie blocheaza accesul anonim. '
                                 'Redeschide playlistul sau cautarea. Nu este o cerere de logare.')
            return response.json(), version
        if kind == 'search':
            page_url = ORIGIN + '/results'
            page_params = {'search_query': params.get('q', ''), 'hl': 'ro', 'gl': 'RO'}
        elif kind == 'playlist':
            page_url = ORIGIN + '/playlist'
            page_params = {'list': params.get('list', ''), 'hl': 'ro'}
        else:
            channel = params.get('channel', '')
            if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}', channel):
                raise ValueError('ID-ul canalului YouTube este invalid.')
            page_url = ORIGIN + '/channel/' + channel + '/videos'
            page_params = {'hl': 'ro', 'gl': 'RO'}
        for attempt in range(2):
            response = session.get(page_url, params=page_params,
                                   headers=HEADERS, timeout=(8, 25))
            if not public_response_gate(response):
                break
            if attempt:
                raise ValueError('Pagina YouTube de preferinte cookie blocheaza accesul anonim '
                                 'pe aceasta conexiune. Nu este o cerere de logare Google.')
            # Retry the same public page once if a regional redirect replaced
            # the preference. Do not submit a consent form or follow a login.
            anonymous_preferences(session)
        data = extract_json(response.text, (r'(?:var\s+)?ytInitialData\s*=\s*',
                                            r'window\["ytInitialData"\]\s*=\s*'))
        config = extract_json(response.text, (r'ytcfg\.set\(\s*',))
        version = config.get('INNERTUBE_CLIENT_VERSION', '')
        if not version:
            match = re.search(r'"INNERTUBE_CLIENT_VERSION"\s*:\s*"([^"]+)"', response.text)
            version = match.group(1) if match else ''
        if not data:
            raise ValueError('YouTube nu a furnizat lista publica. Poate fi o restrictie de retea sau o schimbare a site-ului.')
        return data, version


def list_public(handle, params, kind):
    import xbmcgui
    import xbmcplugin
    from romy_youtube import BASE, _art
    data, version = fetch_public(params, kind)
    videos, token = videos_and_token(data)
    if not videos:
        messages = [text((n.get('alertRenderer') or n.get('alertWithButtonRenderer') or {}).get('text'))
                    for n in walk(data) if 'alertRenderer' in n or 'alertWithButtonRenderer' in n]
        raise ValueError(next((msg for msg in messages if msg), 'Nu am gasit videoclipuri publice disponibile.'))
    xbmcplugin.setContent(handle, 'videos')
    art = _art()
    from romy_youtube_autoplay import enabled, snapshot, uri as autoplay_uri
    autoplay = enabled()
    queue = snapshot([{'title': v['title'], 'url': BASE + 'play/?' + urlencode({'video_id': v['id']}),
                       'thumb': v['thumbnail'], 'plot': v['author'], 'folder': False}
                      for v in videos]) if autoplay else ''
    for video_index, video in enumerate(videos):
        item = xbmcgui.ListItem(video['title'])
        item.setProperty('IsPlayable', 'true')
        item.setArt(dict(art, thumb=video['thumbnail'] or art['thumb']))
        info = {'title': video['title'], 'studio': video['author'],
                'plot': '\n'.join(filter(None, [video['author'], video['duration']]))}
        if video['duration']:
            try:
                seconds = 0
                for part in video['duration'].split(':'):
                    seconds = seconds * 60 + int(part)
                info['duration'] = seconds
            except ValueError:
                pass
        item.setInfo('video', info)
        item.setContentLookup(False)
        uri = BASE + 'play/?' + urlencode({'video_id': video['id']})
        if autoplay:
            uri = autoplay_uri(queue, video_index)
            item.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, uri, item, isFolder=False)
    if token and version:
        next_params = dict(params, token=token, version=version)
        item = xbmcgui.ListItem('Pagina urmatoare')
        item.setArt(art)
        uri = BASE + 'public_' + kind + '/?' + urlencode(next_params)
        xbmcplugin.addDirectoryItem(handle, uri, item, isFolder=True)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
