# subtitles.py
import os
import re
import threading
import time

import requests
import xbmcaddon
import xbmcvfs
import xbmc
from urllib.parse import urlsplit, quote, urlunsplit

addon = xbmcaddon.Addon('plugin.video.samusxui')
profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
subs_path = os.path.join(profile_path, 'subs')

SUB_LANGUAGES = addon.getSetting('subs_languages') or 'ro'
SUB_FORMAT = addon.getSetting('subs_format') or 'srt'
SUB_ENCODING = addon.getSetting('subs_encoding') or 'utf-8'

_WYZIE_URL    = 'https://sub.wyzie.io/search'
_WYZIE_KEY    = 'wyzie-9c717eeb19ce0aed4df716f2e3d4fea6'
_VDRK_BASE    = 'https://sub.vdrk.site'
_VDRK_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Referer': 'https://vidrock.net/', 'Origin': 'https://vidrock.net', 'Accept-Encoding': 'gzip, deflate'}

_LANG_NAME_MAP = {
    'ro': ('romanian', 'română', 'romana'),
    'en': ('english',),
    'fr': ('french', 'français', 'franceza'),
    'de': ('german', 'deutsch', 'germana'),
    'it': ('italian', 'italiano'),
    'es': ('spanish', 'español', 'spaniola'),
    'pt': ('portuguese', 'português'),
    'ru': ('russian', 'rusă', 'rusa'),
    'hu': ('hungarian', 'hungarian'),
    'pl': ('polish', 'polish'),
    'cs': ('czech',),
    'sk': ('slovak',),
    'bg': ('bulgarian',),
    'hr': ('croatian',),
    'sr': ('serbian',),
    'nl': ('dutch',),
    'tr': ('turkish',),
    'zh': ('chinese', 'mandarin'),
    'ja': ('japanese',),
    'ko': ('korean',),
    'ar': ('arabic',),
}


# Codurile pe care le pune Kodi în câmpul `language` al unei piste. Când
# recunoaște limba din numele fișierului („Romanian.vtt"), o SCOATE din
# denumire — pista rămâne „(External)" cu language='rum'. O potrivire făcută
# doar pe nume ratează tocmai subtitrarea principală.
_LANG_CODE_MAP = {
    'ro': ('rum', 'ron', 'ro'),
    'en': ('eng', 'en'),
    'fr': ('fre', 'fra', 'fr'),
    'de': ('ger', 'deu', 'de'),
    'it': ('ita', 'it'),
    'es': ('spa', 'es'),
    'pt': ('por', 'pt'),
    'ru': ('rus', 'ru'),
    'hu': ('hun', 'hu'),
    'pl': ('pol', 'pl'),
    'cs': ('cze', 'ces', 'cs'),
    'sk': ('slo', 'slk', 'sk'),
    'bg': ('bul', 'bg'),
    'hr': ('hrv', 'hr'),
    'sr': ('srp', 'sr'),
    'nl': ('dut', 'nld', 'nl'),
    'tr': ('tur', 'tr'),
    'zh': ('chi', 'zho', 'zh'),
    'ja': ('jpn', 'ja'),
    'ko': ('kor', 'ko'),
    'ar': ('ara', 'ar'),
}


def _lang_matches(label, lang_code):
    label_lower = (label or '').lower()
    for name in _LANG_NAME_MAP.get(lang_code, ()):
        if name in label_lower:
            return True
    return False


def _cod_limba_potrivit(cod, lang_code):
    """True dacă `cod` (câmpul `language` al pistei) e limba cerută."""
    return (cod or '').strip().lower() in _LANG_CODE_MAP.get(lang_code, ())


def _vdrk_fetch(url):
    try:
        r = requests.get(url, headers=_VDRK_HEADERS, timeout=7)
        return r.json() if r.ok else []
    except Exception as e:
        xbmc.log(f'[Samus/vdrk] {e}', xbmc.LOGERROR)
        return []


def search_vdrk(tmdb_id, season=None, episode=None):
    """Fetch subtitle URLs from sub.vdrk.site (v1+v2). Returns direct URLs, preferred langs first."""
    languages = [lang.strip() for lang in SUB_LANGUAGES.split(',') if lang.strip()]

    if season and episode:
        path = f'/tv/{tmdb_id}/{season}/{episode}'
    else:
        path = f'/movie/{tmdb_id}'

    import threading
    results = [[], []]

    def _fetch(idx, version):
        results[idx] = _vdrk_fetch(f'{_VDRK_BASE}/v{version}{path}')

    threads = [threading.Thread(target=_fetch, args=(i, v), daemon=True) for i, v in enumerate([1, 2])]
    for t in threads: t.start()
    for t in threads: t.join(timeout=8)

    def _encode_url(url):
        parts = urlsplit(url)
        encoded_path = quote(parts.path, safe='/:@!$&\'()*+,;=')
        return urlunsplit(parts._replace(path=encoded_path))

    seen, preferred, rest = set(), [], []
    for items in results:
        for it in items or []:
            url = it.get('file') or it.get('url') or it.get('src')
            if not url or url in seen:
                continue
            url = _encode_url(url)
            seen.add(url)
            label = it.get('label') or it.get('name') or ''
            if any(_lang_matches(label, lang) for lang in languages):
                preferred.append(url)
            else:
                rest.append(url)

    all_urls = preferred + rest
    xbmc.log(f'[Samus/vdrk] {len(all_urls)} subtitrări ({len(preferred)} preferred) pentru tmdb_id={tmdb_id}', xbmc.LOGINFO)
    return all_urls


def search_subtitles(imdb_id, season=None, episode=None):
    subtitles = []
    languages = [lang.strip() for lang in SUB_LANGUAGES.split(',') if lang.strip()]

    for lang in languages:
        params = {
            'id': imdb_id,
            'language': lang,
            'format': SUB_FORMAT,
            'encoding': SUB_ENCODING,
            'key': _WYZIE_KEY,
        }
        if season and episode:
            params['season'] = season
            params['episode'] = episode

        try:
            response = requests.get(_WYZIE_URL, params=params, timeout=10)
            if response.ok:
                data = response.json()
                if isinstance(data, dict):
                    subtitles.append(data)
                elif isinstance(data, list):
                    subtitles.extend(data)
            else:
                xbmc.log(f'[WyzieSub] Eroare HTTP: {response.status_code}', xbmc.LOGERROR)
        except Exception as e:
            xbmc.log(f'[WyzieSub] Excepție: {e}', xbmc.LOGERROR)

    return subtitles


def download_subtitle(sub, folder_path):
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
    except Exception as e:
        xbmc.log(f'[Subtitles] Eroare creare folder subtitrări: {e}', xbmc.LOGERROR)
        return ''

    url = sub['url']
    filename = f"{sub['media']}.{sub['language']}.{sub['format']}"
    safe_filename = ''.join(c for c in filename if c not in r'\/:*?"<>|')
    path = os.path.join(folder_path, safe_filename)

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)
        return path
    except Exception as e:
        xbmc.log(f'[Subtitles] Eroare descărcare: {e}', xbmc.LOGERROR)
        return ''


# ── Treapta 2: traducere automată când lipsește româna ───────────────────────
#
# Cascada convenită: 1) subtitrare românească existentă, 2) traducem alta,
# 3) transcriere din audio. Aici e treapta 2. Traducerea o face serverul
# Thrax, care o ține în cache — un episod tradus o dată e servit apoi
# instantaneu oricui, deci nu plătim de două ori aceeași muncă.
#
# Serverul răspunde 202 cât timp lucrează (~70-90 s). Nu blocăm redarea:
# pornim traducerea, filmul începe fără subtitrare, iar când e gata o
# atașăm din mers cu `Player().setSubtitles()`.

_TRADUCERE_URL = 'https://api.derzis.xyz/subtitles/translate'
_ASTEPTARE_MAX = 240          # secunde; peste asta renunțăm tăcut
_PAS_VERIFICARE = 15


def _secunde(marcaj):
    """„01:02:03.400" → secunde. Acceptă și virgula, ca în SRT."""
    p = marcaj.replace(',', '.').split(':')
    try:
        if len(p) == 3:
            return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
        return int(p[0]) * 60 + float(p[1])
    except Exception:
        return None


def _repere(url):
    """(număr_replici, prima, ultima) pentru o subtitrare, fără să reținem text."""
    try:
        r = requests.get(url, headers=_VDRK_HEADERS, timeout=12)
        if not r.ok:
            return None
        ts = re.findall(r'(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->', r.text)
        s = [x for x in (_secunde(t) for t in ts) if x is not None]
        return (len(s), min(s), max(s)) if s else None
    except Exception as e:
        xbmc.log(f'[Subtitles/durată] {url[:60]}: {e}', xbmc.LOGDEBUG)
        return None


def alege_dupa_durata(candidati, durata):
    """Dintre mai multe subtitrări engleze, o alege pe cea potrivită filmului.

    O traducere e la fel de sincronizată ca originalul din care pleacă, deci
    alegerea greşită aici strică totul mai departe. Măsurat pe 2026-08-12:
    pentru „Flower of Evil" varianta generică începea cu 76 s mai târziu şi
    acoperea cu 134 s mai puţin decât fişierul redat, iar la „Squid Game"
    diferenţa de final era de 4 minute şi jumătate — alt montaj.

    Comparăm ultima replică cu durata reală a fluxului. Diferenţele de câteva
    secunde sunt normale (genericul de final); cele de minute înseamnă alt
    montaj. Fără durată cunoscută, păstrăm ordinea primită.
    """
    if not candidati:
        return None
    if len(candidati) == 1 or not durata or durata <= 0:
        return candidati[0]
    cel_mai_bun, scor_bun = candidati[0], None
    for u in candidati[:5]:              # nu cântărim la nesfârşit
        rep = _repere(u)
        if not rep:
            continue
        scor = abs(rep[2] - durata)
        xbmc.log(f'[Subtitles/durată] {rep[0]} replici, ultima la {rep[2]:.0f}s, '
                 f'film {durata:.0f}s → abatere {scor:.0f}s', xbmc.LOGINFO)
        if scor_bun is None or scor < scor_bun:
            cel_mai_bun, scor_bun = u, scor
    if scor_bun is not None and scor_bun > 120:
        xbmc.log(f'[Subtitles/durată] cea mai bună variantă tot ratează cu '
                 f'{scor_bun:.0f}s — probabil alt montaj', xbmc.LOGWARNING)
    return cel_mai_bun


def _normalizeaza(intrari):
    """Aduce lista la perechi (adresă, limbă), oricum ar veni.

    Sursele nu vorbesc la fel: unele întorc adrese simple (`stremio_direct`),
    altele structuri `{url, lang, format}` (`vidlove`). Amestecul strica două
    lucruri deodată — `li.setSubtitles` acceptă doar şiruri, iar detecţia
    limbii se făcea din numele fişierului. Când sursa declară limba, o credem
    pe ea; ghicitul din URL rămâne rezervă.
    """
    out = []
    for it in (intrari or []):
        if isinstance(it, dict):
            u = it.get('url') or it.get('file')
            if u:
                et = it.get('lang') or it.get('label') or _limba_din_url(u)
                out.append((u, str(et).lower()))
        elif isinstance(it, str) and it:
            out.append((it, _limba_din_url(it).lower()))
    return out


_OPENSUB_CAUTARE = 'https://rest.opensubtitles.org/search'
_OPENSUB_VTT     = 'https://opensubtitles.stremio.homes/sub.vtt/?sub_id={}'


def cauta_opensubtitles(imdb_id, season=None, episode=None, limba='rum'):
    """Rezultatele româneşti de la OpenSubtitles, cele mai descărcate întâi.

    Endpointul vechi (`rest.opensubtitles.org`) nu cere cheie. Îl foloseşte şi
    `service.subtitles.opensub`, de unde am luat şi proxy-ul care serveşte VTT
    gata convertit — altfel rezultatele vin comprimate şi Kodi nu le poate reda.
    """
    if not imdb_id:
        return []
    n = str(imdb_id).lower().lstrip('t')
    if season and episode:
        cale = f'/episode-{episode}/imdbid-{n}/season-{season}/sublanguageid-{limba}'
    else:
        cale = f'/imdbid-{n}/sublanguageid-{limba}'
    try:
        r = requests.get(_OPENSUB_CAUTARE + cale,
                         headers={'User-Agent': 'TemporaryUserAgent'}, timeout=12)
        if not r.ok:
            return []
        rez = r.json()
    except Exception as e:
        xbmc.log(f'[Subtitles/opensub] {e}', xbmc.LOGWARNING)
        return []
    if not isinstance(rez, list):
        return []
    def descarcari(it):
        try:
            return int(it.get('SubDownloadsCnt') or 0)
        except Exception:
            return 0
    return sorted(rez, key=descarcari, reverse=True)


def _ia_opensubtitles(imdb_id, season, episode, folder_path, nume):
    """Descarcă prima subtitrare românească şi o scrie local. Întoarce calea.

    O scriem pe disc în loc s-o dăm ca URL fiindcă proxy-ul serveşte totul de
    la `/sub.vtt/?sub_id=…`: numele fişierului nu conţine limba, iar restul
    lanţului (detecţia limbii, alegerea pistei în player) se bazează pe el.
    """
    for it in cauta_opensubtitles(imdb_id, season, episode)[:3]:
        idsub = it.get('IDSubtitle')
        if not idsub:
            continue
        try:
            r = requests.get(_OPENSUB_VTT.format(idsub),
                             headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            if r.ok and r.text.lstrip('﻿').startswith('WEBVTT'):
                return _scrie_local(r.text, folder_path, nume)
        except Exception as e:
            xbmc.log(f'[Subtitles/opensub] descărcare eşuată: {e}', xbmc.LOGDEBUG)
    return None


def _limba_din_url(url):
    """URL-urile vdrk se termină în `/English.vtt`, `/Romanian.vtt` etc."""
    try:
        return os.path.splitext(os.path.basename(urlsplit(url).path))[0]
    except Exception:
        return ''


def _scrie_local(continut, folder_path, nume):
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        cale = os.path.join(folder_path, nume)
        # BOM intenționat: Kodi nu are opțiune „UTF-8" la codarea subtitrărilor,
        # iar „Default" înseamnă codarea regiunii (o variantă pe un octet), nu
        # detectare automată. Fără BOM, diacriticele ies „Ä"/„È™". Cu BOM,
        # playerul comută pe UTF-8 indiferent de setarea utilizatorului.
        with open(cale, 'w', encoding='utf-8-sig') as f:
            f.write(continut)
        return cale
    except Exception as e:
        xbmc.log(f'[Subtitles/traducere] nu pot scrie {nume}: {e}', xbmc.LOGERROR)
        return ''


def _cere_traducere(url_sursa, nota='', ident=None):
    """Întoarce (cod, text). 200 = gata, 202 = în lucru.

    `ident` duce tmdb_id/tip/sezon/episod la server, ca traducerea să fie
    stocată în `subs/filme/{id}/` sau `subs/seriale/{id}/{sezon}/{episod}/`
    în loc de un director plat cu hash-uri.
    """
    from resources.lib.resolvers._common import THRAX_HEADERS
    params = {'url': url_sursa, 'to': 'Romanian', 'src': 'English', 'note': nota}
    params.update({k: v for k, v in (ident or {}).items() if v is not None})
    try:
        r = requests.get(_TRADUCERE_URL, params=params,
                         headers=THRAX_HEADERS, timeout=30)
        partial = r.headers.get('X-Sub-Partial', '').lower() == 'true'
        return r.status_code, r.text, partial
    except Exception as e:
        xbmc.log(f'[Subtitles/traducere] {e}', xbmc.LOGERROR)
        return 0, '', False


def _asteapta_si_ataseaza(url_sursa, folder_path, nume, nota, ident=None):
    """Reia cererea până e gata, apoi atașează subtitrarea la redarea curentă."""
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    limita = time.time() + _ASTEPTARE_MAX
    # Cât timp serverul lucrează, ne întoarce mereu varianta parțială. Fără
    # verificarea asta am reatașa același fișier la fiecare verificare, ceea
    # ce resetează subtitrarea pe ecran degeaba.
    ultima_marime = -1
    # Firul porneşte în timpul rezolvării sursei, deci redarea poate să nu fi
    # început încă la prima verificare. Măsurat pe box (2026-08-11): sursa a
    # avut nevoie de 18 s ca să deschidă fluxul, iar firul renunţa la 15 s —
    # tăcut, fiindcă ieşirea aia n-avea niciun mesaj. Aşteptăm deci pornirea,
    # şi ne oprim doar dacă redarea chiar a existat şi s-a încheiat.
    a_pornit = False
    # `url_sursa` poate fi o listă de engleze candidate: alegerea o facem după
    # ce porneşte redarea, singurul moment în care Kodi ştie durata reală.
    candidati = url_sursa if isinstance(url_sursa, (list, tuple)) else None
    if candidati:
        url_sursa = None
    while time.time() < limita:
        if monitor.waitForAbort(_PAS_VERIFICARE):
            return
        if player.isPlayingVideo():
            if not a_pornit and candidati:
                try:
                    durata = player.getTotalTime()
                except Exception:
                    durata = 0
                url_sursa = alege_dupa_durata(list(candidati), durata)
                xbmc.log(f'[Subtitles/durată] alesă pentru traducere: '
                         f'{str(url_sursa)[-48:]}', xbmc.LOGINFO)
            a_pornit = True
        elif a_pornit:
            xbmc.log('[Subtitles/traducere] redarea s-a încheiat, renunţ',
                     xbmc.LOGINFO)
            return
        else:
            continue                    # încă nu a pornit; mai aşteptăm
        cod, text, partial = _cere_traducere(url_sursa, nota, ident)
        if cod == 200 and text:
            if len(text) == ultima_marime:
                continue                # nimic nou față de ce am atașat deja
            ultima_marime = len(text)
            cale = _scrie_local(text, folder_path, nume)
            if cale:
                try:
                    player.setSubtitles(cale)
                    xbmc.log(f'[Subtitles/traducere] atașată{" (parțial)" if partial else ""}:'
                             f' {nume}', xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f'[Subtitles/traducere] atașare eșuată: {e}', xbmc.LOGWARNING)
            if partial:
                continue          # revenim după varianta completă
            return
        if cod not in (202, 0):
            xbmc.log(f'[Subtitles/traducere] renunț, cod {cod}', xbmc.LOGWARNING)
            return


def asigura_romana(urls, folder_path, eticheta='', nota='', ident=None):
    """Dacă lista are deja o subtitrare românească, o lasă neatinsă.

    Altfel cere traducerea celei engleze. Întoarce lista de folosit imediat —
    cu traducerea pe primul loc dacă era deja în cache pe server.
    """
    perechi = _normalizeaza(urls)
    urls = [u for u, _ in perechi]      # Kodi vrea şiruri, nu structuri
    limbi = [l for _, l in perechi]
    if not perechi and not (ident or {}).get('imdb_id'):
        return []                       # n-avem nici liste, nici după ce căuta
    if any(_lang_matches(l, 'ro') for l in limbi):
        return urls                     # treapta 1: avem deja română

    # Treapta 1½: OpenSubtitles, înainte de a traduce. vdrk are română doar
    # pentru titluri occidentale — măsurat pe 2026-08-12: 3 variante pentru
    # Inception, 0 pentru dramele asiatice. OpenSubtitles are 41 la acelaşi
    # film. O subtitrare făcută de om bate una tradusă automat, iar cota
    # rămâne pentru titlurile care chiar n-au nimic.
    ident = ident or {}
    imdb = ident.get('imdb_id')
    if imdb:
        cale = _ia_opensubtitles(imdb, ident.get('season'), ident.get('episode'),
                                 folder_path, f'{eticheta or "opensub"}.ro.vtt')
        if cale:
            xbmc.log('[Subtitles/opensub] românească găsită, nu mai traduc',
                     xbmc.LOGINFO)
            return [cale] + urls

    engleze = [u for u, l in zip(urls, limbi) if _lang_matches(l, 'en')]
    engleza = engleze[0] if engleze else None
    if not engleza:
        xbmc.log('[Subtitles/traducere] nicio sursă engleză de tradus', xbmc.LOGINFO)
        return urls

    nume = f'{eticheta or "tradus"}.ro.vtt'.replace('/', '_')

    # Mai multe engleze înseamnă că una e potrivită filmului şi restul nu:
    # măsurat, variantele generice pot rata cu minute întregi. Amânăm alegerea
    # şi cererea până porneşte redarea, ca s-o facem cu durata în mână — altfel
    # am traduce (şi am plăti) o subtitrare care oricum ar cădea alături.
    if len(engleze) > 1:
        xbmc.log(f'[Subtitles/durată] {len(engleze)} variante engleze, '
                 f'aleg după pornirea redării', xbmc.LOGINFO)
        threading.Thread(target=_asteapta_si_ataseaza, daemon=True,
                         args=(engleze, folder_path, nume, nota, ident),
                         name='samus-traducere').start()
        return urls

    cod, text, partial = _cere_traducere(engleza, nota, ident)

    if cod == 200 and text:
        cale = _scrie_local(text, folder_path, nume)
        if cale:
            xbmc.log(f'[Subtitles/traducere] servită din cache'
                     f'{" (parțial, continui)" if partial else ""}', xbmc.LOGINFO)
            if partial:
                # avem începutul acum; restul se atașează singur când sosește
                threading.Thread(target=_asteapta_si_ataseaza, daemon=True,
                                 args=(engleza, folder_path, nume, nota, ident),
                                 name='samus-traducere').start()
            return [cale] + urls

    if cod == 202:
        xbmc.log('[Subtitles/traducere] pornită pe server, o atașez când e gata',
                 xbmc.LOGINFO)
        threading.Thread(target=_asteapta_si_ataseaza, daemon=True,
                         args=(engleza, folder_path, nume, nota, ident),
                         name='samus-traducere').start()

    return urls


def pregateste_urmatorul(tv_id, season, episode, nota=''):
    """Traduce în fundal subtitrarea episodului următor.

    Observație practică: la seriale, dacă un episod n-are subtitrare
    românească, de regulă n-are niciunul. Cât timp utilizatorul se uită la
    episodul curent, serverul poate pregăti următorul — la fel de bine ar
    sta degeaba.

    Trimitem o singură cerere și uităm de ea: endpointul e asincron, deci
    răspunde 202 imediat și lucrează în fundal, iar rezultatul rămâne în
    cache-ul serverului. Nu așteptăm și nu atașăm nimic acum.
    """
    def _lucreaza():
        try:
            urmator = search_vdrk(tv_id, season=season, episode=episode + 1)
            if not urmator:
                return                      # probabil ultimul episod din sezon
            limbi = [_limba_din_url(u).lower() for u in urmator]
            if any(_lang_matches(l, 'ro') for l in limbi):
                return                      # are deja română, nu e nevoie
            engleza = next((u for u, l in zip(urmator, limbi)
                            if _lang_matches(l, 'en')), None)
            if not engleza:
                return
            cod, _, _ = _cere_traducere(engleza, nota, {
                'tmdb_id': tv_id, 'type': 'tv',
                'season': season, 'episode': episode + 1})
            xbmc.log(f'[Subtitles/traducere] pregătit episodul {episode + 1} '
                     f'(cod {cod})', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[Subtitles/traducere] pregătire eșuată: {e}', xbmc.LOGDEBUG)

    threading.Thread(target=_lucreaza, daemon=True, name='samus-pregatire').start()


def are_romana(urls):
    """True dacă lista conține deja o subtitrare românească."""
    return any(_lang_matches(l, 'ro') for _, l in _normalizeaza(urls))
