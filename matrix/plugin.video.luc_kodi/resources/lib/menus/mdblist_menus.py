# -*- coding: utf-8 -*-
"""
    luc_kodi Add-on
    MDBList menus — Continue Watching, watchlist, user lists, top/public lists.
"""

from resources.lib.modules import control
from resources.lib.modules import log_utils
from resources.lib.database import cache

getSetting  = control.setting
getLS       = control.lang


# ---------------------------------------------------------------------------
# Resume-point helper
# ---------------------------------------------------------------------------

def _seed_bookmarks(items: list):
    """
    Write MDBList progress into both traktsync.db AND bookmarks.db so that
    Bookmarks().get() returns the correct resume point regardless of whether
    the user has Trakt scrobble enabled or is using local-only bookmarks.
    """
    try:
        from sqlite3 import dbapi2 as _db
        from hashlib import md5 as _md5
        from resources.lib.modules.control import (
            traktSyncFile, bookmarksFile, dataPath, makeFile, existsPath)
        if not existsPath(dataPath):
            makeFile(dataPath)

        # ---- Path A: traktsync.db (Trakt scrobble + resume.source=1) --------
        try:
            conn = _db.connect(traktSyncFile, timeout=10)
            cur  = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS bookmarks
                (tvshowtitle TEXT, title TEXT, resume_id TEXT,
                 imdb TEXT, tmdb TEXT, tvdb TEXT, season TEXT, episode TEXT,
                 genre TEXT, mpaa TEXT, studio TEXT, duration TEXT,
                 percent_played TEXT, paused_at TEXT,
                 UNIQUE(resume_id, imdb, tmdb, tvdb, season, episode))""")
            for i in items:
                try:
                    pct = str(i.get('progress', '0') or '0')
                    if float(pct) <= 0:
                        continue
                    dur_sec = i.get('duration', 0) or 0
                    dur_min = str(int(dur_sec) // 60) if dur_sec else ''
                    cur.execute(
                        """INSERT OR REPLACE INTO bookmarks VALUES
                           (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (i.get('tvshowtitle', ''), i.get('title', ''),
                         i.get('imdb') or i.get('tmdb') or '',
                         i.get('imdb', ''), i.get('tmdb', ''), i.get('tvdb', ''),
                         str(i.get('season', '')), str(i.get('episode', '')),
                         'NA', 'NR', '', dur_min, pct, i.get('paused_at', ''),),
                    )
                except Exception:
                    pass
            conn.commit()
            conn.close()
        except Exception as exc:
            log_utils.log('_seed_bookmarks traktsync: %s' % exc, level=log_utils.LOGWARNING)

        # ---- Path B: bookmarks.db (local, no Trakt scrobble) ----------------
        try:
            conn = _db.connect(bookmarksFile, timeout=10)
            cur  = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS bookmark
                (idFile TEXT, timeInSeconds TEXT, Name TEXT, year TEXT,
                 UNIQUE(idFile))""")
            for i in items:
                try:
                    pct     = float(i.get('progress', 0) or 0)
                    dur_sec = float(i.get('duration', 0) or 0)
                    if pct <= 0 or dur_sec <= 0:
                        continue
                    time_sec = str((pct / 100) * dur_sec)
                    year     = str(i.get('year', '0') or '0')
                    season   = i.get('season', '')
                    episode  = i.get('episode', '')
                    if season and episode:
                        name = '%s S%02dE%02d' % (
                            i.get('tvshowtitle') or i.get('title', ''),
                            int(season), int(episode))
                    else:
                        name = '%s (%s)' % (i.get('title', ''), year)
                    h = _md5()
                    for ch in name:
                        try:    h.update(ch.encode('utf-8'))
                        except: h.update(str(ch))
                    for ch in year:
                        try:    h.update(ch.encode('utf-8'))
                        except: h.update(str(ch))
                    cur.execute(
                        "INSERT OR REPLACE INTO bookmark VALUES (?,?,?,?)",
                        (h.hexdigest(), time_sec, name, year),
                    )
                except Exception:
                    pass
            conn.commit()
            conn.close()
        except Exception as exc:
            log_utils.log('_seed_bookmarks local: %s' % exc, level=log_utils.LOGWARNING)

    except Exception as exc:
        log_utils.log('MDBList _seed_bookmarks failed: %s' % exc, level=log_utils.LOGWARNING)

def _movie_item(raw):
    return {
        'title':         raw.get('title', ''),
        'originaltitle': raw.get('title', ''),
        'year':          raw.get('year', ''),
        'imdb':          raw.get('imdb', ''),
        'tmdb':          raw.get('tmdb', ''),
        'tvdb':          '',
        'next':          '',
    }


def _show_item(raw):
    return {
        'title':         raw.get('title', ''),
        'originaltitle': raw.get('title', ''),
        'tvshowtitle':   raw.get('title', ''),
        'year':          raw.get('year', ''),
        'imdb':          raw.get('imdb', ''),
        'tmdb':          raw.get('tmdb', ''),
        'tvdb':          raw.get('tvdb', ''),
        'next':          '',
    }


def _build_list_directory(lists, action):
    from sys import argv
    highlight_color = control.getHighlightColor()
    art_path  = control.artPath()
    icon_path = control.joinPath(art_path, 'mdblist.png') if art_path else 'DefaultVideoPlaylists.png'
    for lst in lists:
        try:
            list_id   = lst.get('id', '')
            list_name = lst.get('name', '?')
            owner     = lst.get('user_name', '')
            n_items   = lst.get('items', 0)
            dynamic   = lst.get('dynamic', False)
            label = '[I]%s[/I]' % list_name if dynamic else list_name
            if owner:
                label = '%s — [COLOR %s]%s[/COLOR]' % (label, highlight_color, owner)
            url = 'plugin://plugin.video.luc_kodi/?action=%s&list_id=%s' % (action, list_id)
            item = control.item(label=label, offscreen=True)
            item.setArt({'icon': icon_path, 'thumb': icon_path,
                         'poster': icon_path, 'fanart': control.addonFanart()})
            plot = '%s  •  %d items%s' % (list_name, n_items, '  •  auto-updated' if dynamic else '')
            try:
                item.getVideoInfoTag().setPlot(plot)
            except Exception:
                item.setInfo('video', {'plot': plot})
            control.addItem(handle=int(argv[1]), url=url, listitem=item, isFolder=True)
        except Exception:
            log_utils.error()
    control.content(int(argv[1]), '')
    control.directory(int(argv[1]), cacheToDisc=True)


# ============================================================
# CONTINUE WATCHING — MOVIES
# ============================================================
class MDBListContinueMovies:
    def __init__(self):
        from resources.lib.menus.movies import Movies
        self._movies = Movies()

    def get(self):
        try:
            from resources.lib.modules.mdblist import getContinueMovies
            raw = getContinueMovies()
            if not raw:
                control.hide()
                control.notification(title='MDBList', message=getLS(40230))
                return
            self._movies.list = raw
            self._movies.worker()
            self._movies.list = sorted(
                self._movies.list, key=lambda k: k.get('paused_at', ''), reverse=True)
            # Seed resume times via window properties so player.onAVStarted
            # can seek reliably regardless of Bookmarks() dialog / year issues
            for item in self._movies.list:
                try:
                    pct = float(item.get('progress', 0) or 0)
                    dur = float(item.get('duration', 0) or 0)
                    if pct > 0 and dur > 0:
                        resume_sec = str((pct / 100) * dur)
                        _key = 'mdblist.resume.%s.0.0' % (item.get('imdb') or item.get('tmdb') or '')
                        control.homeWindow.setProperty(_key, resume_sec)
                except Exception:
                    pass
            # Also seed traktsync.db + bookmarks.db (Bookmarks().get() fallback)
            _seed_bookmarks(self._movies.list)
            self._movies.movieDirectory(self._movies.list, unfinished=True, next=False)
        except Exception:
            log_utils.error()
            control.hide()
            control.notification(title='MDBList', message=32049)


# ============================================================
# CONTINUE WATCHING — EPISODES
# ============================================================
class MDBListContinueEpisodes:
    """
    Uses trakt_episodes_list(items=raw) for TMDB enrichment — exactly
    the same path as Trakt's own unfinished-episodes list.
    """
    def __init__(self):
        from resources.lib.menus.episodes import Episodes
        self._ep = Episodes()

    def get(self):
        try:
            from resources.lib.modules.mdblist import getContinueEpisodes
            raw = getContinueEpisodes()
            if not raw:
                control.hide()
                control.notification(title='MDBList', message=getLS(40230))
                return

            # Enrich with TMDB metadata via the same path Trakt uses
            self._ep.list = []
            enriched = cache.get(
                self._ep.trakt_episodes_list,
                0,
                self._ep.traktunfinished_link,
                self._ep.trakt_user,
                self._ep.lang,
                raw,        # pre-loaded items — bypasses Trakt API call
            )
            self._ep.list = enriched or raw   # fallback to raw if enrichment fails

            self._ep.list = sorted(
                self._ep.list, key=lambda k: k.get('paused_at', ''), reverse=True)
            _seed_bookmarks(self._ep.list)
            # Seed resume window properties for reliable seek in player.onAVStarted
            for item in self._ep.list:
                try:
                    pct = float(item.get('progress', 0) or 0)
                    dur = float(item.get('duration', 0) or 0)
                    if pct > 0 and dur > 0:
                        resume_sec = str((pct / 100) * dur)
                        _key = 'mdblist.resume.%s.%s.%s' % (
                            item.get('imdb') or item.get('tmdb') or '',
                            item.get('season', '0') or '0',
                            item.get('episode', '0') or '0',
                        )
                        control.homeWindow.setProperty(_key, resume_sec)
                except Exception:
                    pass
            self._ep.episodeDirectory(self._ep.list, unfinished=True, next=False)
        except Exception:
            log_utils.error()
            control.hide()
            control.notification(title='MDBList', message=32049)


# ============================================================
# CALENDAR — upcoming/recent episodes + movie releases
# (equivalente al Calendar de mdblist.com, construido con /upnext
#  y Media Info Batch porque la API no expone /calendar)
# ============================================================
class MDBListCalendar:
    def episodes(self, mode='upcoming'):
        try:
            from resources.lib.menus.episodes import Episodes
            from resources.lib.modules.mdblist import getCalendarEpisodes
            ep = Episodes()
            raw = cache.get(getCalendarEpisodes, 1, mode)
            # REGLA reuselanguageinvoker: aunque la lista venga vacía hay que
            # cargar un directorio vacío (episodeDirectory ya notifica "Nothing
            # Found" y llama a endOfDirectory). Un return temprano deja la
            # CGUIMediaWindow en "updating in progress" y al retroceder Kodi
            # se cierra en nativo (visto en kodi.log de la tablet, ago-2026).
            if raw:
                enriched = cache.get(
                    ep.trakt_episodes_list, 0,
                    ep.traktunfinished_link, ep.trakt_user, ep.lang,
                    raw,  # items precargados — no llama a Trakt
                )
                ep.list = enriched or raw
                # los hilos del enriquecimiento pierden el orden: reordenar por fecha
                reverse = (mode != 'upcoming')
                ep.list = sorted(ep.list, key=lambda k: k.get('sort_date', ''), reverse=reverse)
            else:
                ep.list = []
            ep.episodeDirectory(ep.list, unfinished=False, next=False)
        except Exception:
            log_utils.error()
            self._empty_directory()

    def movies(self):
        try:
            from resources.lib.menus.movies import Movies
            from resources.lib.modules.mdblist import getCalendarMovies
            mv = Movies()
            raw = cache.get(getCalendarMovies, 6)
            # misma regla que en episodes(): directorio vacío, nunca return temprano
            if raw:
                mv.list = raw
                mv.worker()  # enriquecimiento TMDB (metadatos + arte)
                # worker() puede reordenar/rellenar: reimponer orden por fecha de estreno
                mv.list = sorted(mv.list, key=lambda k: k.get('mdb_calendar_date', ''))
            else:
                mv.list = []
            mv.movieDirectory(mv.list, next=False)
        except Exception:
            log_utils.error()
            self._empty_directory()

    def _empty_directory(self):
        # Red de seguridad si el propio builder revienta: cerrar SIEMPRE el
        # directorio para no dejar la ventana en "updating in progress".
        try:
            from sys import argv
            control.hide()
            control.notification(title='MDBList', message=32049)
            control.content(int(argv[1]), '')
            control.directory(int(argv[1]), cacheToDisc=False)
        except Exception:
            pass


# ============================================================
# USER WATCHLIST & LISTS — MOVIES
# ============================================================
class MDBListMovies:
    def __init__(self):
        from resources.lib.menus.movies import Movies
        self._movies = Movies()

    def watchlist(self):
        try:
            from resources.lib.modules.mdblist import getWatchlistMovies
            raw = cache.get(getWatchlistMovies, 30)
            items = [_movie_item(r) for r in (raw or [])]
            self._movies.list = items
            self._movies.worker()
            self._movies.movieDirectory(self._movies.list)
        except Exception:
            log_utils.error()
            control.hide(); control.notification(title='MDBList', message=32049)

    def listItems(self, list_id):
        try:
            from resources.lib.modules.mdblist import getListItems
            movies, _ = cache.get(getListItems, 60, list_id, 'movie')
            self._movies.list = [_movie_item(r) for r in (movies or [])]
            self._movies.worker()
            self._movies.movieDirectory(self._movies.list)
        except Exception:
            log_utils.error()
            control.hide(); control.notification(title='MDBList', message=32049)

    def userLists(self):
        try:
            from resources.lib.modules.mdblist import getUserLists
            _build_list_directory(cache.get(getUserLists, 60) or [], 'mdblist_movieListItems')
        except Exception:
            log_utils.error()

    def topLists(self):
        try:
            from resources.lib.modules.mdblist import getTopLists
            _build_list_directory(cache.get(getTopLists, 240) or [], 'mdblist_movieListItems')
        except Exception:
            log_utils.error()

    def searchLists(self):
        try:
            from resources.lib.modules.mdblist import searchLists
            k = control.keyboard('', getLS(32010)); k.doModal()
            q = k.getText() if k.isConfirmed() else None
            if not q: return control.closeAll()
            _build_list_directory(searchLists(q) or [], 'mdblist_movieListItems')
        except Exception:
            log_utils.error()


# ============================================================
# USER WATCHLIST & LISTS — TV SHOWS
# ============================================================
class MDBListShows:
    def __init__(self):
        from resources.lib.menus.tvshows import TVshows
        self._tv = TVshows()

    def watchlist(self):
        try:
            from resources.lib.modules.mdblist import getWatchlistShows
            raw = cache.get(getWatchlistShows, 30)
            self._tv.list = [_show_item(r) for r in (raw or [])]
            self._tv.worker()
            self._tv.tvshowDirectory(self._tv.list)
        except Exception:
            log_utils.error()
            control.hide(); control.notification(title='MDBList', message=32049)

    def listItems(self, list_id):
        try:
            from resources.lib.modules.mdblist import getListItems
            _, shows = cache.get(getListItems, 60, list_id, 'show')
            self._tv.list = [_show_item(r) for r in (shows or [])]
            self._tv.worker()
            self._tv.tvshowDirectory(self._tv.list)
        except Exception:
            log_utils.error()
            control.hide(); control.notification(title='MDBList', message=32049)

    def userLists(self):
        try:
            from resources.lib.modules.mdblist import getUserLists
            _build_list_directory(cache.get(getUserLists, 60) or [], 'mdblist_showListItems')
        except Exception:
            log_utils.error()

    def topLists(self):
        try:
            from resources.lib.modules.mdblist import getTopLists
            _build_list_directory(cache.get(getTopLists, 240) or [], 'mdblist_showListItems')
        except Exception:
            log_utils.error()

    def searchLists(self):
        try:
            from resources.lib.modules.mdblist import searchLists
            k = control.keyboard('', getLS(32010)); k.doModal()
            q = k.getText() if k.isConfirmed() else None
            if not q: return control.closeAll()
            _build_list_directory(searchLists(q) or [], 'mdblist_showListItems')
        except Exception:
            log_utils.error()


# ============================================================
# PUBLIC TOP LISTS — MOVIES  (appears in main Movies menu)
# Uses mdblist_movieTopListItems — SEPARATE from user-list handler
# ============================================================
class MDBListTopMovies:
    def __init__(self):
        from resources.lib.menus.movies import Movies
        self._movies = Movies()

    def topLists(self):
        try:
            from resources.lib.modules.mdblist import getTopMovieLists
            _build_list_directory(
                cache.get(getTopMovieLists, 240) or [],
                'mdblist_movieTopListItems',   # correct handler
            )
        except Exception:
            log_utils.error()

    def searchLists(self):
        try:
            from resources.lib.modules.mdblist import searchLists
            k = control.keyboard('', getLS(32010)); k.doModal()
            q = k.getText() if k.isConfirmed() else None
            if not q: return control.closeAll()
            results = [l for l in (searchLists(q) or [])
                       if l.get('mediatype') in ('movie', 'both', '')]
            _build_list_directory(results, 'mdblist_movieTopListItems')
        except Exception:
            log_utils.error()

    def listItems(self, list_id):
        try:
            from resources.lib.modules.mdblist import getListItems
            movies, _ = cache.get(getListItems, 60, list_id, 'movie')
            self._movies.list = [_movie_item(r) for r in (movies or [])]
            self._movies.worker()
            self._movies.movieDirectory(self._movies.list)
        except Exception:
            log_utils.error()
            control.hide(); control.notification(title='MDBList', message=32049)


# ============================================================
# PUBLIC TOP LISTS — TV SHOWS  (appears in main TV Shows menu)
# Uses mdblist_showTopListItems — SEPARATE from user-list handler
# ============================================================
class MDBListTopShows:
    def __init__(self):
        from resources.lib.menus.tvshows import TVshows
        self._tv = TVshows()

    def topLists(self):
        try:
            from resources.lib.modules.mdblist import getTopShowLists
            _build_list_directory(
                cache.get(getTopShowLists, 240) or [],
                'mdblist_showTopListItems',   # correct handler
            )
        except Exception:
            log_utils.error()

    def searchLists(self):
        try:
            from resources.lib.modules.mdblist import searchLists
            k = control.keyboard('', getLS(32010)); k.doModal()
            q = k.getText() if k.isConfirmed() else None
            if not q: return control.closeAll()
            results = [l for l in (searchLists(q) or [])
                       if l.get('mediatype') in ('show', 'both', '')]
            _build_list_directory(results, 'mdblist_showTopListItems')
        except Exception:
            log_utils.error()

    def listItems(self, list_id):
        """Items from a public top list — shows, with fallback for mixed-array API responses."""
        try:
            from resources.lib.modules.mdblist import getListItems, _get
            _, shows = cache.get(getListItems, 60, list_id, 'show')
            # Fallback: MDBList sometimes puts shows in movies[] with mediatype='show'
            if not shows:
                data = _get('/lists/%s/items' % list_id) or {}
                raw_shows = data.get('shows') or []
                raw_mix   = [m for m in (data.get('movies') or [])
                             if str(m.get('mediatype', '')).lower()
                             in ('show', 'tv', 'tvshow', 'series')]
                shows = [
                    {'title': s.get('title', ''), 'year': str(s.get('release_year', '')),
                     'imdb': str(s.get('imdb_id', '')),
                     'tmdb': str(s.get('tmdb_id', '')) if s.get('tmdb_id') else '',
                     'tvdb': str(s.get('tvdb_id', '')) if s.get('tvdb_id') else '',
                     'rank': s.get('rank', 9999)}
                    for s in (raw_shows + raw_mix)
                ]
            self._tv.list = [_show_item(r) for r in (shows or [])]
            self._tv.worker()
            self._tv.tvshowDirectory(self._tv.list)
        except Exception:
            log_utils.error()
            control.hide(); control.notification(title='MDBList', message=32049)


# ============================================================
# BROWSE ANOTHER USER'S LISTS
# ============================================================
class MDBListUserBrowse:
    """
    Let the user browse any MDBList user's public lists by username,
    or paste a direct mdblist.com/lists/… URL.
    """

    def __init__(self):
        pass

    # ---- Entry point: ask username ---------------------------------
    def browseUser(self):
        try:
            k = control.keyboard('', getLS(40241))
            k.doModal()
            username = k.getText().strip() if k.isConfirmed() else ''
            if not username:
                return control.closeAll()
            from resources.lib.modules.mdblist import getUserListsByName
            lists = getUserListsByName(username)
            if not lists:
                control.hide()
                control.notification(title='MDBList', message=getLS(40242))
                return
            _build_list_directory(lists, 'mdblist_userBrowseListItems&username=%s' % username)
        except Exception:
            log_utils.error()

    # ---- Enter a full mdblist.com URL ------------------------------
    def importByUrl(self, media_type='movie'):
        try:
            k = control.keyboard('https://mdblist.com/lists/', getLS(40243))
            k.doModal()
            url = k.getText().strip() if k.isConfirmed() else ''
            if not url or 'mdblist.com/lists/' not in url:
                return control.closeAll()
            from resources.lib.modules.mdblist import getListItemsFromUrl
            movies, shows = getListItemsFromUrl(url)
            if media_type == 'show':
                items = [_show_item(r) for r in (shows or [])]
                if not items and movies:
                    items = [_show_item(r) for r in movies if r.get('tvdb')]
                if not items:
                    control.hide()
                    control.notification(title='MDBList', message=getLS(40230))
                    return
                from resources.lib.menus.tvshows import TVshows
                tv = TVshows()
                tv.list = items
                tv.worker()
                tv.tvshowDirectory(tv.list)
            else:
                items = [_movie_item(r) for r in (movies or [])]
                if not items:
                    control.hide()
                    control.notification(title='MDBList', message=getLS(40230))
                    return
                from resources.lib.menus.movies import Movies
                mv = Movies()
                mv.list = items
                mv.worker()
                mv.movieDirectory(mv.list)
        except Exception:
            log_utils.error()

    # ---- Items of a chosen user list ------------------------------
    def listItems(self, list_id, username='', media_type='both'):
        try:
            from resources.lib.modules.mdblist import getListItems
            movies, shows = cache.get(getListItems, 60, list_id)
            if media_type == 'show' or (not movies and shows):
                items = [_show_item(r) for r in (shows or [])]
                if not items:
                    items = [_show_item(r) for r in (movies or []) if r.get('tvdb')]
                from resources.lib.menus.tvshows import TVshows
                tv = TVshows()
                tv.list = items
                tv.worker()
                tv.tvshowDirectory(tv.list)
            elif media_type == 'movie' or (movies and not shows):
                items = [_movie_item(r) for r in (movies or [])]
                from resources.lib.menus.movies import Movies
                mv = Movies()
                mv.list = items
                mv.worker()
                mv.movieDirectory(mv.list)
            else:
                # Mixed: show sub-menu with Movies / TV Shows choice
                _build_list_directory(
                    [
                        {'id': list_id, 'name': getLS(40244), 'items': len(movies), 'user_name': username},
                        {'id': '%s__show' % list_id, 'name': getLS(40245), 'items': len(shows), 'user_name': username},
                    ],
                    'mdblist_userBrowseListItems&username=%s' % username,
                )
        except Exception:
            log_utils.error()
            control.hide()
            control.notification(title='MDBList', message=32049)
