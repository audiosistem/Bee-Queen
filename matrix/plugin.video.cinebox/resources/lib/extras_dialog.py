# -*- coding: utf-8 -*-
import xbmcgui
import xbmc
import json
import urllib.parse
from xbmcaddon import Addon
import xbmcvfs

ADDON = Addon('plugin.video.cinebox')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))

MOVIE_DETAILS_ENABLED = ADDON.getSettingBool("movie.enable_details")
TVSHOW_DETAILS_ENABLED = ADDON.getSettingBool("tvshow.enable_details")
# AUTOPLAY removed from here to be read in real time in function _play and other calls

# === LOGOS CACHE (OPTIMIZED) ===
_PROVIDER_LOGOS = {
    "hulu": "hulu.png",
    "netflix": "netflix.png",
    "amazon video": "prime_video.png",
    "amazon prime": "prime_video.png",
    "amazon prime video": "prime_video.png",
    "prime video": "prime_video.png",
    "primevideo": "prime_video.png",
    "disney plus": "disney_plus.png",
    "hbo max": "hbo_max.png",
    "max": "hbo_max.png",
    "apple tv+": "apple_tv.png",
    "apple tv plus": "apple_tv.png",
    "paramount plus": "paramount_plus.png",
    "paramount plus amazon channel": "paramount_plus.png",
    "crunchyroll": "crunchyroll.png",
    "movistar plus": "movistar_plus.png",
    "globoplay": "globoplay.png",
    "claro tv+": "claro_tv.png",
    "claro tv": "claro_tv.png",
    "claro tv plus": "claro_tv.png",
    "claro video": "claro_tv.png",
    "telecine": "telecine.png",
    "looke": "looke.png",
    "google play movies": "google_play.png",
    "adult swim": "adult_swim.png",
}

_LOGO_PATHS = {}

def _init_logo_cache():
    """Initialize logo cache (runs 1x on import)"""
    for k, logo in _PROVIDER_LOGOS.items():
        path = xbmcvfs.translatePath(f"{ADDON_PATH}/resources/logos/{logo}")
        if xbmcvfs.exists(path):
            _LOGO_PATHS[k] = path

_init_logo_cache()

def get_logo_path(provider):
    """Returns logo path (with cache)"""
    if not provider:
        return ""
    return _LOGO_PATHS.get(provider.lower(), "")

# === DETAILS DIALOG ===
class CineboxDetailsWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta = kwargs.get('meta', {})
        self.is_tvshow = self.meta.get('media_type') == 'tvshow'
        self.has_collection = bool(self.meta.get('collection'))
        
        # Setup BEFORE the first frame
        self._setup_properties()
    
    def _setup_properties(self):
        """Sets dialog properties (snapshot)"""
        m = self.meta
        
        # Basic properties
        self.setProperty("media_type", "tvshow" if self.is_tvshow else "movie")
        self.setProperty("title", m.get("title", ""))
        self.setProperty("poster", m.get("poster", ""))
        self.setProperty("backdrop", m.get("backdrop", ""))
        self.setProperty("year", m.get("year_str", ""))
        self.setProperty("duration", m.get("duration_str", ""))
        self.setProperty("plot", m.get("synopsis", ""))
        self.setProperty("clearlogo", m.get("clearlogo", ""))
        self.setProperty("FavoriteLabel", "Add to List")
        self.setProperty("HasCollection", "true" if self.has_collection else "false")
        self.setProperty("Collection.Label", str(m.get("collection", "")))
        self.setProperty("tmdb_id", str(m.get("tmdb_id", "")))
        
        # Genres (max 3)
        for i, g in enumerate(m.get('genre_list', []), 1):
            self.setProperty(f"Genre.{i}.Label", g)
        
        # Providers (max 4)
        for i, prov in enumerate(m.get('provider_data', []), 1):
            self.setProperty(f"Provider.{i}.Label", prov['name'])
            self.setProperty(f"Provider.{i}.Icon", prov['icon'])
    
    def onInit(self):
        """Initialization (only sets focus)"""
        self.set_focus_immediate()
    
    def set_focus_immediate(self):
        """Sets focus on the correct button"""
        if self.is_tvshow:
            ids = [321, 303, 10]
        elif self.has_collection:
            ids = [311, 301, 10]
        else:
            ids = [301, 10]
        
        for i in ids:
            try:
                self.setFocusId(i)
                break
            except:
                pass
    
    def onClick(self, controlID):
        """Click handler"""
        try:
            tmdb_id = self.meta.get("tmdb_id")
            media_type = "tvshow" if self.is_tvshow else "movie"
            
            # play buttons
            if controlID in (301, 311):
                self.close()
                self._play(True)
            
            elif controlID in (302, 312):
                self.close()
                self._play(False)
            
            # List seasons (series)
            elif controlID in (303, 321) and self.is_tvshow:
                self.close()
                self._open_container(
                    f"plugin://plugin.video.cinebox?"
                    f"action=list_seasons&tvshow_tmdb_id={tmdb_id}"
                )
            
            # List collection (films)
            elif controlID in (304, 313) and self.has_collection:
                self.close()
                collection = urllib.parse.quote_plus(str(self.meta.get("collection", "")))
                self._open_container(
                    f"plugin://plugin.video.cinebox?"
                    f"action=list_movies_by_collection&collection={collection}"
                )
            
            # Favorite toggle
            elif controlID in (305, 315, 322):
                self._toggle_favorite(tmdb_id, media_type)
            
            # Click Genre (400-409)
            elif 400 < controlID < 410:
                idx = controlID - 401
                genres = self.meta.get('genre_list', [])
                if idx < len(genres):
                    genre = urllib.parse.quote_plus(genres[idx])
                    action = "list_tvshows_by_genre" if self.is_tvshow else "list_movies_by_genre"
                    self._open_container(
                        f"plugin://plugin.video.cinebox?"
                        f"action={action}&genre={genre}"
                    )
            
            # Click Provider (500-509)
            elif 500 < controlID < 510:
                idx = controlID - 501
                providers = self.meta.get('provider_data', [])
                if idx < len(providers):
                    provider = urllib.parse.quote_plus(providers[idx]['name'])
                    action = "list_tvshows_by_provider" if self.is_tvshow else "list_movies_by_provider"
                    self._open_container(
                        f"plugin://plugin.video.cinebox?"
                        f"action={action}&provider={provider}"
                    )
        
        except Exception as e:
            xbmc.log(f"[Cinebox] onClick error: {e}", xbmc.LOGERROR)
    
    def _open_container(self, url):
        """Open container (close dialog first)"""
        self.close()
        xbmc.executebuiltin(f"Container.Update({url})")
    
    def _play(self, autoplay):
        """Start playback"""
        from resources.lib import navigation
        # ✅ FIX: Pass season and episode explicitly if available in the meta
        navigation.find_and_play_sources(
            self.meta, 
            autoplay=autoplay,
            season=self.meta.get('season'),
            episode=self.meta.get('episode')
        )
    
    def _toggle_favorite(self, tmdb_id, media_type):
        """Add/remove favorite (optimized)"""
        from resources.lib.favorites import add_item_to_favorites, remove_item_from_favorites
        from resources.lib.db import db
        
        # Use is_favorite() helper if available
        try:
            is_fav = db.is_favorite(tmdb_id, media_type)
            if is_fav:
                remove_item_from_favorites(tmdb_id, media_type)
            else:
                add_item_to_favorites(tmdb_id, media_type)
        except AttributeError:
            # Fallback for direct query
            conn = db._get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM favorites WHERE tmdb_id=? AND media_type=? LIMIT 1",
                (tmdb_id, media_type)
            )
            exists = cur.fetchone()
            db._release_conn(conn)
            
            if exists:
                remove_item_from_favorites(tmdb_id, media_type)
            else:
                add_item_to_favorites(tmdb_id, media_type)
    
    def onAction(self, action):
        """Action handler (back, esc)"""
        if action.getId() in (10, 92, xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()

# === METADATA PREPARATION ===
def _prepare_common_meta(item_data):
    """Prepares common metadata (OPTIMIZED).
    Avoid regex, use utils.py function."""
    meta = item_data.copy()
    
    # === GENRES (limits to 3) ===
    raw_genres = meta.get("genre", "")
    if isinstance(raw_genres, str):
        meta['genre_list'] = [g.strip() for g in raw_genres.split(",") if g.strip()][:3]
    else:
        meta['genre_list'] = []
    
    # === POSTER (uses scale_tmdb from utils.py) ===
    poster = meta.get("poster", "")
    if poster and 'image.tmdb.org' in poster:
        # Import optimized function
        from resources.lib.utils import scale_tmdb
        meta["poster"] = scale_tmdb(poster, "original")
    
    # === YEAR ===
    meta["year_str"] = str(meta.get("year", ""))
    
    # === PROVIDERS (max 4, no duplicates) ===
    providers = meta.get("providers", [])
    if isinstance(providers, str):
        try:
            providers = json.loads(providers)
        except:
            providers = []
    
    meta['provider_data'] = []
    seen_logos = set()
    
    for p in providers:
        logo = get_logo_path(p)
        if logo and logo not in seen_logos:
            meta['provider_data'].append({'name': p, 'icon': logo})
            seen_logos.add(logo)
            if len(meta['provider_data']) >= 4:
                break
    
    return meta

# === PUBLIC FUNCTIONS ===
def show_details_movie(item_data):
    """Shows movie details"""
    if not item_data:
        return
    
    meta = _prepare_common_meta(item_data)
    meta['media_type'] = 'movie'
    meta["duration_str"] = f"{int(meta.get('runtime', 0))} min" if meta.get('runtime') else ""
    meta['streams'] = item_data.get('streams', [])
    
    win = CineboxDetailsWindow(
        "CineboxDetails.xml",
        ADDON_PATH,
        "Default",
        "1080i",
        meta=meta
    )
    win.doModal()
    del win

def show_details_tvshow(item_data):
    """Show series details"""
    if not item_data:
        return
    
    meta = _prepare_common_meta(item_data)
    meta['media_type'] = 'tvshow'
    meta["duration_str"] = ""
    meta['total_seasons'] = item_data.get('total_seasons')
    meta['status'] = item_data.get('status')
    
    win = CineboxDetailsWindow(
        "CineboxDetails.xml",
        ADDON_PATH,
        "Default",
        "1080i",
        meta=meta
    )
    win.doModal()
    del win

def show_details(item_data):
    """Main Dispatcher.
    Decide whether to show dialog or jump straight to play/list."""
    if not item_data:
        return
    
    media_type = item_data.get("media_type")
    
    # === MOVIES ===
    if media_type == "movie":
        if not MOVIE_DETAILS_ENABLED:
            # Skip to direct play
            from resources.lib import navigation
            navigation.find_and_play_sources(
                item_data, 
                autoplay=ADDON.getSettingBool("playback.autoplay"),
                season=item_data.get('season'),
                episode=item_data.get('episode')
            )
        else:
            # Show dialog
            show_details_movie(item_data)
        return
    
    # === SERIES ===
    if media_type == "tvshow":
        # If there is a season and episode, it is a direct episode (e.g. via TMDbHelper)
        if item_data.get('season') and item_data.get('episode'):
            if not TVSHOW_DETAILS_ENABLED:
                from resources.lib import navigation
                navigation.find_and_play_sources(
                    item_data, 
                    autoplay=ADDON.getSettingBool("playback.autoplay"),
                    season=item_data.get('season'),
                    episode=item_data.get('episode')
                )
                return
        
        if not TVSHOW_DETAILS_ENABLED:
            # Skip to season list
            tmdb_id = item_data.get("tmdb_id")
            xbmc.executebuiltin(
                f"Container.Update("
                f"plugin://plugin.video.cinebox?"
                f"action=list_seasons&tvshow_tmdb_id={tmdb_id})"
            )
        else:
            # Show dialog
            show_details_tvshow(item_data)
        return