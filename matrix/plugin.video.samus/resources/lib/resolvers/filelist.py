# -*- coding: utf-8 -*-
"""FileList.io resolver — cauta pe tracker dupa IMDB ID, returneaza magnet links."""
import re
import hashlib
import requests
import xbmc
import xbmcaddon

_API   = 'https://filelist.io/api.php'
_CATS_MOVIE  = '1,2,3,4,6,19,20,25,26'
_CATS_SERIES = '21,23,27'
_PUBLIC_TRACKERS = [
    'udp://tracker.opentrackr.org:1337/announce',
    'udp://open.tracker.cl:1337/announce',
    'udp://tracker.openbittorrent.com:6969/announce',
]
_HEADERS  = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
_hash_cache = {}   # torrent_id → (info_hash, [tracker_urls], [filenames])


def _credentials():
    addon    = xbmcaddon.Addon()
    username = addon.getSetting('fl_username').strip()
    passkey  = addon.getSetting('fl_passkey').strip()
    return username, passkey


def _fl_api(params):
    username, passkey = _credentials()
    if not username or not passkey:
        return []
    try:
        r = requests.get(_API, params={
            'username': username, 'passkey': passkey,
            'output': 'json', **params
        }, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        xbmc.log(f'[FileList] API error: {e}', xbmc.LOGWARNING)
        return []


def _parse_info_dict(buf):
    """Parsează info dict din bencode; returnează (info_hash, [filename_strings])."""
    info_key = b'4:info'
    idx = buf.find(info_key)
    if idx == -1:
        raise ValueError('No info dict in torrent')
    pos = idx + len(info_key)
    if buf[pos:pos+1] != b'd':
        raise ValueError('Info is not a dict')

    info_start = pos
    depth, p = 1, pos + 1
    while p < len(buf) and depth > 0:
        ch = buf[p:p+1]
        if ch in (b'd', b'l'):
            depth += 1; p += 1
        elif ch == b'e':
            depth -= 1; p += 1
        elif b'0' <= ch <= b'9':
            colon = buf.index(b':', p)
            length = int(buf[p:colon])
            p = colon + 1 + length
        elif ch == b'i':
            end = buf.index(b'e', p + 1)
            p = end + 1
        else:
            p += 1

    info_bytes = buf[info_start:p]
    info_hash  = hashlib.sha1(info_bytes).hexdigest()

    # Extrage fișierele din 4:pathl...e (torrent multi-fișier)
    files = []
    for m in re.finditer(rb'4:pathl', info_bytes):
        fpos  = m.end()
        parts = []
        while fpos < len(info_bytes) and info_bytes[fpos:fpos+1] != b'e':
            nm = re.match(rb'(\d+):', info_bytes[fpos:])
            if not nm:
                break
            n     = int(nm.group(1))
            start = fpos + len(nm.group(0))
            parts.append(info_bytes[start:start + n].decode('utf-8', errors='ignore'))
            fpos  = start + n
        if parts:
            files.append('/'.join(parts))

    # Torrent cu un singur fișier — extrage name
    if not files:
        nm = re.search(rb'4:name(\d+):', info_bytes)
        if nm:
            n = int(nm.group(1))
            files.append(info_bytes[nm.end():nm.end() + n].decode('utf-8', errors='ignore'))

    return info_hash, files


def _extract_trackers(buf):
    """Extrage URL-urile tracker din bencode .torrent."""
    trackers = []
    for m in re.finditer(rb'8:announce(\d+):', buf):
        n   = int(m.group(1))
        url = buf[m.end():m.end() + n].decode('utf-8', errors='ignore')
        if (url.startswith('http') or url.startswith('udp')) and url not in trackers:
            trackers.append(url)
    idx = buf.find(b'13:announce-list')
    if idx != -1:
        chunk = buf[idx:idx + 2048]
        for m in re.finditer(rb'(\d+):(https?://[^\x00-\x1f]{10,}|udp://[^\x00-\x1f]{10,})', chunk):
            n   = int(m.group(1))
            url = m.group(2)[:n].decode('utf-8', errors='ignore')
            if url not in trackers:
                trackers.append(url)
    return trackers


def _get_torrent_data(torrent_id, download_url):
    """Descarcă .torrent și returnează (info_hash, [trackers], [files])."""
    if torrent_id in _hash_cache:
        return _hash_cache[torrent_id]
    try:
        r = requests.get(download_url, headers=_HEADERS, timeout=20, allow_redirects=True)
        r.raise_for_status()
        buf      = r.content
        h, files = _parse_info_dict(buf)
        trackers = _extract_trackers(buf)
        _hash_cache[torrent_id] = (h, trackers, files)
        return h, trackers, files
    except Exception as e:
        xbmc.log(f'[FileList] torrent error for {torrent_id}: {e}', xbmc.LOGWARNING)
        return None, [], []


def _find_episode_idx(files, season, episode):
    """Găsește indexul fișierului pentru S{season}E{episode} într-un season pack."""
    pat = re.compile(rf'[Ss]{season:02d}[Ee]{episode:02d}', re.I)
    # video extensions relevante
    video_ext = re.compile(r'\.(mkv|mp4|avi|ts|m2ts)$', re.I)
    video_files = [(i, f) for i, f in enumerate(files) if video_ext.search(f)]
    for i, fname in video_files:
        if pat.search(fname):
            xbmc.log(f'[FileList] fileIdx={i}  {fname}', xbmc.LOGINFO)
            return i
    # Fallback: dacă sunt mai multe video, încearcă ep-1 ca index
    if len(video_files) >= episode:
        i, fname = video_files[episode - 1]
        xbmc.log(f'[FileList] fileIdx={i} (fallback ep-1)  {fname}', xbmc.LOGINFO)
        return i
    return 0


def _quality(torrent):
    name = torrent.get('name', '')
    cat  = torrent.get('category', '')
    if re.search(r'2160p|4K|UHD', name, re.I) or '4K' in cat: return '4K'
    if re.search(r'1080p', name, re.I): return '1080p'
    if re.search(r'720p', name, re.I):  return '720p'
    if re.search(r'BluRay|Blu-Ray', name, re.I) or 'Blu-Ray' in cat: return 'BluRay'
    if 'HD' in cat: return 'HD'
    return 'SD'


def _fmt_size(b):
    if not b: return ''
    gb = int(b) / (1024**3)
    return f'{gb:.1f} GB' if gb >= 1 else f'{int(b)//(1024**2)} MB'


def _parse(results, season=None, episode=None):
    if season and episode:
        se = f'S{season:02d}E{episode:02d}'
        exact = [t for t in results if se.upper() in t.get('name', '').upper()]
        packs = [t for t in results
                 if f'S{season:02d}'.upper() in t.get('name', '').upper()
                 and not re.search(r'E\d{2}', t.get('name', ''), re.I)]
        filtered = exact if exact else (packs or results)
    else:
        filtered = results

    filtered.sort(key=lambda t: int(t.get('seeders') or 0), reverse=True)
    filtered = filtered[:8]

    sources = []
    for t in filtered:
        tid = t.get('id')
        dl  = t.get('download_link') or t.get('url') or ''
        if not (tid and dl):
            continue
        h, private_trackers, files = _get_torrent_data(str(tid), dl)
        if not h:
            continue

        # fileIdx corect dacă e season pack
        file_idx = 0
        if season and episode and files:
            file_idx = _find_episode_idx(files, season, episode)

        all_trackers = private_trackers + [
            tr for tr in _PUBLIC_TRACKERS if tr not in private_trackers
        ]

        name    = t.get('name', '')
        quality = _quality(t)
        size    = _fmt_size(t.get('size'))
        seeds   = int(t.get('seeders') or 0)
        is_ro   = bool(re.search(r'\.(ro|RO)\.|romanian|subtitrare|dublat', name, re.I)
                       or '-RO' in t.get('category', ''))
        free    = t.get('freeleech') or t.get('free_leech')

        title_parts = [f'{quality}{"  🇷🇴" if is_ro else ""}  👥 {seeds}']
        if size:  title_parts.append(size)
        if free:  title_parts.append('⚡ Freeleech')
        title_parts.append(name[:70] + ('...' if len(name) > 70 else ''))

        sources.append({
            'infoHash':   h,
            'fileIdx':    file_idx,
            'trackers':   [f'tracker:{tr}' for tr in all_trackers],
            'provider':   'FileList',
            'quality':    quality,
            'title_line': '  '.join(title_parts),
            'seeds':      seeds,
            'size':       size,
            'is_torrent': True,
        })
        xbmc.log(f'[FileList] {quality}  {seeds}👥  fileIdx={file_idx}  {name[:50]}', xbmc.LOGINFO)
    return sources


def get_movie_sources(imdb_id):
    results = _fl_api({'action': 'search-torrents', 'type': 'imdb',
                       'query': imdb_id, 'category': _CATS_MOVIE})
    if not results:
        xbmc.log(f'[FileList] 0 rezultate film {imdb_id}', xbmc.LOGINFO)
        return []
    return _parse(results)


def get_tv_sources(imdb_id, season, episode):
    results = _fl_api({'action': 'search-torrents', 'type': 'imdb',
                       'query': imdb_id, 'category': _CATS_SERIES})
    if not results:
        xbmc.log(f'[FileList] 0 rezultate serial {imdb_id}', xbmc.LOGINFO)
        return []
    return _parse(results, season, episode)
