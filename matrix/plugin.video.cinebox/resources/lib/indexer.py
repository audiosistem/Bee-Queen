# In: resources/lib/indexer.py
# -*- coding: utf-8 -*-

import xbmcgui
import xbmc
import xbmcaddon
import xbmcplugin
import sys
from datetime import datetime, timezone

from .db.db import db_instance as db, db as db_class
from .tmdb_api import fetch_trending_movies, fetch_trending_tvshows, update_local_popularity

def check_for_updates_silently(addon_object):
    """Checks and adds only new content silently using TMDB Trending."""
    current_check_dt = datetime.now(timezone.utc)
    
    try:
        # ✅ IMPROVEMENT: Search the first 5 trending pages (was 3) to guarantee new content
        trending_movies = []
        trending_tvshows = []
        for p in range(1, 6):
            try:
                trending_movies.extend(fetch_trending_movies(page=p))
                trending_tvshows.extend(fetch_trending_tvshows(page=p))
            except:
                continue
        
        existing_movie_ids = db.get_all_movie_ids_set()
        existing_tvshow_ids = db.get_all_tvshow_ids_set()
        
        new_movies = [m for m in trending_movies if m.get('tmdb_id') not in existing_movie_ids]
        new_tvshows = [s for s in trending_tvshows if s.get('tmdb_id') not in existing_tvshow_ids]
        
        total_new = len(new_movies) + len(new_tvshows)
        
        if total_new > 0:
            if new_movies:
                db.add_movies_bulk(new_movies)
            if new_tvshows:
                db.add_tvshows_bulk(new_tvshows)
            
            xbmc.log(f"[Indexer] {total_new} new trending items added.", xbmc.LOGINFO)
        
        # Updates popularity of existing items that are trending again
        # This helps maintain the correct order in Kodi input
        update_local_popularity()
        
        addon_object.setSetting('last_update_check', current_check_dt.isoformat())
        
    except Exception as e:
        xbmc.log(f"[Indexer] Silent update error via TMDB: {e}", xbmc.LOGERROR)

def run_indexer(batch_size=100):
    """Updates the database using TMDB Trending."""
    progress = xbmcgui.DialogProgress()
    addon = xbmcaddon.Addon()
    
    try:
        progress.create('Cinebox', 'Synchronizing with TMDB...')
        
        # --- STEP 1: PREPARATION ---
        progress.update(5, 'Starting catalog update...')
        if progress.iscanceled(): return

        # --- STEP 2: SEARCH IN TMDB ---
        progress.update(10, 'Looking for updated trends on TMDB...')
        
        all_movies = []
        all_tvshows = []
        
        # ✅ IMPROVEMENT: Search 20 trending pages to ensure new and updated content (~400 items each)
        for p in range(1, 21):
            if progress.iscanceled(): break
            progress.update(10 + (p*4), f'Downloading trends page {p}...')
            try:
                all_movies.extend(fetch_trending_movies(page=p))
                all_tvshows.extend(fetch_trending_tvshows(page=p))
            except:
                continue

        total_movies = len(all_movies)
        total_tvshows = len(all_tvshows)
        total_items = total_movies + total_tvshows

        if total_items == 0:
            xbmcgui.Dialog().ok("Warning", "Could not retrieve data from TMDB.")
            return

        # --- STEP 3: PROCESSING ---
        if all_movies:
            progress.update(50, f"Adding {total_movies} popular movies...")
            db.add_movies_bulk(all_movies)

        if all_tvshows:
            progress.update(75, f"Adding {total_tvshows} popular series...")
            db.add_tvshows_bulk(all_tvshows)

        # --- STAGE 4: FINALIZATION ---
        if not progress.iscanceled():
            progress.update(95, "Optimizing database...")
            update_local_popularity()
            
            progress.update(100, "TMDB catalog synchronized!")
            
            current_check_dt = datetime.now(timezone.utc)
            addon.setSetting('last_update_check', current_check_dt.isoformat())
            
            xbmc.sleep(800)
            xbmcgui.Dialog().notification("Cinebox", "TMDB Catalog Updated!", xbmcgui.NOTIFICATION_INFO, 5000, False)

    except Exception as e:
        xbmc.log(f"[Indexer] TMDB critical error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Update Error", f"Details: {e}")
    
    finally:
        try:
            progress.close()
        except:
            pass
        
        # Finalizes the plugin handle
        h = None
        try:
            from .movies import HANDLE as h_movies
            h = h_movies
        except:
            try:
                h = int(sys.argv[1])
            except:
                pass
        
        if h is not None:
            try:
                xbmcplugin.endOfDirectory(h, succeeded=True, updateListing=True)
            except:
                pass
        
        xbmc.executebuiltin("Dialog.Close(busydialog)")
