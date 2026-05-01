# -*- coding: utf-8 -*-
import base64
import hashlib
import requests
import xbmc

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

_EM      = '4f2a9c7d1e8b3a6f0d5c2e9a7b1f4d8c'
_BASE    = 'https://player.vidzee.wtf'
_APIKEY  = 'https://core.vidzee.wtf/api-key'
_UA      = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'
_HEADERS = {'User-Agent': _UA, 'Referer': f'{_BASE}/', 'Origin': _BASE, 'Accept-Encoding': 'gzip, deflate'}
_LABEL   = '[V]'
_SERVERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
_FALLBACK_KEYS = ['qrincywincyspider', 'ifyouscrapeyouaregay']


def _fetch_session_key():
    r = requests.get(_APIKEY, headers=_HEADERS, timeout=10)
    r.raise_for_status()
    raw = base64.b64decode(r.text.strip())
    iv  = raw[0:12]
    tag = raw[12:28]
    ct  = raw[28:]
    gcm_key = hashlib.sha256(_EM.encode()).digest()
    cipher  = AES.new(gcm_key, AES.MODE_GCM, nonce=iv)
    return cipher.decrypt_and_verify(ct, tag).decode('utf-8')


def _decrypt(encrypted_link, G):
    # Plain URL passthrough — unele servere returnează URL direct
    if encrypted_link.startswith('http'):
        return encrypted_link
    keys_to_try = [G] + [k for k in _FALLBACK_KEYS if k != G]
    for key_str in keys_to_try:
        try:
            decoded = base64.b64decode(encrypted_link).decode('utf-8')
            iv_b64, ct_b64 = decoded.split(':', 1)
            iv  = base64.b64decode(iv_b64)
            ct  = base64.b64decode(ct_b64)
            key = (key_str + '\x00' * 32)[:32].encode('utf-8')
            cipher = AES.new(key, AES.MODE_CBC, iv)
            result = unpad(cipher.decrypt(ct), 16).decode('utf-8')
            if result.startswith('http'):
                return result
        except Exception:
            continue
    xbmc.log(f'[Samus/Vidzee] decrypt failed for all keys', xbmc.LOGWARNING)
    return None


def _fetch_server(tmdb_id, media_type, season, episode, sr, G):
    if media_type == 'movie':
        api_url = f'{_BASE}/api/server?id={tmdb_id}&sr={sr}'
        embed_referer = f'{_BASE}/embed/movie/{tmdb_id}'
    else:
        api_url = f'{_BASE}/api/server?id={tmdb_id}&sr={sr}&ss={season}&ep={episode}'
        embed_referer = f'{_BASE}/embed/tv/{tmdb_id}'
    headers = dict(_HEADERS)
    headers['Referer'] = embed_referer
    try:
        r = requests.get(api_url, headers=headers, timeout=8)
        if r.status_code == 404:
            return [], []
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        xbmc.log(f'[Samus/Vidzee] server {sr}: {e}', xbmc.LOGERROR)
        return [], []

    sources = []
    server_name = data.get('serverInfo', {}).get('name', f'S{sr}')

    raw_items = data.get('url') or []
    if not raw_items and data.get('link') and isinstance(data['link'], str):
        raw_items = [{'link': data['link'], 'lang': data.get('lang', '')}]

    for item in raw_items:
        link = item.get('link')
        if not link:
            continue
        decrypted = _decrypt(link, G)
        if not decrypted or not decrypted.startswith('http'):
            continue
        lang = item.get('lang', '')
        title_line = f'{server_name} [{lang}]' if lang else server_name
        playback_url = f'{decrypted}|User-Agent={_UA}&Referer=https://core.vidzee.wtf/&Origin=https://core.vidzee.wtf'
        sources.append({
            'url': playback_url,
            'provider': _LABEL,
            'quality': '1080p',
            'title_line': title_line,
            'size': None,
            'direct': True,
        })

    tracks = [t['url'] for t in data.get('tracks', []) if t.get('url')]
    return sources, tracks


def get_sources(tmdb_id, media_type='movie', season=None, episode=None):
    if not _CRYPTO_OK:
        xbmc.log('[Samus/Vidzee] pycryptodome indisponibil', xbmc.LOGWARNING)
        return []
    if media_type == 'tv' and (season is None or episode is None):
        return []

    try:
        G = _fetch_session_key()
    except Exception as e:
        xbmc.log(f'[Samus/Vidzee] fetch session key failed, using fallback: {e}', xbmc.LOGWARNING)
        G = _FALLBACK_KEYS[0]

    import threading
    bucket_sources = [[] for _ in _SERVERS]
    bucket_tracks  = [[] for _ in _SERVERS]

    def _worker(idx, sr):
        bucket_sources[idx], bucket_tracks[idx] = _fetch_server(tmdb_id, media_type, season, episode, sr, G)

    threads = [threading.Thread(target=_worker, args=(i, sr), daemon=True)
               for i, sr in enumerate(_SERVERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=9)

    seen_track_urls = set()
    all_tracks = []
    for tracks in bucket_tracks:
        for url in tracks:
            if url not in seen_track_urls:
                seen_track_urls.add(url)
                all_tracks.append(url)

    results = [s for sub in bucket_sources for s in sub]
    for s in results:
        s['subtitles'] = all_tracks

    xbmc.log(f'[Samus/Vidzee] {len(results)} surse, {len(all_tracks)} subtitrări pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    return results
