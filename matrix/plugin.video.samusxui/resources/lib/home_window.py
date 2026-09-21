# -*- coding: utf-8 -*-
import os
import datetime
import threading
import urllib.parse
import xbmc
import xbmcgui
import xbmcaddon

from . import tmdb
from . import db
from . import discover as _discover_mod
from .task_group import TaskGroup

_STATUS_RO = {
    'Post Production': 'Post-producție',
    'In Production':   'În producție',
    'Planned':         'Planificat',
    'Rumored':         'Zvon',
    'Canceled':        'Anulat',
    'Pilot':           'Pilot',
}

ADDON      = xbmcaddon.Addon('plugin.video.samusxui')
ADDON_PATH = ADDON.getAddonInfo('path')
_MEDIA     = os.path.join(ADDON_PATH, 'resources', 'skins', 'Default', 'media')

_SECTIONS = [
    ('Filme',    'movie',     'sidebar_filme2.png'),
    ('Seriale',  'tv',        'sidebar_seriale2.png'),
    ('Favorite', 'favorites', 'sidebar_favorite2.png'),
    ('Continuă', 'continue',  'sidebar_continua2.png'),
    ('Descoperă','discover',  'sidebar_favorite2.png'),
    ('Căutare',  'search',    'sidebar_cautare2.png'),
    ('Trakt',    'trakt',     'sidebar_trakt3.png'),
    ('Adult',    'adult',     'sidebar_filme2.png'),
    ('Setări',   'settings',  'sidebar_setari2.png'),
]

_GENRES_MOVIE = [
    ('Acțiune',          28),
    ('Aventură',    12),
    ('Animație',    16),
    ('Comedie',     35),
    ('Crimă',       80),
    ('Documentare', 99),
    ('Dramă',       18),
    ('Familie',     10751),
    ('Fantezie',    14),
    ('Horror',      27),
    ('Istorie',     36),
    ('Mister',      9648),
    ('Romantism',   10749),
    ('SF',          878),
    ('Thriller',    53),
    ('Război',      10752),
    ('Western',     37),
]

_GENRES_FAV = [
    ('Toate',    None),
    ('Filme',    'movie'),
    ('Seriale',  'tv'),
]

_GENRES_CONT = _GENRES_FAV

_GENRES_TRAKT = [
    ('Trending Filme',    'trending_movie'),
    ('Trending Seriale',  'trending_tv'),
    ('Watchlist Filme',   'watchlist_movie'),
    ('Watchlist Seriale', 'watchlist_tv'),
    ('Recomandări',       'recommendations'),
    ('Liste Trending',    'lists_trending'),
    ('Liste Populare',    'lists_popular'),
    ('Listele Mele',      'lists_mine'),
    ('Caută',             'search_trakt'),
]

_TRAKT_INTERACTIVE  = frozenset(('lists_trending', 'lists_popular', 'lists_mine', 'search_trakt'))
_TRAKT_LIST_TITLES  = {
    'lists_trending': 'Liste Trending',
    'lists_popular':  'Liste Populare',
    'lists_mine':     'Listele Mele',
}

_GENRE_ICON_MAP = {
    None:    'genre_populare.png',
    28:      'genre_actiune.png',
    10759:   'genre_actiune.png',   # Acțiune TV
    12:      'genre_aventura.png',
    16:      'genre_animatie.png',
    35:      'genre_comedie.png',
    80:      'genre_crima.png',
    99:      'genre_doc.png',
    18:      'genre_drama.png',
    10751:   'genre_familie.png',
    14:      'genre_fantezie.png',
    27:      'genre_horror.png',
    36:      'genre_istoric.png',
    9648:    'genre_mister.png',
    10749:   'genre_romantic.png',
    878:     'genre_sf.png',
    10765:   'genre_sf.png',        # SF & Fantasy TV
    53:      'genre_thriller.png',
    10752:   'genre_razboi.png',
    10768:   'genre_razboi.png',    # Război & Politică TV
    10762:   'genre_copii.png',
    10764:   'genre_reality.png',
    37:      'genre_western.png',
    'movie':           'sidebar_filme2.png',
    'tv':              'sidebar_seriale2.png',
    'trending_movie':  'genre_populare.png',
    'trending_tv':     'sidebar_seriale2.png',
    'watchlist_movie': 'sidebar_filme2.png',
    'watchlist_tv':    'sidebar_seriale2.png',
    'recommendations': 'sidebar_favorite2.png',
}

_GENRES_TV = [
    ('Acțiune',           10759),
    ('Animație',          16),
    ('Comedie',           35),
    ('Copii',             10762),
    ('Crimă',             80),
    ('Documentare',       99),
    ('Dramă',             18),
    ('Familie',           10751),
    ('Mister',            9648),
    ('Reality',           10764),
    ('SF & Fantasy',      10765),
    ('Război & Politică', 10768),
    ('Western',           37),
]

# IDs
_ID_BG          = 1
_ID_SIDEBAR_BG  = 10
_ID_SIDEBAR     = 50
_ID_USER_NAME   = 210
_ID_USER_ROLE   = 211
_ID_CLOCK       = 200
_ID_DATE        = 201
_ID_BACKDROP    = 100
_ID_PRECACHE    = (901, 902, 903)   # backdrop pre-cache controls
_ID_GRAD_L      = 101
_ID_GRAD_B      = 102
_ID_LOGO        = 115
_ID_TITLE       = 110
_ID_TITLE_SUB   = 116
_ID_META        = 111
_ID_PLOT        = 113
_ID_PLAY        = 120
_ID_SOURCES     = 121
_ID_DETAILS     = 122
_ID_FAV         = 123
_ID_TRASH       = 124
_ID_FAV_ICON    = 128
_ID_BTN_ICON1   = 125
_ID_BTN_ICON2   = 126
_ID_BTN_ICON3   = 127
_ID_SECTION_LBL = 130
_ID_SORT_BTN    = 145

_FILTER_TYPES  = ['genres', 'tmdb', 'years', 'providers']
_FILTER_LABELS = {
    'genres':    '  GENURI',
    'tmdb':      '  TMDB',
    'years':     '  ANI',
    'providers': '  REȚELE',
}

_GENRES_TMDB_MOVIE = [
    ('Populare',  'popular'),
    ('Trending',  'trending'),
    ('Top Rated', 'top_rated'),
    ('Cinema',    'now_playing'),
    ('Viitoare',  'upcoming'),
]

_GENRES_TMDB_TV = [
    ('Populare',  'popular'),
    ('Trending',  'trending'),
    ('Top Rated', 'top_rated'),
    ('Pe ecrane', 'on_the_air'),
    ('Astăzi',    'airing_today'),
]

_CURRENT_YEAR = 2026
_GENRES_YEARS = [(str(y), y) for y in range(_CURRENT_YEAR, 1989, -1)]

_GENRES_PROVIDERS = [
    ('Netflix',      8),
    ('Amazon',       119),
    ('Disney+',      337),
    ('Max',          1899),
    ('SkyShowtime',  1773),
    ('Crunchyroll',  283),
    ('Mubi',         11),
    ('Plex',         538),
    ('Rakuten TV',   35),
    ('FilmBox+',     701),
]
_ID_POSTERS     = 131
_ID_EMPTY_MSG   = 150
_ID_EMPTY_ICON  = 151
_ID_GENRE_BG    = 139
_ID_GENRES      = 140

ACTION_NAV_BACK   = 10
ACTION_PREV_MENU  = 92
ACTION_MOVE_LEFT  = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP    = 3
ACTION_MOVE_DOWN  = 4


class _HomeTrailerPlayer(xbmc.Player):
    """Player păstrat viu până la final, ca hero-ul să fie restaurat imediat."""

    def __init__(self, owner, generation):
        super().__init__()
        self._owner = owner
        self._generation = generation

    def _finished(self):
        try:
            self._owner._on_auto_trailer_finished(self._generation, self)
        except Exception as exc:
            xbmc.log(f'[SamusXUI] trailer finish callback: {exc}', xbmc.LOGWARNING)

    def onPlayBackEnded(self):
        self._finished()

    def onPlayBackStopped(self):
        self._finished()

    def onPlayBackError(self):
        self._finished()


class HomeWindow(xbmcgui.WindowXML):

    def __init__(self, *args, **kwargs):
        self._section       = 'movie'
        self._items         = []
        self._hero_idx      = 0
        self._genres        = list(_GENRES_MOVIE)
        self._active_genre  = None
        self._page          = 1
        self._total_pages   = 1
        self._loading_more  = False
        self._last_poster_pos = 0
        self._fav_ids       = set()
        self._fav_filter    = None
        self._cont_filter   = None
        self._disc_tag      = None   # id-ul etichetei TMDb selectate
        self._disc_media    = 'movie'
        self._filter_type         = 'genres'
        self._trakt_filter        = 'trending_movie'
        self._selected_list       = None   # {'name', 'user', 'slug'} for list_items
        self._trakt_search_query  = ''
        self._load_gen            = 0
        self._trailer_gen         = 0
        self._trailer_focus_idx   = None
        self._trailer_player      = None
        self._initialized         = False
        self._tasks               = TaskGroup('HomeWindow')

    # ------------------------------------------------------------------ setup

    _EMPTY_MESSAGES = {
        'favorites': 'Nu ai filme sau seriale adăugate la favorite.',
        'continue':  'Nu există vizionări în curs.',
        'discover':  'Vezi câteva filme sau adaugă favorite — de acolo îți deducem temele.',
        'trakt':     'Conectează-ți contul Trakt din Setări pentru a vedea conținut.',
        'settings':  'Setări addon — apasă OK pentru a deschide.',
        'search':    'Căutare — apasă OK pentru a introduce un termen.',
        'adult':     'Nu s-a putut încărca conținut adult.',
    }

    def onInit(self):
        if self._initialized:
            self._restore_focus()
            return
        self._initialized = True
        self._setup_sidebar()
        self._setup_genres()
        self._load_and_show()
        try:
            version = ADDON.getAddonInfo('version')
            self.getControl(212).setLabel(f'v{version}')
        except Exception:
            pass
        self.setFocusId(_ID_SIDEBAR)

    def close(self):
        self._load_gen += 1  # anulează toate task-urile UI legate de generația curentă
        self._cancel_auto_trailer()
        self._tasks.close(timeout=8.0)
        super().close()

    def _cancel_auto_trailer(self):
        """Invalidează rezolvarea curentă și oprește imediat preview-ul activ."""
        self._trailer_gen += 1
        self._trailer_focus_idx = None
        self.setProperty('trailer_starting', '')
        trailer_playing = bool(self.getProperty('trailer_active'))
        self.setProperty('trailer_active', '')
        trailer_player = self._trailer_player
        self._trailer_player = None
        if trailer_playing and trailer_player is not None:
            trailer_player.stop()

    def _on_auto_trailer_finished(self, trailer_gen, trailer_player):
        """Ascunde videowindow-ul la final și reafişează fanartul hero curent."""
        if trailer_gen != self._trailer_gen or trailer_player is not self._trailer_player:
            return
        self.setProperty('trailer_starting', '')
        self.setProperty('trailer_active', '')
        backdrop = self.getProperty('hero_fanart')
        if backdrop:
            # Reaplicarea texturii forțează redesenarea după ultimul frame video.
            self.getControl(_ID_BACKDROP).setImage(backdrop)
        xbmc.log('[SamusXUI] trailer terminat; fanart hero restaurat', xbmc.LOGDEBUG)

    def _restore_focus(self):
        ctrl = self.getControl(_ID_SIDEBAR)
        n = ctrl.size()
        idx = next((i for i in range(n) if ctrl.getListItem(i).getProperty('section') == self._section), 0)
        try:
            self.getControl(_ID_SIDEBAR).selectItem(idx)
        except Exception:
            pass
        if self._items and self._section not in ('settings', 'search'):
            self.setFocusId(_ID_POSTERS)
        else:
            self.setFocusId(_ID_SIDEBAR)

    def _setup_sidebar(self):
        ctrl = self.getControl(_ID_SIDEBAR)
        ctrl.reset()
        show_adult = ADDON.getSetting('use_adult') == 'true'
        items = []
        for label, section, icon in _SECTIONS:
            if section == 'adult' and not show_adult:
                continue
            item = xbmcgui.ListItem(label)
            item.setProperty('section', section)
            item.setProperty('icon', os.path.join(_MEDIA, icon))
            items.append(item)
        ctrl.addItems(items)
        ctrl.selectItem(0)

    def _mark_active_genre(self, idx):
        ctrl = self.getControl(_ID_GENRES)
        for i in range(len(self._genres)):
            try:
                ctrl.getListItem(i).setProperty('active', '1' if i == idx else '')
            except Exception:
                pass

    def _setup_genres(self):
        ctrl = self.getControl(_ID_GENRES)
        ctrl.reset()
        items = []
        for label, gid in self._genres:
            item = xbmcgui.ListItem(label)
            item.setProperty('genre_id', str(gid) if gid else '')
            icon_file = _GENRE_ICON_MAP.get(gid, '')
            icon_path = os.path.join(_MEDIA, icon_file) if icon_file else ''
            item.setProperty('genre_icon', icon_path)
            items.append(item)
        ctrl.addItems(items)
        active_idx = next((i for i, (_, g) in enumerate(self._genres)
                           if g == self._active_genre), 0)
        ctrl.selectItem(active_idx)
        self._mark_active_genre(active_idx)
        try:
            self.getControl(_ID_SECTION_LBL).setLabel('')
        except Exception:
            pass

    # ------------------------------------------------------------------ data

    def _load_and_show(self, genre_id=None):
        self._update_filter_btn()
        self._page         = 1
        self._total_pages  = 1
        self._loading_more = False
        self._load_gen    += 1
        my_gen             = self._load_gen
        if self._section in ('trakt', 'adult'):
            self._items = []
            self._set_content_visible(False)
            try:
                self.getControl(_ID_EMPTY_MSG).setLabel('Se încarcă...')
                self.getControl(_ID_EMPTY_MSG).setVisible(True)
            except Exception:
                pass
            target = self._load_trakt_async if self._section == 'trakt' else self._load_asa_async
            self._tasks.start(target, args=(my_gen,), name='home-load-section')
            return
        try:
            data = self._fetch_page(1, genre_id)
            self._items       = data.get('results', [])
            self._total_pages = data.get('total_pages', 1)
        except Exception as e:
            xbmc.log(f'[SamusXUI] load error: {e}', xbmc.LOGWARNING)
            self._items = []
        if self._load_gen == my_gen:
            self._populate_posters()

    def _load_trakt_async(self, gen):
        from . import trakt as _trakt
        from .dialogs import show_trakt_auth_dialog
        try:
            tf         = self._trakt_filter
            needs_auth = tf in ('watchlist_movie', 'watchlist_tv', 'recommendations')
            if needs_auth and not _trakt.is_authenticated():
                if self._load_gen != gen:
                    return
                authenticated = show_trakt_auth_dialog()
                if not authenticated:
                    if self._load_gen == gen:
                        self._items       = []
                        self._total_pages = 1
                        self._populate_posters()
                    return
            data  = self._fetch_trakt_page(1)
            items = data.get('results', [])
            total = data.get('total_pages', 1)
        except Exception as e:
            xbmc.log(f'[SamusXUI/Trakt] load_async: {e}', xbmc.LOGWARNING)
            items = []
            total = 1
        if self._load_gen != gen:
            return
        self._items       = items
        self._total_pages = total
        self._populate_posters()

    def _load_asa_async(self, gen):
        from . import asa as _asa
        try:
            items = _asa.catalog('recent', skip=0)
            total = 2 if len(items) >= _asa._PAGE_SIZE else 1
        except Exception as e:
            xbmc.log(f'[SamusXUI/ASA] load_async: {e}', xbmc.LOGWARNING)
            items = []
            total = 1
        if self._load_gen != gen:
            return
        self._items       = items
        self._total_pages = total
        self._populate_posters()

    def _fetch_asa_page(self, page):
        from . import asa as _asa
        skip  = (page - 1) * _asa._PAGE_SIZE
        items = _asa.catalog('recent', skip=skip)
        total = page + 1 if len(items) >= _asa._PAGE_SIZE else page
        return {'results': items, 'total_pages': total}

    def _fetch_page(self, page, genre_id=None):
        if self._section == 'adult':
            return self._fetch_asa_page(page)
        if self._section == 'discover':
            if not self._disc_tag:
                # Fără istoric n-avem din ce deduce teme — arătăm ce e în trend,
                # ca secțiunea să nu fie moartă la prima instalare.
                data = tmdb.trending(self._disc_media, 'week', page)
                for r in data.get('results', []):
                    r['media_type'] = self._disc_media
                return data
            data = _discover_mod.by_tag(self._disc_tag, self._disc_media, page)
            xbmc.log(f'[SamusXUI/discover] tag={self._disc_tag} '
                     f'media={self._disc_media} pag={page}: '
                     f'{len(data.get("results") or [])} din '
                     f'{data.get("total_results")}', xbmc.LOGINFO)
            return data

        if self._section == 'favorites':
            if page > 1:
                return {}
            favs    = db.get_favorites()
            results = []
            for f in favs:
                mt = 'tv' if f['media_type'] == 'tvshow' else f['media_type']
                if self._fav_filter and mt != self._fav_filter:
                    continue
                item = {
                    'id':            f['tmdb_id'],
                    'media_type':    mt,
                    'poster_path':   f['poster'],
                    'backdrop_path': '',
                    'vote_average':  0,
                    'vote_count':    0,
                    'genre_ids':     [],
                    'overview':      f.get('plot', ''),
                }
                if mt == 'movie':
                    item['title']        = f['title']
                    item['release_date'] = f'{f["year"]}-01-01' if f.get('year') else ''
                else:
                    item['name']           = f['title']
                    item['first_air_date'] = f'{f["year"]}-01-01' if f.get('year') else ''
                results.append(item)
            return {'results': results, 'total_pages': 1}
        if self._section == 'continue':
            if page > 1:
                return {}
            items   = db.get_continue_watching(self._cont_filter)
            results = []
            for h in items:
                item = {
                    'id':            h['tmdb_id'],
                    'media_type':    h['media_type'],
                    'poster_path':   h['poster'],
                    'backdrop_path': '',
                    'vote_average':  0,
                    'vote_count':    0,
                    'genre_ids':     [],
                    'overview':      h.get('plot', ''),
                    'season':        h.get('season'),
                    'episode':       h.get('episode'),
                    'position':      h.get('position', 0),
                    'duration':      h.get('duration', 0),
                }
                if h['media_type'] == 'movie':
                    item['title']        = h['title']
                    item['release_date'] = ''
                else:
                    item['name']           = h['title']
                    item['first_air_date'] = ''
                results.append(item)
            return {'results': results, 'total_pages': 1}
        if self._section == 'trakt':
            return self._fetch_trakt_page(page)
        gid  = genre_id if genre_id is not None else self._active_genre
        ft   = self._filter_type
        media = 'tv' if self._section == 'tv' else 'movie'
        if self._section in ('movie', 'tv'):
            if gid == 'now_playing':
                return tmdb.now_playing(page=page)
            if gid == 'upcoming':
                return tmdb.upcoming(page=page)
            if gid == 'on_the_air':
                return tmdb.on_the_air(page=page)
            if gid == 'airing_today':
                return tmdb.airing_today(page=page)
            if gid == 'trending':
                return tmdb.trending(media, page=page)
            if gid == 'top_rated':
                return tmdb.top_rated(media, page=page)
            if ft == 'years' and isinstance(gid, int):
                return tmdb.popular_by_year(media, gid, page=page)
            if ft == 'providers' and isinstance(gid, int):
                return tmdb.popular_by_provider(media, gid, page=page)
            return tmdb.popular(media, genre_id=gid if isinstance(gid, int) else None, page=page)
        return {}

    def _fetch_trakt_page(self, page):
        from . import trakt as _trakt
        tf = self._trakt_filter
        needs_auth = tf in ('watchlist_movie', 'watchlist_tv', 'recommendations')
        if needs_auth and not _trakt.is_authenticated():
            return {}
        try:
            total_pages = 1
            if tf == 'trending_movie':
                raw, total_pages = _trakt.trending_movies_paged(page=page, limit=30)
                items = [self._norm_trakt_movie(i) for i in (raw or [])]
            elif tf == 'trending_tv':
                raw, total_pages = _trakt.trending_shows_paged(page=page, limit=30)
                items = [self._norm_trakt_show(i) for i in (raw or [])]
            elif tf == 'watchlist_movie':
                raw, total_pages = _trakt.watchlist_movies_paged(page=page, limit=30)
                items = [self._norm_trakt_movie(i) for i in (raw or [])]
            elif tf == 'watchlist_tv':
                raw, total_pages = _trakt.watchlist_shows_paged(page=page, limit=30)
                items = [self._norm_trakt_show(i) for i in (raw or [])]
            elif tf == 'recommendations':
                raw   = _trakt.get_recommendations_movies(limit=50) or []
                items = [self._norm_trakt_movie(i) for i in raw]
            elif tf == 'list_items':
                sel = self._selected_list
                if not sel:
                    items = []
                else:
                    raw, total_pages = _trakt.list_items_paged(
                        sel['user'], sel['slug'], page=page, limit=30)
                    items = []
                    for i in (raw or []):
                        if i.get('type') == 'movie':
                            items.append(self._norm_trakt_movie(i))
                        elif i.get('type') == 'show':
                            items.append(self._norm_trakt_show(i))
            elif tf == 'search_trakt':
                query = self._trakt_search_query
                if not query:
                    items = []
                else:
                    raw, total_pages = _trakt.search_movies_shows_paged(query, page=page, limit=30)
                    items = []
                    for i in (raw or []):
                        if i.get('type') == 'movie':
                            items.append(self._norm_trakt_movie(i))
                        elif i.get('type') == 'show':
                            items.append(self._norm_trakt_show(i))
            else:
                items = []
        except Exception as e:
            xbmc.log(f'[SamusXUI/Trakt] _fetch_trakt_page {tf}: {e}', xbmc.LOGWARNING)
            items, total_pages = [], 1
        items = [i for i in items if i.get('id')]
        return {'results': items, 'total_pages': total_pages}

    @staticmethod
    def _norm_trakt_movie(item):
        m   = item.get('movie') or item
        ids = m.get('ids', {})
        return {
            'id':            ids.get('tmdb'),
            'title':         m.get('title', ''),
            'overview':      m.get('overview', ''),
            'release_date':  f"{m.get('year', '')}-01-01" if m.get('year') else '',
            'vote_average':  m.get('rating') or 0,
            'vote_count':    0,
            'poster_path':   '',
            'backdrop_path': '',
            'genre_ids':     [],
            'media_type':    'movie',
        }

    @staticmethod
    def _norm_trakt_show(item):
        s   = item.get('show') or item
        ids = s.get('ids', {})
        return {
            'id':             ids.get('tmdb'),
            'name':           s.get('title', ''),
            'overview':       s.get('overview', ''),
            'first_air_date': f"{s.get('year', '')}-01-01" if s.get('year') else '',
            'vote_average':   s.get('rating') or 0,
            'vote_count':     0,
            'poster_path':    '',
            'backdrop_path':  '',
            'genre_ids':      [],
            'media_type':     'tv',
        }

    def _set_content_visible(self, visible):
        for cid in (_ID_PLAY, _ID_SOURCES, _ID_DETAILS, _ID_FAV, _ID_POSTERS,
                    _ID_BTN_ICON1, _ID_BTN_ICON2, _ID_BTN_ICON3):
            try:
                self.getControl(cid).setVisible(visible)
            except Exception:
                pass
        # Genres stay visible whenever section supports them — hiding them loses keyboard focus
        genres_visible = self._section in ('movie', 'tv', 'favorites', 'continue', 'trakt', 'discover')
        for cid in (_ID_GENRE_BG, _ID_GENRES):
            try:
                self.getControl(cid).setVisible(genres_visible)
            except Exception:
                pass
        trash_visible = visible and self._section == 'continue'
        try:
            self.getControl(_ID_TRASH).setVisible(trash_visible)
        except Exception:
            pass
        star_visible = visible and self._section not in ('continue', 'trakt', 'search', 'settings', 'adult')
        try:
            self.getControl(_ID_FAV_ICON).setVisible(star_visible)
        except Exception:
            pass
        try:
            self.getControl(_ID_EMPTY_MSG).setVisible(not visible)
        except Exception:
            pass
        if visible:
            self.clearProperty('empty_icon')
        if not visible:
            self.clearProperty('hero_fanart')
            for cid in (_ID_BACKDROP, _ID_LOGO, 103):
                try:
                    self.getControl(cid).setImage('')
                except Exception:
                    pass
            for cid in (_ID_TITLE, _ID_TITLE_SUB, _ID_META, _ID_PLOT, _ID_SECTION_LBL):
                try:
                    self.getControl(cid).setLabel('')
                except Exception:
                    pass

    def _get_genres_for_filter(self):
        if self._filter_type == 'years':
            return list(_GENRES_YEARS)
        if self._filter_type == 'providers':
            return list(_GENRES_PROVIDERS)
        if self._filter_type == 'tmdb':
            return list(_GENRES_TMDB_TV if self._section == 'tv' else _GENRES_TMDB_MOVIE)
        return list(_GENRES_TV if self._section == 'tv' else _GENRES_MOVIE)

    def _update_filter_btn(self):
        if self._section == 'discover':
            # Aici butonul comută tipul de conținut: eticheta e aceeași, dar
            # /discover se interoghează separat pentru filme și seriale.
            self.setProperty('sort.label', '  SERIALE' if self._disc_media == 'tv' else '  FILME')
            return
        label = _FILTER_LABELS[self._filter_type]
        show  = self._section in ('movie', 'tv')
        self.setProperty('sort.label', label if show else '')

    def _get_section_label(self):
        if self._section == 'adult':
            return 'Recent'
        if self._section == 'trakt':
            if self._trakt_filter == 'list_items':
                return self._selected_list.get('name', '') if self._selected_list else ''
            if self._trakt_filter == 'search_trakt' and self._trakt_search_query:
                return f'Trakt — {self._trakt_search_query}'
            gid = self._trakt_filter
        elif self._section == 'favorites':
            gid = self._fav_filter
        elif self._section == 'continue':
            gid = self._cont_filter
        elif self._section == 'discover':
            gid = self._disc_tag
        else:
            gid = self._active_genre
        idx = next((i for i, (_, g) in enumerate(self._genres) if g == gid), 0)
        return self._genres[idx][0] if self._genres else ''

    def _populate_posters(self):
        if self._section in ('settings', 'search'):
            return
        self._fav_ids = db.get_favorite_ids()
        ctrl = self.getControl(_ID_POSTERS)
        self._last_poster_pos = 0
        ctrl.reset()
        if not self._items:
            if self._section == 'trakt':
                from . import trakt as _trakt
                needs_auth = self._trakt_filter in ('watchlist_movie', 'watchlist_tv', 'recommendations')
                if needs_auth and not _trakt.is_authenticated():
                    msg = 'Conectează-ți contul Trakt din Setări > Conturi pentru a vedea conținut.'
                elif self._trakt_filter in ('watchlist_movie', 'watchlist_tv'):
                    msg = 'Watchlist gol.'
                elif self._trakt_filter == 'list_items':
                    msg = 'Lista este goală.'
                elif self._trakt_filter == 'search_trakt':
                    msg = f'Nu s-au găsit rezultate pentru „{self._trakt_search_query}".'
                else:
                    msg = 'Nu s-a putut încărca conținut de la Trakt.'
            else:
                msg = self._EMPTY_MESSAGES.get(self._section, '')
            try:
                self.getControl(_ID_EMPTY_MSG).setLabel(msg)
            except Exception:
                pass
            # Setează iconița secțiunii cu delay — evită flash la loading inițial
            _section_icons = {
                'movie':    'sidebar_filme2.png',
                'tv':       'sidebar_seriale2.png',
                'favorite': 'sidebar_favorite2.png',
                'continue': 'sidebar_continua2.png',
                'search':   'sidebar_cautare2.png',
                'trakt':    'sidebar_trakt3.png',
                'adult':    'sidebar_filme2.png',
            }
            icon = _section_icons.get(self._section, 'sidebar_filme2.png')
            icon_path = os.path.join(_MEDIA, icon)
            section_snap = self._section
            def _show_empty_icon():
                xbmc.sleep(600)
                if not self._items and self._section == section_snap:
                    self.setProperty('empty_icon', icon_path)
            self._tasks.start(_show_empty_icon, name='home-empty-icon')
            self._set_content_visible(False)
            try:
                # Dacă utilizatorul parcurge bara de filtre, nu-i smulgem focusul:
                # un filtru gol (ex. Watchlist Trakt fără titluri) l-ar arunca în
                # bara laterală și n-ar mai putea trece la filtrul următor.
                if self.getFocusId() != _ID_GENRES:
                    self.setFocusId(_ID_SIDEBAR)
            except Exception:
                pass
            return
        self._update_hero(0)
        self._set_content_visible(True)
        try:
            self.getControl(_ID_SECTION_LBL).setLabel(self._get_section_label())
        except Exception:
            pass
        self._update_filter_btn()
        self._append_to_list(self._items, ctrl)
        ctrl.selectItem(0)
        active_idx = next((i for i, (_, g) in enumerate(self._genres)
                           if g == self._active_genre), 0)
        self._mark_active_genre(active_idx)
        if self._section == 'trakt':
            items_copy = list(enumerate(list(self._items)))
            self._tasks.start(self._fetch_trakt_posters,
                              args=(items_copy, self._load_gen), name='home-trakt-posters')

    def _append_to_list(self, items, ctrl=None):
        if ctrl is None:
            ctrl = self.getControl(_ID_POSTERS)
        list_items = []
        for m in items:
            title  = (m.get('title') or m.get('name')
                      or m.get('original_title') or m.get('original_name', ''))
            # TMDb trimite `null`, nu cheie lipsă, la titlurile fără imagine —
            # `get(..., '')` ar întoarce None și ar rupe construirea listei întregi.
            poster_path = m.get('poster_path') or ''
            poster = poster_path if poster_path.startswith('http') else tmdb.poster_url(poster_path)
            vote   = m.get('vote_average', 0)
            tmdb_id = m.get('id', '')
            media   = m.get('media_type') or (
                self._section if self._section in ('movie', 'tv') else 'movie')
            try:
                is_fav = (int(tmdb_id), media) in self._fav_ids if tmdb_id else False
            except (ValueError, TypeError):
                is_fav = False
            pos  = m.get('position', 0)
            dur  = m.get('duration', 0)
            if dur > 0 and self._section == 'continue':
                remaining   = int((dur - pos) / 60)
                prog_label  = f'{remaining}min' if remaining > 0 else ''
            else:
                prog_label  = ''
            li = xbmcgui.ListItem(title)
            li.setArt({'thumb': poster})
            li.setLabel2(f'★ {vote:.1f}')
            li.setProperty('tmdb_id',        str(tmdb_id))
            li.setProperty('media_type',     media)
            li.setProperty('fav_star',       '1' if is_fav else '')
            li.setProperty('progress_label', prog_label)
            list_items.append(li)
        ctrl.addItems(list_items)

    # ------------------------------------------------------------------ pagination

    def _trigger_load_more(self):
        if self._loading_more or self._page >= self._total_pages:
            return
        self._loading_more = True
        self._tasks.start(self._fetch_more, name='home-fetch-more')

    def _fetch_more(self):
        try:
            next_page = self._page + 1
            data      = self._fetch_page(next_page)
            new_items = data.get('results', [])
            if new_items:
                start_idx = len(self._items)
                self._page = next_page
                self._items.extend(new_items)
                # Salvează poziția curentă înainte de addItems (poate reseta scroll)
                try:
                    ctrl = self.getControl(_ID_POSTERS)
                    saved_pos = ctrl.getSelectedPosition()
                except Exception:
                    saved_pos = -1
                self._append_to_list(new_items)
                # Restaurează poziția după addItems
                if saved_pos >= 0:
                    try:
                        self.getControl(_ID_POSTERS).selectItem(saved_pos)
                    except Exception:
                        pass
                xbmc.log(f'[SamusXUI] pagina {next_page}/{self._total_pages} încărcată '
                         f'({len(new_items)} titluri), pos restaurat={saved_pos}', xbmc.LOGINFO)
                if self._section == 'trakt':
                    snapshot = [(start_idx + i, m) for i, m in enumerate(new_items)]
                    self._fetch_trakt_posters(snapshot)
            else:
                self._total_pages = self._page
        except Exception as e:
            xbmc.log(f'[SamusXUI] load more p{self._page+1}: {e}', xbmc.LOGWARNING)
        finally:
            self._loading_more = False

    def _update_hero(self, idx):
        if not self._items or idx >= len(self._items):
            return
        self._hero_idx = idx
        m = self._items[idx]

        title      = (m.get('title') or m.get('name')
                      or m.get('original_title') or m.get('original_name', ''))
        orig_title = m.get('original_title') or m.get('original_name', '')
        needs_en_title = bool(orig_title) and title == orig_title
        yr_raw     = m.get('release_date') or m.get('first_air_date') or ''
        year       = yr_raw[:4]
        vote       = m.get('vote_average', 0)
        cnt        = m.get('vote_count', 0)
        cnt_str    = f"{int(cnt / 1000)}K voturi" if cnt >= 1000 else (f"{cnt} voturi" if cnt else '')
        plot       = m.get('overview') or ''
        backdrop_path = m.get('backdrop_path') or ''
        backdrop   = backdrop_path if backdrop_path.startswith('http') else tmdb.backdrop_url(backdrop_path)
        genre_ids  = m.get('genre_ids', [])
        media      = m.get('media_type') or (
            self._section if self._section in ('movie', 'tv') else 'movie')

        if media == 'adult':
            studio     = m.get('studio', '')
            runtime    = m.get('runtime', '')
            genres_str = '  •  '.join(m.get('genres', [])[:3])
            parts      = [p for p in [studio, runtime, genres_str] if p]
        else:
            genres_str = tmdb.genre_names(genre_ids, media)
            rating_str = f'[COLOR FFFFD700][B]★ {vote:.1f}[/B][/COLOR]' if vote else ''
            status_str = m.get('_status', '')
            if not status_str and yr_raw:
                try:
                    rel = datetime.date.fromisoformat(yr_raw[:10])
                    if rel > datetime.date.today():
                        status_str = 'În curând'
                except Exception:
                    pass
            if self._section == 'continue' and media == 'tv':
                season  = m.get('season')
                episode = m.get('episode')
                if season is not None and episode is not None:
                    ep_str = f'S{int(season):02d}E{int(episode):02d}'
                    parts  = [ep_str] + [p for p in [status_str, year, genres_str, rating_str, cnt_str] if p]
                else:
                    parts = [p for p in [status_str, year, genres_str, rating_str, cnt_str] if p]
            else:
                parts = [p for p in [status_str, year, genres_str, rating_str, cnt_str] if p]
        meta = '  •  '.join(parts)

        try:
            self.setProperty('hero_fanart', backdrop or '')
            self.getControl(_ID_LOGO).setImage('')
            self.getControl(_ID_TITLE).setLabel(title)
            self.getControl(_ID_TITLE_SUB).setLabel('')
            self.getControl(_ID_META).setLabel(meta)
            self.getControl(_ID_PLOT).setLabel(plot)
            if backdrop:
                self.getControl(_ID_BACKDROP).setImage(backdrop)
                self.getControl(103).setImage(backdrop)
            elif self._section in ('favorites', 'continue', 'trakt'):
                self.getControl(_ID_BACKDROP).setImage('')
                self.getControl(103).setImage('')
        except Exception as e:
            xbmc.log(f'[SamusXUI] hero update: {e}', xbmc.LOGDEBUG)

        # Pre-cache backdropuri adiacente (N+1, N+2, N+3)
        for offset, ctrl_id in enumerate(_ID_PRECACHE, 1):
            next_idx = idx + offset
            if next_idx < len(self._items):
                bp = self._items[next_idx].get('backdrop_path', '')
                if bp:
                    try:
                        url = bp if bp.startswith('http') else tmdb.backdrop_url(bp)
                        self.getControl(ctrl_id).setImage(url)
                    except Exception:
                        pass

        tmdb_id = m.get('id')
        # Buton 123 — ȘTERGE în Continue, WATCHLIST în Trakt, FAVORIT în rest
        if self._section == 'continue':
            try:
                self.getControl(_ID_FAV).setLabel('ȘTERGE')
                self.getControl(_ID_FAV_ICON).setVisible(False)
            except Exception:
                pass
        elif self._section == 'trakt':
            if self._trakt_filter in ('watchlist_movie', 'watchlist_tv'):
                lbl = '✕ WATCHLIST'
            else:
                lbl = '+ WATCHLIST'
            try:
                self.getControl(_ID_FAV).setLabel(lbl)
                self.getControl(_ID_FAV_ICON).setVisible(False)
            except Exception:
                pass
        else:
            is_fav = (tmdb_id, media) in self._fav_ids
            try:
                self.getControl(_ID_FAV).setLabel('FAVORIT')
                icon = self.getControl(_ID_FAV_ICON)
                icon.setVisible(True)
                icon.setColorDiffuse('FFFFD700' if is_fav else 'FF888899')
            except Exception:
                pass

        if media != 'adult':
            self._tasks.start(self._fetch_logo,
                              args=(tmdb_id, media, idx, title, self._load_gen),
                              name='home-logo')
        if self._section in ('favorites', 'continue', 'trakt') and not m.get('backdrop_path'):
            self._tasks.start(self._fetch_fav_backdrop,
                              args=(tmdb_id, media, idx, self._load_gen),
                              name='home-backdrop')
        if not plot or needs_en_title:
            self._tasks.start(self._fetch_en_plot,
                              args=(tmdb_id, media, idx, needs_en_title, self._load_gen),
                              name='home-en-plot')

    def _fetch_fav_backdrop(self, tmdb_id, media, for_idx, gen=None):
        try:
            data = tmdb.tv_details(tmdb_id) if media == 'tv' else tmdb.movie_details(tmdb_id)
            if gen is not None and gen != self._load_gen:
                return
            if self._hero_idx != for_idx or self._section in ('settings', 'search'):
                return
            bp = data.get('backdrop_path', '')
            pp = data.get('poster_path', '')
            va = data.get('vote_average', 0)
            vc = data.get('vote_count', 0)
            if for_idx < len(self._items):
                if bp:
                    self._items[for_idx]['backdrop_path'] = bp
                if pp and not self._items[for_idx].get('poster_path'):
                    self._items[for_idx]['poster_path'] = pp
                if va:
                    self._items[for_idx]['vote_average'] = va
                if vc:
                    self._items[for_idx]['vote_count'] = vc
            if bp:
                try:
                    backdrop = tmdb.backdrop_url(bp)
                    self.getControl(_ID_BACKDROP).setImage(backdrop)
                    self.getControl(103).setImage(backdrop)
                    self.setProperty('hero_fanart', backdrop)
                except Exception:
                    pass
            if pp:
                try:
                    self.getControl(_ID_POSTERS).getListItem(for_idx).setArt(
                        {'thumb': tmdb.poster_url(pp)})
                except Exception:
                    pass
            tmdb_status = data.get('status', '')
            status_str  = _STATUS_RO.get(tmdb_status, '')
            if for_idx < len(self._items):
                self._items[for_idx]['_status'] = status_str
            cnt_str    = (f"{int(vc / 1000)}K voturi" if vc >= 1000
                          else (f"{vc} voturi" if vc else '')) if va else ''
            rating_str = f'[COLOR FFFFD700][B]★ {va:.1f}[/B][/COLOR]' if va else ''
            genre_ids  = (self._items[for_idx].get('genre_ids', [])
                          if for_idx < len(self._items) else [])
            yr_raw     = (self._items[for_idx].get('release_date') or
                          self._items[for_idx].get('first_air_date') or ''
                          if for_idx < len(self._items) else '')
            year       = yr_raw[:4]
            genres_str = tmdb.genre_names(genre_ids, media)
            parts      = [p for p in [status_str, year, genres_str, rating_str, cnt_str] if p]
            if parts:
                meta = '  •  '.join(parts)
                try:
                    self.getControl(_ID_META).setLabel(meta)
                except Exception:
                    pass
        except Exception:
            pass

    def _fetch_en_plot(self, tmdb_id, media, for_idx, update_title=False, gen=None):
        try:
            en = tmdb.text_en(tmdb_id, media)
            if gen is not None and gen != self._load_gen:
                return
            if self._hero_idx != for_idx or self._section in ('settings', 'search'):
                return
            if update_title:
                en_title = en.get('title') or en.get('name', '')
                if en_title and for_idx < len(self._items):
                    m = self._items[for_idx]
                    if 'title' in m:
                        self._items[for_idx]['title'] = en_title
                    else:
                        self._items[for_idx]['name'] = en_title
                    try:
                        self.getControl(_ID_POSTERS).getListItem(for_idx).setLabel(en_title)
                    except Exception:
                        pass
            plot = en.get('overview', '')
            if not plot:
                return
            if for_idx < len(self._items):
                self._items[for_idx]['overview'] = plot
            self.getControl(_ID_PLOT).setLabel(plot)
        except Exception:
            pass

    def _fetch_trakt_posters(self, items_snapshot, gen=None):
        try:
            ctrl = self.getControl(_ID_POSTERS)
        except Exception:
            return
        for i, m in items_snapshot:
            if self._section != 'trakt' or (gen is not None and gen != self._load_gen):
                return
            tmdb_id = m.get('id')
            if not tmdb_id or m.get('poster_path'):
                continue
            media = m.get('media_type', 'movie')
            try:
                data   = tmdb.basic_info(tmdb_id, media)
                poster = data.get('poster_path', '')
                if poster:
                    if i < len(self._items):
                        self._items[i]['poster_path'] = poster
                    try:
                        ctrl.getListItem(i).setArt({'thumb': tmdb.poster_url(poster)})
                    except Exception:
                        pass
            except Exception:
                pass

    def _fetch_logo(self, tmdb_id, media, for_idx, title='', gen=None):
        _LOGO_TTL = 7 * 86400
        key = f'wmeta3_{media}_{tmdb_id}'
        cached = db.cache_get(key, _LOGO_TTL)
        if isinstance(cached, dict):
            meta = cached
        else:
            meta = tmdb.widget_meta(tmdb_id, media)
            db.cache_set(key, meta)

        logo    = meta.get('logo', '')
        tagline = meta.get('tagline', '')
        runtime = meta.get('runtime', 0)

        if (gen is not None and gen != self._load_gen) or self._hero_idx != for_idx or self._section in ('settings', 'search'):
            return
        # Re-read title — English fallback may have arrived while logo was fetching
        if for_idx < len(self._items):
            m = self._items[for_idx]
            title = m.get('title') or m.get('name') or title
        if (gen is not None and gen != self._load_gen) or self._hero_idx != for_idx or self._section in ('settings', 'search'):
            return
        try:
            if logo:
                self.getControl(_ID_LOGO).setImage(logo)
                self.getControl(_ID_TITLE_SUB).setLabel(f'[B]{title}[/B]' if title else '')
                self.getControl(_ID_TITLE).setLabel('')
            else:
                self.getControl(_ID_TITLE).setLabel(title)
                self.getControl(_ID_TITLE_SUB).setLabel(
                    f'[I]{tagline}[/I]' if tagline else '')
        except Exception as e:
            xbmc.log(f'[SamusXUI] logo: {e}', xbmc.LOGDEBUG)

        if runtime:
            try:
                rt_str = (f'{runtime // 60}h {runtime % 60:02d}m'
                          if runtime >= 60 else f'{runtime}m')
                if for_idx < len(self._items):
                    m2 = self._items[for_idx]
                    yr_raw    = m2.get('release_date') or m2.get('first_air_date') or ''
                    year      = yr_raw[:4]
                    genre_ids = m2.get('genre_ids', [])
                    vote      = m2.get('vote_average', 0)
                    cnt       = m2.get('vote_count', 0)
                    status_str = m2.get('_status', '')
                    genres_str = tmdb.genre_names(genre_ids, media)
                    rating_str = f'[COLOR FFFFD700][B]★ {vote:.1f}[/B][/COLOR]' if vote else ''
                    cnt_str    = (f"{int(cnt / 1000)}K voturi" if cnt >= 1000
                                  else (f"{cnt} voturi" if cnt else ''))
                    parts = [p for p in [status_str, year, genres_str, rt_str, rating_str, cnt_str] if p]
                    if parts:
                        self.getControl(_ID_META).setLabel('  •  '.join(parts))
            except Exception as e:
                xbmc.log(f'[SamusXUI] runtime: {e}', xbmc.LOGDEBUG)

    # ------------------------------------------------------------------ navigation

    def onAction(self, action):
        aid = action.getId()
        if aid in (ACTION_NAV_BACK, ACTION_PREV_MENU):
            self.close()
            return

        focused = self.getFocusId()
        if focused == _ID_SIDEBAR and aid in (ACTION_MOVE_UP, ACTION_MOVE_DOWN):
            xbmc.sleep(80)
            self._handle_sidebar_select()

        if focused == _ID_GENRES and aid == ACTION_MOVE_UP and not self._items:
            self.setFocusId(_ID_SIDEBAR)
            return

        if focused == _ID_GENRES and aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            xbmc.sleep(80)
            self._handle_genre_select()

        if focused == _ID_POSTERS and aid in (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            xbmc.sleep(60)
            try:
                ctrl    = self.getControl(_ID_POSTERS)
                pos     = ctrl.getSelectedPosition()
                n_items = len(self._items)
                xbmc.log(f'[SamusXUI] poster nav: aid={aid} pos={pos} last={self._last_poster_pos} n={n_items}', xbmc.LOGINFO)
                if aid == ACTION_MOVE_RIGHT:
                    if pos == 0 and self._last_poster_pos >= n_items - 1:
                        xbmc.log(f'[SamusXUI] anti-wrap: revert la {n_items-1}', xbmc.LOGINFO)
                        ctrl.selectItem(n_items - 1)
                        pos = n_items - 1
                    elif pos >= n_items - 8:
                        self._trigger_load_more()
                self._last_poster_pos = pos
            except Exception as e:
                xbmc.log(f'[SamusXUI] poster nav eroare: {e}', xbmc.LOGERROR)
            self._sync_hero_from_poster()

    def onClick(self, controlId):
        if controlId == _ID_SIDEBAR:
            self._handle_sidebar_click()
        elif controlId == _ID_PLAY:
            self._play_current()
        elif controlId == _ID_SOURCES:
            self._show_sources()
        elif controlId == _ID_DETAILS:
            self._show_details()
        elif controlId == _ID_FAV:
            if self._section == 'continue':
                self._delete_current()
            elif self._section == 'trakt':
                self._toggle_watchlist()
            else:
                self._toggle_fav()
        elif controlId == _ID_POSTERS:
            self._play_current()
        elif controlId == _ID_GENRES:
            self._handle_genre_click()
        elif controlId == _ID_SORT_BTN:
            self._cycle_filter()

    def onFocus(self, controlId):
        if controlId == _ID_POSTERS:
            xbmc.sleep(50)
            self._sync_hero_from_poster()
        else:
            # Cardul a pierdut focusul (sidebar, butoane, filtre): preview-ul
            # nu trebuie să continue în fundal.
            self._cancel_auto_trailer()

    def _sync_hero_from_poster(self):
        try:
            pos = self.getControl(_ID_POSTERS).getSelectedPosition()
            if 0 <= pos < len(self._items):
                if pos != self._hero_idx:
                    self._cancel_auto_trailer()
                    self._update_hero(pos)
                # Programează și primul card când caruselul primește focus,
                # nu numai cardurile selectate ulterior cu stânga/dreapta.
                if self._trailer_focus_idx == pos:
                    return
                self._cancel_auto_trailer()
                self._trailer_focus_idx = pos
                trailer_gen = self._trailer_gen
                xbmc.log(f'[SamusXUI] trailer focus idx={pos} token={trailer_gen}',
                         xbmc.LOGDEBUG)
                self._tasks.start(self._auto_trailer,
                                  args=(pos, trailer_gen), name='home-auto-trailer')
        except Exception:
            pass

    @staticmethod
    def _dialog_open():
        """Un dialog deschis peste HomeWindow (surse, info, filtru) NU schimbă
        focusul ferestrei de dedesubt, deci `getFocusId()` rămâne pe postere și
        numărătoarea pentru trailer merge mai departe. Fără verificarea asta,
        trailerul pornea peste lista de surse și lua playerul din mâna
        utilizatorului exact când alegea o sursă."""
        return xbmc.getCondVisibility('System.HasActiveModalDialog')

    def _auto_trailer(self, for_idx, trailer_gen):
        enabled = ADDON.getSetting('trailer_autoplay')
        xbmc.log(f'[SamusXUI] auto trailer worker idx={for_idx} token={trailer_gen} enabled={enabled}',
                 xbmc.LOGDEBUG)
        if enabled == 'false':
            return
        monitor = xbmc.Monitor()
        try:
            delay = float(ADDON.getSetting('trailer_autoplay_delay') or 5)
        except ValueError:
            delay = 5
        # Sub 2s ar porni în timpul navigării normale prin postere.
        ticks = max(20, int(delay * 10))
        for _ in range(ticks):  # pași de 100ms, ca să reacționăm imediat la mutarea focusului
            if monitor.waitForAbort(0.1):
                return
            if (trailer_gen != self._trailer_gen or self._hero_idx != for_idx
                    or self._dialog_open()):
                return
        if (monitor.abortRequested() or trailer_gen != self._trailer_gen or
                self._hero_idx != for_idx or self.getFocusId() != _ID_POSTERS or self._dialog_open()):
            return
        try:
            m = self._items[for_idx] if for_idx < len(self._items) else None
            if not m:
                return
            tmdb_id = m.get('id')
            media   = m.get('media_type') or (
                self._section if self._section in ('movie', 'tv') else 'movie')
            if not tmdb_id or media not in ('movie', 'tv'):
                return
            data = tmdb.videos(tmdb_id, media)
            # Multe titluri n-au niciun video de tip „Trailer", ci doar teasere
            # sau clipuri — filtrul strict lăsa pornirea automată fără nimic de
            # redat, deși butonul Trailer din Info (care e permisiv) mergea.
            yt   = [v for v in data.get('results', []) if v.get('site') == 'YouTube' and v.get('key')]
            key  = None
            for wanted in ('Trailer', 'Teaser', None):
                for v in yt:
                    if wanted is None or v.get('type') == wanted:
                        key = v['key']
                        break
                if key:
                    break
            if not key:
                return
            if (trailer_gen != self._trailer_gen or self._hero_idx != for_idx or
                    self.getFocusId() != _ID_POSTERS or self._dialog_open()):
                return
            from resources.lib import player as _player
            # Rezolvarea poate dura. Verificăm din nou tokenul înainte de a
            # atinge playerul, astfel un card vechi nu pornește după mutare.
            stream = _player.resolve_trailer_url(key)
            if (not stream or trailer_gen != self._trailer_gen or
                    self._hero_idx != for_idx or
                    self.getFocusId() != _ID_POSTERS or self._dialog_open()):
                return
            # Proprietatea trebuie activată înainte de play(windowed=True),
            # altfel Kodi mută focusul în FullscreenVideo și săgețile devin seek.
            trailer_player = _HomeTrailerPlayer(self, trailer_gen)
            self._trailer_player = trailer_player
            self.setProperty('trailer_active', '1')
            self.setProperty('trailer_starting', '1')
            started = _player.play_trailer(
                key, stream_url=stream, windowed=True, player=trailer_player)
            self.setProperty('trailer_starting', '')
            if not started:
                self.setProperty('trailer_active', '')
                if self._trailer_player is trailer_player:
                    self._trailer_player = None
                return
            if trailer_gen != self._trailer_gen or self._hero_idx != for_idx:
                # NB: focusul mutat de play(windowed) și dialogul modal tranzitoriu
                # ridicat de propria redare NU se verifică aici (ambele dau
                # fals-pozitiv exact la pornire); navigarea reală e prinsă sigur
                # de token (_trailer_gen) + _hero_idx. Checkpoint-urile DINAINTE
                # de play verifică în continuare focus + dialog, unde e corect.
                xbmc.Player().stop()
                self.setProperty('trailer_active', '')
                return
            # Workerul se termină aici. Pierderea focusului este tratată în
            # firul UI; finalul natural este curățat de serviciul persistent.
        except Exception as e:
            xbmc.log(f'[SamusXUI] auto_trailer: {e}', xbmc.LOGWARNING)
            self.setProperty('trailer_starting', '')
            self.setProperty('trailer_active', '')

    # ------------------------------------------------------------------ handlers

    def _handle_sidebar_click(self):
        ctrl = self.getControl(_ID_SIDEBAR)
        idx  = ctrl.getSelectedPosition()
        section = ctrl.getListItem(idx).getProperty('section')
        self._handle_sidebar_select(from_click=True)
        if section not in ('settings', 'search') and self._items:
            self.setFocusId(_ID_POSTERS)
        elif section == 'trakt' and not self._items:
            self.setFocusId(_ID_GENRES)

    def _handle_sidebar_select(self, from_click=False):
        ctrl = self.getControl(_ID_SIDEBAR)
        idx  = ctrl.getSelectedPosition()
        section = ctrl.getListItem(idx).getProperty('section')

        if section == 'settings':
            self._section = 'settings'
            self._load_gen += 1
            self._items = []
            msg = self._EMPTY_MESSAGES['settings']
            try:
                self.getControl(_ID_EMPTY_MSG).setLabel(msg)
            except Exception:
                pass
            self._set_content_visible(False)
            self._update_filter_btn()
            if from_click:
                from .settings_window import SettingsWindow
                win = SettingsWindow('settings.xml', ADDON_PATH, 'Default', '1080i')
                win.doModal()
                del win
            return

        if section == 'search':
            _prev = self._section
            self._section = 'search'
            self._load_gen += 1
            msg = self._EMPTY_MESSAGES['search']
            try:
                self.getControl(_ID_EMPTY_MSG).setLabel(msg)
            except Exception:
                pass
            self._set_content_visible(False)
            self._update_filter_btn()
            if from_click:
                self._open_search()
                _restore = _prev if _prev in ('movie', 'tv') else 'movie'
                _sidebar_idx = next(
                    (i for i, (_, s, _ic) in enumerate(_SECTIONS) if s == _restore), 0)
                self._section      = _restore
                self._genres       = self._get_genres_for_filter()
                self._active_genre = None
                try:
                    self.getControl(_ID_SIDEBAR).selectItem(_sidebar_idx)
                except Exception:
                    pass
                self._setup_genres()
                self._load_and_show()
            return

        if section == self._section:
            return

        self._section = section
        if section == 'tv':
            self._genres = self._get_genres_for_filter()
        elif section == 'favorites':
            self._genres     = list(_GENRES_FAV)
            self._fav_filter = None
        elif section == 'continue':
            self._genres      = list(_GENRES_CONT)
            self._cont_filter = None
        elif section == 'discover':
            self._genres   = _discover_mod.tag_bar(media=self._disc_media)
            self._disc_tag = self._genres[0][1] if self._genres else None
        elif section == 'trakt':
            self._genres       = list(_GENRES_TRAKT)
            self._trakt_filter = 'trending_movie'
        else:
            self._genres = self._get_genres_for_filter()

        self._active_genre = None
        self._setup_genres()
        self._load_and_show()

    def _handle_genre_click(self):
        ctrl = self.getControl(_ID_GENRES)
        genre_id = self._genres[ctrl.getSelectedPosition()][1]
        if self._section == 'trakt' and genre_id in _TRAKT_INTERACTIVE:
            # Update filter/label without loading, then show dialog
            self._trakt_filter = genre_id
            label = self._genres[ctrl.getSelectedPosition()][0]
            try:
                self.getControl(_ID_SECTION_LBL).setLabel(label)
            except Exception:
                pass
            self._handle_trakt_interactive(genre_id)
            return
        self._handle_genre_select()
        self.setFocusId(_ID_POSTERS)

    def _handle_genre_select(self):
        ctrl = self.getControl(_ID_GENRES)
        idx  = ctrl.getSelectedPosition()
        label, genre_id = self._genres[idx]
        self._mark_active_genre(idx)

        if self._section == 'favorites':
            if genre_id == self._fav_filter:
                return
            self._fav_filter = genre_id
            try:
                self.getControl(_ID_SECTION_LBL).setLabel(label)
            except Exception:
                pass
            self._load_and_show()
            return

        if self._section == 'discover':
            if genre_id == self._disc_tag:
                return
            self._disc_tag = genre_id
            try:
                self.getControl(_ID_SECTION_LBL).setLabel(label)
            except Exception:
                pass
            self._load_and_show()
            return

        if self._section == 'continue':
            if genre_id == self._cont_filter:
                return
            self._cont_filter = genre_id
            try:
                self.getControl(_ID_SECTION_LBL).setLabel(label)
            except Exception:
                pass
            self._load_and_show()
            return

        if self._section == 'trakt':
            if genre_id == self._trakt_filter:
                return
            self._trakt_filter = genre_id
            try:
                self.getControl(_ID_SECTION_LBL).setLabel(label)
            except Exception:
                pass
            if genre_id not in _TRAKT_INTERACTIVE:
                self._load_and_show()
            return

        if genre_id == self._active_genre:
            return
        self._active_genre = genre_id
        try:
            self.getControl(_ID_SECTION_LBL).setLabel(label)
        except Exception:
            pass
        self._load_and_show(genre_id=genre_id)

    def _handle_trakt_interactive(self, genre_id):
        from . import trakt as _trakt
        from .dialogs import show_trakt_auth_dialog, show_trakt_search_dialog, show_trakt_list_picker

        if genre_id == 'search_trakt':
            query, media = show_trakt_search_dialog()
            if not query:
                return
            if media == 'list':
                # Caută liste după query
                self._open_list_from_search(query)
            else:
                self._trakt_search_query = query
                self._trakt_filter = 'search_trakt'
                try:
                    self.getControl(_ID_SECTION_LBL).setLabel(f'Trakt — {query}')
                except Exception:
                    pass
                self._load_and_show()
                self.setFocusId(_ID_POSTERS)
            return

        # Liste — fetch metadata, afișează TraktListPickerDialog
        if genre_id == 'lists_mine' and not _trakt.is_authenticated():
            if not show_trakt_auth_dialog():
                return

        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
        lists = []
        try:
            if genre_id == 'lists_trending':
                raw = _trakt.get_trending_lists(limit=50) or []
                for i in raw:
                    lst = i.get('list', i)
                    lists.append({
                        'name':  lst.get('name', ''),
                        'user':  lst.get('user', {}).get('username', ''),
                        'slug':  lst.get('ids', {}).get('slug', ''),
                        'count': lst.get('item_count', 0),
                    })
            elif genre_id == 'lists_popular':
                raw = _trakt.get_popular_lists(limit=50) or []
                for i in raw:
                    lists.append({
                        'name':  i.get('name', ''),
                        'user':  i.get('user', {}).get('username', ''),
                        'slug':  i.get('ids', {}).get('slug', ''),
                        'count': i.get('item_count', 0),
                    })
            elif genre_id == 'lists_mine':
                raw = _trakt.get_my_lists() or []
                for i in raw:
                    lists.append({
                        'name':  i.get('name', ''),
                        'user':  'me',
                        'slug':  i.get('ids', {}).get('slug', ''),
                        'count': i.get('item_count', 0),
                    })
        except Exception as e:
            xbmc.log(f'[SamusXUI] _handle_trakt_interactive {genre_id}: {e}', xbmc.LOGWARNING)
        finally:
            xbmc.executebuiltin('Dialog.Close(busydialognocancel)')

        self._pick_and_load_list(lists, _TRAKT_LIST_TITLES.get(genre_id, 'Liste Trakt'))

    def _open_list_from_search(self, query):
        from . import trakt as _trakt
        from .dialogs import show_trakt_list_picker
        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
        lists = []
        try:
            raw = _trakt.search_lists(query, limit=50) or []
            for i in raw:
                # search/list returnează {'type':'list', 'score':..., 'list':{...}}
                lst = i.get('list', i)
                lists.append({
                    'name':  lst.get('name', ''),
                    'user':  lst.get('user', {}).get('username', ''),
                    'slug':  lst.get('ids', {}).get('slug', ''),
                    'count': lst.get('item_count', 0),
                })
        except Exception as e:
            xbmc.log(f'[SamusXUI] _open_list_from_search: {e}', xbmc.LOGWARNING)
        finally:
            xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
        self._pick_and_load_list(lists, f'Liste — {query}')

    def _pick_and_load_list(self, lists, title):
        from .dialogs import show_trakt_list_picker
        if not lists:
            xbmcgui.Dialog().notification('Trakt', 'Nu s-au găsit liste', xbmcgui.NOTIFICATION_WARNING, 2500)
            return
        idx = show_trakt_list_picker(lists, title)
        if idx < 0:
            return
        self._selected_list = lists[idx]
        self._trakt_filter  = 'list_items'
        try:
            self.getControl(_ID_SECTION_LBL).setLabel(lists[idx]['name'])
        except Exception:
            pass
        self._load_and_show()
        self.setFocusId(_ID_POSTERS)

    def _current_item(self):
        if not self._items:
            return None
        try:
            pos = self.getControl(_ID_POSTERS).getSelectedPosition()
            return self._items[pos] if 0 <= pos < len(self._items) else None
        except Exception:
            return self._items[self._hero_idx] if self._items else None

    def _play_current(self):
        m = self._current_item()
        if not m:
            return
        tmdb_id = m.get('id')
        media   = m.get('media_type') or (
            self._section if self._section in ('movie', 'tv') else 'movie')
        if media == 'adult':
            title = m.get('title') or m.get('name', '')
            xbmc.executebuiltin(
                f'PlayMedia(plugin://plugin.video.samusxui'
                f'?action=play_asa'
                f'&asa_id={urllib.parse.quote(str(tmdb_id), safe="")}'
                f'&title={urllib.parse.quote(title, safe="")})')
            return
        if media == 'tv':
            if self._section == 'continue':
                season  = m.get('season')
                episode = m.get('episode')
                if season is not None and episode is not None:
                    xbmc.executebuiltin(
                        f'PlayMedia(plugin://plugin.video.samusxui'
                        f'?action=play_episode&tv_id={tmdb_id}'
                        f'&season={season}&episode={episode})')
                    return
            self._open_seasons(tmdb_id)
        else:
            xbmc.executebuiltin(
                f'PlayMedia(plugin://plugin.video.samusxui'
                f'?action=play_movie&tmdb_id={tmdb_id})')

    def _open_seasons(self, tmdb_id):
        from .seasons_window import SeasonsWindow
        show = tmdb.tv_details(tmdb_id)
        if not show or not show.get('seasons'):
            xbmcgui.Dialog().notification('SamusXUI', 'Nu s-au găsit sezoane.', xbmcgui.NOTIFICATION_INFO)
            return
        win = SeasonsWindow('tv_seasons.xml', ADDON_PATH, 'Default', '1080i')
        win._tv_id = tmdb_id
        win._show  = show
        win.doModal()
        del win

    def _show_sources(self):
        m = self._current_item()
        if not m:
            return
        tmdb_id = m.get('id')
        media   = m.get('media_type') or (
            self._section if self._section in ('movie', 'tv') else 'movie')
        if media == 'adult':
            title = m.get('title') or m.get('name', '')
            xbmc.executebuiltin(
                f'PlayMedia(plugin://plugin.video.samusxui'
                f'?action=play_asa'
                f'&asa_id={urllib.parse.quote(str(tmdb_id), safe="")}'
                f'&title={urllib.parse.quote(title, safe="")})')
            return
        if media == 'tv':
            if self._section == 'continue':
                season  = m.get('season')
                episode = m.get('episode')
                if season is not None and episode is not None:
                    xbmc.executebuiltin(
                        f'PlayMedia(plugin://plugin.video.samusxui'
                        f'?action=play_episode&tv_id={tmdb_id}'
                        f'&season={season}&episode={episode}&show_sources=1)')
                    return
            self._open_seasons(tmdb_id)
        else:
            xbmc.executebuiltin(
                f'PlayMedia(plugin://plugin.video.samusxui'
                f'?action=play_movie&tmdb_id={tmdb_id}&show_sources=1)')

    def _show_details(self):
        m = self._current_item()
        if not m:
            return
        tmdb_id = m.get('id')
        media   = m.get('media_type') or (
            self._section if self._section in ('movie', 'tv') else 'movie')
        xbmc.executebuiltin(
            f'RunPlugin(plugin://plugin.video.samusxui'
            f'?action=show_info&tmdb_id={tmdb_id}&media_type={media})')

    def _cycle_filter(self):
        if self._section == 'discover':
            self._disc_media = 'tv' if self._disc_media == 'movie' else 'movie'
            # Tag-urile deduse se filtrează după câte titluri au *în tipul curent*,
            # deci bara trebuie recalculată; păstrăm eticheta selectată dacă e și
            # în lista nouă, altfel cade pe prima.
            self._genres = _discover_mod.tag_bar(media=self._disc_media)
            ids = [g for _, g in self._genres]
            if self._disc_tag not in ids:
                self._disc_tag = ids[0] if ids else None
            self._active_genre = self._disc_tag
            self._setup_genres()
            self._update_filter_btn()
            self._load_and_show()
            return
        idx = _FILTER_TYPES.index(self._filter_type)
        self._filter_type  = _FILTER_TYPES[(idx + 1) % len(_FILTER_TYPES)]
        self._genres       = self._get_genres_for_filter()
        self._active_genre = self._genres[0][1]
        self._setup_genres()
        self._load_and_show(genre_id=self._active_genre)

    def _toggle_fav(self):
        m = self._current_item()
        if not m:
            return
        tmdb_id = m.get('id')
        media   = m.get('media_type') or (
            self._section if self._section in ('movie', 'tv') else 'movie')
        title   = m.get('title') or m.get('name', '')
        year    = (m.get('release_date') or m.get('first_air_date') or '')[:4]
        poster  = m.get('poster_path') or ''
        plot    = m.get('overview') or ''

        if (tmdb_id, media) in self._fav_ids:
            db.remove_favorite(tmdb_id, media)
            self._fav_ids.discard((tmdb_id, media))
        else:
            db.add_favorite(tmdb_id, media, title, year, poster, plot)
            self._fav_ids.add((tmdb_id, media))

        is_fav = (tmdb_id, media) in self._fav_ids
        try:
            self.getControl(_ID_FAV).setLabel('FAVORIT')
            icon = self.getControl(_ID_FAV_ICON)
            icon.setVisible(True)
            icon.setColorDiffuse('FFFFD700' if is_fav else 'FF888899')
        except Exception:
            pass
        try:
            pos  = self.getControl(_ID_POSTERS).getSelectedPosition()
            item = self.getControl(_ID_POSTERS).getListItem(pos)
            item.setProperty('fav_star', '1' if is_fav else '')
        except Exception:
            pass

    def _toggle_watchlist(self):
        m = self._current_item()
        if not m:
            return
        from . import trakt as _trakt
        if not _trakt.is_authenticated():
            xbmcgui.Dialog().notification('Trakt', 'Necesită autentificare', xbmcgui.NOTIFICATION_WARNING, 2500)
            return
        tmdb_id = m.get('id')
        media   = m.get('media_type', 'movie')
        if self._trakt_filter in ('watchlist_movie', 'watchlist_tv'):
            self._tasks.start(self._do_watchlist_remove,
                              args=(tmdb_id, media), name='home-watchlist-remove')
        else:
            self._tasks.start(self._do_watchlist_add,
                              args=(tmdb_id, media), name='home-watchlist-add')

    def _do_watchlist_add(self, tmdb_id, media):
        from . import trakt as _trakt
        result = _trakt.add_to_watchlist(media, tmdb_id)
        if result:
            xbmcgui.Dialog().notification('Trakt', 'Adăugat în Watchlist', xbmcgui.NOTIFICATION_INFO, 2000)
            try:
                self.getControl(_ID_FAV).setLabel('+ WATCHLIST')
            except Exception:
                pass

    def _do_watchlist_remove(self, tmdb_id, media):
        from . import trakt as _trakt
        result = _trakt.remove_from_watchlist(media, tmdb_id)
        if result:
            try:
                pos = self.getControl(_ID_POSTERS).getSelectedPosition()
                if 0 <= pos < len(self._items):
                    self._items.pop(pos)
            except Exception:
                pass
            self._populate_posters()

    def _delete_current(self):
        m = self._current_item()
        if not m:
            return
        tmdb_id = m.get('id')
        media   = m.get('media_type', 'movie')
        db.remove_continue(tmdb_id, media)
        try:
            pos = self.getControl(_ID_POSTERS).getSelectedPosition()
            if 0 <= pos < len(self._items):
                self._items.pop(pos)
        except Exception:
            pass
        self._populate_posters()

    def _open_search(self):
        from .settings_window import CustomKeyboard
        from .search_window import SearchWindow
        from .search_results_window import SearchResultsWindow

        kb = CustomKeyboard(title='Căutare')
        kb.doModal()
        xbmc.executebuiltin('Dialog.Close(virtualkeyboard)')
        xbmc.sleep(50)
        xbmc.executebuiltin('Dialog.Close(virtualkeyboard)')
        query = kb.result
        del kb
        if not query:
            return

        win = SearchWindow('search.xml', ADDON_PATH, 'Default', '1080i')
        win._query_text = query
        win.doModal()
        media = win._media
        del win

        if not media:
            return

        try:
            data = tmdb.search(media, query, page=1)
        except Exception as e:
            xbmc.log(f'[SamusXUI] search error: {e}', xbmc.LOGWARNING)
            data = {}

        results = SearchResultsWindow('results.xml', ADDON_PATH, 'Default', '1080i')
        results._query       = query
        results._media       = media
        results._items       = data.get('results', [])
        results._total_pages = data.get('total_pages', 1)
        results.doModal()
        del results
