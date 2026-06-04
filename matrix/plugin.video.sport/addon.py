import datetime
import sys
import urllib.parse
import http.server
import threading
import socket
import json
import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import re
import base64
import os
import unicodedata

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
BASE_URL = sys.argv[0]
HANDLE = int(sys.argv[1])

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
_AE = 'gzip, deflate'
_DLHD_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

ICON = os.path.join(ADDON_PATH, 'icon.png')
FANART = os.path.join(ADDON_PATH, 'fanart.jpg')
MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')

def get_asset(name, fallback=ICON):
    if not name: return fallback
    path = os.path.join(MEDIA_PATH, name)
    return path if os.path.exists(path) else fallback

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------
STRINGS = {
    'Portuguese': {
        'ppv_live': 'PPV.TO LIVE',
        'ppv_schedule': 'Programação PPV.TO',
        'sport_desc': 'O desporto é a celebração da superação, onde cada segundo conta e a paixão não conhece fronteiras. Sente a emoção de cada jogo!',
        'creators': 'CRIADOR: @TrainAgain2, @derzis',
        'all': 'Todos os Eventos',
        'unknown': 'Desconhecido',
        'untitled': 'Sem título',
        'pilkanozna': 'Futebol',
        'motorsport': 'Desportos Motorizados',
        'fights': 'Lutas / MMA',
        'hokej': 'Hóquei no Gelo',
        'tenis': 'Ténis',
        'koszykowka': 'Basquetebol',
        'baseball': 'Beisebol',
        'rugby': 'Râguebi',
        'wrestling': 'Luta Livre',
        'kolarstwo': 'Ciclismo',
        'other': 'Outros Desportos',
        'settings': 'Configurações',
        'resolving': 'A resolver stream...',
        'error_resolve': 'Não foi possível resolver o stream.',
        'lang_label': 'Idioma da Interface',
        'sd': 'Qualidade SD',
        'hd': 'Qualidade HD',
        'countries_menu': 'Canais por País',
        'country_portugal': 'Portugal',
        'country_romania': 'Roménia',
        'country_spain': 'Espanha',
        'country_english': 'Inglês / Internacional',
        'no_country_sources': 'Não foram encontradas fontes para este país.',
        'megadeportes': 'Canais Latinos',
        'live_channels': 'Canais ao Vivo',
        'portugal_sport': 'Portugal Sport',
        'antena_sport': 'Antena Sport',
        'antena_schedule': 'Agenda de Hoje',
        'antena_all_channels': 'Todos os Canais'
    },
    'Romanian': {
        'sport_desc': 'Sportul este celebrarea depășirii limitelor, unde fiecare secundă contează și pasiunea nu cunoaște frontiere. Simte emoția fiecărui pe meci!',
        'creators': 'CREATOR: @TrainAgain2, @derzis',
        'all': 'Toate Evenimentele',
        'unknown': 'Necunoscut',
        'untitled': 'Fără titlu',
        'pilkanozna': 'Fotbal',
        'motorsport': 'Sporturi cu Motor',
        'fights': 'Lupte / MMA',
        'hokej': 'Hochei pe Gheață',
        'tenis': 'Tenis',
        'koszykowka': 'Baschet',
        'baseball': 'Basebal',
        'rugby': 'Rugby',
        'wrestling': 'Wrestling',
        'kolarstwo': 'Ciclism',
        'other': 'Alte Sporturi',
        'settings': 'Setări',
        'resolving': 'Se rezolvă fluxul...',
        'error_resolve': 'Nu s-a putut rezolva fluxul.',
        'lang_label': 'Limba Interfeței',
        'sd': 'Calitate SD',
        'hd': 'Calitate HD',
        'countries_menu': 'Canale pe Țară',
        'country_portugal': 'Portugalia',
        'country_romania': 'România',
        'country_spain': 'Spania',
        'country_english': 'Engleză / Internațional',
        'no_country_sources': 'Nu au fost găsite surse pentru această țară.',
        'megadeportes': 'Canale Latine',
        'live_channels': 'Canale Live',
        'portugal_sport': 'Portugal Sport',
        'antena_sport': 'Antena Sport',
        'antena_schedule': 'Programul de Azi',
        'antena_all_channels': 'Toate Canalele'
    },
    'English': {
        'sport_desc': 'Sport is the celebration of overcoming limits, where every second counts and passion knows no borders. Feel the emotion of every game!',
        'creators': 'CREATOR: @TrainAgain2, @derzis',
        'all': 'All Events',
        'unknown': 'Unknown',
        'untitled': 'Untitled',
        'pilkanozna': 'Soccer',
        'motorsport': 'Motorsport',
        'fights': 'Fights / MMA',
        'hokej': 'Ice Hockey',
        'tenis': 'Tennis',
        'koszykowka': 'Basketball',
        'baseball': 'Baseball',
        'rugby': 'Rugby',
        'wrestling': 'Wrestling',
        'kolarstwo': 'Cycling',
        'other': 'Other Sports',
        'settings': 'Settings',
        'resolving': 'Resolving stream...',
        'error_resolve': 'Could not resolve stream.',
        'lang_label': 'Interface Language',
        'sd': 'SD Quality',
        'hd': 'HD Quality',
        'countries_menu': 'Channels by Country',
        'country_portugal': 'Portugal',
        'country_romania': 'Romania',
        'country_spain': 'Spain',
        'country_english': 'English / International',
        'no_country_sources': 'No sources were found for this country.',
        'megadeportes': 'Latin Channels',
        'live_channels': 'Live Channels',
        'portugal_sport': 'Portugal Sport',
        'antena_sport': 'Antena Sport',
        'antena_schedule': 'Today\'s Schedule',
        'antena_all_channels': 'All Channels'
    },
    'Spanish': {
        'sport_desc': 'El deporte es la celebración de la superación, donde cada segundo cuenta y la pasión no conoce fronteras. ¡Siente la emoción de cada juego!',
        'creators': 'CREADOR: @TrainAgain2, @derzis',
        'all': 'Todos los Eventos',
        'unknown': 'Desconocido',
        'untitled': 'Sin título',
        'pilkanozna': 'Fútbol',
        'motorsport': 'Deportes de Motor',
        'fights': 'Luchas / MMA',
        'hokej': 'Hockey sobre Hielo',
        'tenis': 'Tenis',
        'koszykowka': 'Baloncesto',
        'baseball': 'Béisbol',
        'rugby': 'Rugby',
        'wrestling': 'Lucha Libre',
        'kolarstwo': 'Ciclismo',
        'other': 'Otros Deportes',
        'settings': 'Ajustes',
        'resolving': 'Resolviendo stream...',
        'error_resolve': 'No se pudo resolver el stream.',
        'lang_label': 'Idioma de Interfaz',
        'sd': 'Calidad SD',
        'hd': 'Calidad HD',
        'countries_menu': 'Canales por País',
        'country_portugal': 'Portugal',
        'country_romania': 'Rumanía',
        'country_spain': 'España',
        'country_english': 'Inglés / Internacional',
        'no_country_sources': 'No se encontraron fuentes para este país.',
        'megadeportes': 'Canales Latinos',
        'live_channels': 'Canales en Vivo',
        'portugal_sport': 'Portugal Sport',
        'antena_sport': 'Antena Sport',
        'antena_schedule': 'Agenda de Hoy',
        'antena_all_channels': 'Todos los Canales'
    }
}

def L(msg):
    xbmc.log(f"SPORT_PLUGIN: {msg}", xbmc.LOGINFO)

def T(key):
    try:
        lang_idx = int(ADDON.getSetting('language'))
    except:
        lang_idx = 0
    lang_map = {0: 'Portuguese', 1: 'Romanian', 2: 'English', 3: 'Spanish'}
    lang_name = lang_map.get(lang_idx, 'Portuguese')
    return STRINGS.get(lang_name, STRINGS['Portuguese']).get(key, key)

# ---------------------------------------------------------------------------
# Local HTTP proxy
# ---------------------------------------------------------------------------
_proxy_server = None
_proxy_port = None
_last_drm = {}

def _proxy_url(target, ref=''):
    return (f'http://127.0.0.1:{_proxy_port}/proxy'
            f'?url={urllib.parse.quote(target, safe="")}'
            f'&ref={urllib.parse.quote(ref, safe="")}')

def _rewrite_playlist(raw_bytes, base_url):
    text = raw_bytes.decode('utf-8', errors='replace')
    parsed_base = urllib.parse.urlparse(base_url)
    origin = f'{parsed_base.scheme}://{parsed_base.netloc}'
    base_dir = base_url.split('?')[0].rsplit('/', 1)[0] + '/'
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if stripped.startswith('#'):
            out.append(line)
            continue
        if not stripped.startswith('http'):
            stripped = (origin + stripped) if stripped.startswith('/') else (base_dir + stripped)
        out.append(_proxy_url(stripped, base_url))
    return '\n'.join(out).encode('utf-8')

class _ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        if self.path.startswith('/ckls'):
            import base64 as _b64
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length))
                resp_keys = []
                for kid_b64 in body.get('kids', []):
                    pad = 4 - len(kid_b64) % 4
                    kid_bytes = _b64.urlsafe_b64decode(kid_b64 + '=' * (pad % 4))
                    kid_hex = kid_bytes.hex()
                    key_hex = _last_drm.get('keys', {}).get(kid_hex)
                    if key_hex:
                        k_b64 = _b64.urlsafe_b64encode(bytes.fromhex(key_hex)).rstrip(b'=').decode()
                        resp_keys.append({'kty': 'oct', 'kid': kid_b64, 'k': k_b64})
                resp = json.dumps({'keys': resp_keys, 'type': 'temporary'}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except:
                self.send_error(500)
            return
        self.send_error(404)
    def do_GET(self):
        path = self.path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        target = urllib.parse.unquote(qs.get('url', [''])[0])
        ref = urllib.parse.unquote(qs.get('ref', [''])[0])
        if not target:
            self.send_error(400)
            return
        try:
            tqs = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
            jwt_val = tqs.get('jwt', [None])[0]
            token_val = tqs.get('token', [None])[0]
            hdrs = {'User-Agent': UA, 'Referer': ref or target, 'Accept-Encoding': _AE}
            if jwt_val: hdrs['jwt'] = jwt_val
            if token_val: hdrs['Authorization'] = f'Bearer {token_val}'
            s = requests.Session()
            s.verify = False
            r = s.get(target, headers=hdrs, timeout=20, stream=True, allow_redirects=True)
            raw = r.content
            ct = r.headers.get('Content-Type', 'application/octet-stream')
            is_m3u8 = 'mpegurl' in ct or target.split('?')[0].endswith('.m3u8')
            if is_m3u8:
                raw = _rewrite_playlist(raw, target)
                ct = 'application/vnd.apple.mpegurl'
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(raw)
        except: self.send_error(502)

def _ensure_proxy():
    global _proxy_server, _proxy_port
    if _proxy_server is not None: return
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        _proxy_port = s.getsockname()[1]
    _proxy_server = http.server.HTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    t = threading.Thread(target=_proxy_server.serve_forever, daemon=True)
    t.start()

# ---------------------------------------------------------------------------
# Stream Resolvers
# ---------------------------------------------------------------------------

def _resolve_dlhd(embed_url, ref):
    try:
        sess = requests.Session()
        r = sess.get(embed_url, headers={'User-Agent': _DLHD_UA, 'Referer': ref, 'Accept-Encoding': _AE}, timeout=8)
        mp = re.search(r'<iframe[^>]+src=["\']?(https?://[^"\'> ]+/premiumtv/[^"\'> ]+)', r.text, re.I)
        if not mp: return None, None
        player_url = mp.group(1)
        r2 = sess.get(player_url, headers={'User-Agent': _DLHD_UA, 'Referer': embed_url, 'Accept-Encoding': _AE}, timeout=8)
        b64_m = re.search(r'source\s*:\s*window\.atob\(["\']([A-Za-z0-9+/=]+)["\']\)', r2.text)
        if not b64_m: return None, None
        m3u8_url = base64.b64decode(b64_m.group(1)).decode('utf-8', errors='replace')
        return m3u8_url, player_url
    except: return None, None

def _resolve_la14hd(url, ref):
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Referer': ref, 'Accept-Encoding': _AE}, timeout=10)
        m = re.search(r'var playbackURL\s*=\s*"([^"]+)"', r.text)
        if m: return m.group(1), url
        m = re.search(r'source\s*:\s*"([^"]+)"', r.text)
        if m: return m.group(1), url
        m = re.search(r'source\s*:\s*window\.atob\(["\']([A-Za-z0-9+/=]+)["\']\)', r.text)
        if m: return base64.b64decode(m.group(1)).decode('utf-8'), url
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.I)
        if m:
            iframe_url = m.group(1)
            if iframe_url.startswith('/'):
                parsed = urllib.parse.urlparse(url)
                iframe_url = f"{parsed.scheme}://{parsed.netloc}{iframe_url}"
            return _resolve_la14hd(iframe_url, url)
        return None, None
    except: return None, None

def resolve_embed(embed_url):
    if not embed_url: return None, None
    L(f"Resolving embed: {embed_url}")
    referer = 'https://streami.click/'
    
    try:
        parsed = urllib.parse.urlparse(embed_url)
        domain = parsed.netloc.lower()
        
        if 'megatuga.io' in domain:
            referer = 'https://megatuga.io/'
        
        L(f"Domain: {domain}, Referer: {referer}")

        if 'la14hd.com' in domain or 'tvtvpl.com' in domain:
            return _resolve_la14hd(embed_url, 'https://megadeportes.de/')
        
        if 'dlhd.dad' in domain:
            embed_url = embed_url.replace('dlhd.dad', 'daddyhd.com')
            domain = 'daddyhd.com'
            
        if '/e/vip/' in embed_url:
            return _resolve_dyndamn_iframe(embed_url, referer)
            
        if 'lovetier.bz' in domain:
            return _resolve_lovetier(embed_url, 'https://megatuga.io/' if 'megatuga' in referer else referer)
        elif 'videocdn' in domain:
            return _resolve_videocdn(embed_url, referer)
        elif 'topembed.pw' in domain:
            return _resolve_videocdn(embed_url, referer)
        elif any(d in domain for d in ['dlhd.pk', 'dlhd.link', 'dlhd.sx', 'dlhd.dad', 'daddyhd.com', 'dlstreams.com', 'dlstreams.top']):
            if 'stream/stream-' in embed_url or 'player/stream-' in embed_url or 'watch/stream-' in embed_url:
                return _resolve_dlhd(embed_url, referer)
        elif any(d in domain for d in ['sprtsonline.click', 'sportsonline.to', 'meritend.net', 'herdnew.net', 'dyndamn.net', 'swopglow.net']):
            return _resolve_dyndamn_iframe(embed_url, referer)
        elif 'antenasport.org' in domain:
            return _resolve_antena(embed_url, referer)
        elif 'popcdn.day' in domain:
            return _resolve_antena(embed_url, referer)
            
        return _resolve_generic(embed_url, referer)
    except Exception as e:
        L(f"Error in resolve_embed: {e}")
        return None, None

def _resolve_antena(url, ref):
    L(f"Resolving Antena Sport/PopCDN: {url}")
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Referer': ref, 'Accept-Encoding': _AE}, timeout=10)
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.I)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if iframe_url.startswith('//'): iframe_url = 'https:' + iframe_url
            if not iframe_url.startswith('http'):
                parsed = urllib.parse.urlparse(url)
                iframe_url = f"{parsed.scheme}://{parsed.netloc}{iframe_url}"
            L(f"Antena iframe found: {iframe_url}")
            # Route directly to dyndamn resolver for known xstream domains
            iframe_domain = urllib.parse.urlparse(iframe_url).netloc.lower()
            if any(d in iframe_domain for d in ['herdnew.net', 'dyndamn.net', 'swopglow.net', 'meritend.net']):
                return _resolve_dyndamn_iframe(iframe_url, url)
            return resolve_embed(iframe_url)
        return _resolve_generic(url, ref)
    except Exception as e:
        L(f"Error in _resolve_antena: {e}")
        return None, None

def _resolve_lovetier(url, ref):
    L(f"Resolving Lovetier: {url}")
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Referer': ref, 'Accept-Encoding': _AE}, timeout=10)
        # Tentar streamUrl no JSON de configuração
        m = re.search(r'streamUrl:\s*"(https?:\\/\\/[^"]+\.m3u8[^"]*)"', r.text)
        if not m: m = re.search(r'streamUrl:\s*"(https?://[^"]+\.m3u8[^"]*)"', r.text)
        if m: return m.group(1).replace('\\/', '/'), url
        
        # Tentar Clappr/JS file
        m = re.search(r'file\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', r.text)
        if m: return m.group(1), url
        
        return None, None
    except: return None, None

def _resolve_videocdn(url, ref):
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Referer': ref, 'Accept-Encoding': _AE}, timeout=10)
        # Tentar streamUrl direto no JS
        m = re.search(r'var streamUrl\s*=\s*"([^"]+)"', r.text)
        if m: return m.group(1), url
        # Tentar Clappr file
        m = re.search(r'file\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', r.text)
        if m: return m.group(1), url
        # Tentar iframe aninhado
        m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.I)
        if m:
            iframe_url = m.group(1)
            if iframe_url.startswith('/'):
                p = urllib.parse.urlparse(url)
                iframe_url = f"{p.scheme}://{p.netloc}{iframe_url}"
            return _resolve_videocdn(iframe_url, url)
        return None, None
    except: return None, None

def _decode_econfig(raw):
    import math
    permutation = [2, 0, 3, 1]
    pad = 4 - len(raw) % 4
    data = base64.b64decode(raw + '=' * (pad % 4)).decode('latin-1')
    chunk_size = math.ceil(len(data) / 4)
    chunks = [data[i * chunk_size:(i + 1) * chunk_size] for i in range(4)]
    result = [None] * 4
    for i, chunk in enumerate(chunks):
        chunk = chunk[:3] + chunk[4:]
        pad = 4 - len(chunk) % 4
        result[permutation[i]] = base64.b64decode(chunk + '=' * (pad % 4))
    joined = b''.join(result)
    pad = 4 - len(joined) % 4
    final = base64.b64decode(joined + b'=' * (pad % 4))
    import json as _json
    return _json.loads(final)

def _resolve_dyndamn_iframe(url, ref):
    L(f"Resolving dyndamn iframe: {url} (ref: {ref})")
    try:
        sess = requests.Session()
        r = sess.get(url, headers={'User-Agent': UA, 'Referer': ref, 'Accept-Encoding': _AE}, timeout=10)

        # xstream/_econfig decryption (meritend/dyndamn/herdnew)
        m = re.search(r"_econfig='([^']+)'", r.text)
        if m:
            try:
                config = _decode_econfig(m.group(1))
                stream_url = config.get('stream_url_nop2p') or config.get('stream_url')
                if stream_url:
                    stream_url = stream_url.replace('\\/', '/')
                    L(f"Resolved via _econfig: {stream_url[:80]}")
                    return stream_url, url
            except Exception as ex:
                L(f"_econfig decode error: {ex}")

        # Nested iframe fallback
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.I)
        if iframe_match:
            new_url = iframe_match.group(1)
            L(f"Found nested iframe: {new_url}")
            _XSTREAM_DOMAINS = ('meritend.net', 'dyndamn.net', 'herdnew.net', 'swopglow.net')
            if any(d in new_url for d in _XSTREAM_DOMAINS):
                return _resolve_dyndamn_iframe(new_url, url)
            return resolve_embed(new_url)

        m = re.search(r'source\s*:\s*window\.atob\(["\']([A-Za-z0-9+/=]+)["\']\)', r.text)
        if m:
            m3u8 = base64.b64decode(m.group(1)).decode('utf-8', errors='replace')
            L(f"Resolved m3u8 via b64: {m3u8}")
            return m3u8, url

        m = re.search(r'source\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m:
            L(f"Resolved m3u8 via direct regex: {m.group(1)}")
            return m.group(1), url

        L("No m3u8 found in dyndamn iframe content")
        return None, None
    except Exception as e:
        L(f"Error in _resolve_dyndamn_iframe: {e}")
        return None, None

def _resolve_generic(url, ref):
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Referer': ref, 'Accept-Encoding': _AE}, timeout=10)
        m = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text)
        if m: return m.group(1), url
        return None, None
    except: return None, None

# ---------------------------------------------------------------------------
# Data and Constants
# ---------------------------------------------------------------------------

CATEGORY_MAP = {
    'pilka nozna': 'pilkanozna', 'pilkanozna': 'pilkanozna', 'pilkanozna_wazne': 'pilkanozna',
    'futebol': 'pilkanozna', 'soccer': 'pilkanozna', 'futsal': 'pilkanozna',
    'pilkareczna': 'pilkanozna',
    'motorsport': 'motorsport', 'formula1': 'motorsport', 'f1': 'motorsport',
    'fights': 'fights', 'mma': 'fights', 'box': 'fights',
    'hokej': 'hokej', 'hockey': 'hokej',
    'tenis': 'tenis', 'tennis': 'tenis',
    'koszykowka': 'koszykowka', 'basketball': 'koszykowka',
    'baseball': 'baseball',
    'rugby': 'rugby',
    'wrestling': 'wrestling',
    'kolarstwo': 'kolarstwo', 'cycling': 'kolarstwo',
}

CAT_ASSET = {
    'pilkanozna': 'soccer.png', 'motorsport': 'motorsport.png', 'fights': 'fights.png',
    'hokej': 'hockey.png', 'tenis': 'tennis.png', 'koszykowka': 'basketball.png',
    'baseball': 'baseball.png', 'rugby': 'rugby.png', 'wrestling': 'wrestling.png',
    'kolarstwo': 'cycling.png', 'other': 'soccer.png'
}

COUNTRY_ORDER = ['portugal', 'romania', 'spain', 'english', 'poland', 'croatia', 'slovenia', 'czechia', 'serbia', 'france', 'sweden', 'germany', 'netherlands', 'greece']

COUNTRY_FILTERS = {
    'portugal': {'icon_file': 'flag_portugal.png', 'label_key': 'country_portugal', 'languages': ['portuguese', 'portugues', 'português', 'portugal', 'pt']},
    'romania': {'icon_file': 'flag_romania.png', 'label_key': 'country_romania', 'languages': ['romanian', 'romana', 'română', 'romeno', 'romenia', 'roménia', 'romania', 'ro']},
    'spain': {'icon_file': 'flag_spain.png', 'label_key': 'country_spain', 'languages': ['spanish', 'espanol', 'español', 'espanhol', 'spain', 'españa', 'es']},
    'english': {'icon_file': 'flag_english.png', 'label_key': 'country_english', 'languages': ['english', 'ingles', 'inglês', 'international', 'internacional', 'en']},
    'poland': {'icon_file': 'flag_poland.png', 'label': 'Polónia', 'languages': ['polski', 'polish', 'polonia', 'polónia', 'poland', 'pl']},
    'croatia': {'icon_file': 'flag_croatia.png', 'label': 'Croácia', 'languages': ['hrvatski', 'croatian', 'croacia', 'croácia', 'croatia', 'hr']},
    'slovenia': {'icon_file': 'flag_slovenia.png', 'label': 'Eslovénia', 'languages': ['slovenski', 'slovenian', 'slovene', 'eslovenia', 'eslovénia', 'slovenia', 'si']},
    'czechia': {'icon_file': 'flag_czechia.png', 'label': 'Chéquia', 'languages': ['cestina', 'čeština', 'czech', 'chequia', 'chéquia', 'czechia', 'cz']},
    'serbia': {'icon_file': 'flag_serbia.png', 'label': 'Sérvia', 'languages': ['srpski', 'serbian', 'servia', 'sérvia', 'serbia', 'rs']},
    'france': {'icon_file': 'flag_france.png', 'label': 'França', 'languages': ['francais', 'français', 'french', 'franca', 'frança', 'france', 'fr']},
    'sweden': {'icon_file': 'flag_sweden.png', 'label': 'Suécia', 'languages': ['svenska', 'swedish', 'suecia', 'suécia', 'sweden', 'se']},
    'germany': {'icon_file': 'flag_germany.png', 'label': 'Alemanha', 'languages': ['deutsch', 'german', 'alemao', 'alemão', 'germany', 'de']},
    'netherlands': {'icon_file': 'flag_netherlands.png', 'label': 'Países Baixos', 'languages': ['nederlands', 'dutch', 'holandes', 'holandês', 'netherlands', 'nl']},
    'greece': {'icon_file': 'flag_greece.png', 'label': 'Grécia', 'languages': ['ελληνικά', 'ellinika', 'greek', 'grego', 'grecia', 'grécia', 'greece', 'gr']},
}

def _plain_text(value):
    value = str(value or '').lower()
    return ''.join(c for c in unicodedata.normalize('NFD', value) if unicodedata.category(c) != 'Mn')

def _country_matches_language(country_id, language):
    cfg = COUNTRY_FILTERS.get(country_id, {})
    lang = _plain_text(language)
    if not lang: return False
    for token in cfg.get('languages', []):
        token = _plain_text(token)
        if not token: continue
        if len(token) <= 2:
            if lang == token: return True
        elif token in lang: return True
    return False

def _filter_embeds_by_country(embeds, country_id):
    filtered = []
    for lb in embeds or []:
        if _country_matches_language(country_id, lb.get('language', '')):
            filtered.append(lb)
    return filtered

def list_categories():
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    li_credits = xbmcgui.ListItem(label=f"[COLOR lightblue][B]{T('creators')}[/B][/COLOR]")
    li_credits.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url='', listitem=li_credits, isFolder=False)
    
    li_sport = xbmcgui.ListItem(label=f"[COLOR gold][B]{T('sport_desc')}[/B][/COLOR]")
    li_sport.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url='', listitem=li_sport, isFolder=False)

    li_ppv = xbmcgui.ListItem(label=f"[COLOR red][B]{T('ppv_live')}[/B][/COLOR]")
    li_ppv.setArt({'icon': 'https://ppv.to/assets/img/ppv_to.png', 'thumb': 'https://ppv.to/assets/img/ppv_to.png', 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='ppv_menu'), listitem=li_ppv, isFolder=True)

    li_mega = xbmcgui.ListItem(label=f"[COLOR orange][B]{T('megadeportes')}[/B][/COLOR]")
    icon_mega = get_asset('latin_america.png')
    li_mega.setArt({'icon': icon_mega, 'thumb': icon_mega, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='megadeportes_channels'), listitem=li_mega, isFolder=True)

    li_pt_sport = xbmcgui.ListItem(label=f"[B]{T('portugal_sport')}[/B]")
    icon_pt = get_asset('flag_portugal.png')
    li_pt_sport.setArt({'icon': icon_pt, 'thumb': icon_pt, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='portugal_sport_channels'), listitem=li_pt_sport, isFolder=True)

    li_antena = xbmcgui.ListItem(label=f"[B]{T('antena_sport')}[/B]")
    icon_antena = get_asset('antenasport.png')
    li_antena.setArt({'icon': icon_antena, 'thumb': icon_antena, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='antena_sport_menu'), listitem=li_antena, isFolder=True)
    
    li_countries = xbmcgui.ListItem(label=T('countries_menu'))
    icon_world = get_asset('world_map.png')
    li_countries.setArt({'icon': icon_world, 'thumb': icon_world, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='list_countries'), listitem=li_countries, isFolder=True)

    cats = ['all', 'pilkanozna', 'motorsport', 'fights', 'hokej', 'tenis', 'koszykowka', 'baseball', 'rugby', 'wrestling', 'kolarstwo', 'other']
    for cid in cats:
        li = xbmcgui.ListItem(label=T(cid))
        icon_asset = get_asset(CAT_ASSET.get(cid, 'icon.png'))
        li.setArt({'icon': icon_asset, 'thumb': icon_asset, 'fanart': FANART})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='list_events', category=cid), listitem=li, isFolder=True)
    
    li_settings = xbmcgui.ListItem(label=T('settings'))
    li_settings.setArt({'icon': ICON, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='open_settings'), listitem=li_settings, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)

def _fetch_events():
    session = requests.Session()
    session.headers.update({'User-Agent': UA, 'Referer': 'https://streami.click/', 'X-SSIG': 'bytmo8xialhem066', 'Accept-Encoding': _AE})
    events, seen = [], set()
    for api in ['/api/getEvents.php', '/api/J.php']:
        try:
            r = session.get(f'https://streami.click/{api}', timeout=12)
            if r.status_code == 200:
                c = r.text.strip()
                if not c: continue
                try:
                    pad = len(c) % 4
                    if pad: c += '=' * (4 - pad)
                    data = json.loads(base64.b64decode(c).decode('utf-8'))
                except:
                    try: data = r.json()
                    except: continue
                if isinstance(data, list):
                    for e in data:
                        if e.get('id') and e['id'] not in seen:
                            events.append(e); seen.add(e['id'])
        except: continue
    return events

def list_countries():
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    for country_id in COUNTRY_ORDER:
        cfg = COUNTRY_FILTERS.get(country_id, {})
        label = T(cfg['label_key']) if cfg.get('label_key') else cfg.get('label', country_id)
        li = xbmcgui.ListItem(label=label)
        icon_file = get_asset(cfg.get('icon_file', 'icon.png'))
        li.setArt({'icon': icon_file, 'thumb': icon_file, 'fanart': FANART})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='list_country_events', country=country_id), listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def list_country_events(country_id):
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    events = _fetch_events()
    if not events: xbmcplugin.endOfDirectory(HANDLE); return
    added = 0
    now = datetime.datetime.now().timestamp()
    for e in events:
        st = e.get('startTime', 0)
        if st > 0 and now > (st + 10800): continue
        embeds = _filter_embeds_by_country(e.get('_embeds', []), country_id)
        if not embeds: continue
        m_cat = CATEGORY_MAP.get(e.get('category', '').lower(), 'other')
        title = e.get('title', T('untitled'))
        if 'startTime' in e:
            try: title = f"[{datetime.datetime.fromtimestamp(e['startTime']).strftime('%H:%M')}] {title}"
            except: pass
        if e.get('league'): title = f"{title}  [{e['league']}]"
        is_online = False
        if 'startTime' in e:
            now = datetime.datetime.now().timestamp()
            st = e['startTime']
            if st <= now <= (st + 10800): is_online = True
        display_title = f"{title} [COLOR green]Live[/COLOR]" if is_online else title
        li = xbmcgui.ListItem(label=display_title)
        asset_name = CAT_ASSET.get(m_cat, 'icon.png')
        icon_asset = get_asset(asset_name)
        li.setArt({'icon': icon_asset, 'thumb': icon_asset, 'fanart': FANART})
        li.setInfo('video', {'title': title, 'mediatype': 'video'})
        smart_enabled = ADDON.getSetting('smart_play') == 'true'
        if smart_enabled:
            url = get_url(action='smart_play', embeds=json.dumps(embeds))
            is_folder = False
        else:
            url = get_url(action='list_sources', embeds=json.dumps(embeds), title=e.get('title', ''), cat_asset=asset_name)
            is_folder = True
        li.setProperty('IsPlayable', 'true' if smart_enabled else 'false')
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=li, isFolder=is_folder)
        added += 1
    if added == 0: xbmcgui.Dialog().notification('Sport', T('no_country_sources'), xbmcgui.NOTIFICATION_INFO, 5000)
    xbmcplugin.endOfDirectory(HANDLE)

def list_events(category):
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    events = _fetch_events()
    if not events: xbmcplugin.endOfDirectory(HANDLE); return
    now = datetime.datetime.now().timestamp()
    for e in events:
        st = e.get('startTime', 0)
        if st > 0 and now > (st + 10800): continue
        m_cat = CATEGORY_MAP.get(e.get('category', '').lower(), 'other')
        if category != 'all' and m_cat != category: continue
        embeds = e.get('_embeds', [])
        if not embeds: continue
        title = e.get('title', T('untitled'))
        if 'startTime' in e:
            try: title = f"[{datetime.datetime.fromtimestamp(e['startTime']).strftime('%H:%M')}] {title}"
            except: pass
        if e.get('league'): title = f"{title}  [{e['league']}]"
        is_online = False
        if 'startTime' in e:
            now = datetime.datetime.now().timestamp()
            st = e['startTime']
            if st <= now <= (st + 10800): is_online = True
        display_title = f"{title} [COLOR green]Live[/COLOR]" if is_online else title
        li = xbmcgui.ListItem(label=display_title)
        asset_name = CAT_ASSET.get(m_cat, 'icon.png')
        icon_asset = get_asset(asset_name)
        li.setArt({'icon': icon_asset, 'thumb': icon_asset, 'fanart': FANART})
        li.setInfo('video', {'title': title, 'mediatype': 'video'})
        smart_enabled = ADDON.getSetting('smart_play') == 'true'
        if smart_enabled:
            url = get_url(action='smart_play', embeds=json.dumps(embeds))
            is_folder = False
        else:
            url = get_url(action='list_sources', embeds=json.dumps(embeds), title=e.get('title', ''), cat_asset=asset_name)
            is_folder = True
        li.setProperty('IsPlayable', 'true' if smart_enabled else 'false')
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=li, isFolder=is_folder)
    xbmcplugin.endOfDirectory(HANDLE)

def list_sources(embeds_json, event_title='', cat_asset='icon.png'):
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    try: embeds = json.loads(embeds_json)
    except: embeds = []
    icon_asset = get_asset(cat_asset)
    for lb in embeds:
        lang = lb.get('language', T('unknown'))
        for s_id, si in lb.get('embeds', {}).items():
            url = si.get('embed', '')
            if not url: continue
            q_label = si.get('label', 'SD')
            q_trans = T('hd') if 'HD' in q_label.upper() else T('sd')
            label = f"{lang} — {q_trans}"
            try: label += f" [{urllib.parse.urlparse(url).netloc.split('.')[0].upper()}]"
            except: pass
            li = xbmcgui.ListItem(label=label)
            li.setArt({'icon': icon_asset, 'thumb': icon_asset, 'fanart': FANART})
            li.setInfo('video', {'title': f"{event_title} — {label}", 'mediatype': 'video'})
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='play', video_url=url), listitem=li, isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)

def smart_play_logic(embeds_json):
    try: embeds = json.loads(embeds_json)
    except: return
    all_links = []
    for lb in embeds:
        for s_id, si in lb.get('embeds', {}).items():
            url = si.get('embed', '')
            if url: all_links.append(url)
    if not all_links: return
    progress = xbmcgui.DialogProgress()
    progress.create('Sport', T('resolving'))
    found = False
    for i, url in enumerate(all_links):
        if progress.iscanceled(): break
        progress.update(int((i / len(all_links)) * 100), f"{T('resolving')} {i+1}/{len(all_links)}...")
        try:
            stream_url, referer = resolve_embed(url)
            if stream_url:
                progress.close()
                li = xbmcgui.ListItem(path=stream_url)
                if referer: li.setProperty('inputstream.adaptive.manifest_headers', f'Referer={referer}')
                xbmcplugin.setResolvedUrl(HANDLE, True, listitem=li)
                found = True
                break
        except: continue
    if not found:
        progress.close()
        xbmcgui.Dialog().notification('Sport', T('error_resolve'), xbmcgui.NOTIFICATION_ERROR, 5000)

def play_video(embed_url):
    try: _ensure_proxy()
    except: pass
    progress = xbmcgui.DialogProgress()
    progress.create('Sport', T('resolving'))
    try:
        stream_url, referer = resolve_embed(embed_url)
        if not stream_url:
            progress.close()
            xbmcgui.Dialog().notification('Sport', T('error_resolve'), xbmcgui.NOTIFICATION_ERROR, 5000)
            xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())
            return
        is_mpd = '.mpd' in stream_url
        is_xstream_cdn = ':8443/hls/' in stream_url
        li = xbmcgui.ListItem()
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setInfo('video', {'mediatype': 'video'})
        li.setContentLookup(False)
        if is_mpd:
            manifest_url = stream_url
            li.setMimeType('application/dash+xml')
            if _last_drm.get('type') == 'clearkey' and _last_drm.get('keys'):
                li.setProperty('inputstream.adaptive.drm_legacy', f'org.w3.clearkey|http://127.0.0.1:{_proxy_port}/ckls')
        elif is_xstream_cdn:
            manifest_url = stream_url
            ref = referer or embed_url
            hdrs = f'User-Agent={urllib.parse.quote(UA)}&Referer={urllib.parse.quote(ref)}'
            li.setProperty('inputstream.adaptive.manifest_headers', hdrs)
            li.setProperty('inputstream.adaptive.stream_headers', hdrs)
            li.setMimeType('application/vnd.apple.mpegurl')
        else:
            manifest_url = _proxy_url(stream_url, referer or embed_url)
            li.setMimeType('application/vnd.apple.mpegurl')
        li.setPath(manifest_url)
        progress.close()
        xbmcplugin.setResolvedUrl(HANDLE, True, listitem=li)
    except:
        progress.close()
        xbmcplugin.setResolvedUrl(HANDLE, False, listitem=xbmcgui.ListItem())

# ---------------------------------------------------------------------------
# Canais Latinos (MegaDeportes)
# ---------------------------------------------------------------------------

def megadeportes_channels():
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    try:
        r = requests.get('https://megadeportes.de/', headers={'User-Agent': UA}, timeout=10)
        matches = re.findall(r'<h2 class="title">([^<]+)</h2>\s*<a href="/eventos\.html\?r=([^"]+)"', r.text)
        for name, b64_url in matches:
            try:
                real_url = base64.b64decode(b64_url).decode('utf-8')
                li = xbmcgui.ListItem(label=name)
                li.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
                li.setInfo('video', {'title': name, 'mediatype': 'video'})
                li.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='play', video_url=real_url), listitem=li, isFolder=False)
            except: continue
    except: pass
    xbmcplugin.endOfDirectory(HANDLE)

def portugal_sport_channels():
    L("Listing Portugal Sport channels from Megatuga")
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    try:
        r = requests.get('https://megatuga.io/canais-de-desporto/', headers={'User-Agent': UA}, timeout=10)
        L(f"Megatuga response code: {r.status_code}")
        
        pattern = r'data-key="([^"]+)"\s+data-src="([^"]+)"|data-src="([^"]+)"\s+data-key="([^"]+)"'
        raw_matches = re.findall(pattern, r.text)
        
        matches = []
        for m in raw_matches:
            if m[0]: matches.append((m[1], m[0]))
            else: matches.append((m[2], m[3]))
        
        L(f"Found {len(matches)} channels")
        
        key_names = {
            'sporttv1': 'Sport TV 1', 'sporttv2': 'Sport TV 2', 'sporttv3': 'Sport TV 3',
            'sporttv4': 'Sport TV 4', 'sporttv5': 'Sport TV 5', 'sporttv6': 'Sport TV 6',
            'sporttv7': 'Sport TV 7', 'sporttvplus': 'Sport TV +', 'dazn1': 'DAZN 1',
            'dazn2': 'DAZN 2', 'dazn3': 'DAZN 3', 'dazn4': 'DAZN 4', 'dazn5': 'DAZN 5',
            'btv': 'Benfica TV (BTV)'
        }

        for url, key in matches:
            name = key_names.get(key, key.upper())
            li = xbmcgui.ListItem(label=name)
            icon = ICON
            img_match = re.search(fr'data-key="{key}"[^>]*>\s*<img[^>]+src="([^"]+)"', r.text)
            if img_match:
                icon = img_match.group(1)
                if icon.startswith('/'): icon = 'https://megatuga.io' + icon
            
            li.setArt({'icon': icon, 'thumb': icon, 'fanart': FANART})
            li.setInfo('video', {'title': name, 'mediatype': 'video'})
            li.setProperty('IsPlayable', 'true')
            L(f"Adding channel: {name} -> {url}")
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='play', video_url=url), listitem=li, isFolder=False)
    except Exception as e:
        L(f"Error listing Portugal Sport channels: {e}")
    xbmcplugin.endOfDirectory(HANDLE)

def antena_sport_menu():
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    antena_icon = get_asset('antenasport.png')
    
    li_schedule = xbmcgui.ListItem(label=f"[B]{T('antena_schedule')}[/B]")
    li_schedule.setArt({'icon': antena_icon, 'thumb': antena_icon, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='antena_sport_schedule'), listitem=li_schedule, isFolder=True)
    
    li_channels = xbmcgui.ListItem(label=f"[B]{T('antena_all_channels')}[/B]")
    li_channels.setArt({'icon': antena_icon, 'thumb': antena_icon, 'fanart': FANART})
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='antena_sport_channels'), listitem=li_channels, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)

def antena_sport_schedule():
    L("Listing Antena Sport schedule")
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    antena_icon = get_asset('antenasport.png')
    try:
        json_path = os.path.join(ADDON_PATH, 'resources', 'antena_schedule.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                schedule = json.load(f)
            
            for event in schedule:
                time = event.get('time', '')
                title = event.get('title', 'Unknown')
                channels = event.get('channels', [])
                
                label = f"[COLOR gold]{time}[/COLOR] {title}"
                # Se houver apenas um canal, podemos tornar o item jogável diretamente
                # Se houver vários, criamos uma subpasta
                if len(channels) == 1:
                    ch = channels[0]
                    li = xbmcgui.ListItem(label=label)
                    li.setArt({'icon': antena_icon, 'thumb': antena_icon, 'fanart': FANART})
                    li.setInfo('video', {'title': title, 'plot': f"Canal: {ch['name']}"})
                    li.setProperty('IsPlayable', 'true')
                    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='play', video_url=ch['url']), listitem=li, isFolder=False)
                else:
                    li = xbmcgui.ListItem(label=label)
                    li.setArt({'icon': antena_icon, 'thumb': antena_icon, 'fanart': FANART})
                    li.setInfo('video', {'title': title, 'plot': "Vários canais disponíveis"})
                    # Passar os canais como string JSON para a próxima ação
                    ch_json = json.dumps(channels)
                    xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='antena_event_sources', channels=ch_json, title=title), listitem=li, isFolder=True)
        else:
            xbmcgui.Dialog().notification('Sport', 'Agenda não disponível', xbmcgui.NOTIFICATION_INFO, 5000)
    except Exception as e:
        L(f"Error listing Antena Sport schedule: {e}")
    xbmcplugin.endOfDirectory(HANDLE)

def antena_event_sources(channels_json, title):
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    antena_icon = get_asset('antenasport.png')
    try:
        channels = json.loads(channels_json)
        for ch in channels:
            li = xbmcgui.ListItem(label=ch['name'])
            li.setArt({'icon': antena_icon, 'thumb': antena_icon, 'fanart': FANART})
            li.setInfo('video', {'title': f"{title} - {ch['name']}"})
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='play', video_url=ch['url']), listitem=li, isFolder=False)
    except: pass
    xbmcplugin.endOfDirectory(HANDLE)

def antena_sport_channels():
    L("Listing Antena Sport channels from local database")
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    try:
        json_path = os.path.join(ADDON_PATH, 'resources', 'antena_channels.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                channels = json.load(f)
            
            antena_icon = get_asset('antenasport.png')
            for ch in channels:
                name = ch.get('name', 'Unknown')
                url = ch.get('url', '')
                if not url: continue
                
                li = xbmcgui.ListItem(label=name)
                li.setArt({'icon': antena_icon, 'thumb': antena_icon, 'fanart': FANART})
                li.setInfo('video', {'title': name, 'mediatype': 'video'})
                li.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='play', video_url=url), listitem=li, isFolder=False)
    except Exception as e:
        L(f"Error listing Antena Sport channels: {e}")
    xbmcplugin.endOfDirectory(HANDLE)

def get_url(**kwargs):
    return f"{BASE_URL}?{urllib.parse.urlencode(kwargs)}"


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PPV.TO Integration (v2 - API Based)
# ---------------------------------------------------------------------------

def ppv_menu():
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    api_url = "https://api.ppv.to/api/streams"
    headers = {"User-Agent": UA, "Referer": "https://ppv.to/"}
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        data = r.json()
        if data.get('success'):
            now = datetime.datetime.now().timestamp()
            for cat in data.get('streams', []):
                cat_name = cat.get('category', 'Outros')
                for s in cat.get('streams', []):
                    # Verificar se está ao vivo ou começa em breve
                    starts = s.get('starts_at', 0)
                    ends = s.get('ends_at', 0)
                    
                    is_live = starts <= now <= ends
                    is_soon = now < starts < (now + 86400) # Próximas 24h
                    
                    if is_live:
                        name = f"[COLOR green]● LIVE[/COLOR] {s.get('name')}"
                        label = f"{name} [[COLOR gold]{s.get('tag', '')}[/COLOR]]"
                        li = xbmcgui.ListItem(label=label)
                        icon = s.get('poster', 'https://ppv.to/assets/img/ppv_to.png')
                        li.setArt({'icon': icon, 'thumb': icon, 'fanart': FANART})
                        li.setInfo('video', {'title': s.get('name'), 'plot': f"Categoria: {cat_name}", 'mediatype': 'video'})
                        li.setProperty('IsPlayable', 'true')
                        # Usamos o link do iframe da API como base
                        iframe_url = s.get('iframe', '')
                        xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='play_ppv', video_url=iframe_url), listitem=li, isFolder=False)

            # Adicionar link para Programação Completa
            li_sched = xbmcgui.ListItem(label=f"[I]{T('ppv_schedule')}[/I]")
            li_sched.setArt({'icon': ICON, 'thumb': ICON, 'fanart': FANART})
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=get_url(action='ppv_schedule'), listitem=li_sched, isFolder=True)
    except Exception as e:
        L(f"PPV_MENU ERROR: {e}")
    xbmcplugin.endOfDirectory(HANDLE)

def ppv_schedule():
    xbmcplugin.setPluginFanart(HANDLE, FANART)
    api_url = "https://api.ppv.to/api/streams"
    headers = {"User-Agent": UA, "Referer": "https://ppv.to/"}
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        data = r.json()
        if data.get('success'):
            now = datetime.datetime.now().timestamp()
            for cat in data.get('streams', []):
                for s in cat.get('streams', []):
                    starts = s.get('starts_at', 0)
                    if starts > now:
                        start_time = datetime.datetime.fromtimestamp(starts).strftime('%H:%M')
                        name = f"[COLOR gold][{start_time}][/COLOR] {s.get('name')}"
                        li = xbmcgui.ListItem(label=name)
                        icon = s.get('poster', ICON)
                        li.setArt({'icon': icon, 'thumb': icon, 'fanart': FANART})
                        li.setInfo('video', {'title': s.get('name'), 'plot': f"Começa às {start_time}"})
                        xbmcplugin.addDirectoryItem(handle=HANDLE, url='', listitem=li, isFolder=False)
    except: pass
    xbmcplugin.endOfDirectory(HANDLE)

def play_ppv(iframe_url):
    progress = xbmcgui.DialogProgress()
    progress.create('Sport', T('resolving'))
    resolved = iframe_url
    try:
        # Lógica para extrair o link real oculto no HTML do iframe
        headers = {"User-Agent": UA, "Referer": "https://ppv.to/"}
        r = requests.get(iframe_url, headers=headers, timeout=10)
        
        # 1. Procurar por source m3u8 no JS
        m3u8_match = re.search(r'source\s*:\s*["\'\'](https?://[^"\'\']+\.[Mm]3[Uu]8[^"\'\']*)["\'\']', r.text)
        if m3u8_match:
            resolved = m3u8_match.group(1)
        else:
            # 2. Procurar por window.atob (links em base64)
            b64_match = re.search(r'window\.atob\(["\'\']([A-Za-z0-9+/=]+)["\'\']\)', r.text)
            if b64_match:
                import base64 as _b64
                resolved = _b64.b64decode(b64_match.group(1)).decode('utf-8')
        
        # Se ainda for um link de embed (pooembed, etc), o Kodi/IA pode tentar resolver
    except: pass
    progress.close()
    
    li = xbmcgui.ListItem(path=resolved)
    if 'm3u8' in resolved:
        li.setMimeType('application/vnd.apple.mpegurl')
        li.setProperty('inputstream', 'inputstream.adaptive')
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=li)

def router(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring))
    if params:
        action = params.get('action', '')
        if action == 'list_events': list_events(params.get('category', 'all'))
        elif action == 'list_countries': list_countries()
        elif action == 'list_country_events': list_country_events(params.get('country', ''))
        elif action == 'list_sources': list_sources(params.get('embeds', '[]'), params.get('title', ''), params.get('cat_asset', 'icon.png'))
        elif action == 'smart_play': smart_play_logic(params.get('embeds', '[]'))
        elif action == 'play': play_video(params.get('video_url', ''))
        elif action == 'ppv_menu': ppv_menu()
        elif action == 'ppv_schedule': ppv_schedule()
        elif action == 'play_ppv': play_ppv(params.get('video_url', ''))
        elif action == 'megadeportes_channels': megadeportes_channels()
        elif action == 'portugal_sport_channels': portugal_sport_channels()
        elif action == 'antena_sport_menu': antena_sport_menu()
        elif action == 'antena_sport_schedule': antena_sport_schedule()
        elif action == 'antena_event_sources': antena_event_sources(params.get('channels', '[]'), params.get('title', ''))
        elif action == 'antena_sport_channels': antena_sport_channels()
        elif action == 'open_settings': ADDON.openSettings()
        else: list_categories()
    else: list_categories()

if __name__ == '__main__':
    router(sys.argv[2][1:])
