# -*- coding: utf-8 -*-
"""
RomyLive+ - Cinemateca / Filme Vechi (integrare canal Telegram)
----------------------------------------------------------------------------
Sectiune noua pentru categoria FILME, care afiseaza filmele postate pe un
canal public de Telegram (implicit: @cinematecaro11 - "Cinemateca, filme vechi").

Cum functioneaza
----------------
1. Lista de postari este citita de la serviciul public tg.i-c-a.su
   (Telegram -> JSON, aceeasi sursa folosita si de RSS-ul canalului).
2. Fiecare postare cu video devine un film in lista Kodi:
      titlu      = textul postarii (ex: "Casablanca (1942)")
      thumbnail  = cadrul trimis de canal (/media/<canal>/<id>/preview)
      link       = fisierul video, servit direct cu suport de "Range",
                   deci Kodi il reda fara descarcare completa.
3. Lista este salvata in cache local (implicit 6 ore), ca sa nu lovim
   limita de 15 cereri/minut a serviciului.

Toate valorile (canal, server, cache) se pot schimba din
Setari -> Cinemateca (Telegram).
"""

import base64
import os
import re
import sys
import time
import json

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

try:
    import requests
except Exception:  # pragma: no cover - requests exista in Kodi, dar nu stricam nimic
    requests = None

try:
    import urllib.request as _urlreq
    import urllib.parse as _urlparse
except ImportError:  # Python 2
    import urllib2 as _urlreq
    import urllib as _urlparse

try:
    from html import unescape as _html_unescape
except ImportError:  # Python 2
    from HTMLParser import HTMLParser
    _html_unescape = HTMLParser().unescape

try:
    import unicodedata
except ImportError:
    unicodedata = None


# ---------------------------------------------------------------------------
# Configurare implicita (se poate schimba din setarile addon-ului)
# ---------------------------------------------------------------------------
ADDON_ID = 'plugin.video.RomyLive'
DEFAULT_CHANNEL = 'cinematecaro11'
DEFAULT_API_BASE = 'https://tg.i-c-a.su'

FANART = 'https://documentarys.do.am/2026/Principal/romylive.png'
FALLBACK_THUMB = 'https://documentarys.do.am/2026/filme/filme.png'

PAGE_SIZE = 100          # serviciul returneaza maximum 100 de postari/cerere
MAX_PAGES = 8            # plasa de siguranta (8 x 100 = 800 postari)
FILMS_PER_PAGE = 100     # cate filme afisam pe o "pagina" in Kodi
DEFAULT_CACHE_HOURS = 6
HTTP_TIMEOUT = 20
HTTP_RETRIES = 2
MAX_FLOOD_WAIT = 15      # cat asteptam maxim cand serviciul ne cere sa asteptam
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Kodi RomyLive+'
# Lista completa a filmelor, inclusa in addon. Serviciul public da des
# "FLOOD_WAIT" (limita de cereri), asa ca lista trebuie sa functioneze si fara el.
SNAPSHOT_NAME = 'cinemateca_snapshot.json'

# Ultimul motiv de esec (apare in textul butonului "Actualizeaza lista")
_LAST_ERROR = ''

MONTHS_RO = ['', 'ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie',
             'iulie', 'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie']


# ---------------------------------------------------------------------------
# Ajutoare generale
# ---------------------------------------------------------------------------
def _addon():
    try:
        return xbmcaddon.Addon(ADDON_ID)
    except Exception:
        return xbmcaddon.Addon()


def _setting(key, default=''):
    try:
        value = _addon().getSetting(key)
        if value is None:
            return default
        value = value.strip()
        return value if value != '' else default
    except Exception:
        return default


def _setting_bool(key, default=True):
    try:
        value = _addon().getSetting(key)
        if value is None or value == '':
            return default
        return str(value).lower() == 'true'
    except Exception:
        return default


def _setting_int(key, default=0):
    try:
        return int(float(_addon().getSetting(key)))
    except Exception:
        return default


def _log(message, level=xbmc.LOGINFO):
    try:
        xbmc.log('[Cinemateca] ' + message, level)
    except Exception:
        pass


def _translate(path):
    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        return xbmc.translatePath(path)


def _profile_path():
    try:
        path = _translate(_addon().getAddonInfo('profile'))
        if isinstance(path, bytes):
            path = path.decode('utf-8')
    except Exception:
        path = ''
    if not path:
        try:
            path = _translate('special://profile/addon_data/' + ADDON_ID + '/')
        except Exception:
            path = ''
    try:
        if path and not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)
    except Exception:
        pass
    return path


def _cache_file():
    return os.path.join(_profile_path(), 'cinemateca_cache.json')


# ---------------------------------------------------------------------------
# Cache local
# ---------------------------------------------------------------------------
def _cache_hours():
    hours = _setting_int('cinemateca_cache_hours', DEFAULT_CACHE_HOURS)
    if hours <= 0:
        hours = DEFAULT_CACHE_HOURS
    return hours * 3600


def _cache_load(max_age=None):
    """Returneaza lista salvata sau None daca lipseste/expira."""
    try:
        path = _cache_file()
        if not path or not os.path.isfile(path):
            return None
        if max_age is None:
            max_age = _cache_hours()
        if max_age and (time.time() - os.path.getmtime(path)) > max_age:
            return None
        with open(path, 'r') as handle:
            payload = json.load(handle)
        items = payload.get('items') if isinstance(payload, dict) else payload
        if isinstance(items, list) and items:
            return items
    except Exception as exc:
        _log('Citire cache a esuat: %s' % exc, xbmc.LOGWARNING)
    return None


def _cache_save(items):
    try:
        path = _cache_file()
        if not path:
            return
        payload = {'ts': int(time.time()), 'channel': _channel(), 'items': items}
        with open(path, 'w') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        _log('Scriere cache a esuat: %s' % exc, xbmc.LOGWARNING)


def clear_cache(delete_file=False):
    """Goleste cache-ul (forteaza recitirea canalului la urmatoarea deschidere)."""
    try:
        path = _cache_file()
        if path and os.path.isfile(path):
            if delete_file:
                os.remove(path)
            else:
                os.utime(path, (time.time() - 86400 * 30, time.time() - 86400 * 30))
    except Exception as exc:
        _log('Stergere cache a esuat: %s' % exc, xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# Acces la serviciul Telegram -> JSON
# ---------------------------------------------------------------------------
def _channel():
    value = _setting('cinemateca_channel', DEFAULT_CHANNEL)
    if value.startswith('@'):
        value = value[1:]
    value = value.rstrip('/')
    if '/' in value:  # acceptam si link complet t.me/canal
        value = value.split('/')[-1]
    return value or DEFAULT_CHANNEL


def _api_base():
    return _setting('cinemateca_api_base', DEFAULT_API_BASE).rstrip('/') or DEFAULT_API_BASE


def _http_get(url):
    """GET cu User-Agent + retry pe FLOOD_WAIT/429. Intoarce text sau None."""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ro-RO,ro;q=0.9,en;q=0.8'
    }
    for attempt in range(HTTP_RETRIES):
        body = None
        status = None
        try:
            if requests is not None:
                response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
                status = response.status_code
                if status == 200:
                    return response.text
                try:
                    body = response.text
                except Exception:
                    body = ''
            else:
                request = _urlreq.Request(url, headers=headers)
                try:
                    raw = _urlreq.urlopen(request, timeout=HTTP_TIMEOUT).read()
                except Exception as exc:
                    body = str(exc)
                    raw = None
                if raw is not None:
                    try:
                        return raw.decode('utf-8', 'ignore')
                    except Exception:
                        return raw
        except Exception as exc:
            body = str(exc)

        wait = 4
        match = re.search(r'FLOOD_WAIT_(\d+)', body or '')
        if match:
            wait = min(int(match.group(1)) + 1, MAX_FLOOD_WAIT)
        elif status == 429:
            wait = 8
        elif status is not None and status != 200:
            _remember_error('HTTP %s' % status)
            _log('Raspuns HTTP %s pentru %s' % (status, url), xbmc.LOGWARNING)
            return None
        _remember_error((body or 'raspuns gol')[:120])
        if attempt < HTTP_RETRIES - 1:
            _log('Se reincearca in %ss (%s)' % (wait, (body or '')[:120]), xbmc.LOGWARNING)
            try:
                xbmc.sleep(wait * 1000)
            except Exception:
                time.sleep(wait)
    return None


def _api_json(page):
    url = '%s/json/%s?limit=%d' % (_api_base(), _channel(), PAGE_SIZE)
    if page > 1:
        url += '&page=%d' % page
    raw = _http_get(url)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception as exc:
        _log('JSON invalid: %s' % exc, xbmc.LOGWARNING)
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Curatare texte / titluri
# ---------------------------------------------------------------------------
def _clean_text(value):
    text = value or ''
    text = re.sub(r'(?is)<br\s*/?>', ' ', text)
    text = re.sub(r'(?is)</p>', ' ', text)
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    try:
        text = _html_unescape(text)
    except Exception:
        pass
    text = text.replace(' ', ' ').replace('​', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _split_title(caption, post_id, date_ts):
    """Din textul postarii scoate titlul si anul: 'Casablanca (1942)' -> ('Casablanca','1942')."""
    text = _clean_text(caption)
    year = ''
    match = re.search(r'[\(\[]\s*((?:1[89]|20)\d{2})\s*[\)\]]\s*$', text)
    if match:
        year = match.group(1)
        text = text[:match.start()].strip(' -–—–.,:')
    else:
        match = re.search(r'\b((?:1[89]|20)\d{2})\b\s*$', text)
        if match:
            year = match.group(1)
            text = text[:match.start()].strip(' -–—–.,:')
    if not year:
        # an scris oriunde in titlu (ex: "12 angry men (1957) locul 5 in top all time")
        match = re.search(r'[\(\[]\s*((?:1[89]|20)\d{2})\s*[\)\]]', text)
        if match:
            year = match.group(1)
    text = text.strip(' -–—–.,:')
    if not text:
        try:
            date_label = time.strftime('%d.%m.%Y', time.localtime(date_ts)) if date_ts else ''
        except Exception:
            date_label = ''
        text = 'Film #%s' % post_id
        if date_label:
            text += ' (' + date_label + ')'
    return text, year


def _normalize_for_search(text):
    value = _clean_text(text).lower()
    if unicodedata is not None:
        try:
            value = unicodedata.normalize('NFKD', value)
            value = ''.join(c for c in value if not unicodedata.combining(c))
        except Exception:
            pass
    value = value.replace('ş', 's').replace('ţ', 't').replace('ş', 's')
    return re.sub(r'\s+', ' ', value).strip()


def _human_size(size):
    try:
        size = float(size or 0)
    except Exception:
        return ''
    if size <= 0:
        return ''
    size /= 1024.0 * 1024.0
    if size < 1024:
        return '%.0f MB' % size
    size /= 1024.0
    if size < 1024:
        return '%.2f GB' % size
    return '%.2f TB' % (size / 1024.0)


def _pretty_date(ts):
    try:
        stamp = time.localtime(ts)
        return '%d %s %d' % (stamp.tm_mday, MONTHS_RO[stamp.tm_mon], stamp.tm_year)
    except Exception:
        return ''


# ---------------------------------------------------------------------------
# Normalizarea unei postari
# ---------------------------------------------------------------------------
def _normalize_message(message):
    media = message.get('media') or {}
    if media.get('_') != 'messageMediaDocument':
        return None
    document = media.get('document') or {}
    mime = (document.get('mime_type') or '').lower()
    if not mime.startswith('video'):
        return None
    post_id = message.get('id')
    access_hash = document.get('access_hash')
    file_id = document.get('id')
    if not post_id or access_hash is None or not file_id:
        return None
    if 'mp4' in mime:
        extension = 'mp4'
    elif 'mkv' in mime:
        extension = 'mkv'
    elif 'webm' in mime:
        extension = 'webm'
    else:
        extension = 'mp4'
    base = _api_base()
    channel = _channel()
    title, year = _split_title(message.get('message'), post_id, message.get('date'))
    description = 'Film postat pe canalul Telegram @%s' % channel
    posted = _pretty_date(message.get('date'))
    if posted:
        description += ' pe ' + posted
    description += '.'
    file_size = _human_size(document.get('size'))
    if file_size:
        description += ' Marime fisier: ' + file_size + '.'
    description += ' Redare in streaming, direct din Telegram.'
    return {
        'id': post_id,
        'title': title,
        'year': year,
        'thumb': '%s/media/%s/%d/preview' % (base, channel, post_id),
        # Forma scurta: serverul redirectioneaza singur catre fisierul curent,
        # deci linkul ramane valabil si dupa ce Telegram schimba "access_hash".
        'stream': '%s/media/%s/%d' % (base, channel, post_id),
        'desc': description,
        'date': message.get('date') or 0,
        'size': document.get('size') or 0,
        'search': _normalize_for_search('%s %s' % (title, year))
    }


# ---------------------------------------------------------------------------
# Surse de date: lista inclusa in addon + cache local + serviciul live
# ---------------------------------------------------------------------------
def _remember_error(message):
    global _LAST_ERROR
    _LAST_ERROR = message or ''


def _last_error():
    return _LAST_ERROR


def _snapshot_file():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = ''
    return os.path.join(base, SNAPSHOT_NAME) if base else ''


def _load_snapshot():
    """Lista completa de filme inclusa in addon (functioneaza si fara internet)."""
    try:
        path = _snapshot_file()
        if not path or not os.path.isfile(path):
            return []
        with open(path, 'r') as handle:
            payload = json.load(handle)
        items = payload.get('items') if isinstance(payload, dict) else payload
        if isinstance(items, list) and items:
            return [item for item in items if item.get('id') and item.get('stream')]
    except Exception as exc:
        _log('Snapshot indisponibil: %s' % exc, xbmc.LOGDEBUG)
    return []


def _merge(*sources):
    """Combina listele; sursele de mai tarziu au prioritate (dupa id-ul postarii)."""
    merged = {}
    for source in sources:
        for film in (source or []):
            try:
                if film.get('id') and film.get('stream'):
                    merged[film['id']] = film
            except Exception:
                continue
    return sorted(merged.values(), key=lambda item: item['id'], reverse=True)


def _parse_rss_feed(raw):
    """A doua sursa: RSS-ul canalului (doar ultimele postari, dar nelimitat)."""
    films = []
    try:
        blocks = re.findall(r'(?s)<item>(.*?)</item>', raw)
    except Exception:
        return films
    channel = _channel()
    for block in blocks:
        guid = re.search(r'<guid[^>]*>(.*?)</guid>', block, re.S)
        if not guid:
            continue
        match = re.search(r'/(' + re.escape(channel) + r')/(\d+)', guid.group(1))
        if not match:
            continue
        post_id = int(match.group(2))
        enclosure = re.search(r'<enclosure[^>]*url="([^"]+)"', block)
        if not enclosure:
            continue
        caption = ''
        description = re.search(r'(?s)<description>(.*?)</description>', block)
        if description:
            text = description.group(1)
            text = re.sub(r'(?is)<img[^>]*>', ' ', text)
            text = re.sub(r'(?is)<br\s*/?>', '|', text)
            text = re.sub(r'(?s)<[^>]+>', ' ', text)
            try:
                text = _html_unescape(text)
            except Exception:
                pass
            text = text.split('|')[-1] if '|' in text else text
            caption = text.strip()
        date_ts = 0
        pubdate = re.search(r'<pubDate>(.*?)</pubDate>', block, re.S)
        if pubdate:
            date_ts = _parse_rss_date(pubdate.group(1).strip())
        title, year = _split_title(caption, post_id, date_ts)
        size_match = re.search(r'<enclosure[^>]*length="(\d+)"', block)
        size = int(size_match.group(1)) if size_match else 0
        films.append({
            'id': post_id,
            'title': title,
            'year': year,
            'thumb': '%s/media/%s/%d/preview' % (_api_base(), channel, post_id),
            'stream': '%s/media/%s/%d' % (_api_base(), channel, post_id),
            'desc': 'Film postat pe canalul Telegram @%s. Redare directa (streaming).' % _channel(),
            'date': date_ts,
            'size': size,
            'search': _normalize_for_search('%s %s' % (title, year))
        })
    return films


def _parse_rss_date(text):
    months = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
              'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
    try:
        parts = text.split()
        day = int(parts[1])
        month = months.get(parts[2][:3].lower(), 0)
        year = int(parts[3])
        clock = parts[4].split(':')
        return int(time.mktime((year, month, day, int(clock[0]), int(clock[1]), 0, 0, 0, -1)))
    except Exception:
        return 0


def _fetch_json(max_pages):
    films = []
    for page in range(1, max_pages + 1):
        data = _api_json(page)
        if not data:
            break
        messages = data.get('messages') or []
        if not messages:
            break
        for message in messages:
            film = _normalize_message(message)
            if film:
                films.append(film)
        if len(messages) < PAGE_SIZE:
            break
    return films


def _fetch_rss():
    raw = _http_get('%s/rss/%s' % (_api_base(), _channel()))
    if not raw:
        return []
    return _parse_rss_feed(raw)


def _fetch_films(force=False):
    """
    Lista filmelor, cele mai noi primele.

    Ordinea surselor (fiecare o acopera pe cea dinainte, dupa id-ul postarii):
      1. snapshot  - lista completa inclusa in addon (merge mereu, fara internet)
      2. cache     - ultima lista citita cu succes de pe canal
      3. live      - serviciul Telegram (JSON, apoi RSS)
    Asa categoria nu mai poate rămâne goala din cauza limitei de cereri a
    serviciului public (FLOOD_WAIT).
    """
    _remember_error('')
    snapshot = _load_snapshot()
    cached = _cache_load(max_age=0)

    if not force:
        fresh = _cache_load()
        if fresh:
            _log('Lista din cache (%d filme).' % len(fresh))
            return _merge(snapshot, fresh)

    live = _fetch_json(MAX_PAGES if force else 1)
    if not live:
        live = _fetch_rss()
        if live:
            _log('JSON indisponibil, folosesc RSS (%d postari).' % len(live), xbmc.LOGWARNING)

    films = _merge(snapshot, cached, live)

    if live:
        _cache_save(films)
        _log('Lista reincarcata de pe canal: %d filme live, %d in total.' % (len(live), len(films)))
    elif films:
        _log('Serviciul nu a raspuns (%s); folosesc lista salvata (%d filme).'
             % (_last_error() or 'necunoscut', len(films)), xbmc.LOGWARNING)

    return films


# ---------------------------------------------------------------------------
# Construirea XML-ului pentru listare (formatul intern RomyLive+)
# ---------------------------------------------------------------------------
def _item_xml(title, externallink=None, link=None, thumb=None, fanart=None,
              info='', genre='Cinemateca / Filme Vechi', year=''):
    parts = ['<item>']
    parts.append('<title>%s</title>' % title)
    if externallink:
        parts.append('<externallink>%s</externallink>' % externallink)
    if link:
        parts.append('<link>%s</link>' % link)
    parts.append('<thumbnail>%s</thumbnail>' % (thumb or FALLBACK_THUMB))
    parts.append('<fanart>%s</fanart>' % (fanart or FANART))
    if genre:
        parts.append('<genre>[COLOR grey][I]%s[/COLOR][/I]</genre>' % genre)
    if year:
        parts.append('<year>%s</year>' % year)
    parts.append('<info>%s</info>' % info)
    parts.append('</item>')
    return ''.join(parts)


def _message_xml(title, message, externallink='cinemateca://refresh', thumb=None):
    return _item_xml(
        title='[COLOR red][B]' + title + '[/B][/COLOR]',
        externallink=externallink,
        thumb=thumb or FALLBACK_THUMB,
        info=message
    )


def _folder_xml(title, target, info='', thumb=None):
    return _item_xml(title=title, externallink=target, thumb=thumb or FALLBACK_THUMB, info=info)


def _film_label(film):
    title = film.get('title') or ''
    year = film.get('year') or ''
    if year and year not in title:
        return '[COLOR gold][B]%s[/B][/COLOR] [COLOR white](%s)[/COLOR]' % (title, year)
    return '[COLOR gold][B]%s[/B][/COLOR]' % title


# ---------------------------------------------------------------------------
# Redare
# ---------------------------------------------------------------------------
# Serverul care serveste fisierele canalului raspunde in 4-8 secunde pentru
# FIECARE cerere (isi rezolva de fiecare data referinta pe Telegram). Un player
# care citeste in bucati mici se blocheaza dupa ~35 de secunde. De aceea filmul
# nu e trimis direct catre Kodi, ci catre un proxy local (cinemateca_stream.py)
# care descarca o singura data, in fundal, si serveste playerului de pe disc.
STREAM_MODE = '80'


def _plugin_root():
    """Calea pluginului, asa cum o vede Kodi (ex: plugin://plugin.video.RomyLive/)."""
    try:
        root = sys.argv[0]
        if isinstance(root, str) and root.startswith('plugin://'):
            return root
    except Exception:
        pass
    return 'plugin://%s/' % ADDON_ID


def _play_link(film):
    """Link de redare: pluginul isi rezolva singur filmul prin proxy-ul local."""
    stream = film.get('stream') or ''
    if not stream:
        return ''
    try:
        payload = stream + '|' + str(int(film.get('size') or 0))
    except Exception:
        payload = stream + '|0'
    try:
        payload = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('ascii')
    except Exception:
        return stream
    return '%s?mode=%s&url=%s' % (_plugin_root(), STREAM_MODE, _quote(payload))


def _ensure_addon_path():
    """
    Se asigura ca radacina addon-ului este in sys.path, ca sa putem importa
    cinemateca_stream.py indiferent de unde a fost executat codul principal
    (loader remote, fallback local sau test).
    """
    candidates = []
    try:
        candidates.append(_addon().getAddonInfo('path'))
    except Exception:
        pass
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception:
        pass
    for raw in candidates:
        if not raw:
            continue
        path = (raw or '').rstrip('/' + os.sep)
        if path and os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


def _stream_module():
    for attempt in (0, 1):
        try:
            from cinemateca_stream import play as _stream_play
            return _stream_play
        except Exception as exc:
            if attempt:
                _log('Modulul cinemateca_stream.py nu este disponibil (%s).' % exc,
                     xbmc.LOGWARNING)
                return None
            _ensure_addon_path()


def _direct_play(handle, film_url, name=''):
    """Plasa de siguranta: redare directa de la sursa, fara proxy."""
    listitem = xbmcgui.ListItem(name or '')
    try:
        listitem.setPath(film_url)
        listitem.setProperty('IsPlayable', 'true')
    except Exception:
        pass
    xbmcplugin.setResolvedUrl(handle, True, listitem)


def play_from_payload(handle, payload, name=''):
    """
    Apelat de plugin cand Kodi deschide un film din Cinemateca (mode=80).
    Porneste proxy-ul local si rezolva redarea catre el.
    """
    film_url, size = ('', 0)
    try:
        from cinemateca_stream import decode_payload as _decode
    except Exception:
        _ensure_addon_path()
        try:
            from cinemateca_stream import decode_payload as _decode
        except Exception:
            _decode = None
    if _decode is not None:
        film_url, size = _decode(payload)
    if not film_url:
        # payload-ul poate fi chiar linkul (versiune veche / fallback)
        film_url = _unquote(payload or '').strip()
    if not film_url:
        _log('Link de redare lipsa.', xbmc.LOGERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem(name or ''))
        return

    if not _setting_bool('cinemateca_proxy_enabled', True):
        _direct_play(handle, film_url, name)
        return

    stream_play = _stream_module()
    if stream_play is None:
        _direct_play(handle, film_url, name)
        return
    try:
        stream_play(handle, film_url, name, size)
        return
    except Exception as exc:
        _log('Proxy local indisponibil (%s); redare directa.' % exc, xbmc.LOGERROR)
    _direct_play(handle, film_url, name)


def _quote(value):
    try:
        return _urlparse.quote_plus(value.encode('utf-8') if not isinstance(value, str) else value)
    except Exception:
        try:
            return _urlparse.quote_plus(value)
        except Exception:
            return value


def _unquote(value):
    try:
        return _urlparse.unquote_plus(value)
    except Exception:
        return value


def _ask_query():
    try:
        keyboard = _addon().getSetting('keyboard')
    except Exception:
        keyboard = '0'
    dialog = xbmcgui.Dialog()
    try:
        if str(keyboard) == '0':
            return dialog.input('Cauta film in Cinemateca:', type=xbmcgui.INPUT_ALPHANUM)
        return dialog.input('Cauta film in Cinemateca:')
    except Exception:
        try:
            return dialog.input('Cauta film in Cinemateca:')
        except Exception:
            return ''


def get_list_xml(url):
    """
    Punctul de intrare apelat din plugin.
      cinemateca://list            -> prima pagina
      cinemateca://page/N          -> pagina N
      cinemateca://search          -> cere textul si cauta
      cinemateca://search/<text>   -> cauta in lista
      cinemateca://refresh         -> ignora cache-ul si reincarca de pe canal
    """
    url = url or 'cinemateca://list'
    if url.startswith('cinemateca://refresh'):
        clear_cache(True)
    elif url.startswith('cinemateca://reload'):
        clear_cache(False)

    query = ''
    page = 1

    if url.startswith('cinemateca://search'):
        remainder = url[len('cinemateca://search'):].lstrip('/')
        page_match = re.search(r'(?:^|/)page/(\d+)$', remainder)
        if page_match:
            page = int(page_match.group(1))
            remainder = remainder[:page_match.start()].rstrip('/')
        query = _unquote(remainder).strip()
        if not query:
            query = _ask_query().strip()
        if not query:
            return _message_xml('Cauta in Cinemateca',
                                'Nu ai introdus niciun text. Apasa din nou pentru a cauta.',
                                externallink='cinemateca://list')
    else:
        page_match = re.search(r'page/(\d+)', url)
        if page_match:
            page = int(page_match.group(1))

    if page < 1:
        page = 1

    films = _fetch_films(force=url.startswith('cinemateca://refresh'))
    if not films:
        return _message_xml(
            'Cinemateca momentan indisponibila',
            'Nu am putut citi canalul Telegram @%s si nici lista salvata (%s). '
            'Apasa aici pentru a reincerca.' % (_channel(), _last_error() or 'lipsa internet'),
            externallink='cinemateca://refresh'
        )

    if query:
        needle = _normalize_for_search(query)
        films = [film for film in films if needle in film.get('search', '')]
        if not films:
            return _message_xml(
                'Niciun rezultat',
                'Nu am gasit niciun film pentru "' + query + '" in Cinemateca.',
                externallink='cinemateca://list'
            )

    total = len(films)
    start = (page - 1) * FILMS_PER_PAGE
    end = start + FILMS_PER_PAGE
    chunk = films[start:end]
    if not chunk and total:
        page = 1
        start = 0
        end = FILMS_PER_PAGE
        chunk = films[start:end]

    blocks = []

    for film in chunk:
        blocks.append(_item_xml(
            title=_film_label(film),
            link=_play_link(film) or film.get('stream', ''),
            thumb=film.get('thumb'),
            info=film.get('desc', ''),
            year=film.get('year', '')
        ))

    base_url = 'cinemateca://search/%s' % _quote(query) if query else 'cinemateca://page/%d'
    if query:
        next_url = 'cinemateca://search/%s/page/%d' % (_quote(query), page + 1)
        prev_url = 'cinemateca://search/%s/page/%d' % (_quote(query), page - 1)
        info_url = 'cautare: ' + query
    else:
        next_url = base_url % (page + 1)
        prev_url = base_url % (page - 1)
        info_url = ''

    if page > 1:
        blocks.append(_folder_xml(
            '[COLOR lime][B]<< Pagina %d <<[/B][/COLOR]' % (page - 1),
            prev_url,
            'Cinemateca - pagina anterioara (%s)' % info_url if info_url else 'Cinemateca - pagina anterioara'
        ))

    if end < total:
        blocks.append(_folder_xml(
            '[COLOR lime][B]>> Pagina %d >>[/B][/COLOR]' % (page + 1),
            next_url,
            'Cinemateca - urmatoarele %d filme' % min(FILMS_PER_PAGE, total - end)
        ))

    if not query:
        blocks.append(_folder_xml(
            '[COLOR aqua][B]Cauta in Cinemateca[/B][/COLOR]',
            'cinemateca://search',
            'Cauta un film dupa titlu sau an in cele %d filme de pe canalul @%s' % (total, _channel())
        ))
        status = 'serviciul a raspuns' if not _last_error() else 'serviciul: ' + _last_error()
        blocks.append(_folder_xml(
            '[COLOR gold][B]Actualizeaza lista[/B][/COLOR]',
            'cinemateca://refresh',
            'Reciteste postarile de pe canalul @%s (%d filme in lista curenta; %s)'
            % (_channel(), total, status)
        ))

    return '\n'.join(blocks)
