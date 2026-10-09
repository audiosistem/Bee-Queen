# -*- coding: utf-8 -*-
"""Select a tagged Romanian audio stream for RomyLive playback only."""
import json
import os
import re
import time
import unicodedata
import uuid


def normal(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', str(value or '').lower())
                   if not unicodedata.combining(char))


def romanian_score(stream):
    language = normal(stream.get('language')).strip().split('-', 1)[0].split('_', 1)[0]
    name = normal(stream.get('name', ''))
    score = 100 if language in ('ro', 'ron', 'rum', 'romanian', 'romana') else 0
    if re.search(r'\b(?:romanian|romana|roumain|rumano|rumanisch)\b', name):
        score = max(score, 80)
    if score and re.search(r'commentary|comentariu|audio description|audiodescri', name):
        score -= 40
    return score


def choose_romanian(streams, current=None):
    candidates = [item for item in streams if romanian_score(item) > 0
                  and isinstance(item.get('index'), int)]
    if not candidates:
        return None
    best = max(romanian_score(item) for item in candidates)
    ranked = [item for item in candidates if romanian_score(item) == best]
    for item in ranked:
        if item['index'] == current:
            return current
    return ranked[0]['index']


def marker_path():
    import xbmcaddon
    import xbmcvfs
    addon = xbmcaddon.Addon('plugin.video.RomyLive')
    if addon.getSetting('audio_prefer_romanian') == 'false':
        return ''
    profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    os.makedirs(profile, exist_ok=True)
    return os.path.join(profile, 'romy_audio_pending.json')


def mark_playback(path, name=''):
    # Errors here must never interrupt playback.
    try:
        destination = marker_path()
        if not destination or not isinstance(path, str) or not path:
            return
        data = {'id': uuid.uuid4().hex, 'time': time.time(),
                'path': path.split('|', 1)[0], 'name': name or ''}
        temporary = destination + '.' + data['id'] + '.tmp'
        with open(temporary, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(temporary, destination)
    except Exception:
        pass


def read_request(path):
    try:
        with open(path, encoding='utf-8') as handle:
            value = json.load(handle)
        if isinstance(value, dict) and value.get('id') and isinstance(value.get('time'), (int, float)):
            return value
    except (OSError, ValueError):
        pass
    return None


def matches(request, playing_file, item_label=''):
    expected = request.get('path') or ''
    actual = (playing_file or '').split('|', 1)[0]
    if expected and expected == actual:
        return True
    # Delegated plugin playback changes its URL: require the same item label.
    return bool(expected.startswith('plugin://') and request.get('name') and
                normal(request['name']) == normal(item_label))


def install_hooks(ns):
    """Scope the marker to this plugin's namespace, not Kodi's global modules."""
    original_plugin = ns.get('xbmcplugin')
    if original_plugin:
        class PluginProxy:
            def __getattr__(self, key):
                return getattr(original_plugin, key)
            def setResolvedUrl(self, handle, succeeded, item):
                if succeeded:
                    try:
                        mark_playback(item.getPath(), item.getLabel())
                    except Exception:
                        pass
                return original_plugin.setResolvedUrl(handle, succeeded, item)
        ns['xbmcplugin'] = PluginProxy()
    # Old Player.play-based paths don't pass through setResolvedUrl.
    original_resolver = ns.get('resolver')
    if original_resolver:
        def wrapped_resolver(url):
            result = original_resolver(url)
            if result:
                mark_playback(result)
            return result
        ns['resolver'] = wrapped_resolver
    for key in ('individual_player', 'm3u8_player', 'mpd_player'):
        original = ns.get(key)
        if not original:
            continue
        def wrap(function):
            def player(name, url, iconimage=None, description=None, subtitle=None):
                mark_playback(url, name)
                return function(name or '', url, iconimage or '', description or '', subtitle or '')
            return player
        ns[key] = wrap(original)


def run_service():
    import xbmc
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    completed = set()
    attempts = {}

    def rpc(method, params=None):
        message = {'jsonrpc': '2.0', 'id': 1, 'method': method}
        if params is not None:
            message['params'] = params
        response = json.loads(xbmc.executeJSONRPC(json.dumps(message)))
        return response.get('result')

    xbmc.log('[RomyLive Audio] Serviciu activ; preferinta romana doar pentru RomyLive.', xbmc.LOGINFO)
    while not monitor.abortRequested():
        try:
            request = read_request(marker_path())
            if request and request['id'] not in completed and 0 <= time.time() - request['time'] < 120:
                if player.isPlayingVideo():
                    players = rpc('Player.GetActivePlayers') or []
                    video = next((entry['playerid'] for entry in players if entry.get('type') == 'video'), None)
                    if video is not None:
                        result = rpc('Player.GetItem', {'playerid': video, 'properties': ['title']}) or {}
                        item = result.get('item') or {}
                        if matches(request, player.getPlayingFile(), item.get('label')):
                            props = rpc('Player.GetProperties', {'playerid': video,
                                'properties': ['audiostreams', 'currentaudiostream']}) or {}
                            streams = props.get('audiostreams') or []
                            current = (props.get('currentaudiostream') or {}).get('index')
                            selected = choose_romanian(streams, current)
                            if selected is not None:
                                if selected != current:
                                    answer = rpc('Player.SetAudioStream', {'playerid': video, 'stream': selected})
                                    if answer is None:
                                        raise RuntimeError('Kodi nu a acceptat schimbarea pistei audio')
                                xbmc.log('[RomyLive Audio] Pista romana selectata: %s' % selected, xbmc.LOGINFO)
                                completed.add(request['id'])
                            else:
                                attempts[request['id']] = attempts.get(request['id'], 0) + 1
                                # Allow audio tracks to populate after AV startup.
                                if attempts[request['id']] >= 30:
                                    completed.add(request['id'])
                                    xbmc.log('[RomyLive Audio] Nicio pista etichetata romana; audio nemodificat.',
                                             xbmc.LOGINFO)
            if len(completed) > 64:
                completed.clear()
                attempts.clear()
        except Exception:
            # Kodi may briefly report no player/streams during startup or stop.
            pass
        monitor.waitForAbort(0.5)