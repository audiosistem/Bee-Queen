# -*- coding: utf-8 -*-
"""Snapshot the visible YouTube list and play it as a native Kodi playlist."""
import hashlib
import json
import os
import re
from urllib.parse import urlencode


def enabled():
    from romy_youtube import _addon
    return _addon().getSetting('romy.youtube.autoplay') != 'false'


def snapshot(entries):
    import xbmcvfs
    from romy_youtube import _addon
    videos = [e for e in entries if not e.get('folder')]
    payload = json.dumps(videos, ensure_ascii=False, sort_keys=True)
    token = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    directory = xbmcvfs.translatePath(_addon().getAddonInfo('profile'))
    directory = os.path.join(directory, 'youtube', 'autoplay')
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, token + '.json')
    with open(path, 'w', encoding='utf-8') as stream:
        stream.write(payload)
    # Bound disk use; keep recent list snapshots, not playback credentials.
    files = [os.path.join(directory, name) for name in os.listdir(directory)
             if re.fullmatch(r'[a-f0-9]{64}\.json', name)]
    files.sort(key=os.path.getmtime, reverse=True)
    for old in files[40:]:
        if old != path:
            try:
                os.remove(old)
            except OSError:
                pass
    return token


def uri(token, index):
    from romy_youtube import BASE
    return BASE + 'autoplay/?' + urlencode({'queue': token, 'index': index})


def start(handle, token, index):
    import xbmc
    import xbmcgui
    import xbmcplugin
    import xbmcvfs
    from romy_youtube import _addon, _art, BASE
    if not re.fullmatch(r'[a-f0-9]{64}', token):
        raise ValueError('Lista autoplay invalida. Redeschide categoria.')
    path = os.path.join(xbmcvfs.translatePath(_addon().getAddonInfo('profile')),
                        'youtube', 'autoplay', token + '.json')
    with open(path, encoding='utf-8') as stream:
        entries = json.load(stream)
    index = int(index)
    if not 0 <= index < len(entries):
        raise ValueError('Pozitie autoplay invalida.')
    autoplay = enabled()
    selected = entries[index:] if autoplay else entries[index:index + 1]
    # Validate the entire queue before touching the user's active playlist.
    for entry in selected:
        if not re.fullmatch(re.escape(BASE) + r'play/\?video_id=[A-Za-z0-9_-]{11}', entry['url']):
            raise ValueError('Lista autoplay contine o ruta invalida.')
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()
    for entry in selected:
        item = xbmcgui.ListItem(entry['title'], path=entry['url'])
        art = _art()
        if entry.get('thumb'):
            art.update(thumb=entry['thumb'], icon=entry['thumb'])
        if entry.get('fanart'):
            art['fanart'] = entry['fanart']
        item.setArt(art)
        item.setInfo('video', {'title': entry['title'], 'plot': entry.get('plot', '')})
        item.setProperty('IsPlayable', 'true')
        item.setContentLookup(False)
        playlist.add(entry['url'], item)
    # This is a side-effect action, NOT a directory. A successful empty
    # directory puts /autoplay/ into Kodi's navigation history; returning
    # from fullscreen after Stop can invoke it again and restart the queue.
    # Cancel navigation before playback so the source video list stays open.
    xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
    # Do not loop/shuffle, and do not modify global Kodi autoplay settings.
    xbmc.executebuiltin('PlayerControl(RepeatOff)')
    xbmc.executebuiltin('PlayerControl(RandomOff)')
    # Player().play(playlist) can resume Kodi's previous playlist cursor.
    # Start at queue position zero, which is the video the user selected.
    xbmc.executebuiltin('Playlist.PlayOffset(video,0)')
