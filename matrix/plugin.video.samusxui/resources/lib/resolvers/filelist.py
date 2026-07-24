# -*- coding: utf-8 -*-
"""FileList.io resolver — cauta pe tracker dupa IMDB ID, returneaza magnet links."""
import os
import re
import hashlib
import tempfile
import requests
import xbmc
import xbmcaddon
import xbmcvfs

_API   = 'https://filelist.io/api.php'
_CATS_MOVIE  = '1,2,3,4,6,19,20,25,26,28'
_CATS_SERIES = '21,23,27'
_FL_TRACKER_PROXY = 'https://api.derzis.xyz/fl/announce'
_PUBLIC_TRACKERS = [
    'udp://tracker.opentrackr.org:1337/announce',
    'udp://open.tracker.cl:1337/announce',
    'udp://tracker.openbittorrent.com:6969/announce',
]
_HEADERS  = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Accept-Encoding': 'gzip, deflate'}
_hash_cache = {}         # torrent_id → (info_hash, [tracker_urls], [filenames])
_torrent_file_cache = {} # torrent_id → filepath of saved .torrent


_SESSION = requests.Session()
_SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})


def _credentials():
    addon    = xbmcaddon.Addon('plugin.video.samusxui')
    username = addon.getSetting('fl_username').strip()
    passkey  = addon.getSetting('fl_passkey').strip()
    password = addon.getSetting('fl_password').strip()
    return username, passkey, password


def _fetch_passkey(username, password):
    """Login cu user+password și extrage passkey-ul din profilul FileList."""
    try:
        sess = requests.Session()
        sess.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

        r = sess.get('https://filelist.io/login.php', timeout=10)
        r.raise_for_status()

        # Extrage toate câmpurile din form pentru a nu rata câmpuri hidden
        form_data = {}
        for inp in re.finditer(r'<input([^>]+)>', r.text, re.I):
            attrs = inp.group(1)
            name_m  = re.search(r'''name=['"]([^'"]+)['"]''', attrs)
            value_m = re.search(r'''value=['"]([^'"]*)['"]''', attrs)
            if name_m:
                form_data[name_m.group(1)] = value_m.group(1) if value_m else ''

        form_data['username'] = username
        form_data['password'] = password

        r2 = sess.post('https://filelist.io/takelogin.php', data=form_data,
                       headers={'Referer': 'https://filelist.io/login.php'},
                       timeout=10, allow_redirects=True)

        if 'takelogin.php' in r2.url or 'login.php' in r2.url:
            xbmc.log('[FileList] Login eșuat — credențiale invalide', xbmc.LOGWARNING)
            return None

        profile = sess.get('https://filelist.io/my.php', timeout=10)

        text = profile.text
        # Passkey apare ca text după checkbox-ul resetpasskey:
        # name='resetpasskey' value='1' /> PASSKEY<br />
        m = re.search(r"name=['\"]resetpasskey['\"][^>]*/>\s*([a-f0-9]{32,})", text, re.I)
        if m:
            passkey = m.group(1)
            xbmc.log(f'[FileList] Passkey obținut automat', xbmc.LOGINFO)
            addon = xbmcaddon.Addon('plugin.video.samusxui')
            addon.setSetting('fl_passkey', passkey)
            return passkey

        xbmc.log('[FileList] Login OK dar passkey negăsit în profil', xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log(f'[FileList] Eroare login: {e}', xbmc.LOGWARNING)
        return None


def _get_passkey():
    """Returnează passkey-ul — din setări sau auto-fetch dacă avem parolă."""
    username, passkey, password = _credentials()
    if not username:
        return None, None
    if passkey:
        return username, passkey
    if password:
        passkey = _fetch_passkey(username, password)
        return username, passkey
    return username, None


def _fl_api(params):
    username, passkey = _get_passkey()
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
    """Parsează info dict din bencode; returnează (info_hash, [(path_str, size_bytes)])."""
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

    # Extrage fișierele (path + size) din lista files din info dict
    # Bencode: 5:filesl d 6:length i<N>e 4:path l<parts>e e ... e
    files = []
    size_by_pos = {}
    for ms in re.finditer(rb'6:lengthi(\d+)e', info_bytes):
        size_by_pos[ms.start()] = int(ms.group(1))

    for m in re.finditer(rb'4:pathl', info_bytes):
        # Găsește cel mai apropiat 6:length dinaintea 4:path
        path_pos = m.start()
        fsize = 0
        closest = max((pos for pos in size_by_pos if pos < path_pos), default=None)
        if closest is not None:
            fsize = size_by_pos[closest]

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
            files.append(('/'.join(parts), fsize))

    # Torrent cu un singur fișier — extrage name + length
    if not files:
        nm = re.search(rb'4:name(\d+):', info_bytes)
        ms = re.search(rb'6:lengthi(\d+)e', info_bytes)
        if nm:
            n = int(nm.group(1))
            name = info_bytes[nm.end():nm.end() + n].decode('utf-8', errors='ignore')
            fsize = int(ms.group(1)) if ms else 0
            files.append((name, fsize))

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


def _replace_bencode_str(buf, old_bytes, new_bytes):
    """Înlocuiește un string bencode, actualizând prefixul de lungime."""
    old_prefix = f'{len(old_bytes)}:'.encode()
    new_prefix = f'{len(new_bytes)}:'.encode()
    result = b''
    idx = 0
    while idx < len(buf):
        pos = buf.find(old_prefix + old_bytes, idx)
        if pos == -1:
            result += buf[idx:]
            break
        result += buf[idx:pos] + new_prefix + new_bytes
        idx = pos + len(old_prefix) + len(old_bytes)
    return result


def _patch_announce(buf):
    """Înlocuiește URL-ul announce FileList cu proxy-ul Thrax.
    Modifică doar câmpul announce (în afara info dict) → infoHash neschimbat.
    """
    m = re.search(rb'8:announce(\d+):', buf)
    if not m:
        return buf
    n = int(m.group(1))
    url_start = m.end()
    original_url = buf[url_start:url_start + n].decode('utf-8', errors='ignore')
    if 'filelist' not in original_url.lower():
        return buf
    pk = re.search(r'passkey=([a-fA-F0-9]+)', original_url)
    if not pk:
        return buf
    proxy_url = f'{_FL_TRACKER_PROXY}?passkey={pk.group(1)}'
    patched = _replace_bencode_str(buf, buf[url_start:url_start + n], proxy_url.encode())
    xbmc.log(f'[FileList] Announce patched → {proxy_url[:60]}', xbmc.LOGINFO)
    return patched


def _get_torrent_data(torrent_id, download_url):
    """Descarcă .torrent și returnează (info_hash, [trackers], [files], torrent_filepath)."""
    if torrent_id in _hash_cache:
        return (*_hash_cache[torrent_id], _torrent_file_cache.get(torrent_id))
    try:
        r = requests.get(download_url, headers=_HEADERS, timeout=20, allow_redirects=True)
        r.raise_for_status()
        buf      = r.content
        h, files = _parse_info_dict(buf)
        trackers = _extract_trackers(buf)
        buf      = _patch_announce(buf)

        tmp_dir = xbmcvfs.translatePath('special://temp/')
        fd, tfile = tempfile.mkstemp(suffix='.torrent', prefix='samus_fl_', dir=tmp_dir)
        os.write(fd, buf)
        os.close(fd)

        _hash_cache[torrent_id] = (h, trackers, files)
        _torrent_file_cache[torrent_id] = tfile
        return h, trackers, files, tfile
    except Exception as e:
        xbmc.log(f'[FileList] torrent error for {torrent_id}: {e}', xbmc.LOGWARNING)
        return None, [], [], None


def _find_episode_idx(files, season, episode):
    """Găsește indexul și numele fișierului pentru S{season}E{episode} într-un season pack.
    Returnează (idx, filename) unde idx e poziția în lista bencode.
    files: [(path_str, size_bytes)]"""
    pat = re.compile(rf'[Ss]{season:02d}[Ee]{episode:02d}', re.I)
    video_ext = re.compile(r'\.(mkv|mp4|avi|ts|m2ts)$', re.I)
    video_files = [(i, path) for i, (path, _sz) in enumerate(files) if video_ext.search(path)]
    for i, fname in video_files:
        if pat.search(fname):
            xbmc.log(f'[FileList] fileIdx={i}  {fname}', xbmc.LOGINFO)
            return i, fname.split('/')[-1]
    # Fallback: dacă sunt mai multe video, încearcă ep-1 ca index
    if len(video_files) >= episode:
        i, fname = video_files[episode - 1]
        xbmc.log(f'[FileList] fileIdx={i} (fallback ep-1)  {fname}', xbmc.LOGINFO)
        return i, fname.split('/')[-1]
    return 0, None


def _find_bdmv_idx(files):
    """Găsește indexul celui mai mare fișier .m2ts din structura BDMV (= filmul principal).
    files: [(path_str, size_bytes)]"""
    m2ts_files = [
        (i, path, sz) for i, (path, sz) in enumerate(files)
        if path.lower().endswith('.m2ts') and 'STREAM' in path
    ]
    if not m2ts_files:
        m2ts_files = [(i, path, sz) for i, (path, sz) in enumerate(files)
                      if path.lower().endswith('.m2ts')]
    if not m2ts_files:
        return 0, None
    # Cel mai mare m2ts = filmul principal; dacă dimensiunile sunt 0 (parse eșuat),
    # fallback: m2ts cu numărul de fișier cel mai mare (00040 > 00007)
    if all(sz == 0 for _, _, sz in m2ts_files):
        best = max(m2ts_files, key=lambda x: x[1].split('/')[-1])
    else:
        best = max(m2ts_files, key=lambda x: x[2])
    idx, path, sz = best
    name = path.split('/')[-1]
    xbmc.log(f'[FileList] BDMV main: fileIdx={idx}  {name}  ({sz // (1024**3):.1f} GB)', xbmc.LOGINFO)
    return idx, name


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
        h, private_trackers, files, tfile = _get_torrent_data(str(tid), dl)
        if not h:
            continue

        # fileIdx corect: season pack → episode match, BDMV → cel mai mare m2ts, altfel 0
        file_idx = 0
        file_name = None
        if season and episode and files:
            file_idx, file_name = _find_episode_idx(files, season, episode)
        elif files and any('BDMV' in path for path, _ in files):
            file_idx, file_name = _find_bdmv_idx(files)

        all_trackers = private_trackers + [
            tr for tr in _PUBLIC_TRACKERS if tr not in private_trackers
        ]

        name    = t.get('name', '')
        quality = _quality(t)
        size    = _fmt_size(t.get('size'))
        seeds   = int(t.get('seeders') or 0)
        is_ro   = bool(re.search(r'\.(ro|RO)\.|romanian|subtitrare|dublat', name, re.I)
                       or '-RO' in t.get('category', ''))
        free    = t.get('freeleech') == 1 or t.get('free_leech') == 1

        ro_tag = '  [RO]' if is_ro else ''
        title_line = f'{name}{ro_tag}'

        sources.append({
            'infoHash':          h,
            'fileIdx':           file_idx,
            'fileName':          file_name,
            'trackers':          [f'tracker:{tr}' for tr in all_trackers],
            'torrent_file':      tfile,
            'provider':          'FileList',
            'quality':           quality,
            'title_line':        title_line,
            'seeds':             seeds,
            'file_size':         size,
            'is_free':           '1' if free else '',
            'show_freeleech':    '1',
            'is_torrent':        True,
        })
        xbmc.log(f'[FileList] {quality}  {seeds}👥  fileIdx={file_idx}  fileName={file_name}  {name[:50]}', xbmc.LOGINFO)
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
