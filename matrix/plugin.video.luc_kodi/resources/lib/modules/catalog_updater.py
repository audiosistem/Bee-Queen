# -*- coding: utf-8 -*-
"""
luc_kodi - TMDB Catalog Precache / Auto Update 

This service prefetches key TMDB endpoints into luc_kodi cache DB so widgets/menus load fast.
"""

from __future__ import absolute_import

import re
import time
from threading import Thread, Semaphore, Lock

import xbmc

from resources.lib.modules import control, log_utils
from resources.lib.modules import notif_queue

LOGINFO = log_utils.LOGINFO

# Settings IDs (added in resources/settings.xml)
S_ENABLED = 'catalog.auto_update.enabled'
S_ON_START = 'catalog.auto_update.on_start'
S_INTERVAL = 'catalog.auto_update.interval_hours'
S_NOTIFY = 'catalog.auto_update.notify'
S_LASTRUN = 'catalog.auto_update.last_run'  # internal timestamp (seconds)
# v1.0.54: el refresco COMPLETO de metadatos (fresh_meta: invalidar metacache y
# re-pedir el detalle por título a TMDb) ya no corre en cada arranque — es lo que
# costaba 6-7s. Ahora se limita a una vez cada N horas (ajuste meta_hours); el
# resto de arranques solo hacen el refresco VISUAL ligero (ver
# tmdb_list_visual_refresh en indexers/tmdb.py), que pinta la parrilla al
# instante desde metacache con póster/fanart/rating frescos de la propia lista.
S_META_HOURS = 'catalog.auto_update.meta_hours'  # enum: índice sobre _META_HOURS
S_LASTMETA = 'catalog.auto_update.last_meta'     # internal timestamp (seconds)
# v1.0.80 — Plataformas (Movies > Streaming) y cadenas (TV shows > Networks)
# seleccionadas para precachear. Se guardan como lista separada por comas:
#   streaming -> 'id:region'  (p.ej. '8:US,1773:ES')
#   networks  -> 'id'         (p.ej. '213,49,2552')
# La selección se hace desde Ajustes con un diálogo multiselección sobre las
# mismas tablas curadas que pintan los menús (tools_selectPrecacheStreaming /
# tools_selectPrecacheNetworks en router.py).
S_PRE_STREAM = 'catalog.precache.streaming'
S_PRE_STREAM_IDS = 'catalog.precache.streaming.ids'
S_PRE_NET = 'catalog.precache.networks'
S_PRE_NET_IDS = 'catalog.precache.networks.ids'
# ── DOS NIVELES para plataformas y cadenas (v1.0.80) ──────────────────────────
# NIVEL 1 (rápido): hasta 10 marcadas a mano. Entran en el ciclo principal junto
#   a las listas base, así que están calientes desde el arranque igual que
#   Popular o Top Rated.
# NIVEL 2 (fondo): TODAS las demás de las tablas curadas. No corren en el ciclo
#   principal; las refresca una pasada rotatoria que solo toca las que llevan más
#   de N días sin renovarse, y que se corta en seco al agotar su presupuesto de
#   tiempo. Así el catálogo de cada plataforma cambia cada semana sin que ninguna
#   pasada se alargue.
MAX_PRECACHE_PLATFORMS = 10
# ── v1.0.81: TRES NIVELES, no dos ────────────────────────────────────────────
# NIVEL 1 "RAPIDO" (sin presupuesto de tiempo, corre el primero y solo):
#   Trending y Popular de Movies y TV shows -- que van por TRAKT, no por TMDb, y
#   por eso NO se precacheaban hasta ahora pese a ser las dos primeras entradas
#   del menu --, TMDb Now Playing, y las hasta 10 plataformas y 10 cadenas que
#   el usuario haya marcado. Es lo que tiene que estar caliente al abrir.
# NIVEL 2 "RESTO DEL MENU" (segundo plano, en CADA arranque, tope de 30 s):
#   Top Rated, Upcoming, Box Office, Airing Today, On The Air. Box Office entra
#   aqui por decision expresa: no necesita ser instantaneo.
# NIVEL 3 "ROTACION" (segundo plano, tope de 30 s, caducidad de 7 dias):
#   todas las plataformas y cadenas NO marcadas, por turnos.
# El nivel 1 no comparte presupuesto con los otros dos: un TMDb lento puede
# recortar el fondo, nunca lo que el usuario ve primero.
_PRIORITY_SAFETY_FACTOR = 4  # tope duro del nivel 1 = 4 x el presupuesto de fondo

# Listas de Trakt del nivel 1. (mediatype, nombre del *_link, ajuste del menu).
_PRIORITY_TRAKT = (
    ('movie',  'traktpopular',  'navi.movie.trakt.popular'),
    ('movie',  'trakttrending', 'navi.movie.trakt.trending'),
    ('tvshow', 'traktpopular',  'navi.tv.trakt.popular'),
    ('tvshow', 'trakttrending', 'navi.tv.trakt.trending'),
)

S_ROTATE = 'catalog.precache.rotate'
S_ROTATE_DAYS = 'catalog.precache.rotate.days'    # enum: índice sobre _ROTATE_DAYS
S_ROTATE_INDEX = 'catalog.precache.rotate.index'  # oculto: por dónde iba la vuelta
S_BUDGET = 'catalog.precache.budget'              # enum: índice sobre _BUDGET_SECONDS
_ROTATE_DAYS = (3, 7, 14, 30)
_BUDGET_SECONDS = (15, 30, 60, 120)
# Metas ligeras que el servicio completa por pasada (ver upgrade_light_meta).
# v1.0.81 -- el lote de 20 en SERIE cada 30 s daba 40 metas/minuto. Medido en un
# kodi.log real con 20 widgets en la pantalla de inicio, la cola estaba en 713
# pendientes y bajaba 3 en 33 s, porque abrir cualquier lista crea fichas
# ligeras casi al mismo ritmo al que se completaban. Con lote de 40, cuatro en
# vuelo y una espera de 10 s mientras quede cola, la misma cola se vacia en
# unos minutos en vez de no vaciarse nunca.
LIGHT_UPGRADE_BATCH = 40
LIGHT_UPGRADE_WORKERS = 4
LIGHT_UPGRADE_EVERY_SECONDS = 10
# Cadencia PROPIA de la rotacion (nivel 3). Antes solo corria "si no queda arte
# pendiente", y con una cola que no se vaciaba eso significaba no correr nunca.
ROTATION_EVERY_SECONDS = 900

# Los settings type="enum" de Kodi devuelven el ÍNDICE seleccionado, no el valor.
# Mapeos índice -> horas para los dos enums de este módulo.
_INTERVAL_HOURS = (1, 3, 6, 12, 24)   # catalog.auto_update.interval_hours
_META_HOURS = (6, 12, 24, 48)         # catalog.auto_update.meta_hours

CHECK_EVERY_SECONDS = 300  # 5 minutes

# Tope global de peticiones TMDb concurrentes durante el precache. El diseño
# anterior corría las 9 listas en SECUENCIA, y cada lista lanzaba ~20 hilos de
# meta: 9 tandas de 20 una detrás de otra. Ahora las 9 listas se procesan a la
# vez bajo un único semáforo que limita el TOTAL de peticiones de meta en vuelo,
# así el arranque acaba antes sin saturar la CPU/red del Shield ni a TMDb.
# v1.0.38: 16. Probamos 28 y NO ayudó — el cuello no era la concurrencia de red
# sino una tormenta de lecturas de settings (ya resuelta en control.setting) más
# la latencia propia de TMDb. Con el fix de settings, 16 hilos van sobrados y no
# saturan el parseo de settings ni compiten de más con el arranque de Kodi.
PRECACHE_MAX_WORKERS = 16

def _now():
    return int(time.time())

def _get_bool(setting_id, default=False):
    v = control.setting(setting_id)
    if v == '':
        return default
    return v == 'true'

def _get_int(setting_id, default):
    try:
        v = control.setting(setting_id)
        return int(v) if v != '' else default
    except:
        return default

def _get_last_run():
    try:
        v = control.setting(S_LASTRUN)
        return int(v) if v else 0
    except:
        return 0

def _set_last_run(ts):
    try:
        control.setSetting(S_LASTRUN, str(int(ts)))
    except:
        pass

def _is_due(interval_hours):
    last = _get_last_run()
    if last == 0:
        return True
    return (_now() - last) >= (int(interval_hours) * 3600)

def _enum_hours(setting_id, table, default_hours):
    """Los enum de Kodi guardan el ÍNDICE; traducir a horas con `table`.
    Si el valor almacenado no es un índice válido, caer a default_hours."""
    try:
        v = control.setting(setting_id)
        if v == '':
            return default_hours
        idx = int(v)
        if 0 <= idx < len(table):
            return table[idx]
        return default_hours
    except:
        return default_hours

def _get_last_meta():
    try:
        v = control.setting(S_LASTMETA)
        return int(v) if v else 0
    except:
        return 0

def _set_last_meta(ts):
    try:
        control.setSetting(S_LASTMETA, str(int(ts)))
    except:
        pass

def _meta_refresh_due():
    """True si toca el refresco COMPLETO de metadatos (fresh_meta). La primera
    vez (sin marca) siempre toca, para que una instalación nueva se llene."""
    last = _get_last_meta()
    if last == 0:
        return True
    hours = _enum_hours(S_META_HOURS, _META_HOURS, 12)
    return (_now() - last) >= (hours * 3600)

def _notify(msg):
    try:
        notif_queue.push(title='luc_kodi · Catalog', message=msg, time=3500)
    except:
        pass

def _page_url(url, page):
    # replace page=xxx
    if 'page=' in url:
        return re.sub(r'page=\d+', 'page=%d' % int(page), url)
    sep = '&' if '?' in url else '?'
    return url + ('%spage=%d' % (sep, int(page)))

def _menu_on(setting_id):
    """Como getMenuEnabled(), pero un valor VACIO cuenta como activado. Los
    ajustes navi.* salen con default="true"; si la clave aun no esta escrita en
    el settings.xml de userdata, getMenuEnabled() la leeria como desactivada y
    el precache se saltaria justo las listas que el menu SI esta mostrando."""
    try:
        return (control.setting(setting_id) or '').strip() != 'false'
    except Exception:
        return True


def _get_tmdb_links(tier='all'):
    """
    Devuelve (movie_links, tv_links) de TMDb para el nivel pedido.

      tier='fast'  -> nivel 1: Now Playing + las plataformas/cadenas marcadas.
      tier='slow'  -> nivel 2: el resto de listas TMDb del menu.
      tier='all'   -> las dos cosas (boton manual de Tools > Update Catalog).

    Los enlaces son los MISMOS objetos que usan los menus (movies.py/tvshows.py),
    ya con el marcador api_key=%s y page=1.

    v1.0.81 -- se corrigio que dependieran de lo que hay en el menu: el precache
    calentaba tmdb_popular y tmdb_boxoffice, que el menu de Movies NO muestra
    (usa las de Trakt), asi que dos de las cinco listas de peliculas eran trabajo
    tirado. Ahora cada lista se pide solo si su entrada de menu esta activada.
    """
    fast = tier in ('fast', 'all')
    slow = tier in ('slow', 'all')
    movie_links = []
    tv_links = []
    try:
        from resources.lib.menus.movies import Movies as MoviesMenu
        m = MoviesMenu()
        if fast and _menu_on('navi.movie.tmdb.nowplaying'):
            movie_links.append(getattr(m, 'tmdb_nowplaying_link', ''))
        if slow:
            if _menu_on('navi.movie.tmdb.toprated'): movie_links.append(getattr(m, 'tmdb_toprated_link', ''))
            if _menu_on('navi.movie.tmdb.upcoming'): movie_links.append(getattr(m, 'tmdb_upcoming_link', ''))
            # Box Office y Popular de TMDb: el menu de peliculas tira de Trakt
            # para las dos, asi que aqui solo sirven para los widgets que
            # alguien haya podido apuntar a ellas. Nivel 2 siempre.
            movie_links.append(getattr(m, 'tmdb_boxoffice_link', ''))
            movie_links.append(getattr(m, 'tmdb_popular_link', ''))
        movie_links = [i for i in movie_links if i]
        # Plataformas de Movies > Streaming marcadas a mano: NIVEL 1. Hasta la
        # 1.0.80 eran las unicas listas del addon que nunca se precacheaban.
        if fast and _get_bool(S_PRE_STREAM, default=False):
            for pid, region in _selected_streaming():
                try:
                    url = m.tmdb_watchproviders_link % ('%s', pid)
                    if region and region != 'US':
                        url = url.replace('region=US&watch_region=US', 'region=%s&watch_region=%s' % (region, region))
                    movie_links.append(url)
                except: log_utils.error()
    except:
        log_utils.error()

    try:
        # luc_kodi uses class name `TVshows` (not `TVShows`)
        from resources.lib.menus.tvshows import TVshows as TVShowsMenu
        t = TVShowsMenu()
        if slow:
            if _menu_on('navi.tv.tmdb.toprated'): tv_links.append(getattr(t, 'tmdb_toprated_link', ''))
            if _menu_on('navi.tv.tmdb.airingtoday'): tv_links.append(getattr(t, 'tmdb_airingtoday_link', ''))
            # tvshows.py uses tmdb_ontheair_link (not tmdb_ontv_link)
            if _menu_on('navi.tv.tmdb.ontv'): tv_links.append(getattr(t, 'tmdb_ontheair_link', ''))
            tv_links.append(getattr(t, 'tmdb_popular_link', ''))
        tv_links = [i for i in tv_links if i]
        # Cadenas de TV shows > Networks marcadas a mano: NIVEL 1.
        if fast and _get_bool(S_PRE_NET, default=False):
            for nid in _selected_networks():
                try: tv_links.append(t.tmdb_networks_link % ('%s', nid))
                except: log_utils.error()
    except Exception:
        # TV precache is optional.
        pass

    return movie_links, tv_links


def _budget_seconds():
    return _enum_hours(S_BUDGET, _BUDGET_SECONDS, 30)


def _rotate_days():
    return _enum_hours(S_ROTATE_DAYS, _ROTATE_DAYS, 7)


def _precache_trakt_list(mediatype, url_name, meta_sem=None, deadline=None):
    """Calienta una lista de TRAKT (Trending / Popular) por el MISMO camino que
    usa el menu: cache.get(trakt_list) + worker() -> metacache. No pinta ningun
    directorio (create_directory=False) ni saca notificaciones.

    Los dos ganchos del menu (precache_sem / precache_deadline, v1.0.81) hacen
    que su enriquecido comparta el semaforo global de peticiones con el resto
    del precache en vez de soltar sus propias tandas de 40 hilos.
    """
    try:
        if mediatype == 'tvshow':
            from resources.lib.menus.tvshows import TVshows as Menu
        else:
            from resources.lib.menus.movies import Movies as Menu
        menu = Menu(notifications=False)
        menu.precache_sem = meta_sem
        menu.precache_deadline = deadline
        menu.get(url_name, idx=True, create_directory=False)
        return True
    except Exception:
        log_utils.error()
        return False


def _priority_trakt_jobs():
    """Listas de Trakt del nivel 1 que el menu esta mostrando de verdad."""
    return [(mt, name) for mt, name, setting_id in _PRIORITY_TRAKT if _menu_on(setting_id)]


def _selected_streaming():
    """[(provider_id, region)] de las plataformas marcadas en Ajustes."""
    out = []
    try:
        raw = control.setting(S_PRE_STREAM_IDS) or ''
        for chunk in raw.split(','):
            chunk = chunk.strip()
            if not chunk: continue
            pid, _, region = chunk.partition(':')
            if pid: out.append((pid.strip(), (region or 'US').strip()))
    except: log_utils.error()
    return out[:MAX_PRECACHE_PLATFORMS]


def _selected_networks():
    """[network_id] de las cadenas marcadas en Ajustes."""
    try:
        raw = control.setting(S_PRE_NET_IDS) or ''
        saved = [i.strip() for i in raw.split(',') if i.strip()]
        # v1.0.94: la lista de Networks paso de 105 a 29 y algunas cadenas se
        # unieron con su nombre anterior. Una seleccion guardada con ids viejos
        # se lleva a la entrada actual y lo retirado se descarta, para no
        # seguir precargando cadenas que ya no estan en el menu.
        try:
            from resources.lib.indexers.tmdb import canonical_network_ids
            saved = canonical_network_ids(saved)
        except Exception:
            log_utils.error()
        return saved[:MAX_PRECACHE_PLATFORMS]
    except:
        log_utils.error()
        return []

def precache_tmdb_catalog(pages=1, silent=False, force_refresh=False, fresh_meta=False, budget=True, tier='all'):
    """
    Precarga las listas TMDb para que widgets/menús abran rápido tras iniciar Kodi.

    v1.0.54 — dos niveles de refresco:
      - LIGERO (fresh_meta=False, el arranque típico): re-lee las listas y
        actualiza los campos visuales de la parrilla (póster/fanart/rating/
        votos/plot/fecha) directamente desde la respuesta de lista para los
        títulos ya cacheados (tmdb_list_visual_refresh). Solo los títulos
        nuevos o caducados piden su detalle completo. Coste: ~9 peticiones.
      - COMPLETO (fresh_meta=True): invalida en metacache las metas de página 1
        y re-pide el detalle entero por título (reparto, logos, posters_all...).
        Corre como mucho cada meta_hours (sello S_LASTMETA, se renueva aquí al
        terminar bien) o al pulsar el botón manual de Tools.

    Cambios v1.0.38 (rendimiento de arranque):
      - pages=1 por defecto: solo se precarga lo que el usuario ve primero
        (~180 títulos en vez de ~540). Las páginas 2+ se cargan bajo demanda.
      - POOL GLOBAL ACOTADO: en vez de procesar las 9 listas en secuencia (cada
        una con su propia tanda de ~20 hilos de meta), todas las listas se lanzan
        en paralelo bajo un único semáforo que limita el total de peticiones
        concurrentes (PRECACHE_MAX_WORKERS). Mismo coste de red, reparto óptimo,
        arranque más corto.
      - fresh_meta=True (FRESCURA REAL): antes de enriquecer, invalida en metacache
        SOLO las metas de los títulos de página 1. Así el arranque trae pósters y
        metadatos realmente nuevos de lo visible, sin destruir el resto del
        catálogo cacheado (que sigue su TTL de 30 días).

    `force_refresh` se mantiene: invalida la entrada cacheada de las LISTAS (no de
    las metas por título). Útil para detectar títulos que entran/salen de la lista.

    Returns True/False.
    """
    try:
        # Pre-calienta el dict de settings (window property) UNA vez antes de
        # lanzar los hilos. Así todos los workers leen settings desde el dict ya
        # poblado en vez de provocar parseos concurrentes del settings.xml. Junto
        # con el fix de control.setting() (re-consulta a xbmcaddon limitada a
        # credenciales), esto elimina la tormenta de ~1000 parseos que añadía ~8s.
        try:
            control.make_settings_dict()
        except: pass

        # luc_kodi implementa tmdb_list()/tmdb_list_ids() en Movies/TVshows.
        from resources.lib.indexers.tmdb import Movies as TMDbMovies, TVshows as TMDbTVshows

        movies_idx = TMDbMovies()
        tv_idx = TMDbTVshows()

        movie_links, tv_links = _get_tmdb_links(tier)
        trakt_jobs = _priority_trakt_jobs() if tier in ('fast', 'all') else []
        if not (movie_links or tv_links or trakt_jobs):
            if not silent:
                _notify(control.lang(400704))  # "TMDB Catalog: No TMDB links found."
            return False

        log_utils.log('[luc_kodi] TMDB Catalog: precache start (tier=%s, pages=%s, force=%s, fresh_meta=%s, listas=%s+%s tmdb / %s trakt)' % (tier, pages, force_refresh, fresh_meta, len(movie_links), len(tv_links), len(trakt_jobs)), level=LOGINFO)

        # Trabajos (idx, url_con_pagina, nº_pagina) de las 9 listas × N páginas.
        jobs = []
        for url in movie_links:
            for p in range(1, int(pages) + 1):
                jobs.append((movies_idx, _page_url(url, p), p))
        for url in tv_links:
            for p in range(1, int(pages) + 1):
                jobs.append((tv_idx, _page_url(url, p), p))

        if force_refresh:
            # Invalida la entrada cacheada de cada LISTA/página (clave de tmdb_list).
            try:
                from resources.lib.database import cache
                for idx, page_url, _p in jobs:
                    try: cache.remove(idx.get_request, page_url % idx.API_key)
                    except: pass
            except: log_utils.error()

        # ── FRESCURA REAL: invalidar metacache solo de los títulos de página 1 ──
        # Se hace ANTES de enriquecer, leyendo los ids con tmdb_list_ids (consulta
        # barata que reutiliza la caché de lista). Tras esto, metacache.fetch verá
        # esos títulos como ausentes y los re-descargará con datos frescos; el
        # resto del catálogo no se toca.
        if fresh_meta:
            try:
                from resources.lib.database import metacache
                fresh_ids = []
                for idx, page_url, p in jobs:
                    if p != 1:  # solo refrescamos lo visible (página 1)
                        continue
                    try: fresh_ids.extend(idx.tmdb_list_ids(page_url))
                    except: pass
                fresh_ids = list(dict.fromkeys([i for i in fresh_ids if i]))  # dedup, preserva orden
                if fresh_ids:
                    removed = metacache.remove_by_ids(fresh_ids)
                    log_utils.log('[luc_kodi] TMDB Catalog: fresh_meta invalidó %s metas (página 1)' % removed, level=LOGINFO)
            except: log_utils.error()

        # ── REFRESCO VISUAL LIGERO (v1.0.54, solo cuando NO toca fresh_meta) ──
        # La respuesta de LISTA de TMDb ya trae poster_path, backdrop_path,
        # vote_average, vote_count, overview y fecha: todo lo que la parrilla
        # necesita ver fresco. Para los títulos que YA están en metacache se
        # actualizan esos campos directamente desde la lista — CERO peticiones
        # de detalle por título. El detalle completo (reparto, logos,
        # posters_all, certificaciones, tráilers) lo renueva el ciclo fresh_meta
        # cada N horas (meta_hours), no cada arranque. Con esto el arranque
        # típico queda en las 9 peticiones de lista (~1-2s) en vez de ~180
        # peticiones de detalle (~6-7s).
        if not fresh_meta:
            def _visual(idx, page_url, p):
                if p != 1: return  # solo lo visible
                try:
                    n = idx.tmdb_list_visual_refresh(page_url)
                    if n: log_utils.log('[luc_kodi] TMDB Catalog: visual refresh %s metas <- %s' % (n, page_url.split('?')[0]), level=LOGINFO)
                except:
                    log_utils.error()
            vthreads = [Thread(target=_visual, args=(idx, page_url, _p)) for idx, page_url, _p in jobs]
            [t.start() for t in vthreads]
            [t.join() for t in vthreads]

        # ── Enriquecimiento con POOL GLOBAL ACOTADO ──
        # Las 9 listas corren todas en paralelo (son pocas), pero el TOPE real de
        # peticiones de red lo pone un semáforo GLOBAL compartido que acota las
        # metas individuales de TODAS las listas a la vez. Sin esto, 9 listas ×
        # ~20 títulos lanzarían ~180 peticiones HTTP simultáneas a TMDb en el
        # arranque (saturación de sockets / throttling / competencia con Kodi).
        # Con el semáforo, nunca hay más de PRECACHE_MAX_WORKERS metas en vuelo.
        meta_sem = Semaphore(PRECACHE_MAX_WORKERS)

        # Presupuesto de tiempo (v1.0.80): las listas se piden siempre (son
        # baratas y es lo que hace que la parrilla exista), pero el enriquecido
        # título a título se corta al agotarse. Lo que quede sin ficha se
        # completa en la siguiente pasada o al abrir la sección.
        if budget is True: deadline = time.time() + _budget_seconds()
        elif budget in (False, None): deadline = None
        else: deadline = time.time() + int(budget)

        def _run(idx, page_url):
            try: idx.tmdb_list(page_url, meta_sem=meta_sem, deadline=deadline)
            except:
                from resources.lib.modules import log_utils as _lu
                _lu.error()

        threads = [Thread(target=_run, args=(idx, page_url)) for idx, page_url, _p in jobs]
        # Trending y Popular van por Trakt y entran en la MISMA tanda, bajo el
        # mismo semaforo y el mismo deadline que las listas de TMDb.
        threads += [Thread(target=_precache_trakt_list, args=(mt, name, meta_sem, deadline)) for mt, name in trakt_jobs]
        [t.start() for t in threads]
        [t.join() for t in threads]

        log_utils.log('[luc_kodi] TMDB Catalog: precache finished (tier=%s, %s listas)' % (tier, len(jobs) + len(trakt_jobs)), level=LOGINFO)

        # El sello del refresco completo se pone AQUÍ (única fuente de verdad):
        # cualquier llamada con fresh_meta=True que termine bien lo renueva,
        # venga del servicio de arranque, del tick programado o del botón
        # manual "Update Catalog" de Tools.
        if fresh_meta:
            _set_last_meta(_now())

        if not silent:
            _notify(control.lang(400702))  # "TMDB Catalog: Completed."
        return True
    except Exception:
        log_utils.error()
        if not silent:
            _notify(control.lang(400703))  # "TMDB Catalog: Error (see kodi.log)."
        return False

def _rotation_targets():
    """URLs del NIVEL 2: todas las plataformas y cadenas curadas MENOS las que ya
    van en el ciclo rápido. Devuelve [(mediatype, url)] en orden estable, que es
    lo que permite que el puntero de rotación signifique siempre lo mismo."""
    targets = []
    try:
        from resources.lib.menus.movies import Movies as MoviesMenu
        from resources.lib.menus.tvshows import TVshows as TVshowsMenu
        from resources.lib.indexers.tmdb import Movies as TMDbMovies, TVshows as TMDbTVshows

        fast_streaming = set(pid for pid, _r in _selected_streaming())
        m = MoviesMenu()
        for _name, pid, region in TMDbMovies().watchproviders_curated():
            if pid in fast_streaming: continue
            url = m.tmdb_watchproviders_link % ('%s', pid)
            if region and region != 'US':
                url = url.replace('region=US&watch_region=US', 'region=%s&watch_region=%s' % (region, region))
            targets.append(('movie', url))

        fast_networks = set(_selected_networks())
        t = TVshowsMenu()
        for _name, nid, _logo in TMDbTVshows().get_networks():
            if str(nid) in fast_networks: continue
            targets.append(('tvshow', t.tmdb_networks_link % ('%s', nid)))
    except:
        log_utils.error()
    return targets


def refresh_rotating_catalogs():
    """v1.0.80 — NIVEL 2. Renueva por turnos el catálogo de las plataformas y
    cadenas que no están en el ciclo rápido.

    Solo toca las que llevan más de `rotate_days` (7 por defecto) sin renovarse,
    mirando la fecha de la entrada cacheada de la lista — no hay peticiones de
    sondeo: si está fresca se salta sin tocar la red. Al agotar el presupuesto de
    tiempo se corta y guarda el punto donde iba, así la siguiente pasada sigue por
    ahí en vez de volver a empezar.

    Devuelve (renovadas, pendientes_en_esta_vuelta).
    """
    try:
        from resources.lib.database import cache
        from resources.lib.indexers.tmdb import Movies as TMDbMovies, TVshows as TMDbTVshows

        targets = _rotation_targets()
        if not targets: return 0, 0

        start = time.time()
        deadline = start + _budget_seconds()
        max_age = _rotate_days() * 86400
        try: pointer = int(control.setting(S_ROTATE_INDEX) or 0) % len(targets)
        except: pointer = 0

        movies_idx = TMDbMovies()
        tv_idx = TMDbTVshows()
        sem = Semaphore(PRECACHE_MAX_WORKERS)
        done = 0 ; checked = 0 ; stale_left = 0

        for step in range(len(targets)):
            i = (pointer + step) % len(targets)
            mediatype, url = targets[i]
            idx = tv_idx if mediatype == 'tvshow' else movies_idx
            checked = step + 1
            try:
                cached_at = cache.timeout(idx.get_request, url % idx.API_key)
            except:
                cached_at = 0
            if cached_at and (time.time() - cached_at) < max_age:
                continue  # todavía fresca: ni se mira
            if time.time() >= deadline or control.monitor.abortRequested() or xbmc.Player().isPlayingVideo():
                stale_left = 1  # queda trabajo por hacer en esta vuelta
                break
            try:
                idx.tmdb_list(url, meta_sem=sem, deadline=deadline)
                done += 1
            except:
                log_utils.error()

        if control.monitor.abortRequested():
            return done, stale_left  # Kodi is stopping or updating the add-on: its settings may already be unloaded
        control.setSetting(S_ROTATE_INDEX, str((pointer + checked) % len(targets)))
        if done:
            log_utils.log('[luc_kodi] TMDB Catalog: rotacion renovo %s catalogos en %.1fs' % (done, time.time() - start), level=LOGINFO)
        return done, stale_left
    except:
        log_utils.error()
        return 0, 0


def upgrade_light_meta(batch=LIGHT_UPGRADE_BATCH):
    """v1.0.80 — SEGUNDO PLANO del modo ligero.

    Las listas se enriquecen en primer plano sin el bloque `images` de TMDb (que
    es el 90% del peso de la respuesta): la parrilla aparece enseguida con
    póster, fanart, rating y sinopsis, pero sin clearlogo ni pósters alternativos.
    Esta pasada recupera justo eso, unos pocos títulos cada vez, sin que el
    usuario espere por ello.

    Devuelve (actualizados, pendientes_restantes).
    """
    try:
        from resources.lib.database import metacache
        rows, pending = metacache.fetch_light(batch)
        if not rows:
            return 0, 0
        from resources.lib.indexers.tmdb import Movies as TMDbMovies, TVshows as TMDbTVshows
        # Una sola instancia de cada indexador para todos los hilos:
        # refresh_meta_full solo lee atributos de self y escribe en metacache,
        # asi que se puede compartir. Crear una por titulo costaria un __init__
        # completo (lectura de ajustes + is_4k_display) por ficha.
        movies_idx = TMDbMovies()
        tv_idx = TMDbTVshows() if any(r[1] == 'tvshow' for r in rows) else None
        done = [0]
        stop = []
        lock = Lock()
        sem = Semaphore(LIGHT_UPGRADE_WORKERS)

        def _one(tmdb, mediatype, lang, user):
            # Cuatro en vuelo como mucho, y a la primera senal de reproduccion o
            # de apagado se corta la pasada entera: esto corre mientras el
            # usuario usa Kodi, asi que prima no estorbar.
            if stop: return
            if control.monitor.abortRequested() or xbmc.Player().isPlayingVideo():
                stop.append(1) ; return
            sem.acquire()
            try:
                if stop: return
                idx = tv_idx if (mediatype == 'tvshow' and tv_idx is not None) else movies_idx
                if idx.refresh_meta_full(tmdb, lang, user):
                    with lock: done[0] += 1
            except:
                log_utils.error()
            finally:
                sem.release()

        threads = [Thread(target=_one, args=r) for r in rows]
        [t.start() for t in threads]
        [t.join() for t in threads]
        done = done[0]
        remaining = max(0, pending - done)
        if done:
            log_utils.log('[luc_kodi] TMDB Catalog: %s metas ligeras completadas (%s pendientes)' % (done, remaining), level=LOGINFO)
        return done, remaining
    except:
        log_utils.error()
        return 0, 0


class CatalogService:
    """
    Background thread: update on startup + every X hours.
    """
    def run(self):
        log_utils.log('[ plugin.video.luc_kodi ]  CatalogService Starting...', level=LOGINFO)

        monitor = control.monitor

        # Pequeño retardo tras el arranque de Kodi para no competir con el resto
        # de servicios (skin, otros addons). v1.0.38: bajado de 10s a 3s — el
        # precache ya es ligero (solo página 1 + pool acotado), así que no
        # necesita esperar tanto. El semáforo de metas evita saturar la red.
        monitor.waitForAbort(3)

        did_startup = False  # guard por sesión: el refresco de arranque corre UNA vez por inicio de Kodi
        last_rotation = time.time()  # la pasada de arranque ya cuenta como la primera vuelta

        while not monitor.abortRequested():
            try:
                # Skip iteration entirely if user is actively watching — avoid
                # competing with the stream for bandwidth, disk I/O and CPU.
                if xbmc.Player().isPlayingVideo():
                    # v1.0.55: si el refresco de ARRANQUE aun no ha corrido, no
                    # se pospone 5 minutos enteros — se reintenta en 15s.
                    # Motivo (visto en kodi.log): muchos skins reproducen un
                    # video de intro al iniciar Kodi (p.ej. intro-omega.mp4,
                    # ~10s). La primera iteracion cae dentro de ese intro, el
                    # guard la salta y el refresco de catalogo (y su
                    # notificacion) se iba a los 5 minutos EN CADA ARRANQUE:
                    # para entonces el usuario ya lleva rato en el menu con los
                    # widgets sin refrescar. El guard sigue intacto para la
                    # reproduccion real: mientras se ve algo, no se compite por
                    # ancho de banda; solo cambia cada cuanto se vuelve a mirar.
                    monitor.waitForAbort(15 if not did_startup else CHECK_EVERY_SECONDS)
                    continue

                enabled = _get_bool(S_ENABLED, default=False)
                if enabled:
                    on_start = _get_bool(S_ON_START, default=True)
                    notify = _get_bool(S_NOTIFY, default=True)
                    # v1.0.54 FIX: interval_hours es un enum y Kodi devuelve el
                    # ÍNDICE (0-4), no las horas. Antes se usaba el índice como
                    # horas ("2" -> 2h en vez de las 6h de la etiqueta).
                    interval = _enum_hours(S_INTERVAL, _INTERVAL_HOURS, 6)

                    # On startup (v1.0.54): en CADA inicio de Kodi se hace el
                    # ciclo LIGERO — force_refresh=True re-lee las 9 listas
                    # (títulos que entran/salen) y el refresco visual actualiza
                    # póster/fanart/rating de lo cacheado desde la propia lista.
                    # El ciclo COMPLETO (fresh_meta: invalidar metacache y
                    # re-pedir ~180 detalles a TMDb) solo corre si han pasado
                    # meta_hours desde el último completo: era lo que costaba
                    # 6-7s en cada arranque. El guard de sesión evita repetirlo
                    # dentro del mismo arranque.
                    if on_start and not did_startup:
                        heavy = _meta_refresh_due()
                        # ── NIVEL 1 ── Trending y Popular (Trakt) de Movies y TV
                        # shows, TMDb Now Playing y las plataformas/cadenas
                        # marcadas. Sin presupuesto de fondo: solo un tope duro
                        # de seguridad para que un TMDb caido no deje la pasada
                        # colgada. Se refresca la interfaz nada mas terminar,
                        # que es lo que hace que el usuario lo vea "al instante".
                        precache_tmdb_catalog(pages=1, silent=not notify, force_refresh=True,
                                              fresh_meta=heavy, tier='fast',
                                              budget=_budget_seconds() * _PRIORITY_SAFETY_FACTOR)
                        try: control.trigger_widget_refresh()
                        except: pass
                        # ── NIVEL 2 ── el resto de listas del menu (Top Rated,
                        # Upcoming, Box Office, Airing Today, On The Air). En
                        # CADA arranque y siempre acotado por el presupuesto.
                        precache_tmdb_catalog(pages=1, silent=True, force_refresh=True,
                                              fresh_meta=False, tier='slow', budget=True)
                        # ── NIVEL 3 ── rotacion de las plataformas y cadenas no
                        # marcadas: solo se tocan las que llevan mas de
                        # rotate_days (7 por defecto) sin renovarse, y la pasada
                        # se corta al agotar el presupuesto. Corre en todo
                        # arranque, no depende del interruptor de sesion.
                        refresh_rotating_catalogs()
                        _set_last_run(_now())
                        did_startup = True
                        try:
                            control.trigger_widget_refresh()
                        except:
                            pass

                    # Scheduled run: refresco ligero de página 1. Si en sesiones
                    # largas vence meta_hours, el ciclo completo corre aquí (con
                    # force_refresh para que las listas también sean frescas);
                    # si no, solo se re-evalúan listas para captar novedades.
                    elif _is_due(interval):
                        heavy = _meta_refresh_due()
                        precache_tmdb_catalog(pages=1, silent=not notify, force_refresh=heavy,
                                              fresh_meta=heavy, tier='fast',
                                              budget=_budget_seconds() * _PRIORITY_SAFETY_FACTOR)
                        precache_tmdb_catalog(pages=1, silent=True, force_refresh=heavy,
                                              fresh_meta=False, tier='slow', budget=True)
                        _set_last_run(_now())
                        try:
                            control.trigger_widget_refresh()
                        except:
                            pass
                # ── v1.0.80: completar metas ligeras en segundo plano ──
                # Independiente del auto-update: si el modo ligero dejó fichas a
                # medias (clearlogo/pósters alternativos), se completan aunque el
                # precache esté desactivado. Mientras queden pendientes la pasada
                # se repite cada 30s en vez de cada 5 min, para que una lista
                # recién abierta termine de rellenarse en poco rato.
                upgraded, remaining = upgrade_light_meta()
                if upgraded and not remaining:
                    try: control.trigger_widget_refresh()
                    except: pass

                # ── v1.0.81: rotación del resto de plataformas/cadenas ──
                # Tiene cadencia PROPIA. Hasta la 1.0.80 se exigía que no
                # quedase arte pendiente, y con una cola que no se vaciaba
                # (713 pendientes en un log real) eso era no correr nunca.
                if _get_bool(S_ROTATE, default=True) and (time.time() - last_rotation) >= ROTATION_EVERY_SECONDS:
                    refresh_rotating_catalogs()
                    last_rotation = time.time()
                # Mientras quede cola y la pasada esté completando algo, se
                # vuelve en 10s en vez de en 5 min. Si NO completó nada (TMDb
                # caído, títulos que devuelven 404) se vuelve al ritmo normal
                # en vez de reintentar en bucle.
                if remaining and upgraded:
                    monitor.waitForAbort(LIGHT_UPGRADE_EVERY_SECONDS)
                    continue
            except:
                log_utils.error()

            # check again every 5 minutes
            monitor.waitForAbort(CHECK_EVERY_SECONDS)

        log_utils.log('[ plugin.video.luc_kodi ]  CatalogService Stopped', level=LOGINFO)
