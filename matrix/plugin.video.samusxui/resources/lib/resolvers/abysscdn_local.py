# resources/lib/resolvers/abysscdn_local.py
"""Rezolvare AbyssCDN 100% locală (fără proxy pe api.derzis.xyz).

Portare a schemei server-side (`abysscdn.py` de pe backend-ul Thrax) direct
în Kodi, ca sursele marcate `thrax_resolved=false` să nu mai consume banda
serverului. Reutilizează AES-CTR pur-Python deja inclus în resolveurl
(`resolveurl.lib.pyaes`), nu pycryptodome/curl_cffi — acelea nu sunt
garantat disponibile pe toate device-urile Kodi (ARM/Android etc.).

Schema pe 3 etape (confirmată de backend, 2026-07-29):
  1. [0, encrypted_end)      — header decriptat, prefetch (max 300KB brute)
  2. [encrypted_end, part_size) — fetch direct pe URL-ul plat (url+path),
     Range normal pe CDN, decriptat AES-CTR cu offset continuat din (1)
  3. [part_size, total_size) — token "sora", chunk_idx = offset GLOBAL în
     fișier (pos // SORA_CHUNK_SIZE), path construit cu total_size (nu
     part_size) — deja NEDECRIPTAT la primire (CDN-ul servește gata decriptat
     pentru chunk-urile sora).

Un fișier fără `sora_meta` (part_size >= total_size) nu ajunge niciodată în
etapa 3 — rămâne doar etapele 1+2, ca un fișier normal.
"""

import re
import json
import base64
import hashlib
import struct
import threading
import socket
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import http.server as _http_server

import requests
import xbmc

from resolveurl.lib.pyaes.aes import AESModeOfOperationCTR, Counter

SORA_CHUNK_SIZE = 2_097_152  # 2 MB
# CDN-ul limitează ~5 Mbps PE CONEXIUNE (măsurat: burst ~120 MiB, apoi constant
# 4,7-4,9 Mbps, indiferent dacă refolosim conexiunea). Un film de 10,5 GiB /
# 108 min cere 13,9 Mbps, deci o singură cerere pe rând nu-l poate susține —
# de aici sacadarea. Cu aducere în avans pe mai multe conexiuni: 16-19 Mbps
# susținut. Fereastra costă SORA_AHEAD × 2 MB de memorie per redare.
SORA_WORKERS = 4
SORA_AHEAD = 6
_HEADER_PREFETCH = 300_000
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
_LABEL = '[ABYSS/local]'

_MP4_CONTAINERS = {
    b'moov', b'trak', b'mdia', b'minf', b'stbl', b'dinf', b'udta',
    b'edts', b'moof', b'traf', b'mfra', b'mvex', b'meta', b'ilst',
}
_MP4_BOXES = _MP4_CONTAINERS | {
    b'ftyp', b'mvhd', b'tkhd', b'mdhd', b'hdlr', b'vmhd', b'smhd',
    b'dref', b'stsd', b'stts', b'stss', b'stsc', b'stsz', b'stco',
    b'co64', b'ctts', b'sdtp', b'avc1', b'mp4a', b'esds', b'avcC',
    b'btrt', b'pasp', b'colr', b'free', b'skip', b'mdat', b'uuid',
    b'elst', b'nmhd', b'subs', b'saiz', b'saio', b'tfra', b'mfhd',
    b'tfhd', b'trun', b'sbgp', b'sgpd', b'leva',
    b'tref', b'chap', b'hint', b'cdsc', b'font', b'mpod', b'sync',
    b'av01', b'av1C', b'hev1', b'hvc1', b'hvcC', b'vp08', b'vp09', b'vpcC',
    b'dvcC', b'dvvC', b'dvwC', b'dby1',
    b'iods', b'mehd', b'trex', b'tx3g', b'wvtt', b'stpp',
}


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'{_LABEL} {msg}', level)


# ── crypto (pyaes, nu pycryptodome) ────────────────────────────────────────

def _derive_key(seed):
    seed_str = str(seed)
    if seed_str.replace('.', '', 1).replace(':', '').replace('-', '').isdigit():
        buf = bytearray(
            int(ch) if ch.isdigit() else (ord(ch) & 0xFF) for ch in seed_str
        )
    else:
        buf = seed_str.encode('utf-8')
    return bytearray(hashlib.md5(bytes(buf)).hexdigest().encode('utf-8'))


def _aes_ctr_transform(data_bytes, key_seed):
    """Criptează/decriptează un bloc complet, pornind de la offset 0."""
    key = _derive_key(key_seed)
    iv_int = int.from_bytes(bytes(key[:16]), 'big')
    counter = Counter(initial_value=iv_int)
    cipher = AESModeOfOperationCTR(bytes(key), counter=counter)
    return bytes(cipher.encrypt(bytes(data_bytes)))


def _aes_ctr_at_offset(key_bytes, byte_offset, data_bytes):
    """Decriptează `data_bytes` care încep la `byte_offset` global în fișier
    — CTR permite sărirea la orice bloc de 16 octeți fără să decriptăm ce e
    înainte."""
    block_offset = byte_offset // 16
    iv_int = int.from_bytes(bytes(key_bytes[:16]), 'big')
    counter = Counter(initial_value=iv_int + block_offset)
    cipher = AESModeOfOperationCTR(bytes(key_bytes), counter=counter)
    # CTR e aliniat pe blocuri de 16B — counter-ul pornește la începutul
    # blocului (block_offset*16), care e `lead` octeți ÎNAINTE de
    # byte_offset cerut. Prependăm `lead` octeți fictivi ca să aliniem, apoi
    # tăiem exact aceiași `lead` octeți din rezultat.
    lead = byte_offset % 16
    if lead:
        padded = bytes(lead) + bytes(data_bytes)
        return bytes(cipher.encrypt(padded))[lead:]
    return bytes(cipher.encrypt(bytes(data_bytes)))


def _build_sora_token(path_value, size_value):
    transformed = _aes_ctr_transform(path_value.encode('utf-8'), str(size_value))
    first = base64.b64encode(transformed).decode('utf-8').replace('=', '')
    second = base64.b64encode(first.encode('utf-8')).decode('utf-8').replace('=', '')
    return second


# ── page parsing ────────────────────────────────────────────────────────────

def _decode_escaped_binary(escaped):
    if not escaped:
        return ''
    out = []
    i = 0
    esc_map = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b',
               'f': '\f', '\\': '\\', '"': '"', '/': '/'}
    while i < len(escaped):
        ch = escaped[i]
        if ch == '\\' and i + 1 < len(escaped):
            nxt = escaped[i + 1]
            if nxt == 'u' and i + 5 < len(escaped):
                try:
                    out.append(chr(int(escaped[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except Exception:
                    pass
            if nxt in esc_map:
                out.append(esc_map[nxt])
                i += 2
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _extract_datas_payload(html):
    match = re.search(r'(?:const|var)\s+datas\s*=\s*"([^"]+)"', html or '')
    if not match:
        return {}
    try:
        raw = base64.b64decode(match.group(1).strip())
    except Exception:
        return {}
    try:
        payload = json.loads(raw.decode('utf-8'))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    decoded = raw.decode('latin-1', 'ignore')
    payload = {}
    for key, pat in [
        ('slug', r'"slug"\s*:\s*"([^"]+)"'),
        ('md5_id', r'"md5_id"\s*:\s*(\d+)'),
        ('user_id', r'"user_id"\s*:\s*(\d+)'),
    ]:
        m = re.search(pat, decoded)
        if m:
            payload[key] = int(m.group(1)) if key != 'slug' else m.group(1)
    media_marker = b'"media":"'
    config_marker = b'","config"'
    m_idx = raw.find(media_marker)
    c_idx = raw.find(config_marker)
    if m_idx >= 0 and c_idx > m_idx:
        try:
            blob = raw[m_idx + len(media_marker):c_idx].decode('latin-1', 'ignore')
            payload['media'] = _decode_escaped_binary(blob)
        except Exception:
            pass
    elif 'media' not in payload:
        m = re.search(r'"media"\s*:\s*"((?:\\.|[^"\\])*)"', decoded, re.DOTALL)
        if m:
            payload['media'] = _decode_escaped_binary(m.group(1))
    return payload if payload else {}


def _decrypt_media(encrypted_text, user_id, slug, md5_id):
    if not encrypted_text or not user_id or not slug or not md5_id:
        return {}
    key_seed = '{0}:{1}:{2}'.format(user_id, slug, md5_id)
    raw_bytes = bytes(ord(ch) & 0xFF for ch in encrypted_text)
    result = _aes_ctr_transform(raw_bytes, key_seed)
    try:
        decoded = json.loads(result.decode('utf-8', 'ignore'))
        return decoded if isinstance(decoded, dict) else {}
    except Exception:
        return {}


def _is_encrypted_url(url):
    path = urllib.parse.urlparse(url).path
    return bool(re.search(r'/[0-9a-f]/[0-9a-f]/[0-9a-f]/[0-9a-f]+\.\d+\.\d+$', path))


def _extract_best_source(media_payload):
    """Alege sursa de cea mai bună calitate cu url+path direct (cere codec
    dominant, ca în resolver-ul server-side — evită un unic AV1 rătăcit
    printre variante H.264)."""
    mp4 = media_payload.get('mp4') if isinstance(media_payload.get('mp4'), dict) else {}
    domains = mp4.get('domains') if isinstance(mp4.get('domains'), list) else []
    raw_sources = mp4.get('sources') if isinstance(mp4.get('sources'), list) else []
    sources = [s for s in raw_sources if isinstance(s, dict)]

    codec_counts = {}
    for s in sources:
        c = s.get('codec', '')
        codec_counts[c] = codec_counts.get(c, 0) + 1
    dominant = max(codec_counts, key=codec_counts.get) if codec_counts else None

    with_url = [s for s in sources if isinstance(s.get('url'), str) and isinstance(s.get('path'), str)]
    candidates = [s for s in with_url if s.get('codec') == dominant] or with_url
    candidates.sort(key=lambda s: int(s.get('size', 0) or 0), reverse=True)

    for src in candidates:
        url_ = src['url'].rstrip('/')
        path_ = src['path'].lstrip('/')
        video_url = f'{url_}/{path_}'.replace('\\/', '/')
        part_size = int(src.get('partSize', 0) or 0)
        total_size = int(src.get('size', 0) or 0)
        sub = src.get('sub', '')
        res_id = src.get('res_id')
        sora_domain = None
        if sub:
            d = next((d for d in domains if isinstance(d, str) and sub in d), None)
            if d:
                sora_domain = d if d.startswith('http') else 'https://' + d
        return {
            'video_url': video_url,
            'part_size': part_size or total_size,
            'total_size': total_size,
            'res_id': res_id,
            'sora_domain': sora_domain,
            'label': src.get('label', '?'),
        }

    # fallback: fișier simplu ("file"), fără criptare/chunking
    for src in sources:
        direct = src.get('file')
        if isinstance(direct, str) and direct:
            return {'video_url': direct.replace('\\/', '/'), 'simple': True}

    # fallback: surse EXCLUSIV sora (fără url/path direct) — tot fișierul vine
    # din chunk-uri, deci part_size=0: sărim complet etapele header+direct
    sora_only = [
        s for s in sources
        if s.get('sub') and s.get('res_id') and int(s.get('size', 0) or 0) > 0
    ]
    cand = [s for s in sora_only if s.get('codec') == dominant] or sora_only
    cand.sort(key=lambda s: int(s.get('size', 0) or 0), reverse=True)
    for src in cand:
        d = next((d for d in domains if isinstance(d, str) and src['sub'] in d), None)
        if not d:
            continue
        return {
            'video_url': '',                     # nu există URL plat pentru asta
            'part_size': 0,                      # nimic din CDN direct
            'total_size': int(src['size']),
            'res_id': src['res_id'],
            'sora_domain': d if d.startswith('http') else 'https://' + d,
            'label': src.get('label', '?'),
            'sora_only': True,
        }
    return None


def _fetch_and_prepare_header(url, key, referer):
    r = requests.get(
        url,
        headers={'User-Agent': _UA, 'Referer': referer,
                 'Range': f'bytes=0-{_HEADER_PREFETCH - 1}'},
        timeout=30,
    )
    raw = r.content
    decrypted = bytearray(_aes_ctr_at_offset(key, 0, raw))

    cursor = 0
    box_end = len(decrypted)
    while cursor + 8 <= len(decrypted):
        sz = struct.unpack_from('>I', decrypted, cursor)[0]
        tp = bytes(decrypted[cursor + 4:cursor + 8])
        if sz < 8 or sz > 50_000_000 or tp not in _MP4_BOXES:
            box_end = cursor
            break
        if sz > 16 and tp in _MP4_CONTAINERS:
            cursor += 8
        else:
            cursor += sz

    encrypted_end = box_end
    idx = decrypted.find(b'stts', 0, box_end)
    if idx >= 4:
        stts_sz = struct.unpack_from('>I', decrypted, idx - 4)[0]
        if 8 <= stts_sz <= 10_000_000:
            entry_count = struct.unpack_from('>I', decrypted, idx + 8)[0]
            ep_base = idx + 12
            for i in range(entry_count):
                ep = ep_base + i * 8
                if ep + 8 > len(decrypted):
                    break
                count = struct.unpack_from('>I', decrypted, ep)[0]
                delta = struct.unpack_from('>I', decrypted, ep + 4)[0]
                # ordinea contează: dacă AMBELE depășesc pragul, granița e la
                # `ep` (count), nu la `ep + 4` — o inversare aici deplasează
                # limita cu 4 octeți și strică alinierea NAL-urilor
                if count >= 1_000_000:
                    encrypted_end = ep
                    break
                if delta >= 1_000_000:
                    encrypted_end = ep + 4
                    break

    return encrypted_end, bytes(decrypted[:encrypted_end])


def build_sora_url(sora_domain, total_size, chunk_idx, res_id, md5_id):
    path = f'/mp4/{md5_id}/{res_id}/{total_size}/{SORA_CHUNK_SIZE}/{chunk_idx}'
    token = _build_sora_token(path, str(total_size))
    return f'{sora_domain.rstrip("/")}/sora/{total_size}/{token}'


def resolve_info(page_url, referer_page=None):
    """Fetch pagina + decriptează payload-ul. Returnează dict gata pentru
    proxy sau None la eșec."""
    headers = {'User-Agent': _UA, 'Referer': referer_page or re.sub(r'(https?://[^/]+).*', r'\1/', page_url)}
    r = requests.get(page_url, headers=headers, timeout=20)
    if r.url != page_url:
        page_url = r.url
        headers['Referer'] = re.sub(r'(https?://[^/]+).*', r'\1/', page_url)
    datas = _extract_datas_payload(r.text)
    if not datas:
        _log(f'nu s-a găsit blocul datas în pagină: {page_url}', xbmc.LOGWARNING)
        return None

    slug = datas.get('slug')
    md5_id = datas.get('md5_id')
    user_id = datas.get('user_id')
    media_blob = datas.get('media')
    media_payload = media_blob if isinstance(media_blob, dict) else _decrypt_media(media_blob, user_id, slug, md5_id)
    if not media_payload:
        _log(f'decriptare media eșuată: {page_url}', xbmc.LOGWARNING)
        return None

    best = _extract_best_source(media_payload)
    if not best:
        _log(f'nicio sursă găsită: {page_url}', xbmc.LOGWARNING)
        return None

    if best.get('simple'):
        return {'simple_url': best['video_url']}

    video_url = best['video_url']
    referer = headers['Referer']
    encrypted = _is_encrypted_url(video_url)
    key = _derive_key(video_url.split('/')[-1]) if encrypted else None
    encrypted_end, patched_header = (0, b'')
    if encrypted:
        encrypted_end, patched_header = _fetch_and_prepare_header(video_url, key, referer)

    return {
        'video_url': video_url,
        'referer': referer,
        'encrypted': encrypted,
        'key': key,
        'encrypted_end': encrypted_end,
        'patched_header': patched_header,
        'part_size': best['part_size'],
        'total_size': best['total_size'],
        'sora_domain': best.get('sora_domain'),
        'res_id': best.get('res_id'),
        'md5_id': md5_id,
    }


# ── local HTTP proxy ─────────────────────────────────────────────────────────

def _get_with_retry(url, headers, what, attempts=3, timeout=30):
    """Un film de ~2h înseamnă mii de cereri către CDN — un timeout izolat nu
    trebuie să rupă redarea, deci reîncercăm scurt înainte să renunțăm."""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code in (200, 206):
                return r.content
            last = f'HTTP {r.status_code}'
        except Exception as e:
            last = str(e)
        if attempt < attempts:
            _log(f'{what}: {last} (încercarea {attempt}/{attempts}), reîncerc', xbmc.LOGWARNING)
            xbmc.sleep(500 * attempt)
    raise RuntimeError(f'{what} eșuat după {attempts} încercări: {last}')


def _fetch_direct_range(url, referer, start, end):
    return _get_with_retry(
        url,
        {'User-Agent': _UA, 'Referer': referer, 'Range': f'bytes={start}-{end}'},
        f'CDN range {start}-{end}',
    )


# Setat la shutdown, înaintea închiderii socketurilor: firele de aducere în
# avans trebuie să iasă înainte de Py_EndInterpreter, ca handler-ele HTTP.
_PREFETCH_STOP = threading.Event()


class _SoraPrefetcher:
    """Aduce bucăți sora în avans, pe mai multe conexiuni, dar le livrează
    STRICT în ordine. Limitarea CDN-ului e per conexiune, deci paralelismul e
    singurul mod de a depăși ~5 Mbps; ordinea contează pentru că ieșirea merge
    direct în socketul playerului.

    Firele sunt daemon și se opresc la `close()` sau la `_PREFETCH_STOP`.
    """

    def __init__(self, info, first_chunk, last_chunk, workers=SORA_WORKERS, ahead=SORA_AHEAD):
        self._info = info
        self._last = last_chunk
        self._ahead = max(1, ahead)
        self._next_fetch = first_chunk
        self._delivered = first_chunk - 1
        self._done = {}
        self._stop = threading.Event()
        self._cv = threading.Condition()
        count = max(1, min(workers, last_chunk - first_chunk + 1))
        self._threads = [
            threading.Thread(target=self._worker, daemon=True, name=f'abyss-sora-{i}')
            for i in range(count)
        ]
        for t in self._threads:
            t.start()

    def _stopped(self):
        return self._stop.is_set() or _PREFETCH_STOP.is_set()

    def _worker(self):
        while True:
            with self._cv:
                while True:
                    if self._stopped():
                        return
                    idx = self._next_fetch
                    if idx > self._last:
                        return
                    # fereastra: nu alergăm mai departe de `ahead` peste ce s-a livrat
                    if idx - self._delivered <= self._ahead:
                        self._next_fetch = idx + 1
                        break
                    self._cv.wait(0.5)
            url = build_sora_url(self._info['sora_domain'], self._info['total_size'],
                                 idx, self._info['res_id'], self._info['md5_id'])
            try:
                # Timeout mai scurt decât implicitul: un fir prins într-o cerere
                # e un fir viu pentru Py_EndInterpreter, iar acum sunt patru,
                # nu unul. O bucată de 2 MB durează ~3,5 s chiar și la debitul
                # limitat de CDN, deci 15 s rămâne larg.
                data = _get_with_retry(
                    url,
                    {'User-Agent': _UA, 'Referer': self._info['referer']},
                    f'sora chunk {idx}',
                    timeout=15,
                )
                err = None
            except Exception as e:  # o raportăm consumatorului, în ordinea lui
                data, err = None, e
            with self._cv:
                self._done[idx] = (data, err)
                self._cv.notify_all()

    def get(self, idx):
        with self._cv:
            while idx not in self._done:
                if self._stopped():
                    raise RuntimeError('proxy oprit în timpul aducerii')
                self._cv.wait(0.5)
            data, err = self._done.pop(idx)
            self._delivered = idx
            self._cv.notify_all()
        if err is not None:
            raise err
        return data

    def close(self, timeout=5):
        self._stop.set()
        with self._cv:
            self._cv.notify_all()
        deadline = time.monotonic() + timeout
        for t in self._threads:
            t.join(max(0, deadline - time.monotonic()))
        alive = [t.name for t in self._threads if t.is_alive()]
        if alive:
            _log(f'fire de aducere încă active la închidere: {", ".join(alive)}',
                 xbmc.LOGWARNING)


def _iter_sora_range(info, global_start, global_end):
    """Generează bucăți din zona sora pentru [global_start, global_end], în
    ordine — nu acumulează tot intervalul în memorie (playerul poate cere zeci
    de GB într-un singur range deschis). Aducerea e în avans, vezi
    `_SoraPrefetcher`."""
    total_size = info['total_size']
    first_chunk = global_start // SORA_CHUNK_SIZE
    last_chunk = min(global_end // SORA_CHUNK_SIZE, (total_size - 1) // SORA_CHUNK_SIZE)
    if last_chunk < first_chunk:
        return
    pf = _SoraPrefetcher(info, first_chunk, last_chunk)
    try:
        for idx in range(first_chunk, last_chunk + 1):
            data = pf.get(idx)
            chunk_start = idx * SORA_CHUNK_SIZE
            lo = max(0, global_start - chunk_start)
            hi = min(len(data), global_end - chunk_start + 1)
            if hi > lo:
                yield data[lo:hi]
    finally:
        # și la seek/stop (GeneratorExit), nu doar la epuizare
        pf.close()


def _fetch_sora_range(info, global_start, global_end):
    """Variantă buffered (folosită la teste/validare)."""
    return b''.join(_iter_sora_range(info, global_start, global_end))


def _iter_range(info, start, end, block=4 * 1024 * 1024):
    """Generează [start, end] inclusiv, în bucăți, traversând cele 3 etape.
    Streaming — prima bucată pleacă spre player imediat, fără să așteptăm
    tot intervalul."""
    pos = start
    while pos <= end:
        if pos < info['encrypted_end']:
            seg_end = min(end, info['encrypted_end'] - 1)
            yield bytes(info['patched_header'][pos:seg_end + 1])
            pos = seg_end + 1
        elif pos < info['part_size']:
            # NU se decriptează: cheia AES se aplică DOAR headerului
            # [0, encrypted_end). Dincolo de el, CDN-ul servește deja
            # plaintext — verificat byte-cu-byte contra streamului Thrax.
            seg_end = min(end, info['part_size'] - 1, pos + block - 1)
            yield _fetch_direct_range(info['video_url'], info['referer'], pos, seg_end)
            pos = seg_end + 1
        else:
            # Zona sora e ultima și merge până la capăt: o parcurgem într-un
            # singur generator, ca fereastra de aducere în avans să se aplice
            # întregului range. Tăiat în blocuri de `block`, prefetcher-ul ar
            # fi recreat la fiecare două bucăți și avansul n-ar folosi la nimic.
            for piece in _iter_sora_range(info, pos, end):
                yield piece
            pos = end + 1


_INFO_CACHE = {}
_INFO_LOCK = threading.Lock()


def _get_info(page_url):
    """resolve_info() cu cache — proxy-ul primește pagina în query string, deci
    rezolvă la prima cerere și refolosește la seek-uri ulterioare."""
    with _INFO_LOCK:
        cached = _INFO_CACHE.get(page_url)
    if cached is not None:
        return cached
    info = resolve_info(page_url)
    if info:
        with _INFO_LOCK:
            _INFO_CACHE[page_url] = info
    return info


class _AbyssProxyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        BaseHTTPRequestHandler.setup(self)
        # Playerul citește în rafale: umple bufferul, apoi tace minute întregi.
        # Cu timeout pe socket, `wfile.write` crapă cu "timed out" și rupem
        # streamul în mijlocul filmului. Blocăm la nesfârșit — dacă playerul
        # chiar pleacă (stop/seek), primim BrokenPipe/ConnectionReset.
        try:
            self.connection.settimeout(None)
        except Exception:
            pass

    def log_message(self, fmt, *args):
        pass

    def _resolve_from_path(self):
        qs = urllib.parse.urlparse(self.path).query
        page_url = urllib.parse.parse_qs(qs).get('u', [''])[0]
        if not page_url:
            return None
        try:
            return _get_info(page_url)
        except Exception as e:
            _log(f'rezolvare eșuată în proxy pentru {page_url}: {e}', xbmc.LOGERROR)
            return None

    def _send_fail(self, code=502):
        self.send_response(code)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        info = self._resolve_from_path()
        if not info or 'total_size' not in info:
            self._send_fail()
            return
        total_size = info['total_size']
        rng = self.headers.get('Range')
        m = re.match(r'bytes=(\d+)-(\d*)', rng) if rng else None
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else total_size - 1
        else:
            start, end = 0, total_size - 1
        end = min(end, total_size - 1)

        self.send_response(206 if m else 200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if m:
            self.send_header('Content-Range', f'bytes {start}-{end}/{total_size}')
        self.end_headers()

        try:
            for piece in _iter_range(info, start, end):
                if self.server.stopping.is_set():
                    break
                self.wfile.write(piece)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            # playerul a închis conexiunea sau a încetat să citească (seek/stop)
            # — normal la streaming, nu e eroare
            pass
        except Exception as e:
            xbmc.log(f'{_LABEL} eroare servire range {start}-{end}: {e}', xbmc.LOGERROR)

    def do_HEAD(self):
        info = self._resolve_from_path()
        if not info or 'total_size' not in info:
            self._send_fail()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(info['total_size']))
        self.end_headers()


class _ThreadingHTTPServer(ThreadingMixIn, _http_server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, *args, **kwargs):
        self.stopping = threading.Event()
        self._active_lock = threading.Lock()
        self._active_requests = set()
        self._request_threads = set()
        super().__init__(*args, **kwargs)

    def process_request_thread(self, request, client_address):
        thread = threading.current_thread()
        with self._active_lock:
            self._active_requests.add(request)
            self._request_threads.add(thread)
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self._active_lock:
                self._active_requests.discard(request)
                self._request_threads.discard(thread)

    def stop_active_requests(self):
        """Întrerupe inclusiv handler-ele HTTP/1.1 rămase în keep-alive.

        ``shutdown()`` oprește doar bucla ``serve_forever``; socketurile deja
        acceptate pot rămâne blocate în ``rfile.readline()`` deoarece proxy-ul
        folosește intenționat timeout infinit pentru redare. Închiderea lor
        trezește handler-ele înainte de Py_EndInterpreter.
        """
        self.stopping.set()
        with self._active_lock:
            requests_active = list(self._active_requests)
        for connection in requests_active:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass

    def handle_error(self, request, client_address):
        # Închiderea forțată a unui socket keep-alive produce intenționat
        # ConnectionResetError în BaseHTTPRequestHandler. Nu poluăm logul la
        # shutdown; erorile din timpul funcționării rămân raportate normal.
        if self.stopping.is_set():
            return
        super().handle_error(request, client_address)

    def join_request_threads(self, timeout=5):
        deadline = time.monotonic() + timeout
        while True:
            with self._active_lock:
                threads = [t for t in self._request_threads if t.is_alive()]
            if not threads:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _log(f'{len(threads)} handler(e) proxy n-au ieșit la shutdown', xbmc.LOGWARNING)
                return
            for thread in threads:
                thread.join(min(0.2, remaining))


_PORT_PROPERTY = 'samusxui_abyss_proxy_port'
_server_ref = None  # ține serverul viu în procesul serviciului
_server_thread = None


def start_service_proxy():
    """Pornește proxy-ul în procesul SERVICIULUI (persistent pe toată durata
    sesiunii Kodi). Procesul plugin-ului moare imediat după setResolvedUrl —
    un proxy pornit acolo ar muri odată cu el, în mijlocul redării."""
    global _server_ref, _server_thread
    if _server_ref is not None:
        return _server_ref.server_address[1]
    _PREFETCH_STOP.clear()  # o repornire în același interpretor nu trebuie să moștenească oprirea
    server = _ThreadingHTTPServer(('127.0.0.1', 0), _AbyssProxyHandler)
    port = server.server_address[1]
    _server_thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name='abyss-proxy-service',
    )
    _server_thread.start()
    _server_ref = server
    import xbmcgui
    xbmcgui.Window(10000).setProperty(_PORT_PROPERTY, str(port))
    _log(f'proxy pornit în serviciu, port {port}')
    return port


def stop_service_proxy():
    """Oprește complet proxy-ul înainte ca Kodi să închidă subinterpretorul.

    Un fir daemon rămas în ``serve_forever()`` este tot un fir viu pentru
    ``Py_EndInterpreter``. Pe Python 3.14 asta poate bloca Kodi definitiv pe
    GIL, deci serviciul trebuie să facă shutdown explicit, ca Bendis.
    """
    global _server_ref, _server_thread
    server = _server_ref
    thread = _server_thread
    if server is None:
        return
    try:
        # întâi firele de aducere în avans: handler-ele le așteaptă în `finally`
        _PREFETCH_STOP.set()
        server.stop_active_requests()
        server.shutdown()
    finally:
        server.server_close()
        server.join_request_threads(timeout=5)
        if thread is not None:
            thread.join(timeout=5)
        _server_ref = None
        _server_thread = None
        import xbmcgui
        xbmcgui.Window(10000).clearProperty(_PORT_PROPERTY)
        _log('proxy oprit')


def _service_port():
    import xbmcgui
    try:
        return int(xbmcgui.Window(10000).getProperty(_PORT_PROPERTY) or 0)
    except (TypeError, ValueError):
        return 0


def resolve(page_url):
    """API principal — echivalent cu resolveurl.resolve(), dar 100% local
    pentru schema AbyssCDN (header criptat + part direct + chunk-uri sora).
    Returnează un URL playable sau None la eșec."""
    try:
        info = _get_info(page_url)
    except Exception as e:
        _log(f'resolve_info eșuat pentru {page_url}: {e}', xbmc.LOGERROR)
        return None
    if not info:
        return None
    if 'simple_url' in info:
        return info['simple_url']
    if info['part_size'] >= info['total_size'] and not info['encrypted']:
        # fișier simplu, neîncriptat, fără chunking — nu are rost de proxy
        return info['video_url']

    port = _service_port()
    if not port:
        # serviciul nu rulează (ex. dezactivat) — pornim în proces, ca plasă
        # de siguranță; ține doar cât trăiește procesul curent
        _log('serviciul nu rulează, pornesc proxy in-process (fallback)', xbmc.LOGWARNING)
        port = start_service_proxy()

    stream_url = f'http://127.0.0.1:{port}/stream?u={urllib.parse.quote(page_url, safe="")}'
    # încălzire: serviciul are cache-ul lui, îl punem să rezolve ACUM, ca prima
    # cerere a playerului să nu aștepte page fetch + header (și să nu pice pe
    # timeout-ul lui CCurlFile)
    try:
        requests.head(stream_url, timeout=90)
    except Exception as e:
        _log(f'încălzire proxy eșuată: {e}', xbmc.LOGWARNING)
    return stream_url
