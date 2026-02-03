# -*- coding: utf-8 -*-
"""Integration with Kodi Library - FIXED VERSION ANDROID/TV
Complete .strm and .nfo management with accessible paths"""

import os
import json
import shutil
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()

# === SETTINGS - ACCESSIBLE PATHS ===
def get_library_paths():
    """Returns library paths (Android/TV compatible)"""
    
    # Uses paths ACCESSIBLE through Kodi (settings removed)
    addon_profile = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    movies_path = os.path.join(addon_profile, 'library', 'movies')
    tvshows_path = os.path.join(addon_profile, 'library', 'tvshows')
    
    # Ensures paths are translated
    movies_path = xbmcvfs.translatePath(movies_path)
    tvshows_path = xbmcvfs.translatePath(tvshows_path)
    
    return movies_path, tvshows_path

def ensure_library_folders():
    """Create library folders if they don't exist"""
    movies_path, tvshows_path = get_library_paths()
    
    for path in [movies_path, tvshows_path]:
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)
            xbmc.log(f"[Library] Folder created: {path}", xbmc.LOGINFO)
    
    return movies_path, tvshows_path

def check_library_access():
    """Check if Kodi can access library folders"""
    movies_path, tvshows_path = get_library_paths()
    
    test_file_movie = os.path.join(movies_path, '.test')
    test_file_tv = os.path.join(tvshows_path, '.test')
    
    try:
        # Test writing in films
        with open(test_file_movie, 'w') as f:
            f.write('test')
        xbmcvfs.delete(test_file_movie)
        
        # Test writing in series
        with open(test_file_tv, 'w') as f:
            f.write('test')
        xbmcvfs.delete(test_file_tv)
        
        return True
    except Exception as e:
        xbmc.log(f"[Library] ACCESS ERROR: {e}", xbmc.LOGERROR)
        return False

def setup_library_sources():
    """Add library folders as sources in Kodi"""
    movies_path, tvshows_path = get_library_paths()
    
    # Check if you need to configure
    sources_xml = xbmcvfs.translatePath('special://userdata/sources.xml')
    
    # Create sources.xml if it doesn't exist
    if not xbmcvfs.exists(sources_xml):
        sources_content = '''<sources>
    <programs>
        <default pathversion="1"></default>
    </programs>
    <video>
        <default pathversion="1"></default>
    </video>
    <music>
        <default pathversion="1"></default>
    </music>
    <pictures>
        <default pathversion="1"></default>
    </pictures>
    <files>
        <default pathversion="1"></default>
    </files>
    <games>
        <default pathversion="1"></default>
    </games>
</sources>'''
        try:
            with open(sources_xml, 'w', encoding='utf-8') as f:
                f.write(sources_content)
        except:
            pass
    
    # Message to the user
    dialog = xbmcgui.Dialog()
    dialog.ok(
        "Set Up Library",
        f"[B]IMPORTANTE:[/B] Add these folders to Kodi:",
        f"[B]Movies:[/B] {movies_path}",
        f"[B]TV Shows:[/B] {tvshows_path}"
    )
    
    return True

def sanitize_filename(name):
    """Remove invalid characters"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.strip()

# === OPERATIONS WITH KODI (JSON-RPC) ===
def get_all_library_movies():
    """Fetch ALL movies from Kodi library via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetMovies",
        "params": {"properties": ["file"]},
        "id": 1
    }
    result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
    return result.get('result', {}).get('movies', [])

def get_all_library_tvshows():
    """Fetches ALL series from the Kodi library via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetTVShows",
        "params": {"properties": ["file"]},
        "id": 1
    }
    result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
    return result.get('result', {}).get('tvshows', [])

def remove_movie_from_kodi(movieid):
    """Remove movies from library to Kodi via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.RemoveMovie",
        "params": {"movieid": movieid},
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(query))

def remove_tvshow_from_kodi(tvshowid):
    """Remove series from Kodi library via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.RemoveTVShow",
        "params": {"tvshowid": tvshowid},
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(query))

# === FILE CREATION ===
def create_strm_file(filepath, plugin_url):
    """Create .strm file"""
    try:
        directory = os.path.dirname(filepath)
        if not xbmcvfs.exists(directory):
            xbmcvfs.mkdirs(directory)
        
        # Use translated path
        translated_path = xbmcvfs.translatePath(filepath)
        
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(plugin_url)
        
        # Check if it was created
        if not xbmcvfs.exists(filepath):
            xbmc.log(f"[Library] WARNING: .strm was not created: {filepath}", xbmc.LOGWARNING)
            return False
        
        return True
    except Exception as e:
        xbmc.log(f"[Library] Error creating .strm: {e}", xbmc.LOGERROR)
        return False

def create_movie_nfo(filepath, movie_data):
    """Create .nfo for movie"""
    try:
        nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>{movie_data.get('title', '')}</title>
    <originaltitle>{movie_data.get('original_title', '')}</originaltitle>
    <rating>{movie_data.get('rating', 0.0)}</rating>
    <year>{movie_data.get('year', '')}</year>
    <plot>{movie_data.get('synopsis', '')}</plot>
    <runtime>{movie_data.get('runtime', 0)}</runtime>
    <thumb>{movie_data.get('poster', '')}</thumb>
    <fanart>{movie_data.get('backdrop', '')}</fanart>
    <uniqueid type="tmdb" default="true">{movie_data.get('tmdb_id', '')}</uniqueid>
    <uniqueid type="imdb">{movie_data.get('imdb_id', '')}</uniqueid>"""
        genres = movie_data.get('genres', [])
        if isinstance(genres, list):
            for genre in genres:
                nfo_content += f"    <genre>{genre}</genre>\n"
        nfo_content += "</movie>"
        
        translated_path = xbmcvfs.translatePath(filepath)
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        return True
    except Exception as e:
        xbmc.log(f"[Library] Error creating .nfo: {e}", xbmc.LOGERROR)
        return False

def create_tvshow_nfo(filepath, show_data):
    """Create .nfo for series"""
    try:
        nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
    <title>{show_data.get('title', '')}</title>
    <originaltitle>{show_data.get('original_title', '')}</originaltitle>
    <rating>{show_data.get('rating', 0.0)}</rating>
    <year>{show_data.get('year', '')}</year>
    <plot>{show_data.get('synopsis', '')}</plot>
    <thumb>{show_data.get('poster', '')}</thumb>
    <fanart>{show_data.get('backdrop', '')}</fanart>
    <uniqueid type="tmdb" default="true">{show_data.get('tmdb_id', '')}</uniqueid>
    <uniqueid type="imdb">{show_data.get('imdb_id', '')}</uniqueid>"""
        genres = show_data.get('genres', [])
        if isinstance(genres, list):
            for genre in genres:
                nfo_content += f"    <genre>{genre}</genre>\n"
        nfo_content += "</tvshow>"
        
        translated_path = xbmcvfs.translatePath(filepath)
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        return True
    except Exception as e:
        xbmc.log(f"[Library] Error creating tvshow.nfo: {e}", xbmc.LOGERROR)
        return False

def create_episode_nfo(filepath, episode_data, show_data):
    """Create .nfo for episode"""
    try:
        nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
    <title>{episode_data.get('name', '')}</title>
    <showtitle>{show_data.get('title', '')}</showtitle>
    <season>{episode_data.get('season_number', 1)}</season>
    <episode>{episode_data.get('episode_number', 1)}</episode>
    <plot>{episode_data.get('overview', '')}</plot>
    <aired>{episode_data.get('air_date', '')}</aired>
    <rating>{episode_data.get('vote_average', 0.0)}</rating>
    <thumb>{episode_data.get('still_path', '')}</thumb>
    <uniqueid type="tmdb" default="true">{show_data.get('tmdb_id', '')}</uniqueid>
</episodedetails>"""
        
        translated_path = xbmcvfs.translatePath(filepath)
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        return True
    except Exception as e:
        xbmc.log(f"[Library] Error creating episode.nfo: {e}", xbmc.LOGERROR)
        return False

import urllib.parse

import urllib.parse
import xbmc, xbmcgui, xbmcvfs, os

# === VERIFICATION HELPERS ===

def is_in_library(movie_data, media_type):
    """Checks if the item already exists in the physical library (Quick)"""
    try:
        movies_path, tvshows_path = get_library_paths()
        title = sanitize_filename(movie_data.get('title', 'Unknown'))
        
        if media_type == 'movie':
            year = movie_data.get('year', '')
            folder_name = f"{title} ({year})" if year else title
            check_path = os.path.join(movies_path, folder_name)
        else:
            check_path = os.path.join(tvshows_path, title)
            
        return xbmcvfs.exists(check_path)
    except:
        return False

# === ADD TO LIBRARY ===

def add_movie_to_library(movie_data, show_notification=True):
    """Add movie to library by including artwork in the plugin URL"""
    try:
        movies_path, _ = ensure_library_folders()
        
        title = sanitize_filename(movie_data.get('title', 'Unknown'))
        year = movie_data.get('year', '')
        folder_name = f"{title} ({year})" if year else title
        movie_folder = os.path.join(movies_path, folder_name)
        
        if not xbmcvfs.exists(movie_folder):
            xbmcvfs.mkdirs(movie_folder)

        # Extraction of the arts
        poster = movie_data.get('poster', '')
        backdrop = movie_data.get('backdrop', '') or movie_data.get('fanart', '')
        clearlogo = movie_data.get('clearlogo', '')

        plugin_url = (
            f"plugin://plugin.video.cinebox/"
            f"?action=find_sources"
            f"&media_type=movie"
            f"&tmdb_id={movie_data.get('tmdb_id')}"
            f"&imdb_id={movie_data.get('imdb_id', '')}"
            f"&title={urllib.parse.quote_plus(str(movie_data.get('title', '')))}"
            f"&year={year}"
            f"&poster={urllib.parse.quote_plus(str(poster))}"
            f"&backdrop={urllib.parse.quote_plus(str(backdrop))}"
            f"&clearlogo={urllib.parse.quote_plus(str(clearlogo))}"
        )
        
        strm_file = os.path.join(movie_folder, f"{folder_name}.strm")
        nfo_file = os.path.join(movie_folder, "movie.nfo")
        
        if not create_strm_file(strm_file, plugin_url): return False
        if not create_movie_nfo(nfo_file, movie_data): return False
        
        if show_notification:
            xbmcgui.Dialog().notification("Library", f"{title} added!", xbmcgui.NOTIFICATION_INFO, 3000)
        
        xbmc.log(f"[Library] Movie added: {title}", xbmc.LOGINFO)
        return True
        
    except Exception as e:
        xbmc.log(f"[Library] Error adding movie: {e}", xbmc.LOGERROR)
        return False

def add_tvshow_to_library(show_data, show_notification=True):
    """Add series to library"""
    try:
        _, tvshows_path = ensure_library_folders()
        
        raw_title = show_data.get('title', 'Unknown')
        title = sanitize_filename(raw_title)
        show_folder = os.path.join(tvshows_path, title)
        
        if not xbmcvfs.exists(show_folder):
            xbmcvfs.mkdirs(show_folder)
        
        if show_notification:
            xbmcgui.Dialog().notification("Library", f"Synchronizing:{raw_title}", xbmcgui.NOTIFICATION_INFO, 2000)

        tvshow_nfo = os.path.join(show_folder, "tvshow.nfo")
        if not create_tvshow_nfo(tvshow_nfo, show_data):
            return False
        
        from resources.lib.db import db
        from resources.lib.tmdb_api import get_tvshow_seasons, get_season_episodes
        
        tmdb_id = show_data.get('tmdb_id')
        seasons = db.get_cached_seasons(tmdb_id) or get_tvshow_seasons(tmdb_id) or []
        
        episodes_added = 0
        
        # Optimization: Encoding the arts once outside the loop
        poster = urllib.parse.quote_plus(str(show_data.get('poster', '')))
        backdrop = urllib.parse.quote_plus(str(show_data.get('backdrop', '') or show_data.get('fanart', '')))
        clearlogo = urllib.parse.quote_plus(str(show_data.get('clearlogo', '')))
        encoded_title = urllib.parse.quote_plus(str(raw_title))

        for season in seasons:
            season_number = season.get('season_number', 0)
            if season_number == 0: continue
            
            season_folder = os.path.join(show_folder, f"Season {str(season_number).zfill(2)}")
            if not xbmcvfs.exists(season_folder):
                xbmcvfs.mkdirs(season_folder)
            
            episodes = db.get_cached_episodes(tmdb_id, season_number) or get_season_episodes(tmdb_id, season_number) or []
            
            for episode in episodes:
                ep_number = episode.get('episode_number', 0)
                ep_name = f"S{str(season_number).zfill(2)}E{str(ep_number).zfill(2)}"
                
                plugin_url = (
                    f"plugin://plugin.video.cinebox/?action=find_sources&media_type=tvshow"
                    f"&tmdb_id={tmdb_id}&imdb_id={show_data.get('imdb_id', '')}&title={encoded_title}"
                    f"&poster={poster}&backdrop={backdrop}&clearlogo={clearlogo}"
                    f"&season={season_number}&episode={ep_number}"
                )
                
                strm_file = os.path.join(season_folder, f"{ep_name}.strm")
                nfo_file = os.path.join(season_folder, f"{ep_name}.nfo")
                
                if create_strm_file(strm_file, plugin_url):
                    create_episode_nfo(nfo_file, episode, show_data)
                    episodes_added += 1
        
        if show_notification:
            xbmcgui.Dialog().notification("Library", f"{raw_title} completed!", xbmcgui.NOTIFICATION_INFO, 3000)
        xbmc.log(f"[Library] Series added: {title} ({episodes_added} episodes)", xbmc.LOGINFO)
        return True
        
    except Exception as e:
        xbmc.log(f"[Library] Error adding series: {e}", xbmc.LOGERROR)
        return False

# === SYNC LIBRARY (USED BY SERVICE.PY) ===
    
def sync_library_silently():
    """Checks local bank and ensures everything is in the physical library without alerts"""
    from resources.lib.db import db
    
    # 1. Sync Movies
    all_movies = db.get_all_movie_ids_set()
    for tmdb_id in all_movies:
        movie_data = db.get_movie_by_id(tmdb_id)
        if movie_data and not is_in_library(movie_data, 'movie'):
            add_movie_to_library(movie_data, show_notification=False)

    # 2. Sync TV Shows
    all_series = db.get_all_tvshow_ids_set()
    for tmdb_id in all_series:
        show_data = db.get_tvshow_by_id(tmdb_id)
        if show_data and not is_in_library(show_data, 'tvshow'):
            add_tvshow_to_library(show_data, show_notification=False)
    

# === CLEAN UP LIBRARY (REFACTORED) ===
def clear_library():
    """Remove ALL items from library (FULL method fixed)"""
    if not xbmcgui.Dialog().yesno(
        "Limpar Library",
        "ATTENTION: This will DELETE EVERYTHING from the library!",
        "Are you sure?"
    ):
        return False
    
    progress = xbmcgui.DialogProgressBG()
    progress.create("Cleaning Library", "Starting...")
    
    try:
        # === STEP 0: Stop scanners ===
        progress.update(5, message="Stopping scanners...")
        xbmc.executebuiltin('CancelLibraryScan')
        xbmc.sleep(1000)
        
        # === STEP 1: Remove from Kodi library (full JSON-RPC) ===
        progress.update(10, message="Removing movies from Kodi...")
        
        # Remove ALL movies (not just from Cinebox)
        movies = get_all_library_movies()
        for idx, movie in enumerate(movies):
            progress.update(10 + int((idx/len(movies))*20) if movies else 10, 
                          message=f"Removing movie{idx+1}/{len(movies)}...")
            remove_movie_from_kodi(movie['movieid'])
            xbmc.sleep(50)
        
        progress.update(30, message="Removing series from Kodi...")
        
        # Remove ALL series
        tvshows = get_all_library_tvshows()
        for idx, tvshow in enumerate(tvshows):
            progress.update(30 + int((idx/len(tvshows))*20) if tvshows else 30,
                          message=f"Removing series {idx+1}/{len(tvshows)}...")
            remove_tvshow_from_kodi(tvshow['tvshowid'])
            xbmc.sleep(100)  # More time for series
        
        # === STEP 2: Clean Kodi database ===
        progress.update(50, message="Cleaning database...")
        
        # Command to clean database completely
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "VideoLibrary.Clean",
            "params": {"showdialogs": False},
            "id": 1
        }))
        xbmc.sleep(2000)
        
        # === STEP 3: DELETE physical files COMPLETELY ===
        progress.update(60, message="Deleting files...")
        
        movies_path, tvshows_path = get_library_paths()
        
        # Robust removal function
        def force_delete_folder(path):
            try:
                if xbmcvfs.exists(path):
                    # Try deleting via shutil first
                    shutil.rmtree(xbmcvfs.translatePath(path), ignore_errors=True)
                    xbmc.sleep(500)
                    
                    # Try deleting file by file
                    dirs, files = xbmcvfs.listdir(path)
                    for file in files:
                        try:
                            xbmcvfs.delete(os.path.join(path, file))
                        except:
                            pass
                    
                    # Try deleting again
                    if xbmcvfs.exists(path):
                        xbmcvfs.rmdir(path, force=True)
            except:
                pass
        
        force_delete_folder(movies_path)
        force_delete_folder(tvshows_path)
        
        # Recreate empty folders
        xbmcvfs.mkdirs(movies_path)
        xbmcvfs.mkdirs(tvshows_path)
        
        # === STEP 4: AGGRESSIVE cache cleaning ===
        progress.update(75, message="Cleaning deep caches...")
        
        # Clears various types of cache
        cache_paths = [
            'special://temp/archive_cache/',
            'special://temp/library/',
            'special://userdata/Thumbnails/',
            'special://userdata/Database/Textures*.db'
        ]
        
        for cache_path in cache_paths:
            try:
                xbmc.executebuiltin(f'CleanLibrary({cache_path}, true)')
            except:
                pass
        
        # Performs multiple cleanings
        for i in range(5):
            xbmc.executebuiltin('CleanLibrary(video)')
            xbmc.sleep(500)
        
        # Cleaning via JSON-RPC
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "VideoLibrary.Clean",
            "params": {"content": "video", "showdialogs": False},
            "id": 1
        }))
        
        # === STEP 5: Remove sources from sources.xml ===
        progress.update(85, message="Removing sources...")
        
        try:
            sources_xml = xbmcvfs.translatePath('special://userdata/sources.xml')
            if xbmcvfs.exists(sources_xml):
                with open(sources_xml, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Remove references to folders
                import re
                content = re.sub(r'<path.*?</path>', '', content, flags=re.DOTALL)
                
                with open(sources_xml, 'w', encoding='utf-8') as f:
                    f.write(content)
        except:
            pass
        
        # === STEP 6: Final Updates ===
        progress.update(90, message="Forcing update...")
        
        # Update empty library
        xbmc.executebuiltin('UpdateLibrary(video)')
        xbmc.sleep(3000)
        
        # Clean again
        xbmc.executebuiltin('CleanLibrary(video)')
        xbmc.sleep(1000)
        
        # Recharge skin TWICE
        xbmc.executebuiltin('ReloadSkin()')
        xbmc.sleep(1000)
        xbmc.executebuiltin('ReloadSkin()')
        
        progress.update(95, message="Restarting services...")
        
        # Restarts video services
        xbmc.executebuiltin('RestartVideoLibrary')
        xbmc.sleep(2000)
        
        progress.update(100, message="Done!")
        xbmc.sleep(1000)
        progress.close()
        
        # Final message with instructions
        xbmcgui.Dialog().ok(
            "Library Completely Clean",
            "✅ All items have been removed!",
            "",
            "If something still shows up:",
            "1. Restart Kodi completely",
            "2. Go to Settings > Media > Clear library",
            "3. Execute 'Update library' again"
        )
        
        # Suggests restart
        if xbmcgui.Dialog().yesno("Restart", "Recommended: Restart Kodi now?"):
            xbmc.executebuiltin('RestartApp')
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Library] Error clearing: {e}", xbmc.LOGERROR)
        progress.close()
        xbmcgui.Dialog().ok(
            "Cleaning Error",
            f"Error: {str(e)}",
            "Try:",
            "1. Restart Kodi",
            "2. Go to Settings > Media",
            "3. Execute 'Clear library' manuallye"
        )
        return False

# === ADD ALL (IN BULK) ===
def add_all_movies_to_library(*args, **kwargs):
    """Add all movies"""
    from resources.lib.db import db
    
    # Check access first
    if not check_library_access():
        if xbmcgui.Dialog().yesno(
            "Access Problem",
            "I can't access the library folders.",
            "Do you want to set up the fonts now?"
        ):
            setup_library_sources()
        return False
    
    all_movie_ids = db.get_all_movie_ids_set()
    if not all_movie_ids:
        xbmcgui.Dialog().ok("Library", "No movies found.")
        return False
    
    total = len(all_movie_ids)
    if not xbmcgui.Dialog().yesno("Add All", f"Add {total} movies?"):
        return False
    
    progress = xbmcgui.DialogProgressBG()
    progress.create("Cinebox", "Adding movies...")
    
    added = 0
    for idx, tmdb_id in enumerate(all_movie_ids, 1):
        progress.update(int((idx / total) * 100), message=f"Movie {idx}/{total}")
        movie_data = db.get_movie_by_id(tmdb_id)
        if movie_data and add_movie_to_library(movie_data):
            added += 1
        if idx % 10 == 0:
            xbmc.sleep(100)
    
    progress.close()
    
    if xbmcgui.Dialog().yesno("Completed", f"{added} added movies", "Update library?"):
        xbmc.executebuiltin('UpdateLibrary(video)')
    
    return True

def add_all_tvshows_to_library(*args, **kwargs):
    """Add all series"""
    from resources.lib.db import db
    
    # Check access first
    if not check_library_access():
        if xbmcgui.Dialog().yesno(
            "Access Problem",
            "I can't access the library folders.",
            "Do you want to set up the fonts now?"
        ):
            setup_library_sources()
        return False
    
    all_tvshow_ids = db.get_all_tvshow_ids_set()
    if not all_tvshow_ids:
        xbmcgui.Dialog().ok("Library", "No series found.")
        return False
    
    total = len(all_tvshow_ids)
    if not xbmcgui.Dialog().yesno("Add All", f"Add {total} series?", "It can take A LOT of time!"):
        return False
    
    progress = xbmcgui.DialogProgressBG()
    progress.create("Cinebox", "Adding series...")
    
    added = 0
    for idx, tmdb_id in enumerate(all_tvshow_ids, 1):
        progress.update(int((idx / total) * 100), message=f"Series {idx}/{total}")
        show_data = db.get_tvshow_by_id(tmdb_id)
        if show_data and add_tvshow_to_library(show_data):
            added += 1
        if idx % 5 == 0:
            xbmc.sleep(200)
    
    progress.close()
    
    if xbmcgui.Dialog().yesno("Completed", f"{added} series added", "Update Library?"):
        xbmc.executebuiltin('UpdateLibrary(video)')
    
    return True

# === MENU ===
def show_library_menu(*args, **kwargs):
    """Management Menu"""
    from resources.lib.db import db
    
    # Shows paths to the user
    movies_path, tvshows_path = get_library_paths()
    
    total_movies = len(db.get_all_movie_ids_set())
    total_tvshows = len(db.get_all_tvshow_ids_set())
    
    options = [
        f"Add Movies ({total_movies})",
        f"Add TV Shows ({total_tvshows})",
        "Add All",
        "Clear Library",
        "Update Kodi",
        "View Library Paths",
        "Configure Sources",
        "Cancel"
    ]
    
    choice = xbmcgui.Dialog().select("Library", options)
    
    if choice == 0:
        add_all_movies_to_library()
    elif choice == 1:
        add_all_tvshows_to_library()
    elif choice == 2:
        add_all_movies_to_library()
        add_all_tvshows_to_library()
    elif choice == 3:
        clear_library()
    elif choice == 4:
        xbmc.executebuiltin('UpdateLibrary(video)')
    elif choice == 5:
        xbmcgui.Dialog().textviewer(
            "Library Paths",
            f"MOVIES:\n{movies_path}\n\nseries:\n{tvshows_path}\n\n"
            f"Add these folders as sources in Kodi:\n"
            f"Settings > Media > Library > Videos > Add sources..."
        )
    elif choice == 6:
        setup_library_sources()


def update_kodi_library(media_type='video', *args, **kwargs):
    """Update Kodi library"""
    xbmc.executebuiltin('UpdateLibrary(video)')
    xbmc.sleep(2000)
    xbmc.executebuiltin('CleanLibrary(video)')

def get_library_stats():
    """Returns statistics"""
    import glob
    movies_path, tvshows_path = get_library_paths()
    
    try:
        movies_count = len(glob.glob(os.path.join(xbmcvfs.translatePath(movies_path), '**', '*.strm'), recursive=True))
        tvshows_count = len([d for d in os.listdir(xbmcvfs.translatePath(tvshows_path)) if os.path.isdir(os.path.join(xbmcvfs.translatePath(tvshows_path), d))])
        episodes_count = len(glob.glob(os.path.join(xbmcvfs.translatePath(tvshows_path), '**', '*.strm'), recursive=True))
        
        return {'movies': movies_count, 'tvshows': tvshows_count, 'episodes': episodes_count}
    except:
        return {'movies': 0, 'tvshows': 0, 'episodes': 0}

def remove_from_library(tmdb_id=None, media_type=None, *args, **kwargs):

    """Remove item individual"""
    # Simplified implementation - use clear_library() for complete removal
    return False