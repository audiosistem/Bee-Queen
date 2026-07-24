# -*- coding: utf-8 -*-
"""
    luc_kodi Add-on
    MDBList integration module — FULL in-plugin client.

    Esta versión absorbe todo lo que antes hacía el servicio externo
    `service.luc_kodi.mdblist`: scrobbling (start/pause/stop/clear), resume
    cross-device (/sync/playback), historial de vistos (/sync/watched),
    "siguiente no visto" (/upnext), watchlist y listas públicas — igual que
    Trakt y SIMKL viven dentro del plugin. Ya NO se lee ninguna BD del
    servicio externo.

    Autenticación (DOS modos, ambos soportados):
      1) OAuth 2.0 Device Flow (RECOMENDADO, sin teclado, con PIN + QR) —
         igual que Trakt/SIMKL. POST /oauth/device-authorization/ devuelve
         user_code + device_code; el usuario abre mdblist.com/oauth/device,
         mete el PIN (o escanea el QR) y aprueba. Se hace polling a
         POST /oauth/token/ hasta recibir access_token. Las llamadas van con
         cabecera Authorization: Bearer <token>. La app aparece en
         "Authorized Apps" del perfil con su nombre e icono (definidos al
         registrar el client_id en mdblist.com).
      2) API key manual (?apikey=KEY) — alternativa/legacy.

    IMPORTANTE: el Device Flow necesita un client_id propio registrado en
    mdblist.com (Preferences -> API Access). Ponlo en el ajuste
    mdblist.client_id. Sin client_id, el plugin cae a modo API key.

    Endpoints reales (api.mdblist.com, OpenAPI 1.0.0):
      POST /oauth/device-authorization/   → user_code, device_code, QR
      POST /oauth/token/                  → access_token, refresh_token
      POST /scrobble/start|pause|stop|clear
      GET  /sync/playback          → sesiones en pausa (resume)
      GET  /sync/watched / POST    → historial de vistos
      GET  /upnext                 → series en curso con próximo episodio
      GET  /user                   → perfil + límites (validación de key)
      GET  /watchlist/items ; POST /watchlist/items/add | /remove
      GET  /lists/top ; GET /lists/search ; GET /lists/{id}/items
"""

import time
import requests

from resources.lib.modules import control
from resources.lib.modules import log_utils

BASE_URL = 'https://api.mdblist.com'

# --- OAuth 2.0 Device Flow (PIN + QR) -------------------------------------
# Endpoints verificados contra una implementación funcional.
_OAUTH_DEVICE_URL = 'https://api.mdblist.com/oauth/device-authorization/'
_OAUTH_TOKEN_URL = 'https://api.mdblist.com/oauth/token/'
_OAUTH_GRANT_DEVICE = 'urn:ietf:params:oauth:grant-type:device_code'
# Página donde el usuario mete el PIN (o aterriza el QR).
_OAUTH_VERIFY_URL = 'https://mdblist.com/oauth/device/'

# NO incluir aquí ninguna API key personal: si se rellena, TODAS las llamadas
# /user de un usuario recién instalado (o con el OAuth aún no activo) caerían en
# esta cuenta y mostrarían/guardarían el username del dueño de la key. Cada
# usuario autoriza su propia cuenta vía Device Flow (PIN+QR) o pone su API key.
DEFAULT_APIKEY = ''

# client_id propio de la app luc_kodi registrada en mdblist.com. Viene de
# fábrica para que el Device Flow (PIN+QR) funcione recién instalado y la
# cuenta del usuario aparezca en "Authorized Apps" con el nombre/icono de
# luc_kodi. El usuario puede sobreescribirlo en Ajustes si registra su propia app.
DEFAULT_CLIENT_ID = 'QaD4kr5BnGQuIGbWxPoN2E0vPokG1227YWvc2wCo'

# Identificador de la app que MDBList registra en cada scrobble.
APP_NAME = 'luc_kodi'

getSetting = control.setting
setSetting = control.setSetting

# Throttle local para no chocar con el lock de 20s del servidor en scrobbles.
_SCROBBLE_THROTTLE_SECONDS = 5
_last_scrobble_at = {'ts': 0.0}


# ---------------------------------------------------------------------------
# Credenciales
# ---------------------------------------------------------------------------

def getOAuthToken():
    """access_token guardado por el Device Flow (vacío si no autorizado)."""
    return (getSetting('mdblist.token') or '').strip()


def getClientID():
    """client_id de la app en mdblist.com (Device Flow). Usa el del usuario si
    lo ha puesto, si no el de fábrica de luc_kodi."""
    cid = (getSetting('mdblist.client_id') or '').strip()
    if not cid:
        cid = DEFAULT_CLIENT_ID
    return cid


def oauthActive():
    """True si hay un access_token utilizable (modo OAuth)."""
    tok = getOAuthToken()
    return bool(tok and tok not in ('0', 'empty_setting'))


def getMDBListCredentials():
    """Devuelve (cred, base_url) donde cred es el access_token OAuth si existe,
    si no la API key del usuario, si no la del plugin. La forma de enviarlo
    (Bearer vs ?apikey=) la decide _auth_headers_params()."""
    url = (getSetting('mdblist.url') or '').strip().rstrip('/')
    if not url:
        url = BASE_URL
    if oauthActive():
        return getOAuthToken(), url
    apikey = (getSetting('mdblist.apikey') or '').strip()
    if not apikey:
        apikey = DEFAULT_APIKEY
    if apikey:
        return apikey, url
    return None, None


def _auth_headers_params():
    """Devuelve (headers, params) con la credencial colocada según el modo:
    OAuth -> Authorization: Bearer; API key -> ?apikey=."""
    if oauthActive():
        return {'Authorization': 'Bearer %s' % getOAuthToken()}, {}
    apikey, _ = getMDBListCredentials()
    if apikey:
        return {}, {'apikey': apikey}
    return {}, {}


def usingDefaultKey():
    """True si el usuario aún no ha puesto su propia key NI autorizado OAuth."""
    if oauthActive():
        return False
    return not (getSetting('mdblist.apikey') or '').strip()


def getMDBListCredentialsInfo():
    """True si hay una credencial utilizable (token OAuth o API key)."""
    cred, _ = getMDBListCredentials()
    return bool(cred)


def getMDBListScrobbleInfo():
    """True si el usuario ha activado el scrobbling Y hay credencial. Es el
    ÚNICO interruptor visible que controla el scrobbling. Pensado para player.py.
    Requiere además estar autorizado (token OAuth o API key propia): con la key
    por defecto del plugin NO se scrobblea, para no escribir en la cuenta dueña."""
    if getSetting('mdblist.scrobble') != 'true':
        return False
    if usingDefaultKey():
        # Sólo key por defecto del plugin y sin OAuth → no escribir.
        return False
    return getMDBListCredentialsInfo()


# ---------------------------------------------------------------------------
# Request de bajo nivel
# ---------------------------------------------------------------------------

def _get(endpoint, params=None, timeout=15):
    cred, base_url = getMDBListCredentials()
    if not cred:
        return None
    headers, auth_params = _auth_headers_params()
    p = dict(auth_params)
    if params:
        p.update(params)
    try:
        r = requests.get(base_url + endpoint, params=p, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_utils.log('MDBList GET %s failed: %s' % (endpoint, e), level=log_utils.LOGWARNING)
        return None


def _post(endpoint, json_data=None, timeout=15, silent=False):
    cred, base_url = getMDBListCredentials()
    if not cred:
        return None
    headers, auth_params = _auth_headers_params()
    try:
        r = requests.post(base_url + endpoint, params=auth_params, headers=headers,
                          json=json_data or {}, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {}
    except Exception as e:
        if not silent:
            log_utils.log('MDBList POST %s failed: %s' % (endpoint, e), level=log_utils.LOGWARNING)
        return None


def _delete(endpoint, json_data=None, timeout=15):
    apikey, base_url = getMDBListCredentials()
    if not apikey:
        return None
    try:
        r = requests.delete(base_url + endpoint, params={'apikey': apikey},
                           json=json_data or {}, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {}
    except Exception as e:
        log_utils.log('MDBList DELETE %s failed: %s' % (endpoint, e), level=log_utils.LOGWARNING)
        return None


# ---------------------------------------------------------------------------
# Scrobbling  (POST /scrobble/{start,pause,stop,clear})
# ---------------------------------------------------------------------------

def _build_scrobble_body(imdb, tmdb, tvdb, season, episode, progress):
    """Cuerpo para /scrobble/*. OJO: MDBList anida temporada/episodio DENTRO
    del objeto show (show.season.number / show.season.episode.number), no en
    un objeto 'episode' separado como Trakt/SIMKL."""
    ids = {}
    if imdb:
        _i = str(imdb)
        if not _i.startswith('tt'):
            _i = 'tt' + _i
        ids['imdb'] = _i
    if tmdb:
        ids['tmdb'] = int(str(tmdb)) if str(tmdb).isdigit() else str(tmdb)
    if tvdb:
        ids['tvdb'] = int(str(tvdb)) if str(tvdb).isdigit() else str(tvdb)

    body = {
        'progress': float(progress),
        'app_version': control.getluc_kodiVersion() if hasattr(control, 'getluc_kodiVersion') else '1.0.0',
        'app_date': time.strftime('%Y-%m-%d'),
    }
    if not episode:
        body['movie'] = {'ids': ids}
    else:
        body['show'] = {
            'ids': ids,
            'season': {'number': int(season), 'episode': {'number': int(episode)}},
        }
    return body


def _scrobble_call(action, imdb, tmdb, tvdb, season, episode, progress):
    """Despacha /scrobble/{action} con throttle local."""
    global _last_scrobble_at
    now = time.time()
    if action not in ('stop', 'clear') and (now - _last_scrobble_at['ts']) < _SCROBBLE_THROTTLE_SECONDS:
        log_utils.log('MDBList scrobble %s skipped (cooldown).' % action, level=log_utils.LOGDEBUG)
        return False
    _last_scrobble_at['ts'] = now

    # Si es episodio y NO hay NINGÚN id, la llamada fracasará seguro en MDBList
    # (no puede emparejar la serie). Avisar claramente en el log.
    if episode and not (imdb or tmdb or tvdb):
        log_utils.log('MDBList scrobble/%s ABORTADO: episodio sin ids '
                      '(tvshow=S%sE%s prog=%s). El item de "Continuar viendo" '
                      'no traía imdb/tmdb/tvdb.' % (action, season, episode, progress),
                      level=log_utils.LOGWARNING)
        return False

    try:
        body = _build_scrobble_body(imdb, tmdb, tvdb, season, episode, progress)
        r = _post('/scrobble/%s' % action, json_data=body, silent=True)
        if r is None:
            log_utils.log('MDBList scrobble/%s FAILED (imdb=%s tmdb=%s tvdb=%s S%sE%s prog=%s)' %
                          (action, imdb, tmdb, tvdb, season, episode, progress), level=log_utils.LOGINFO)
            return False
        if getSetting('mdblist.notify') == 'true':
            control.notification(title='MDBList', message='Scrobble %s OK' % action)
        log_utils.log('MDBList scrobble/%s OK (imdb=%s tmdb=%s tvdb=%s S%sE%s prog=%s)' %
                      (action, imdb, tmdb, tvdb, season, episode, progress), level=log_utils.LOGINFO)
        return True
    except Exception:
        log_utils.error()
        return False


def scrobbleStart(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
    if not getMDBListScrobbleInfo():
        return False
    return _scrobble_call('start', imdb, tmdb, tvdb, season, episode, watched_percent)


def scrobblePause(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=0):
    if not getMDBListScrobbleInfo():
        return False
    return _scrobble_call('pause', imdb, tmdb, tvdb, season, episode, watched_percent)


def scrobbleStop(imdb=None, tmdb=None, tvdb=None, season=None, episode=None, watched_percent=100):
    """/scrobble/stop con progress >= 80 marca como visto en MDBList."""
    if not getMDBListScrobbleInfo():
        return False
    ok = _scrobble_call('stop', imdb, tmdb, tvdb, season, episode, watched_percent)
    if ok and float(watched_percent) >= 80:
        try:
            invalidateSectionCaches()
        except Exception:
            log_utils.error()
    return ok


def scrobbleClear(imdb=None, tmdb=None, tvdb=None, season=None, episode=None):
    """/scrobble/clear — borra la sesión en pausa (resume) sin marcar visto."""
    if not getMDBListScrobbleInfo():
        return False
    return _scrobble_call('clear', imdb, tmdb, tvdb, season, episode, 0)


def invalidateSectionCaches():
    """Invalida los caches de las secciones MDBList (continuar viendo /
    siguiente no visto) para que se refresquen al instante tras un stop."""
    try:
        from resources.lib.database import cache
        from resources.lib.menus.episodes import Episodes
        ep = Episodes(notifications=False)
        for attr_list, attr_link in (
            ('mdblist_continue_list', 'mdblistcontinue_link'),
            ('mdblist_upnext_list', 'mdblistupnext_link'),
        ):
            try:
                cache.remove(getattr(ep, attr_list), getattr(ep, attr_link))
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Continue Watching  (GET /sync/playback)  — reemplaza la BD del servicio
# ---------------------------------------------------------------------------

def _id_from(ids, *keys):
    """Primer id no vacío probando varias variantes de clave. MDBList es
    INCONSISTENTE: unos endpoints devuelven 'tmdb', otros 'tmdbid'."""
    if not isinstance(ids, dict):
        return ''
    for k in keys:
        v = ids.get(k)
        if v:
            return str(v)
    return ''


def _tmdb_from(ids):
    return _id_from(ids, 'tmdb', 'tmdbid', 'tmdb_id')


def _imdb_from(ids):
    return _id_from(ids, 'imdb', 'imdbid', 'imdb_id')


def _tvdb_from(ids):
    return _id_from(ids, 'tvdb', 'tvdbid', 'tvdb_id')


def _fetch_server_paused():
    """GET /sync/playback → (movies_list, episodes_list) normalizados.

    El servidor devuelve una LISTA plana donde cada item tiene type, progress,
    paused_at y un objeto movie/episode/show con ids.{imdbid,tmdbid,tvdbid}
    (¡con sufijo 'id'!)."""
    data = _get('/sync/playback')
    if not data or not isinstance(data, list):
        return [], []

    movies, episodes = [], []

    for it in data:
        try:
            typ = (it.get('type') or '').lower()
            pct = float(it.get('progress') or 0)
            if pct <= 0 or pct >= 85:
                continue
            paused_at = it.get('paused_at', '') or ''

            if typ == 'movie' and it.get('movie'):
                mv = it['movie']
                ids = mv.get('ids') or {}
                movies.append({
                    'type': 'movie',
                    'imdb': _imdb_from(ids),
                    'tmdb': _tmdb_from(ids),
                    'tvdb': '',
                    'title': mv.get('title', ''),
                    'originaltitle': mv.get('title', ''),
                    'tvshowtitle': '',
                    'year': str(mv.get('year', '')),
                    'season': 0,
                    'episode': 0,
                    'duration': int((mv.get('runtime') or 0)) * 60,
                    'progress': str(round(pct, 2)),
                    'paused_at': paused_at,
                    'next': '',
                })
            elif typ == 'episode' and it.get('show'):
                sh = it['show']
                epd = it.get('episode') or {}
                sids = sh.get('ids') or {}
                eids = epd.get('ids') or {}
                episodes.append({
                    'type': 'episode',
                    'imdb': _imdb_from(sids) or _imdb_from(eids),
                    'tmdb': _tmdb_from(sids),
                    'tvdb': _tvdb_from(sids),
                    'title': epd.get('title', ''),
                    'originaltitle': epd.get('title', ''),
                    'tvshowtitle': sh.get('title', ''),
                    'year': str(sh.get('year', '')),
                    'season': int(epd.get('season') or 0),
                    'episode': int(epd.get('number') or 0),
                    'duration': int((epd.get('runtime') or sh.get('runtime') or 0)) * 60,
                    'progress': str(round(pct, 2)),
                    'paused_at': paused_at,
                    'next': '',
                })
        except Exception:
            pass

    movies.sort(key=lambda k: k.get('paused_at', ''), reverse=True)
    episodes.sort(key=lambda k: k.get('paused_at', ''), reverse=True)
    return movies, episodes


def getContinueMovies():
    """Películas en progreso desde el servidor MDBList (/sync/playback)."""
    movies, _ = _fetch_server_paused()
    return movies


def getContinueEpisodes():
    """Episodios en progreso desde el servidor MDBList (/sync/playback)."""
    _, episodes = _fetch_server_paused()
    return episodes


# ---------------------------------------------------------------------------
# Up Next  (GET /upnext) — siguiente episodio no visto de series en curso
# ---------------------------------------------------------------------------

def getUpNext(hide_unreleased=True, limit=40):
    """Devuelve lista de episodios "siguiente no visto" normalizada al formato
    que consumen las secciones de episodios."""
    params = {'limit': limit}
    if hide_unreleased:
        params['hide_unreleased'] = 'true'
    data = _get('/upnext', params=params)
    if not data or not isinstance(data, dict):
        return []
    out = []
    for it in (data.get('items') or []):
        try:
            sh = it.get('show') or {}
            ne = it.get('next_episode') or {}
            sids = sh.get('ids') or {}
            eids = ne.get('ids') or {}
            out.append({
                'type': 'episode',
                'imdb': str(sids.get('imdb') or sids.get('imdbid') or ''),
                'tmdb': str(sids.get('tmdb') or sids.get('tmdbid') or '') if (sids.get('tmdb') or sids.get('tmdbid')) else '',
                'tvdb': str(sids.get('tvdb') or sids.get('tvdbid') or '') if (sids.get('tvdb') or sids.get('tvdbid')) else '',
                'title': ne.get('title', ''),
                'originaltitle': ne.get('title', ''),
                'tvshowtitle': sh.get('title', ''),
                'year': str(sh.get('year', '')),
                'season': int(ne.get('season') or 0),
                'episode': int(ne.get('episode') or 0),
                'premiered': (ne.get('air_date') or '')[:10],
                'duration': int((ne.get('runtime') or 0)) * 60,
                'last_watched_at': it.get('last_watched_at', ''),
                'next': '',
            })
        except Exception:
            pass
    out.sort(key=lambda k: k.get('last_watched_at', ''), reverse=True)
    return out


# ---------------------------------------------------------------------------
# Watched history  (GET/POST /sync/watched)
# ---------------------------------------------------------------------------

def addWatched(imdb=None, tmdb=None, tvdb=None, season=None, episode=None):
    """Marca un título como visto en MDBList vía /sync/watched."""
    if not getMDBListCredentialsInfo():
        return False
    ids = {}
    if imdb:
        _i = str(imdb)
        if not _i.startswith('tt'):
            _i = 'tt' + _i
        ids['imdb'] = _i
    if tmdb and str(tmdb).isdigit():
        ids['tmdb'] = int(tmdb)
    if tvdb and str(tvdb).isdigit():
        ids['tvdb'] = int(tvdb)
    if not episode:
        payload = {'movies': [{'ids': ids}]}
    else:
        payload = {'shows': [{'ids': ids, 'seasons': [
            {'number': int(season), 'episodes': [{'number': int(episode)}]}]}]}
    return _post('/sync/watched', json_data=payload, silent=True) is not None


# ---------------------------------------------------------------------------
# Watchlist  (GET /watchlist/items ; POST /watchlist/items/{add,remove})
# ---------------------------------------------------------------------------

def _build_watchlist_items(data, kind):
    items = []
    for m in (data.get(kind) or []):
        try:
            items.append({
                'title': m.get('title', ''),
                'year': str(m.get('release_year', '')),
                'imdb': str(m.get('imdb_id', '')),
                'tmdb': str(m.get('tmdb_id', '')) if m.get('tmdb_id') else '',
                'tvdb': str(m.get('tvdb_id', '')) if m.get('tvdb_id') else '',
                'rank': m.get('rank', 9999),
            })
        except Exception:
            log_utils.error()
    items.sort(key=lambda x: x.get('rank', 9999))
    return items


def getWatchlistMovies():
    data = _get('/watchlist/items')
    return _build_watchlist_items(data, 'movies') if data else []


def getWatchlistShows():
    data = _get('/watchlist/items')
    return _build_watchlist_items(data, 'shows') if data else []


def addToWatchlist(imdb_id, media_type):
    """media_type: 'movie' | 'show'. Endpoint real: POST /watchlist/items/add."""
    key = 'movies' if media_type == 'movie' else 'shows'
    payload = {key: [{'ids': {'imdb': imdb_id}}]}
    return _post('/watchlist/items/add', json_data=payload) is not None


def removeFromWatchlist(imdb_id, media_type):
    key = 'movies' if media_type == 'movie' else 'shows'
    payload = {key: [{'ids': {'imdb': imdb_id}}]}
    return _post('/watchlist/items/remove', json_data=payload) is not None


# ---------------------------------------------------------------------------
# Listas de usuario y listas públicas
# ---------------------------------------------------------------------------

def getUserLists():
    data = _get('/lists/user')
    return data if isinstance(data, list) else []


def _build_movie(m):
    return {
        'title': m.get('title', ''),
        'year': str(m.get('release_year', '')),
        'imdb': str(m.get('imdb_id', '')),
        'tmdb': str(m.get('tmdb_id', '')) if m.get('tmdb_id') else '',
        'tvdb': '',
        'rank': m.get('rank', 9999),
    }


def _build_show(s):
    return {
        'title': s.get('title', ''),
        'year': str(s.get('release_year', '')),
        'imdb': str(s.get('imdb_id', '')),
        'tmdb': str(s.get('tmdb_id', '')) if s.get('tmdb_id') else '',
        'tvdb': str(s.get('tvdb_id', '')) if s.get('tvdb_id') else '',
        'rank': s.get('rank', 9999),
    }


def getListItems(list_id, media_type=None):
    data = _get('/lists/%s/items' % list_id)
    if not data:
        return [], []
    movies = sorted([_build_movie(m) for m in (data.get('movies') or [])], key=lambda x: x['rank'])
    shows = sorted([_build_show(s) for s in (data.get('shows') or [])], key=lambda x: x['rank'])
    if media_type == 'show' and not shows:
        sfm = [_build_show(m) for m in (data.get('movies') or [])
               if str(m.get('mediatype', '')).lower() in ('show', 'tv', 'tvshow', 'series')]
        if sfm:
            shows = sorted(sfm, key=lambda x: x['rank'])
    if media_type == 'movie':
        return movies, []
    if media_type == 'show':
        return [], shows
    return movies, shows


def getTopLists():
    data = _get('/lists/top')
    return data if isinstance(data, list) else []


def searchLists(query):
    data = _get('/lists/search', params={'query': query})
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('lists'), list):
        return data['lists']
    return []


def getMediaInfo(imdb_id):
    return _get('/imdb/movie/%s' % imdb_id)


def resolveShowIds(ids_dict):
    if ids_dict.get('tvdb'):
        return ids_dict
    try:
        if ids_dict.get('tmdb'):
            data = _get('/tmdb/show/%s' % ids_dict['tmdb'])
        elif ids_dict.get('imdb'):
            data = _get('/imdb/show/%s' % ids_dict['imdb'])
        else:
            return ids_dict
        if data:
            remote_ids = data.get('ids') or {}
            tvdb = remote_ids.get('tvdb') or remote_ids.get('tvdbid') or data.get('tvdb_id')
            if tvdb:
                ids_dict['tvdb'] = str(tvdb)
            if not ids_dict.get('imdb'):
                imdb = remote_ids.get('imdb') or remote_ids.get('imdbid')
                if imdb:
                    ids_dict['imdb'] = str(imdb)
    except Exception as e:
        log_utils.log('MDBList resolveShowIds failed: %s' % e, level=log_utils.LOGWARNING)
    return ids_dict


def getTopMovieLists():
    return [l for l in getTopLists() if l.get('mediatype') in ('movie', 'both', '')]


def getTopShowLists():
    return [l for l in getTopLists() if l.get('mediatype') in ('show', 'both', '')]


def getUserListsByName(username):
    if not username:
        return []
    data = _get('/lists/user/%s' % username.strip())
    return data if isinstance(data, list) else []


def getListItemsFromUrl(mdblist_url):
    import re
    mdblist_url = mdblist_url.strip().rstrip('/')
    m = re.search(r'mdblist\.com/lists/([^/]+)/([^/]+)', mdblist_url)
    if not m:
        return [], []
    username, slug = m.group(1), m.group(2)
    list_id = None
    for lst in getUserListsByName(username):
        if lst.get('slug') == slug:
            list_id = lst.get('id')
            break
    if list_id:
        return getListItems(list_id)
    try:
        r = requests.get('https://mdblist.com/lists/%s/%s/json/' % (username, slug), timeout=15)
        r.raise_for_status()
        data = r.json()

        def _b(item):
            return {
                'title': item.get('title', ''),
                'year': str(item.get('release_year') or item.get('year') or ''),
                'imdb': str(item.get('imdb_id') or item.get('imdb') or ''),
                'tmdb': str(item.get('tmdb_id') or item.get('tmdb') or '') if (item.get('tmdb_id') or item.get('tmdb')) else '',
                'tvdb': str(item.get('tvdb_id') or item.get('tvdb') or '') if (item.get('tvdb_id') or item.get('tvdb')) else '',
                'rank': item.get('rank', 9999),
            }

        if isinstance(data, list):
            movies = sorted([_b(i) for i in data if not i.get('tvdb_id')], key=lambda x: x['rank'])
            shows = sorted([_b(i) for i in data if i.get('tvdb_id')], key=lambda x: x['rank'])
            return movies, shows
        movies = sorted([_b(mm) for mm in (data.get('movies') or [])], key=lambda x: x['rank'])
        shows = sorted([_b(s) for s in (data.get('shows') or [])], key=lambda x: x['rank'])
        return movies, shows
    except Exception as exc:
        log_utils.log('getListItemsFromUrl failed: %s' % exc, level=log_utils.LOGWARNING)
        return [], []


# ---------------------------------------------------------------------------
# Context-menu helper (watchlist add/remove)
# ---------------------------------------------------------------------------

def manager(name, imdb, media_type):
    items = [control.lang(40201), control.lang(40202)]
    select = control.selectDialog(items, control.lang(40200))
    if select == 0:
        ok = addToWatchlist(imdb, media_type)
        control.notification(title='MDBList', message=control.lang(40203) if ok else control.lang(40205))
        control.refresh()
    elif select == 1:
        ok = removeFromWatchlist(imdb, media_type)
        control.notification(title='MDBList', message=control.lang(40204) if ok else control.lang(40205))
        control.refresh()


# ---------------------------------------------------------------------------
# Auth / account  (validación de key vía GET /user)
# ---------------------------------------------------------------------------

def getUserInfo(apikey=None, token=None):
    """GET /user. Prioridad: token OAuth explícito (Bearer) > apikey explícita
    (?apikey=) > credencial configurada (su modo correcto). Devuelve dict o
    None. Sirve para validar credenciales y obtener el username.

    `token` permite obtener la identidad con un access_token recién emitido sin
    depender de que la caché de settings ya esté invalidada (evita caer por
    error en otra credencial y traer un username ajeno)."""
    key = (apikey or '').strip()
    tok = (token or '').strip()
    try:
        if tok:
            r = requests.get(BASE_URL + '/user',
                             headers={'Authorization': 'Bearer %s' % tok}, timeout=15)
        elif key:
            r = requests.get(BASE_URL + '/user', params={'apikey': key}, timeout=15)
        else:
            cred, _ = getMDBListCredentials()
            if not cred:
                return None
            headers, auth_params = _auth_headers_params()
            r = requests.get(BASE_URL + '/user', params=auth_params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_utils.log('MDBList getUserInfo failed: %s' % e, level=log_utils.LOGWARNING)
        return None


def validateAndSaveKey(apikey):
    """Valida una API key contra /user y, si es buena, la guarda + activa
    MDBList + rellena el username. Devuelve (ok, username|mensaje_error)."""
    apikey = (apikey or '').strip()
    if not apikey:
        return False, 'Empty key'
    info = getUserInfo(apikey)
    if not info or not (info.get('username') or info.get('user_id')):
        return False, 'Invalid key'
    username = info.get('username') or str(info.get('user_id'))
    try:
        setSetting('mdblist.apikey', apikey)
        setSetting('mdblist.username', username)
        setSetting('mdblist.enable', 'true')
        try:
            control.homeWindow.clearProperty('luc_kodi_settings')
        except Exception:
            pass
    except Exception:
        log_utils.error()
        return False, 'Could not write settings'
    return True, username


# ---------------------------------------------------------------------------
# OAuth 2.0 Device Flow  (PIN + QR, sin teclado) — igual que Trakt/SIMKL
# ---------------------------------------------------------------------------

_last_device_error = {'msg': ''}


def getDeviceCode():
    """POST /oauth/device-authorization/ con el client_id. Devuelve el dict
    (user_code, device_code, verification_uri, interval, expires_in) o None.
    Guarda el motivo del fallo en _last_device_error para mostrarlo."""
    _last_device_error['msg'] = ''
    client_id = getClientID()
    if not client_id:
        _last_device_error['msg'] = 'No client_id'
        return None
    try:
        r = requests.post(_OAUTH_DEVICE_URL,
                          data={'client_id': client_id, 'scope': 'write'}, timeout=20)
        if not r.ok:
            body = ''
            try:
                body = r.text[:300]
            except Exception:
                pass
            _last_device_error['msg'] = 'HTTP %s — %s' % (r.status_code, body)
            log_utils.log('MDBList device-auth HTTP %s: %s' % (r.status_code, body),
                          level=log_utils.LOGWARNING)
            return None
        try:
            return r.json()
        except Exception as e:
            _last_device_error['msg'] = 'Bad JSON: %s' % e
            return None
    except Exception as e:
        _last_device_error['msg'] = 'Network error: %s' % e
        log_utils.log('MDBList getDeviceCode failed: %s' % e, level=log_utils.LOGWARNING)
        return None


def _device_verify_url(device_data):
    base = (device_data.get('verification_uri') or device_data.get('verification_url')
            or _OAUTH_VERIFY_URL).rstrip('/')
    user_code = device_data.get('user_code', '')
    if user_code:
        return '%s?code=%s' % (base, user_code)
    return base


def pollDeviceToken(device_data):
    """Muestra PIN + QR en un diálogo de progreso y hace polling a
    /oauth/token/ hasta recibir access_token, expiración o cancelación.
    Devuelve el dict del token o None."""
    device_code = device_data.get('device_code')
    user_code = device_data.get('user_code')
    if not device_code or not user_code:
        return None
    client_id = getClientID()
    expires_in = int(device_data.get('expires_in') or 300)
    interval = max(int(device_data.get('interval') or 5), 1)
    verify_base = (device_data.get('verification_uri') or device_data.get('verification_url')
                   or _OAUTH_VERIFY_URL).replace('https://', '').replace('http://', '').rstrip('/')
    verify_full = _device_verify_url(device_data)

    # QR (mismo proveedor que SIMKL/Trakt en este addon) + clipboard.
    qr_icon = ''
    try:
        from urllib.parse import quote_plus
    except ImportError:
        from urllib import quote_plus
    try:
        qr_icon = ('https://api.qrserver.com/v1/create-qr-code/?size=256x256&qzone=1&data='
                   + quote_plus(verify_full))
    except Exception:
        qr_icon = ''
    try:
        from resources.lib.modules.source_utils import copy2clip
        copy2clip(verify_full)
    except Exception:
        pass

    try:
        control.notification(title='MDBList', message='%s  |  %s' % (verify_base, user_code),
                             icon=qr_icon, time=15000)
    except Exception:
        pass

    progressDialog = control.progressDialog
    progressDialog.create('MDBList authorization')
    line = ('[B]Visit:[/B] %s\n[B]Enter code:[/B] %s\n'
            'OR scan the QR  ·  link copied to clipboard\n\nWaiting for authorization...'
            % (verify_base, user_code))
    try:
        progressDialog.update(100, line)
    except Exception:
        pass

    time_passed = expires_in
    token_resp = None
    while True:
        if progressDialog.iscanceled():
            break
        if time_passed <= 0:
            try: progressDialog.close()
            except Exception: pass
            control.notification(title='MDBList', message='Code expired, please try again.')
            return None
        control.sleep(1000)
        time_passed -= 1
        try:
            progressDialog.update(int((expires_in - time_passed) / float(expires_in) * 100))
        except Exception:
            pass
        # Poll cada `interval` segundos.
        if (expires_in - time_passed) % interval != 0:
            continue
        try:
            r = requests.post(_OAUTH_TOKEN_URL, data={
                'grant_type': _OAUTH_GRANT_DEVICE,
                'device_code': device_code,
                'client_id': client_id}, timeout=20)
            if r.status_code == 200:
                token_resp = r.json()
                break
            # 400/428 = authorization_pending / slow_down → seguir.
        except Exception:
            pass

    try: progressDialog.close()
    except Exception: pass
    return token_resp


def authenticate():
    """Flujo completo Device: pide código, muestra PIN+QR, espera token y lo
    guarda. Rellena username vía /user (Bearer). Devuelve True/False."""
    if not getClientID():
        control.dialog.ok('MDBList',
            'Missing [B]client_id[/B].\n\nRegister your app at [B]mdblist.com[/B] '
            '(Preferences > API Access), paste the client_id under Settings > MDBList > '
            'Client ID, and try again.')
        return False
    device_data = getDeviceCode()
    if not device_data or not device_data.get('user_code'):
        reason = _last_device_error.get('msg') or 'unknown'
        control.dialog.ok('MDBList — could not start',
            'Could not get the authorization code.\n\n[B]Reason:[/B] %s\n\n'
            'Endpoint: %s' % (reason, _OAUTH_DEVICE_URL))
        return False
    token_result = pollDeviceToken(device_data)
    if not token_result:
        control.notification(title='MDBList', message='Authorization canceled.')
        return False
    access_token = token_result.get('access_token')
    if not access_token:
        control.notification(title='MDBList', message='Authorization failed.')
        return False
    try:
        setSetting('mdblist.token', access_token)
        setSetting('mdblist.refresh', token_result.get('refresh_token') or '0')
        setSetting('mdblist.enable', 'true')
    except Exception:
        log_utils.error()
        return False
    info = getUserInfo(token=access_token) or {}
    username = info.get('username') or str(info.get('user_id') or 'MDBList User')
    try:
        setSetting('mdblist.username', username)
        control.homeWindow.clearProperty('luc_kodi_settings')
    except Exception:
        pass
    invalidateSectionCaches()
    control.notification(title='MDBList', message='Account authorized: %s' % username)
    return True


def auth():
    """Autorización por OAuth Device Flow (PIN + QR). Único método."""
    authenticate()


def deauth():
    """Borra token OAuth + key del usuario, username y desactiva MDBList.
    Sin credencial propia, MDBList queda inactivo (no hay key por defecto)."""
    try:
        setSetting('mdblist.token', '')
        setSetting('mdblist.refresh', '')
        setSetting('mdblist.apikey', '')
        setSetting('mdblist.username', '')
        setSetting('mdblist.enable', 'false')
        setSetting('mdblist.scrobble', 'false')
        try:
            control.homeWindow.clearProperty('luc_kodi_settings')
        except Exception:
            pass
        invalidateSectionCaches()
        control.notification(title='MDBList', message='Deauthorized')
    except Exception:
        log_utils.error()


def account_info_to_dialog():
    """Muestra perfil + límites + contador de peticiones de la credencial activa."""
    info = getUserInfo()
    if not info:
        control.dialog.ok('MDBList', 'Could not fetch account info. Authorize first (PIN + QR).')
        return
    using_default = usingDefaultKey()
    limits = info.get('limits') or {}
    auth_mode = 'OAuth (Bearer)' if oauthActive() else info.get('auth_method', 'apikey')
    lines = (
        '[B]User:[/B] %s\n'
        '[B]Plan:[/B] %s\n'
        '[B]Requests:[/B] %s / %s   (remaining: %s)\n'
        '[B]Lists:[/B] %s   [B]List items:[/B] %s\n'
        '[B]Auth method:[/B] %s\n'
        '[B]Credential:[/B] %s'
    ) % (
        info.get('username', '?'),
        info.get('plan', '?'),
        info.get('api_requests_count', '?'), info.get('api_requests', '?'),
        info.get('rate_limit_remaining', '?'),
        limits.get('lists', '?'), limits.get('lists_items', '?'),
        auth_mode,
        'plugin default (authorize with PIN + QR)' if using_default else 'your own account',
    )
    control.dialog.ok('MDBList account', lines)
