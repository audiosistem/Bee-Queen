# -*- coding: utf-8 -*-
# 9Movies Kodi Plugin  v2.5.3
# TMDB-powered catalog  •  HdHub Stremio addon for streams
# Author: Zeus768

import sys
import re
import os
import json

try:
    from urllib.parse import urlencode, parse_qs, quote, quote_plus
except ImportError:
    from urlparse import parse_qs
    from urllib import urlencode, quote, quote_plus

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import threading
import time

# ── Constants ────────────────────────────────────────────────────────────────

ADDON       = xbmcaddon.Addon()
ADDON_PATH  = ADDON.getAddonInfo('path')
ICON        = os.path.join(ADDON_PATH, 'icon.png')
FANART      = os.path.join(ADDON_PATH, 'fanart.jpg')
MEDIA_PATH  = os.path.join(ADDON_PATH, 'resources', 'lib', 'media')
HANDLE      = int(sys.argv[1])
PLUGIN_URL  = sys.argv[0]


def _media(name):
    """Return absolute path of a media icon, falling back to default ICON."""
    p = os.path.join(MEDIA_PATH, name)
    if os.path.exists(p):
        return p
    return ICON

_TK  = 'f15af109700aab95d564acda15bdcd97'
_TB  = 'https://api.themoviedb.org/3'
_TI  = 'https://image.tmdb.org/t/p/'
_SB  = ('https://hdhub.thevolecitor.qzz.io/'
        'eyJ0b3Jib3giOiJ1bnNldCIsInF1YWxpdGllcyI6IjIxNjBwLDEwODBwLDcyMHAiLCJzb3J0IjoiZGVzYyJ9')

_PROFILE      = ADDON.getAddonInfo('profile')
_HISTORY_FILE = os.path.join(_PROFILE, 'watch_history.json')
_FAVS_FILE    = os.path.join(_PROFILE, 'favourites.json')

# ── Static data ───────────────────────────────────────────────────────────────

MOVIE_GENRES = [
    (28, 'Action'), (12, 'Adventure'), (16, 'Animation'), (35, 'Comedy'),
    (80, 'Crime'), (99, 'Documentary'), (18, 'Drama'), (10751, 'Family'),
    (14, 'Fantasy'), (36, 'History'), (27, 'Horror'), (10402, 'Music'),
    (9648, 'Mystery'), (10749, 'Romance'), (878, 'Science Fiction'),
    (53, 'Thriller'), (10752, 'War'), (37, 'Western'),
]

TV_GENRES = [
    (10759, 'Action & Adventure'), (16, 'Animation'), (35, 'Comedy'),
    (80, 'Crime'), (99, 'Documentary'), (18, 'Drama'), (10751, 'Family'),
    (10762, 'Kids'), (9648, 'Mystery'), (10764, 'Reality'),
    (10765, 'Sci-Fi & Fantasy'), (10768, 'War & Politics'), (37, 'Western'),
]

NETWORKS = [
    ('Netflix',     213), ('Amazon Prime', 1024), ('HBO',        49),
    ('Disney+',    2739), ('Hulu',          453), ('Apple TV+', 2552),
    ('Peacock',    3353), ('Paramount+',   4330), ('BBC',          4),
    ('AMC',         174), ('NBC',             6), ('ABC',           2),
    ('CBS',          16), ('Fox',            19), ('Showtime',     67),
    ('FX',           88), ('Starz',         318),
]

MOVIE_CATS = {
    'new_releases':  ('/movie/now_playing',  {}),
    'trending':      ('/trending/movie/week', {}),
    'oscars':        ('/discover/movie',      {'sort_by': 'vote_average.desc',
                                               'vote_count.gte': '500',
                                               'with_original_language': 'en'}),
    'popular':       ('/movie/popular',       {}),
    'most_watched':  ('/trending/movie/day',  {}),
    'box_office':    ('/discover/movie',      {'sort_by': 'revenue.desc'}),
    'blockbusters':  ('/discover/movie',      {'sort_by': 'revenue.desc',
                                               'vote_count.gte': '500',
                                               'vote_average.gte': '6'}),
}

TV_CATS = {
    'trending':      ('/trending/tv/week',  {}),
    'popular':       ('/tv/popular',        {}),
    'premieres':     ('/tv/on_the_air',     {}),
    'most_watched':  ('/trending/tv/day',   {}),
    'airing_today':  ('/tv/airing_today',   {}),
    'upcoming':      ('/discover/tv',       {'sort_by': 'first_air_date.asc',
                                             'first_air_date.gte': '2025-01-01',
                                             'first_air_date.lte': '2026-12-31'}),
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────

try:
    import requests as _req
    _HAS_REQ = True
except ImportError:
    _HAS_REQ = False

def _san(t):
    if not isinstance(t, str):
        t = str(t)
    return t.replace('\x00', '').replace('\r', '')

def log_info(m): xbmc.log('[9Movies] ' + _san(m), xbmc.LOGINFO)
def log_err(m):  xbmc.log('[9Movies] ERR: ' + _san(m), xbmc.LOGERROR)
def log_dbg(m):  xbmc.log('[9Movies] ' + _san(m), xbmc.LOGDEBUG)

# ── Watch-history helpers ─────────────────────────────────────────────────────

def _load_history():
    try:
        if os.path.exists(_HISTORY_FILE):
            with open(_HISTORY_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_history(h):
    try:
        profile = xbmc.translatePath(_PROFILE)
        if not os.path.exists(profile):
            os.makedirs(profile)
        with open(_HISTORY_FILE, 'w') as f:
            json.dump(h, f)
    except Exception:
        pass

def _get_resume(key):
    entry = _load_history().get(key, {})
    return entry.get('position', 0), entry.get('total', 0)

def _mark_resume(key, position, total, title='', poster=''):
    h = _load_history()
    if position > 30 and (total == 0 or position < total * 0.95):
        h[key] = {'position': position, 'total': total,
                  'title': title, 'poster': poster}
    elif key in h:
        del h[key]
    _save_history(h)

def _clear_resume(key):
    h = _load_history()
    if key in h:
        del h[key]
        _save_history(h)

# ── Favourites helpers ────────────────────────────────────────────────────────

def _load_favs():
    try:
        if os.path.exists(_FAVS_FILE):
            with open(_FAVS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_favs(favs):
    try:
        profile = xbmc.translatePath(_PROFILE)
        if not os.path.exists(profile):
            os.makedirs(profile)
        with open(_FAVS_FILE, 'w') as f:
            json.dump(favs, f)
    except Exception:
        pass

def _add_to_favs(tmdb_id, title, poster, bg, year, plot, media):
    favs = _load_favs()
    key  = '%s_%s' % (media, str(tmdb_id))
    for f in favs:
        if f.get('key') == key:
            xbmcgui.Dialog().notification('9Movies', '"%s" is already in favourites.' % title,
                                          xbmcgui.NOTIFICATION_INFO, 3000)
            return
    favs.append({'key': key, 'tmdb_id': str(tmdb_id), 'title': title,
                 'poster': poster, 'bg': bg, 'year': year, 'plot': plot, 'media': media})
    _save_favs(favs)
    xbmcgui.Dialog().notification('9Movies', 'Added "%s" to Favourites.' % title,
                                  xbmcgui.NOTIFICATION_INFO, 3000)

def _remove_from_favs(key):
    favs = [f for f in _load_favs() if f.get('key') != key]
    _save_favs(favs)
    xbmcgui.Dialog().notification('9Movies', 'Removed from Favourites.',
                                  xbmcgui.NOTIFICATION_INFO, 2000)

# ── Autoplay helpers ──────────────────────────────────────────────────────────

def _autoplay_on():
    return ADDON.getSetting('autoplay') == 'true'

def _autonext_on():
    return ADDON.getSetting('autonext') == 'true'

def _autoplay_quality_pref():
    try:
        idx = int(ADDON.getSetting('autoplay_quality'))
    except Exception:
        idx = 0
    return [None, '4K', '1080p', '720p', '480p'][idx]

def _pick_best_stream(parsed, quality_pref=None):
    if quality_pref:
        preferred = [p for p in parsed if p['quality'] == quality_pref]
        if preferred:
            return preferred[0]
    return parsed[0] if parsed else None

# ── Player monitor ────────────────────────────────────────────────────────────

class _PlayerMonitor(xbmc.Player):
    def __init__(self, history_key, title, poster):
        super(_PlayerMonitor, self).__init__()
        self._key    = history_key
        self._title  = title
        self._poster = poster
        self._ready  = False

    def onPlayBackStarted(self):
        self._ready = True

    def onAVStarted(self):
        self._ready = True

    def onPlayBackStopped(self):
        if not self._ready:
            return
        try:
            pos   = self.getTime()
            total = self.getTotalTime()
            _mark_resume(self._key, pos, total, self._title, self._poster)
        except Exception:
            pass

    def onPlayBackEnded(self):
        _clear_resume(self._key)

# ── HTTP fetchers ─────────────────────────────────────────────────────────────

_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/124.0.0.0 Safari/537.36'),
    'Accept': 'application/json',
}

def _get_json(url):
    log_dbg('GET ' + url)
    try:
        if _HAS_REQ:
            r = _req.get(url, headers=_HEADERS, timeout=20, verify=False)
            if not r.ok:
                log_err('HTTP %d  %s' % (r.status_code, url))
                return None
            return r.json()
        else:
            import urllib.request
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode('utf-8', errors='replace'))
    except Exception as e:
        log_err('fetch failed: %s' % str(e))
        return None

def tmdb(path, extra=None):
    params = {'api_key': _TK, 'language': 'en-US'}
    if extra:
        params.update(extra)
    url = _TB + path + '?' + urlencode(params)
    return _get_json(url)

def stremio_streams(imdb_id, media_type, season=None, episode=None):
    if media_type == 'series' and season is not None and episode is not None:
        resource_id = '%s:%d:%d' % (imdb_id, season, episode)
    else:
        resource_id = imdb_id
    url = '%s/stream/%s/%s.json' % (_SB, media_type, resource_id)
    data = _get_json(url)
    if data and 'streams' in data:
        return data['streams']
    return []

# ── URL / param helpers ───────────────────────────────────────────────────────

def build_url(params):
    return PLUGIN_URL + '?' + urlencode(params)

def get_params():
    raw = sys.argv[2][1:]
    if not raw:
        return {}
    return {k: v[0] for k, v in parse_qs(raw).items()}

# ── Art / info helpers ────────────────────────────────────────────────────────

def poster_url(path, size='w500'):
    if path:
        return _TI + size + path
    return ICON

def backdrop_url(path, size='w1280'):
    if path:
        return _TI + size + path
    return FANART

def set_video_info(li, info):
    try:
        tag = li.getVideoInfoTag()
        if info.get('title'):     tag.setTitle(info['title'])
        if info.get('plot'):      tag.setPlot(info['plot'])
        if info.get('mediatype'): tag.setMediaType(info['mediatype'])
        if info.get('year'):
            try: tag.setYear(int(info['year']))
            except: pass
        if info.get('rating'):
            try: tag.setRating(float(info['rating']))
            except: pass
        if info.get('runtime'):
            try: tag.setDuration(int(info['runtime']) * 60)
            except: pass
        if info.get('director'):
            try: tag.setDirectors([info['director']])
            except: pass
        if info.get('genre'):
            try: tag.setGenres(info['genre'] if isinstance(info['genre'], list) else [info['genre']])
            except: pass
        if info.get('cast'):
            try:
                actors = [xbmc.Actor(a) for a in info['cast'][:10]]
                tag.setCast(actors)
            except: pass
        if info.get('votes'):
            try: tag.setVotes(int(info['votes']))
            except: pass
    except AttributeError:
        safe = {k: v for k, v in info.items()
                if k in ('title', 'plot', 'mediatype', 'year', 'rating', 'duration',
                         'director', 'genre', 'cast', 'votes') and v is not None}
        li.setInfo('video', safe)

def _folder(label, params, thumb=None, fanart=None, plot=''):
    li = xbmcgui.ListItem(label=label)
    t = thumb or ICON
    f = fanart or FANART
    li.setArt({'icon': t, 'thumb': t, 'fanart': f, 'poster': t})
    set_video_info(li, {'title': label, 'plot': plot, 'mediatype': 'video'})
    xbmcplugin.addDirectoryItem(HANDLE, build_url(params), li, isFolder=True)

# ── Stream bento parser ───────────────────────────────────────────────────────

def _fmt_size(size_bytes):
    if size_bytes <= 0:
        return ''
    if size_bytes >= 1073741824:
        return '%.1f GB' % (size_bytes / 1073741824)
    return '%d MB' % (size_bytes // 1048576)


def _parse_stream(stream):
    name  = stream.get('name', '')
    desc  = stream.get('description', '')
    url   = stream.get('url', '')
    hints = stream.get('behaviorHints', {})

    size_bytes = hints.get('videoSize', 0) or 0
    if size_bytes:
        size_str = _fmt_size(size_bytes)
    else:
        m = re.search(r'💾\s*([\d.]+\s*(?:GB|MB))', desc, re.I)
        size_str = m.group(1).strip() if m else ''
        if 'gb' in size_str.lower():
            try: size_bytes = int(float(re.search(r'[\d.]+', size_str).group()) * 1073741824)
            except: pass
        elif 'mb' in size_str.lower():
            try: size_bytes = int(float(re.search(r'[\d.]+', size_str).group()) * 1048576)
            except: pass

    quality  = ''
    haystack = (name + ' ' + desc).upper()
    if '4K' in haystack or '2160P' in haystack or 'UHD' in haystack:
        quality = '4K'
    elif '1080P' in haystack:
        quality = '1080p'
    elif '720P' in haystack:
        quality = '720p'
    elif '480P' in haystack:
        quality = '480p'

    codec = ''
    if re.search(r'HEVC|x265|H\.265|H265', desc, re.I):
        codec = 'HEVC'
    elif re.search(r'AVC|x264|H\.264|H264', desc, re.I):
        codec = 'AVC'

    # Audio language
    audio = ''
    for tag, pat in [
        ('Hindi', r'hindi'), ('Tamil', r'tamil'), ('Telugu', r'telugu'),
        ('Punjabi', r'punjabi'), ('Malayalam', r'malayalam'),
        ('Dual', r'dual.?audio'), ('Multi', r'multi.?audio'),
        ('English', r'english'),
    ]:
        if re.search(pat, desc, re.I):
            audio = tag
            break

    # Audio codec (separate from language)
    audio_codec = ''
    if re.search(r'atmos', desc, re.I):
        audio_codec = 'Atmos'
    elif re.search(r'truehd', desc, re.I):
        audio_codec = 'TrueHD'
    elif re.search(r'\bDTS\b', desc, re.I):
        audio_codec = 'DTS'
    elif re.search(r'\bEAC3\b|\bDDP\b|\bDD\+\b', desc, re.I):
        audio_codec = 'DDP'
    elif re.search(r'\bAC3\b|\bDD\b', desc, re.I):
        audio_codec = 'AC3'
    elif re.search(r'\bAAC\b', desc, re.I):
        audio_codec = 'AAC'

    # Audio channels
    channels = ''
    if re.search(r'7\.1', desc):
        channels = '7.1'
    elif re.search(r'5\.1', desc):
        channels = '5.1'
    elif re.search(r'2\.0', desc):
        channels = '2.0'

    hdr = ''
    if re.search(r'HDR10\+', desc, re.I):           hdr = 'HDR10+'
    elif re.search(r'HDR10', desc, re.I):            hdr = 'HDR10'
    elif re.search(r'DV|Dolby.?Vision', desc, re.I): hdr = 'DV'
    elif re.search(r'\bHDR\b', desc, re.I):          hdr = 'HDR'

    rtype = ''
    if re.search(r'REMUX', desc, re.I):          rtype = 'REMUX'
    elif re.search(r'BluRay|BDRip', desc, re.I): rtype = 'BluRay'
    elif re.search(r'WEB-?DL', desc, re.I):      rtype = 'WEB-DL'
    elif re.search(r'WEBRip', desc, re.I):       rtype = 'WEBRip'
    elif re.search(r'HDCAM|HDTS', desc, re.I):   rtype = 'CAM'

    url_l = url.lower()
    if 'pixeldrain' in url_l:
        server = 'PixelDrain'
    elif 'drive.google' in url_l or 'googleusercontents' in url_l:
        server = 'Drive'
    elif 'telegramcdn' in url_l or 'telegram' in url_l:
        server = 'TG CDN'
    elif 'fsl-bucket' in url_l:
        server = 'FSL CDN'
    elif 'workers.dev' in url_l:
        server = 'CDN'
    elif url.startswith('magnet:') or url.endswith('.torrent'):
        server = 'Torrent'
    else:
        lines  = [l.strip() for l in desc.split('\n') if l.strip()]
        server = ''
        if lines:
            m = re.search(r'^([A-Za-z0-9_\-\.v]+)\s*\|', lines[-1])
            if m:
                server = m.group(1).strip()

    return {
        'quality': quality, 'size_str': size_str, 'size_bytes': size_bytes,
        'codec': codec, 'audio': audio, 'audio_codec': audio_codec,
        'channels': channels, 'hdr': hdr, 'rtype': rtype,
        'server': server, 'url': url, 'raw_name': name, 'raw_desc': desc,
    }


_Q_RANK = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1}


def _sort_streams(parsed_list):
    return sorted(parsed_list,
                  key=lambda x: (_Q_RANK.get(x['quality'], 0), x['size_bytes']),
                  reverse=True)


def _bento_label(p, num=0):
    """
    Quality-tag label. Pipe-separated tokens only — NO movie/show title.
    Example:  4K | REMUX | HDR10 | HEVC | DTS | 5.1 | PixelDrain
    """
    parts = []
    if p['quality']:     parts.append(p['quality'])
    if p['rtype']:       parts.append(p['rtype'])
    if p['hdr']:         parts.append(p['hdr'])
    if p['codec']:       parts.append(p['codec'])
    if p['audio_codec']: parts.append(p['audio_codec'])
    if p['channels']:    parts.append(p['channels'])
    if p['audio']:       parts.append(p['audio'])
    if p['server']:      parts.append(p['server'])
    if p['size_str']:    parts.append(p['size_str'])
    return ' | '.join(parts) if parts else (p['raw_name'] or 'Stream')


def _download_filename(p, fallback_title='stream'):
    """Build a safe filename from parsed stream tags + url extension."""
    tags = []
    if p.get('quality'):     tags.append(p['quality'])
    if p.get('rtype'):       tags.append(p['rtype'])
    if p.get('codec'):       tags.append(p['codec'])
    if p.get('audio_codec'): tags.append(p['audio_codec'])
    if p.get('channels'):    tags.append(p['channels'])
    base = fallback_title.strip() or 'stream'
    base = re.sub(r'[\\/:*?"<>|]+', '_', base)
    if tags:
        base = '%s [%s]' % (base, ' '.join(tags))
    ext = '.mp4'
    url_l = (p.get('url') or '').lower().split('?')[0]
    for e in ('.mkv', '.mp4', '.avi', '.mov', '.webm', '.m4v'):
        if url_l.endswith(e):
            ext = e
            break
    return base + ext


def _build_stream_items(streams, title, poster, bg, plot, media_type,
                        quality_filter='all', history_key=''):
    if not streams:
        return 0

    parsed = _sort_streams([_parse_stream(s) for s in streams])

    if quality_filter and quality_filter != 'all':
        parsed = [p for p in parsed if p['quality'] == quality_filter]

    resume_pos, resume_total = _get_resume(history_key) if history_key else (0, 0)

    for i, p in enumerate(parsed):
        bento      = _bento_label(p)
        display_label = bento
        if resume_pos > 0 and i == 0:
            mins = int(resume_pos) // 60
            secs = int(resume_pos) % 60
            display_label = 'Resume %dm %ds | %s' % (mins, secs, bento)

        li = xbmcgui.ListItem(label=display_label)
        li.setLabel2(bento)
        li.setArt({'thumb': poster, 'icon': poster, 'poster': poster, 'fanart': bg})
        # Set the InfoTag title to the bento (quality) label so Kodi skins
        # display the stream-quality tags instead of the movie/show title.
        # Do NOT pass mediatype 'movie'/'episode' here — that would let Kodi
        # auto-fill the underlying title from the library, overriding ours.
        set_video_info(li, {
            'title':     bento,
            'plot':      p['raw_desc'] or plot,
            'mediatype': 'video',
        })
        li.setProperty('IsPlayable', 'true')
        if resume_pos > 0:
            li.setProperty('ResumeTime', str(int(resume_pos)))
            li.setProperty('TotalTime', str(int(resume_total)) if resume_total else '0')

        # Context menu — Download link to device
        dl_filename = _download_filename(p, title)
        ctx = [
            ('Download',
             'RunPlugin(%s)' % build_url({
                 'mode': 'download_link',
                 'url': p['url'],
                 'filename': dl_filename,
                 'label': bento,
             })),
            ('Copy URL to Clipboard',
             'RunPlugin(%s)' % build_url({
                 'mode': 'show_download', 'url': p['url'], 'title': bento
             })),
        ]
        li.addContextMenuItems(ctx)

        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'mode': 'play', 'url': p['url'], 'title': bento,
                       'history_key': history_key, 'poster': poster}),
            li, isFolder=False)

    return len(parsed)

# ── TMDB rich detail helpers ──────────────────────────────────────────────────

def _year(date_str):
    if date_str and len(date_str) >= 4:
        return date_str[:4]
    return ''

def _get_movie_detail(tmdb_id):
    """Return enriched movie dict with director, cast, genres, runtime."""
    data = tmdb('/movie/%s' % tmdb_id, {'append_to_response': 'credits,videos,recommendations,similar'})
    return data

def _get_tv_detail(tmdb_id):
    """Return enriched TV dict."""
    data = tmdb('/tv/%s' % tmdb_id, {'append_to_response': 'credits,videos,recommendations,similar'})
    return data

def _extract_director(credits):
    if not credits:
        return ''
    for c in credits.get('crew', []):
        if c.get('job') == 'Director':
            return c.get('name', '')
    return ''

def _extract_cast(credits):
    if not credits:
        return []
    return [c.get('name', '') for c in credits.get('cast', [])[:10]]

def _extract_genres(data):
    return [g['name'] for g in data.get('genres', [])]

def _trailer_url(videos):
    """Return YouTube plugin URL for best trailer, or ''."""
    if not videos:
        return ''
    results = videos.get('results', [])
    for vtype in ('Trailer', 'Teaser'):
        for v in results:
            if v.get('site') == 'YouTube' and v.get('type') == vtype:
                return 'plugin://plugin.video.youtube/play/?video_id=' + v['key']
    return ''

def _format_runtime(minutes):
    if not minutes:
        return ''
    h = minutes // 60
    m = minutes % 60
    if h:
        return '%dh %dm' % (h, m)
    return '%dm' % m

# ── Context-menu builder for movie/TV items ───────────────────────────────────

def _movie_context_menu(tmdb_id, title, poster, bg, year, plot):
    return [
        ('Play Trailer',
         'RunPlugin(%s)' % build_url({'mode': 'trailer', 'tmdb_id': str(tmdb_id),
                                      'media': 'movie', 'title': title})),
        ('Extras',
         'Container.Update(%s)' % build_url({'mode': 'extras', 'tmdb_id': str(tmdb_id),
                                              'media': 'movie', 'title': title,
                                              'poster': poster, 'bg': bg})),
        ('Similar Movies',
         'Container.Update(%s)' % build_url({'mode': 'similar_movies',
                                              'tmdb_id': str(tmdb_id), 'title': title,
                                              'poster': poster, 'bg': bg})),
        ('Add to Favourites',
         'RunPlugin(%s)' % build_url({'mode': 'add_fav', 'tmdb_id': str(tmdb_id),
                                      'title': title, 'poster': poster, 'bg': bg,
                                      'year': year, 'plot': plot, 'media': 'movie'})),
    ]

def _tv_context_menu(tmdb_id, title, poster, bg, year, plot):
    return [
        ('Play Trailer',
         'RunPlugin(%s)' % build_url({'mode': 'trailer', 'tmdb_id': str(tmdb_id),
                                      'media': 'tv', 'title': title})),
        ('Extras',
         'Container.Update(%s)' % build_url({'mode': 'extras', 'tmdb_id': str(tmdb_id),
                                              'media': 'tv', 'title': title,
                                              'poster': poster, 'bg': bg})),
        ('Similar Shows',
         'Container.Update(%s)' % build_url({'mode': 'similar_tv',
                                              'tmdb_id': str(tmdb_id), 'title': title,
                                              'poster': poster, 'bg': bg})),
        ('Add to Favourites',
         'RunPlugin(%s)' % build_url({'mode': 'add_fav', 'tmdb_id': str(tmdb_id),
                                      'title': title, 'poster': poster, 'bg': bg,
                                      'year': year, 'plot': plot, 'media': 'tv'})),
    ]

# ── TMDB result parsers ───────────────────────────────────────────────────────

def _add_movie_items(results):
    """Add TMDB movie items — clicks go to rich movie_detail page."""
    autoplay = _autoplay_on()
    for item in results:
        tmdb_id  = item.get('id')
        title    = item.get('title', 'Unknown')
        overview = item.get('overview', '')
        poster   = poster_url(item.get('poster_path'))
        bg       = backdrop_url(item.get('backdrop_path'))
        year     = _year(item.get('release_date', ''))
        rating   = str(item.get('vote_average', ''))

        label = '%s (%s)' % (title, year) if year else title
        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': poster, 'icon': poster, 'poster': poster,
                   'fanart': bg or FANART})
        set_video_info(li, {
            'title': title, 'plot': overview, 'mediatype': 'movie',
            'year': year, 'rating': rating,
        })
        li.addContextMenuItems(_movie_context_menu(
            tmdb_id, title, poster, bg or FANART, year, overview))

        if autoplay:
            li.setProperty('IsPlayable', 'true')
            url = build_url({'mode': 'autoplay_movie', 'tmdb_id': str(tmdb_id),
                             'title': title, 'poster': poster, 'bg': bg or FANART,
                             'year': year, 'plot': overview})
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
        else:
            url = build_url({'mode': 'movie_detail', 'tmdb_id': str(tmdb_id),
                             'title': title, 'poster': poster, 'bg': bg or FANART,
                             'year': year, 'plot': overview})
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

def _add_tv_items(results):
    for item in results:
        tmdb_id  = item.get('id')
        title    = item.get('name', 'Unknown')
        overview = item.get('overview', '')
        poster   = poster_url(item.get('poster_path'))
        bg       = backdrop_url(item.get('backdrop_path'))
        year     = _year(item.get('first_air_date', ''))
        rating   = str(item.get('vote_average', ''))

        label = '%s (%s)' % (title, year) if year else title
        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': poster, 'icon': poster, 'poster': poster,
                   'fanart': bg or FANART})
        set_video_info(li, {
            'title': title, 'plot': overview, 'mediatype': 'tvshow',
            'year': year, 'rating': rating,
        })
        li.addContextMenuItems(_tv_context_menu(
            tmdb_id, title, poster, bg or FANART, year, overview))

        url = build_url({'mode': 'tv_seasons', 'tmdb_id': str(tmdb_id),
                         'title': title, 'poster': poster, 'bg': bg or FANART,
                         'year': year, 'plot': overview})
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

def _next_page_btn(params_dict, page, total_pages):
    if page < total_pages and page < 20:
        nxt = dict(params_dict)
        nxt['page'] = str(page + 1)
        _folder('Next Page  (%d of %d)' % (page + 1, min(total_pages, 20)),
                nxt, thumb=ICON)

# ── Mode handlers ─────────────────────────────────────────────────────────────

def list_main():
    xbmcplugin.setPluginCategory(HANDLE, '9Movies')
    xbmcplugin.setContent(HANDLE, 'videos')
    _folder('Movies',        {'mode': 'movies'},       thumb=_media('movies.png'))
    _folder('TV Shows',      {'mode': 'tv'},           thumb=_media('tvshows.png'))
    _folder('My Downloads',  {'mode': 'downloads'},    thumb=_media('downloads.png'))
    _folder('Favourites',    {'mode': 'favourites'},   thumb=_media('favourites.png'))
    _folder('Search',        {'mode': 'search'},       thumb=_media('search.png'))
    _folder('Settings',      {'mode': 'open_settings'},thumb=_media('settings.png'))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def list_movies_menu():
    xbmcplugin.setPluginCategory(HANDLE, 'Movies')
    xbmcplugin.setContent(HANDLE, 'videos')
    items = [
        ('New Releases',   'new_releases',  'movies_new_releases.png'),
        ('Trending',       'trending',      'movies_trending.png'),
        ('Oscar Winners',  'oscars',        'movies_oscars.png'),
        ('Popular',        'popular',       'movies_popular.png'),
        ('Most Watched',   'most_watched',  'movies_most_watched.png'),
        ('Top Box Office', 'box_office',    'movies_box_office.png'),
        ('Blockbusters',   'blockbusters',  'movies_blockbusters.png'),
        ('Genres',         'genres_movie',  'movies_genres.png'),
        ('Years',          'years',         'movies_years.png'),
    ]
    for label, cat, icon_name in items:
        thumb = _media(icon_name)
        if cat in ('genres_movie', 'years'):
            _folder(label, {'mode': cat}, thumb=thumb)
        else:
            _folder(label, {'mode': 'list_movies', 'cat': cat, 'page': '1',
                            'label': label}, thumb=thumb)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def list_tv_menu():
    xbmcplugin.setPluginCategory(HANDLE, 'TV Shows')
    xbmcplugin.setContent(HANDLE, 'videos')
    items = [
        ('Trending',      'trending',     'tv_trending.png'),
        ('Popular',       'popular',      'tv_popular.png'),
        ('Premieres',     'premieres',    'tv_premieres.png'),
        ('Most Watched',  'most_watched', 'tv_most_watched.png'),
        ('Airing Today',  'airing_today', 'tv_airing_today.png'),
        ('Upcoming',      'upcoming',     'tv_upcoming.png'),
        ('Genres',        'genres_tv',    'tv_genres.png'),
        ('Networks',      'networks',     'tv_networks.png'),
    ]
    for label, cat, icon_name in items:
        thumb = _media(icon_name)
        if cat in ('genres_tv', 'networks'):
            _folder(label, {'mode': cat}, thumb=thumb)
        else:
            _folder(label, {'mode': 'list_tv', 'cat': cat, 'page': '1',
                            'label': label}, thumb=thumb)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_list_movies(params):
    cat       = params.get('cat', 'popular')
    page      = int(params.get('page', '1'))
    cat_label = params.get('label', cat.replace('_', ' ').title())

    xbmcplugin.setPluginCategory(HANDLE, cat_label)
    xbmcplugin.setContent(HANDLE, 'movies')

    path, extra = MOVIE_CATS.get(cat, ('/movie/popular', {}))
    data = tmdb(path, dict(extra, page=page))
    if not data or 'results' not in data:
        xbmcgui.Dialog().notification('9Movies', 'Could not load results.',
                                      xbmcgui.NOTIFICATION_ERROR, 4000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_movie_items([r for r in data['results'] if r.get('poster_path')])
    _next_page_btn({'mode': 'list_movies', 'cat': cat, 'label': cat_label},
                   page, data.get('total_pages', 1))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_list_tv(params):
    cat       = params.get('cat', 'popular')
    page      = int(params.get('page', '1'))
    cat_label = params.get('label', cat.replace('_', ' ').title())

    xbmcplugin.setPluginCategory(HANDLE, cat_label)
    xbmcplugin.setContent(HANDLE, 'tvshows')

    path, extra = TV_CATS.get(cat, ('/tv/popular', {}))
    data = tmdb(path, dict(extra, page=page))
    if not data or 'results' not in data:
        xbmcgui.Dialog().notification('9Movies', 'Could not load results.',
                                      xbmcgui.NOTIFICATION_ERROR, 4000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_tv_items([r for r in data['results'] if r.get('poster_path')])
    _next_page_btn({'mode': 'list_tv', 'cat': cat, 'label': cat_label},
                   page, data.get('total_pages', 1))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_genres_movie():
    xbmcplugin.setPluginCategory(HANDLE, 'Movie Genres')
    xbmcplugin.setContent(HANDLE, 'videos')
    for gid, gname in MOVIE_GENRES:
        thumb = _media('genre_%s.png' % gname.lower().replace(' ', '_'))
        _folder(gname, {'mode': 'list_genre_movie', 'genre_id': str(gid),
                        'label': gname, 'page': '1'}, thumb=thumb)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_genres_tv():
    xbmcplugin.setPluginCategory(HANDLE, 'TV Genres')
    xbmcplugin.setContent(HANDLE, 'videos')
    for gid, gname in TV_GENRES:
        thumb = _media('genre_%s.png' % gname.lower().replace(' ', '_').replace('&', 'and'))
        _folder(gname, {'mode': 'list_genre_tv', 'genre_id': str(gid),
                        'label': gname, 'page': '1'}, thumb=thumb)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_list_genre_movie(params):
    genre_id  = params.get('genre_id', '28')
    page      = int(params.get('page', '1'))
    cat_label = params.get('label', 'Genre')

    xbmcplugin.setPluginCategory(HANDLE, cat_label)
    xbmcplugin.setContent(HANDLE, 'movies')

    data = tmdb('/discover/movie', {
        'with_genres': genre_id, 'sort_by': 'popularity.desc', 'page': page,
    })
    if not data or 'results' not in data:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_movie_items([r for r in data['results'] if r.get('poster_path')])
    _next_page_btn({'mode': 'list_genre_movie', 'genre_id': genre_id,
                    'label': cat_label}, page, data.get('total_pages', 1))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_list_genre_tv(params):
    genre_id  = params.get('genre_id', '18')
    page      = int(params.get('page', '1'))
    cat_label = params.get('label', 'Genre')

    xbmcplugin.setPluginCategory(HANDLE, cat_label)
    xbmcplugin.setContent(HANDLE, 'tvshows')

    data = tmdb('/discover/tv', {
        'with_genres': genre_id, 'sort_by': 'popularity.desc', 'page': page,
    })
    if not data or 'results' not in data:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_tv_items([r for r in data['results'] if r.get('poster_path')])
    _next_page_btn({'mode': 'list_genre_tv', 'genre_id': genre_id,
                    'label': cat_label}, page, data.get('total_pages', 1))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_years():
    xbmcplugin.setPluginCategory(HANDLE, 'Movies by Year')
    xbmcplugin.setContent(HANDLE, 'videos')
    thumb = _media('movies_years.png')
    for y in range(2026, 1979, -1):
        _folder(str(y), {'mode': 'list_year', 'year': str(y),
                         'label': str(y), 'page': '1'}, thumb=thumb)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_list_year(params):
    year      = params.get('year', '2025')
    page      = int(params.get('page', '1'))
    cat_label = params.get('label', year)

    xbmcplugin.setPluginCategory(HANDLE, cat_label)
    xbmcplugin.setContent(HANDLE, 'movies')

    data = tmdb('/discover/movie', {
        'primary_release_year': year, 'sort_by': 'popularity.desc', 'page': page,
    })
    if not data or 'results' not in data:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_movie_items([r for r in data['results'] if r.get('poster_path')])
    _next_page_btn({'mode': 'list_year', 'year': year, 'label': cat_label},
                   page, data.get('total_pages', 1))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_networks():
    xbmcplugin.setPluginCategory(HANDLE, 'TV Networks')
    xbmcplugin.setContent(HANDLE, 'videos')
    for name, nid in NETWORKS:
        logo     = ICON
        net_data = tmdb('/network/%d' % nid)
        if net_data and net_data.get('logo_path'):
            logo = _TI + 'w92' + net_data['logo_path']
        _folder(name, {'mode': 'list_network', 'network_id': str(nid),
                       'label': name, 'page': '1'}, thumb=logo)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_list_network(params):
    network_id = params.get('network_id', '213')
    page       = int(params.get('page', '1'))
    cat_label  = params.get('label', 'Network')

    xbmcplugin.setPluginCategory(HANDLE, cat_label)
    xbmcplugin.setContent(HANDLE, 'tvshows')

    data = tmdb('/discover/tv', {
        'with_networks': network_id, 'sort_by': 'popularity.desc', 'page': page,
    })
    if not data or 'results' not in data:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_tv_items([r for r in data['results'] if r.get('poster_path')])
    _next_page_btn({'mode': 'list_network', 'network_id': network_id,
                    'label': cat_label}, page, data.get('total_pages', 1))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Movie detail page ─────────────────────────────────────────────────────────

def do_movie_detail(params):
    """
    Rich detail page for a movie.  Shows:
      Play Movie  |  Play Trailer  |  Extras  |  Recommendations  |  Similar Movies
    with full metadata in the info panel.
    """
    tmdb_id = params.get('tmdb_id', '')
    title   = params.get('title', 'Movie')
    poster  = params.get('poster', ICON)
    bg      = params.get('bg', FANART)
    year    = params.get('year', '')
    plot    = params.get('plot', '')

    # Fetch full details (credits + videos + recommendations + similar)
    detail = _get_movie_detail(tmdb_id) or {}

    # Enrich from detail
    overview  = detail.get('overview', plot)
    runtime   = detail.get('runtime', 0)
    rating    = detail.get('vote_average', 0)
    genres    = _extract_genres(detail)
    director  = _extract_director(detail.get('credits', {}))
    cast      = _extract_cast(detail.get('credits', {}))
    tagline   = detail.get('tagline', '')
    videos    = detail.get('videos', {})
    recs      = detail.get('recommendations', {}).get('results', [])
    similar   = detail.get('similar', {}).get('results', [])
    has_trailer = bool(_trailer_url(videos))

    # Build rich plot string
    meta_lines = []
    if tagline:
        meta_lines.append(tagline)
    if director:
        meta_lines.append('Director: %s' % director)
    if cast:
        meta_lines.append('Cast: %s' % ', '.join(cast[:5]))
    if genres:
        meta_lines.append('Genre: %s' % ', '.join(genres))
    if runtime:
        meta_lines.append('Runtime: %s' % _format_runtime(runtime))
    if rating:
        meta_lines.append('Rating: %.1f / 10  (TMDB)' % float(rating))
    if overview:
        meta_lines.append('')
        meta_lines.append(overview)
    full_plot = '\n'.join(meta_lines)

    xbmcplugin.setContent(HANDLE, 'movies')
    xbmcplugin.setPluginCategory(HANDLE, title)

    def _detail_li(lbl, thumb_name=None):
        thumb = _media(thumb_name) if thumb_name else poster
        li = xbmcgui.ListItem(label=lbl)
        li.setArt({'thumb': thumb, 'icon': thumb,
                   'poster': poster, 'fanart': bg})
        # InfoTag title MUST match the button label, otherwise Kodi skins
        # will replace the row label with the movie title via InfoTag.Title.
        # mediatype='video' (not 'movie') stops Kodi auto-filling from library.
        set_video_info(li, {
            'title': lbl, 'plot': full_plot, 'mediatype': 'video',
            'year': year, 'rating': str(rating), 'runtime': runtime,
            'director': director, 'genre': genres, 'cast': cast,
        })
        return li

    # 1. Find Link
    li = _detail_li('Find Link', 'detail_find_link.png')
    li.addContextMenuItems(_movie_context_menu(tmdb_id, title, poster, bg, year, overview))
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url({'mode': 'quality_filter', 'next_mode': 'movie_streams',
                   'tmdb_id': tmdb_id, 'title': title, 'poster': poster,
                   'bg': bg, 'year': year, 'plot': overview}),
        li, isFolder=True)

    # 2. Trailer
    if has_trailer:
        li2 = _detail_li('Trailer', 'detail_trailer.png')
        li2.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'mode': 'trailer', 'tmdb_id': tmdb_id,
                       'media': 'movie', 'title': title}),
            li2, isFolder=False)

    # 3. Extras (all videos: teasers, featurettes, BTS…)
    li3 = _detail_li('Extras', 'detail_extras.png')
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url({'mode': 'extras', 'tmdb_id': tmdb_id, 'media': 'movie',
                   'title': title, 'poster': poster, 'bg': bg}),
        li3, isFolder=True)

    # 4. Recommended
    if recs:
        li4 = _detail_li('Recommended', 'detail_recommended.png')
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'mode': 'recommendations', 'tmdb_id': tmdb_id,
                       'media': 'movie', 'title': title}),
            li4, isFolder=True)

    # 5. Similar To
    if similar:
        li5 = _detail_li('Similar To', 'detail_similar.png')
        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'mode': 'similar_movies', 'tmdb_id': tmdb_id, 'title': title,
                       'poster': poster, 'bg': bg}),
            li5, isFolder=True)

    # 6. Add to Favourites
    li6 = _detail_li('Add to Favourites', 'detail_favourite.png')
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url({'mode': 'add_fav', 'tmdb_id': tmdb_id, 'title': title,
                   'poster': poster, 'bg': bg, 'year': year,
                   'plot': overview, 'media': 'movie'}),
        li6, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Trailer ───────────────────────────────────────────────────────────────────

def do_trailer(params):
    tmdb_id = params.get('tmdb_id', '')
    media   = params.get('media', 'movie')
    title   = params.get('title', '')

    videos  = tmdb('/%s/%s/videos' % (media, tmdb_id))
    url     = _trailer_url(videos) if videos else ''

    if not url:
        xbmcgui.Dialog().ok('9Movies', 'No trailer found for [B]%s[/B].' % title)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    li = xbmcgui.ListItem(label='Trailer — ' + title, path=url)
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


# ── Extras ────────────────────────────────────────────────────────────────────

def do_extras(params):
    tmdb_id = params.get('tmdb_id', '')
    media   = params.get('media', 'movie')
    title   = params.get('title', '')
    poster  = params.get('poster', ICON)
    bg      = params.get('bg', FANART)

    videos  = tmdb('/%s/%s/videos' % (media, tmdb_id))
    results = (videos or {}).get('results', [])

    yt_videos = [v for v in results if v.get('site') == 'YouTube']

    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.setPluginCategory(HANDLE, '%s — Extras' % title)

    if not yt_videos:
        xbmcgui.Dialog().ok('9Movies', 'No extras found for [B]%s[/B].' % title)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    for v in yt_videos:
        vtype  = v.get('type', 'Video')
        vname  = v.get('name', vtype)
        label  = '%s  |  %s' % (vtype, vname)
        yt_url = 'plugin://plugin.video.youtube/play/?video_id=' + v['key']

        li = xbmcgui.ListItem(label=label, path=yt_url)
        li.setProperty('IsPlayable', 'true')
        li.setArt({'thumb': 'https://img.youtube.com/vi/%s/mqdefault.jpg' % v['key'],
                   'icon': poster, 'fanart': bg})
        set_video_info(li, {'title': label, 'mediatype': 'video'})
        xbmcplugin.addDirectoryItem(HANDLE, yt_url, li, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Recommendations / Similar ─────────────────────────────────────────────────

def do_recommendations(params):
    tmdb_id = params.get('tmdb_id', '')
    media   = params.get('media', 'movie')
    title   = params.get('title', '')

    data = tmdb('/%s/%s/recommendations' % (media, tmdb_id))
    results = (data or {}).get('results', [])

    xbmcplugin.setContent(HANDLE, 'movies' if media == 'movie' else 'tvshows')
    xbmcplugin.setPluginCategory(HANDLE, 'Recommended — ' + title)

    if not results:
        xbmcgui.Dialog().ok('9Movies', 'No recommendations found.')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if media == 'movie':
        _add_movie_items([r for r in results if r.get('poster_path')])
    else:
        _add_tv_items([r for r in results if r.get('poster_path')])

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_similar_movies(params):
    tmdb_id = params.get('tmdb_id', '')
    title   = params.get('title', '')

    data    = tmdb('/movie/%s/similar' % tmdb_id)
    results = (data or {}).get('results', [])

    xbmcplugin.setContent(HANDLE, 'movies')
    xbmcplugin.setPluginCategory(HANDLE, 'Similar to ' + title)

    if not results:
        xbmcgui.Dialog().ok('9Movies', 'No similar movies found.')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_movie_items([r for r in results if r.get('poster_path')])
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_similar_tv(params):
    tmdb_id = params.get('tmdb_id', '')
    title   = params.get('title', '')

    data    = tmdb('/tv/%s/similar' % tmdb_id)
    results = (data or {}).get('results', [])

    xbmcplugin.setContent(HANDLE, 'tvshows')
    xbmcplugin.setPluginCategory(HANDLE, 'Similar to ' + title)

    if not results:
        xbmcgui.Dialog().ok('9Movies', 'No similar shows found.')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    _add_tv_items([r for r in results if r.get('poster_path')])
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Favourites ────────────────────────────────────────────────────────────────

def do_add_fav(params):
    _add_to_favs(
        params.get('tmdb_id', ''), params.get('title', ''),
        params.get('poster', ICON), params.get('bg', FANART),
        params.get('year', ''), params.get('plot', ''),
        params.get('media', 'movie'),
    )
    xbmcplugin.endOfDirectory(HANDLE, False)


def do_favourites():
    favs = _load_favs()
    xbmcplugin.setContent(HANDLE, 'videos')
    xbmcplugin.setPluginCategory(HANDLE, 'Favourites')

    if not favs:
        xbmcgui.Dialog().ok('9Movies', 'Your favourites list is empty.\n\n'
                            'Add titles using the context menu on any movie or TV show.')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for f in favs:
        tmdb_id = f.get('tmdb_id', '')
        title   = f.get('title', '')
        poster  = f.get('poster', ICON)
        bg      = f.get('bg', FANART)
        year    = f.get('year', '')
        plot    = f.get('plot', '')
        media   = f.get('media', 'movie')
        key     = f.get('key', '')

        label = '%s (%s)' % (title, year) if year else title
        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': poster, 'icon': poster, 'poster': poster, 'fanart': bg})
        set_video_info(li, {'title': title, 'plot': plot, 'mediatype': media,
                            'year': year})

        # Context menu: remove from favourites
        li.addContextMenuItems([
            ('Remove from Favourites',
             'RunPlugin(%s)' % build_url({'mode': 'remove_fav', 'key': key})),
        ])

        if media == 'movie':
            url = build_url({'mode': 'movie_detail', 'tmdb_id': tmdb_id,
                             'title': title, 'poster': poster, 'bg': bg,
                             'year': year, 'plot': plot})
        else:
            url = build_url({'mode': 'tv_seasons', 'tmdb_id': tmdb_id,
                             'title': title, 'poster': poster, 'bg': bg,
                             'year': year, 'plot': plot})
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_remove_fav(params):
    _remove_from_favs(params.get('key', ''))
    xbmcplugin.endOfDirectory(HANDLE, False)
    xbmc.executebuiltin('Container.Refresh')


# ── Downloads ─────────────────────────────────────────────────────────────────

def _download_dir():
    """Resolved on-disk path where downloads go. Reads user-configurable
    setting `download_path` if set, else falls back to addon profile/downloads."""
    raw = ''
    try:
        raw = ADDON.getSetting('download_path') or ''
    except Exception:
        raw = ''
    if not raw:
        raw = 'special://home/userdata/addon_data/%s/downloads/' % ADDON.getAddonInfo('id')
    path = xbmcvfs.translatePath(raw)
    try:
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)
    except Exception:
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except Exception:
            pass
    return path


def _toast(msg, ms=3500, icon=None):
    try:
        xbmcgui.Dialog().notification('9Movies', msg,
                                      icon or xbmcgui.NOTIFICATION_INFO, ms)
    except Exception:
        pass


def _download_worker(url, dest_path, display_label):
    """Background worker: stream URL → dest_path, post toasts on start/done."""
    try:
        _toast('Download started: %s' % display_label, 4000)
        log_info('Download → %s' % dest_path)

        tmp_path = dest_path + '.part'
        bytes_written = 0
        t0 = time.time()

        if _HAS_REQ:
            with _req.get(url, headers=_HEADERS, timeout=30,
                          verify=False, stream=True) as r:
                if not r.ok:
                    raise IOError('HTTP %d' % r.status_code)
                with open(tmp_path, 'wb') as fh:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            fh.write(chunk)
                            bytes_written += len(chunk)
        else:
            import urllib.request
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp, \
                 open(tmp_path, 'wb') as fh:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fh.write(chunk)
                    bytes_written += len(chunk)

        try:
            if xbmcvfs.exists(dest_path):
                xbmcvfs.delete(dest_path)
        except Exception:
            pass
        os.rename(tmp_path, dest_path)

        dur = max(1, int(time.time() - t0))
        size_mb = bytes_written / 1048576.0
        _toast('Download complete: %s  (%.1f MB, %ds)' %
               (display_label, size_mb, dur), 6000)
        log_info('Download complete: %s  %.1f MB' % (dest_path, size_mb))
    except Exception as e:
        log_err('Download failed: %s' % str(e))
        _toast('Download failed: %s' % str(e)[:80], 6000,
               icon=xbmcgui.NOTIFICATION_ERROR)


def do_download_link(params):
    url      = params.get('url', '')
    filename = params.get('filename', 'stream.mp4')
    label    = params.get('label', filename)

    if not url:
        _toast('No URL available to download.',
               icon=xbmcgui.NOTIFICATION_ERROR)
        return

    if url.startswith('magnet:') or url.endswith('.torrent'):
        _toast('Torrent/magnet downloads are not supported.',
               5000, icon=xbmcgui.NOTIFICATION_WARNING)
        return

    target_dir = _download_dir()
    dest_path  = os.path.join(target_dir, filename)

    # If file already exists, ask before overwriting
    if os.path.exists(dest_path):
        if not xbmcgui.Dialog().yesno(
                '9Movies — Download',
                '[B]%s[/B] already exists in your downloads folder.\n\n'
                'Overwrite?' % filename):
            return

    t = threading.Thread(target=_download_worker,
                         args=(url, dest_path, label))
    t.daemon = True
    t.start()


def do_downloads_list():
    """List all files currently in the downloads folder."""
    xbmcplugin.setPluginCategory(HANDLE, 'My Downloads')
    xbmcplugin.setContent(HANDLE, 'videos')

    target_dir = _download_dir()
    try:
        files = sorted(os.listdir(target_dir))
    except Exception:
        files = []

    files = [f for f in files
             if not f.startswith('.') and not f.endswith('.part')]

    if not files:
        _folder('No downloads yet — use "Download" from any link\'s context menu',
                {'mode': 'main'}, thumb=_media('downloads.png'))
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for f in files:
        full = os.path.join(target_dir, f)
        try:
            size = os.path.getsize(full)
        except Exception:
            size = 0
        size_str = _fmt_size(size) if size else ''
        label = '%s  |  %s' % (f, size_str) if size_str else f

        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': _media('downloads.png'),
                   'icon':  _media('downloads.png'),
                   'fanart': FANART})
        set_video_info(li, {'title': f, 'mediatype': 'video'})
        li.setProperty('IsPlayable', 'true')

        ctx = [
            ('Delete',
             'RunPlugin(%s)' % build_url({
                 'mode': 'download_delete', 'filename': f})),
            ('Open Downloads Folder',
             'RunPlugin(%s)' % build_url({'mode': 'download_open_folder'})),
        ]
        li.addContextMenuItems(ctx)

        xbmcplugin.addDirectoryItem(
            HANDLE,
            build_url({'mode': 'play', 'url': full, 'title': f}),
            li, isFolder=False)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(HANDLE)


def do_download_delete(params):
    filename = params.get('filename', '')
    if not filename:
        return
    target = os.path.join(_download_dir(), filename)
    try:
        if os.path.exists(target):
            os.remove(target)
            _toast('Deleted: %s' % filename)
        else:
            _toast('File not found.', icon=xbmcgui.NOTIFICATION_WARNING)
    except Exception as e:
        _toast('Delete failed: %s' % str(e)[:80],
               icon=xbmcgui.NOTIFICATION_ERROR)
    xbmc.executebuiltin('Container.Refresh')


def do_download_open_folder():
    target = _download_dir()
    xbmcgui.Dialog().ok('9Movies — Downloads folder', target)


# ── Download URL dialog (clipboard) ───────────────────────────────────────────

def do_show_download(params):
    url   = params.get('url', '')
    title = params.get('title', 'Stream')
    if not url:
        xbmcgui.Dialog().ok('9Movies', 'No URL available.')
        xbmcplugin.endOfDirectory(HANDLE, False)
        return
    choice = xbmcgui.Dialog().yesno(
        'Download  —  ' + title,
        'Direct URL:\n%s\n\nCopy to clipboard (via Kodi) or open in browser?' % url[:200],
        nolabel='Cancel', yeslabel='Copy URL'
    )
    if choice:
        try:
            xbmc.executebuiltin('Clipboard(%s)' % url)
        except Exception:
            pass
        xbmcgui.Dialog().notification('9Movies', 'URL copied to clipboard.',
                                      xbmcgui.NOTIFICATION_INFO, 3000)
    xbmcplugin.endOfDirectory(HANDLE, False)


# ── Search ────────────────────────────────────────────────────────────────────

def do_search():
    kbd = xbmc.Keyboard('', 'Search Movies & TV Shows')
    kbd.doModal()
    if not kbd.isConfirmed():
        xbmcplugin.endOfDirectory(HANDLE, False)
        return
    query = kbd.getText().strip()
    if not query:
        xbmcplugin.endOfDirectory(HANDLE, False)
        return
    do_search_results({'query': query, 'page': '1'})


def do_search_results(params):
    query = params.get('query', '')
    page  = int(params.get('page', '1'))

    xbmcplugin.setPluginCategory(HANDLE, 'Search: ' + query)
    xbmcplugin.setContent(HANDLE, 'videos')

    data = tmdb('/search/multi', {'query': query, 'page': page,
                                  'include_adult': 'false'})
    if not data or 'results' not in data:
        xbmcgui.Dialog().notification('9Movies', 'No results found.',
                                      xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    movies = [r for r in data['results']
              if r.get('media_type') == 'movie' and r.get('poster_path')]
    tv     = [r for r in data['results']
              if r.get('media_type') == 'tv' and r.get('poster_path')]

    if movies:
        _add_movie_items(movies)
    if tv:
        _add_tv_items(tv)

    _next_page_btn({'mode': 'search_results', 'query': query},
                   page, data.get('total_pages', 1))
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Quality filter menu ───────────────────────────────────────────────────────

_QUALITY_OPTIONS = [
    ('All Qualities', 'all'),
    ('4K only',       '4K'),
    ('1080p only',    '1080p'),
    ('720p only',     '720p'),
    ('480p only',     '480p'),
]

def do_quality_filter(params):
    next_mode = params.get('next_mode', 'movie_streams')
    title     = params.get('title', '')
    poster    = params.get('poster', ICON)
    bg        = params.get('bg', FANART)

    xbmcplugin.setPluginCategory(HANDLE, title)
    xbmcplugin.setContent(HANDLE, 'videos')

    forward = {k: v for k, v in params.items() if k not in ('mode', 'next_mode')}
    forward['mode'] = next_mode

    for label, qval in _QUALITY_OPTIONS:
        fwd = dict(forward, quality=qval)
        li  = xbmcgui.ListItem(label=label)
        li.setArt({'icon': poster, 'thumb': poster, 'fanart': bg})
        set_video_info(li, {'title': label, 'mediatype': 'video'})
        xbmcplugin.addDirectoryItem(HANDLE, build_url(fwd), li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Movie streams ─────────────────────────────────────────────────────────────

def do_movie_streams(params):
    tmdb_id = params.get('tmdb_id', '')
    title   = params.get('title', 'Movie')
    poster  = params.get('poster', ICON)
    bg      = params.get('bg', FANART)
    year    = params.get('year', '')
    plot    = params.get('plot', '')

    ext     = tmdb('/movie/%s/external_ids' % tmdb_id)
    imdb_id = ext.get('imdb_id', '') if ext else ''

    if not imdb_id:
        xbmcgui.Dialog().notification('9Movies', 'No IMDB ID found.',
                                      xbmcgui.NOTIFICATION_WARNING, 5000)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    log_info('Movie: %s  IMDB: %s' % (title, imdb_id))
    streams = stremio_streams(imdb_id, 'movie')

    if not streams:
        xbmcgui.Dialog().ok('9Movies',
            'No streams available for:\n[B]%s[/B]\n\n'
            'The title may not be in the HdHub library yet.' % title)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    quality     = params.get('quality', 'all')
    history_key = 'movie_%s' % imdb_id
    xbmcplugin.setContent(HANDLE, 'movies')
    xbmcplugin.setPluginCategory(HANDLE, title)
    _build_stream_items(streams, title, poster, bg, plot, 'movie',
                        quality_filter=quality, history_key=history_key)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── TV seasons → episodes → streams ──────────────────────────────────────────

def do_tv_seasons(params):
    tmdb_id = params.get('tmdb_id', '')
    title   = params.get('title', 'Show')
    poster  = params.get('poster', ICON)
    bg      = params.get('bg', FANART)
    plot    = params.get('plot', '')

    data = tmdb('/tv/%s' % tmdb_id)
    if not data:
        xbmcgui.Dialog().notification('9Movies', 'Could not load show info.',
                                      xbmcgui.NOTIFICATION_ERROR, 4000)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    ext     = tmdb('/tv/%s/external_ids' % tmdb_id)
    imdb_id = ext.get('imdb_id', '') if ext else ''

    seasons = [s for s in data.get('seasons', [])
               if s.get('season_number', 0) > 0 and s.get('episode_count', 0) > 0]

    if not seasons:
        xbmcgui.Dialog().ok('9Movies', 'No seasons found for [B]%s[/B].' % title)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    xbmcplugin.setContent(HANDLE, 'tvshows')
    xbmcplugin.setPluginCategory(HANDLE, title)

    for s in seasons:
        snum   = s['season_number']
        sname  = s.get('name', 'Season %d' % snum)
        s_air  = _year(s.get('air_date', ''))
        s_plot = s.get('overview', plot)
        s_post = poster_url(s.get('poster_path')) if s.get('poster_path') else poster
        ep_cnt = s.get('episode_count', 0)
        label  = '%s  (%d eps)' % (sname, ep_cnt)
        if s_air:
            label += '  %s' % s_air

        _folder(label,
                {'mode': 'tv_episodes', 'tmdb_id': tmdb_id, 'imdb_id': imdb_id,
                 'season': str(snum), 'title': title, 'poster': s_post,
                 'bg': bg, 'plot': s_plot},
                thumb=s_post, fanart=bg, plot=s_plot)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_tv_episodes(params):
    tmdb_id = params.get('tmdb_id', '')
    imdb_id = params.get('imdb_id', '')
    season  = int(params.get('season', '1'))
    title   = params.get('title', 'Show')
    poster  = params.get('poster', ICON)
    bg      = params.get('bg', FANART)

    data = tmdb('/tv/%s/season/%d' % (tmdb_id, season))
    if not data:
        xbmcgui.Dialog().notification('9Movies', 'Could not load episodes.',
                                      xbmcgui.NOTIFICATION_ERROR, 4000)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    episodes = data.get('episodes', [])
    if not episodes:
        xbmcgui.Dialog().ok('9Movies', 'No episodes found.')
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    cat_title = '%s — Season %d' % (title, season)
    xbmcplugin.setContent(HANDLE, 'episodes')
    xbmcplugin.setPluginCategory(HANDLE, cat_title)

    autoplay = _autoplay_on()

    for ep in episodes:
        enum  = ep.get('episode_number', 0)
        ename = ep.get('name', 'Episode %d' % enum)
        eplot = ep.get('overview', '')
        still = poster_url(ep.get('still_path'), 'w300') if ep.get('still_path') else poster
        label = 'S%02dE%02d  %s' % (season, enum, ename)

        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': still, 'icon': still, 'fanart': bg, 'poster': poster})
        set_video_info(li, {'title': label, 'plot': eplot, 'mediatype': 'episode'})

        if autoplay:
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'mode': 'autoplay_tv', 'imdb_id': imdb_id,
                           'season': str(season), 'episode': str(enum),
                           'title': label, 'poster': still, 'bg': bg}),
                li, isFolder=False)
        else:
            xbmcplugin.addDirectoryItem(
                HANDLE,
                build_url({'mode': 'quality_filter', 'next_mode': 'tv_streams',
                           'imdb_id': imdb_id,
                           'season': str(season), 'episode': str(enum),
                           'title': label, 'poster': still, 'bg': bg,
                           'show_title': title, 'plot': eplot}),
                li, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def do_tv_streams(params):
    imdb_id = params.get('imdb_id', '')
    season  = int(params.get('season', '1'))
    episode = int(params.get('episode', '1'))
    title   = params.get('title', 'Episode')
    poster  = params.get('poster', ICON)
    bg      = params.get('bg', FANART)
    plot    = params.get('plot', '')

    if not imdb_id:
        xbmcgui.Dialog().notification('9Movies',
            'No IMDB ID for this show — cannot fetch streams.',
            xbmcgui.NOTIFICATION_WARNING, 5000)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    log_info('TV streams: %s  S%02dE%02d' % (imdb_id, season, episode))
    streams = stremio_streams(imdb_id, 'series', season, episode)

    if not streams:
        xbmcgui.Dialog().ok('9Movies',
            'No streams found for:\n[B]%s[/B]\n\n'
            'This episode may not be in the HdHub library yet.' % title)
        xbmcplugin.endOfDirectory(HANDLE, False)
        return

    quality     = params.get('quality', 'all')
    history_key = 'tv_%s_s%02de%02d' % (imdb_id, season, episode)
    xbmcplugin.setContent(HANDLE, 'episodes')
    xbmcplugin.setPluginCategory(HANDLE, title)
    _build_stream_items(streams, title, poster, bg, plot, 'tv',
                        quality_filter=quality, history_key=history_key)

    # Next Episode button
    next_ep    = episode + 1
    next_label = 'Next Episode  S%02dE%02d' % (season, next_ep)
    _folder(next_label,
            {'mode': 'quality_filter', 'next_mode': 'tv_streams',
             'imdb_id': imdb_id, 'season': str(season), 'episode': str(next_ep),
             'title': next_label, 'poster': poster, 'bg': bg, 'plot': ''},
            thumb=poster, fanart=bg)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ── Autoplay ──────────────────────────────────────────────────────────────────

def do_autoplay_movie(params):
    tmdb_id = params.get('tmdb_id', '')
    title   = params.get('title', 'Movie')
    poster  = params.get('poster', ICON)

    ext     = tmdb('/movie/%s/external_ids' % tmdb_id)
    imdb_id = ext.get('imdb_id', '') if ext else ''
    if not imdb_id:
        xbmcgui.Dialog().notification('9Movies', 'No IMDB ID found.',
                                      xbmcgui.NOTIFICATION_WARNING, 5000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    streams = stremio_streams(imdb_id, 'movie')
    if not streams:
        xbmcgui.Dialog().ok('9Movies', 'No streams available for:\n[B]%s[/B]' % title)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    parsed = _sort_streams([_parse_stream(s) for s in streams])
    best   = _pick_best_stream(parsed, _autoplay_quality_pref())
    if not best:
        xbmcgui.Dialog().ok('9Movies', 'No matching stream for your quality preference.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    play_video(best['url'], _bento_label(best, num=1),
               history_key='movie_%s' % imdb_id, poster=poster)


def do_autoplay_tv(params):
    imdb_id = params.get('imdb_id', '')
    season  = int(params.get('season', '1'))
    episode = int(params.get('episode', '1'))
    title   = params.get('title', 'Episode')
    poster  = params.get('poster', ICON)

    if not imdb_id:
        xbmcgui.Dialog().notification('9Movies', 'No IMDB ID — cannot autoplay.',
                                      xbmcgui.NOTIFICATION_WARNING, 5000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    streams = stremio_streams(imdb_id, 'series', season, episode)
    if not streams:
        xbmcgui.Dialog().ok('9Movies', 'No streams found for:\n[B]%s[/B]' % title)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    parsed = _sort_streams([_parse_stream(s) for s in streams])
    best   = _pick_best_stream(parsed, _autoplay_quality_pref())
    if not best:
        xbmcgui.Dialog().ok('9Movies', 'No matching stream for your quality preference.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    play_video(best['url'], _bento_label(best, num=1),
               history_key='tv_%s_s%02de%02d' % (imdb_id, season, episode),
               poster=poster)


# ── Playback ──────────────────────────────────────────────────────────────────

def play_video(url, title, history_key='', poster=ICON):
    if not url:
        xbmcgui.Dialog().notification('9Movies', 'No stream URL available.',
                                      xbmcgui.NOTIFICATION_ERROR, 4000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    safe_url = url.replace(' ', '%20')
    log_info('Play: ' + safe_url[:120])

    li = xbmcgui.ListItem(label=title, path=safe_url)
    li.setProperty('IsPlayable', 'true')
    li.setContentLookup(False)

    if history_key:
        resume_pos, resume_total = _get_resume(history_key)
        if resume_pos > 0:
            li.setProperty('ResumeTime', str(int(resume_pos)))
            li.setProperty('TotalTime', str(int(resume_total)) if resume_total else '0')

    low = safe_url.lower()
    if '.m3u8' in low:
        try:
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setMimeType('application/x-mpegURL')
        except Exception:
            li.setMimeType('video/mp4')
    elif '.mkv' in low:
        li.setMimeType('video/x-matroska')
    elif '.mp4' in low:
        li.setMimeType('video/mp4')
    else:
        li.setMimeType('video/mp4')

    xbmcplugin.setResolvedUrl(HANDLE, True, li)

    if history_key:
        monitor = _PlayerMonitor(history_key, title, poster)
        timeout = 0
        while not monitor.isPlaying() and timeout < 15:
            xbmc.sleep(1000)
            timeout += 1
        while monitor.isPlaying():
            xbmc.sleep(2000)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    params = get_params()
    mode   = params.get('mode', 'main')
    log_info('mode=' + mode)

    if   mode == 'main':             list_main()
    elif mode == 'movies':           list_movies_menu()
    elif mode == 'tv':               list_tv_menu()
    elif mode == 'list_movies':      do_list_movies(params)
    elif mode == 'list_tv':          do_list_tv(params)
    elif mode == 'genres_movie':     do_genres_movie()
    elif mode == 'genres_tv':        do_genres_tv()
    elif mode == 'list_genre_movie': do_list_genre_movie(params)
    elif mode == 'list_genre_tv':    do_list_genre_tv(params)
    elif mode == 'years':            do_years()
    elif mode == 'list_year':        do_list_year(params)
    elif mode == 'networks':         do_networks()
    elif mode == 'list_network':     do_list_network(params)
    elif mode == 'movie_detail':     do_movie_detail(params)
    elif mode == 'quality_filter':   do_quality_filter(params)
    elif mode == 'movie_streams':    do_movie_streams(params)
    elif mode == 'tv_seasons':       do_tv_seasons(params)
    elif mode == 'tv_episodes':      do_tv_episodes(params)
    elif mode == 'tv_streams':       do_tv_streams(params)
    elif mode == 'autoplay_movie':   do_autoplay_movie(params)
    elif mode == 'autoplay_tv':      do_autoplay_tv(params)
    elif mode == 'trailer':          do_trailer(params)
    elif mode == 'extras':           do_extras(params)
    elif mode == 'recommendations':  do_recommendations(params)
    elif mode == 'similar_movies':   do_similar_movies(params)
    elif mode == 'similar_tv':       do_similar_tv(params)
    elif mode == 'favourites':       do_favourites()
    elif mode == 'add_fav':          do_add_fav(params)
    elif mode == 'remove_fav':       do_remove_fav(params)
    elif mode == 'show_download':    do_show_download(params)
    elif mode == 'download_link':    do_download_link(params)
    elif mode == 'downloads':        do_downloads_list()
    elif mode == 'download_delete':  do_download_delete(params)
    elif mode == 'download_open_folder': do_download_open_folder()
    elif mode == 'search':           do_search()
    elif mode == 'search_results':   do_search_results(params)
    elif mode == 'play':             play_video(params.get('url', ''),
                                                params.get('title', 'Stream'),
                                                history_key=params.get('history_key', ''),
                                                poster=params.get('poster', ICON))
    elif mode == 'open_settings':    ADDON.openSettings()
    else:                            list_main()


if __name__ == '__main__':
    main()
