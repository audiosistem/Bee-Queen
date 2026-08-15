# -*- coding: utf-8 -*-
"""
luc_kodi - TMDB Catalog Precache / Auto Update 

This service prefetches key TMDB endpoints into luc_kodi cache DB so widgets/menus load fast.
"""

from __future__ import absolute_import

import re
import time
from threading import Thread, Semaphore

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

def _get_tmdb_links():
    """
    Reads the same TMDB links used by menus (movies.py / tvshows.py).
    Those links already contain api_key=%s placeholder and page=1.
    """
    movie_links = []
    tv_links = []
    try:
        from resources.lib.menus.movies import Movies as MoviesMenu
        m = MoviesMenu()
        movie_links = [
            getattr(m, 'tmdb_popular_link', ''),
            getattr(m, 'tmdb_toprated_link', ''),
            getattr(m, 'tmdb_nowplaying_link', ''),
            getattr(m, 'tmdb_boxoffice_link', ''),
            getattr(m, 'tmdb_upcoming_link', ''),
        ]
        movie_links = [i for i in movie_links if i]
    except:
        log_utils.error()

    try:
        # luc_kodi uses class name `TVshows` (not `TVShows`)
        from resources.lib.menus.tvshows import TVshows as TVShowsMenu
        t = TVShowsMenu()
        tv_links = [
            getattr(t, 'tmdb_popular_link', ''),
            getattr(t, 'tmdb_toprated_link', ''),
            getattr(t, 'tmdb_airingtoday_link', ''),
            # tvshows.py uses tmdb_ontheair_link (not tmdb_ontv_link)
            getattr(t, 'tmdb_ontheair_link', ''),
        ]
        tv_links = [i for i in tv_links if i]
    except Exception:
        # TV precache is optional.
        pass

    return movie_links, tv_links

def precache_tmdb_catalog(pages=1, silent=False, force_refresh=False, fresh_meta=False):
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

        movie_links, tv_links = _get_tmdb_links()
        if not (movie_links or tv_links):
            if not silent:
                _notify(control.lang(400704))  # "TMDB Catalog: No TMDB links found."
            return False

        log_utils.log('[luc_kodi] TMDB Catalog: precache start (pages=%s, force=%s, fresh_meta=%s)' % (pages, force_refresh, fresh_meta), level=LOGINFO)

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

        def _run(idx, page_url):
            try: idx.tmdb_list(page_url, meta_sem=meta_sem)
            except:
                from resources.lib.modules import log_utils as _lu
                _lu.error()

        threads = [Thread(target=_run, args=(idx, page_url)) for idx, page_url, _p in jobs]
        [t.start() for t in threads]
        [t.join() for t in threads]

        log_utils.log('[luc_kodi] TMDB Catalog: precache finished (%s listas)' % len(jobs), level=LOGINFO)

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
                        precache_tmdb_catalog(pages=1, silent=not notify, force_refresh=True, fresh_meta=heavy)
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
                        precache_tmdb_catalog(pages=1, silent=not notify, force_refresh=heavy, fresh_meta=heavy)
                        _set_last_run(_now())
                        try:
                            control.trigger_widget_refresh()
                        except:
                            pass
            except:
                log_utils.error()

            # check again every 5 minutes
            monitor.waitForAbort(CHECK_EVERY_SECONDS)

        log_utils.log('[ plugin.video.luc_kodi ]  CatalogService Stopped', level=LOGINFO)
