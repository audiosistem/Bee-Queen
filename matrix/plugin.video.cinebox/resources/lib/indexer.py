# Em: resources/lib/indexer.py
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
    """
    Verifica e adiciona apenas o novo conteúdo de forma silenciosa usando TMDB Trending.
    """
    current_check_dt = datetime.now(timezone.utc)
    
    try:
        # ✅ MELHORIA: Busca as 5 primeiras páginas de tendências (era 3) para garantir conteúdo novo
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
            
            xbmc.log(f"[Indexer] {total_new} noi articole la modă adăugate.", xbmc.LOGINFO)
        
        # Atualiza popularidade dos itens existentes que voltaram a ser tendência
        # Isso ajuda a manter a ordem correta na entrada do Kodi
        update_local_popularity()
        
        addon_object.setSetting('last_update_check', current_check_dt.isoformat())
        
    except Exception as e:
        xbmc.log(f"[Indexer] Eroare la actualizarea silențioasă prin TMDB: {e}", xbmc.LOGERROR)

def run_indexer(batch_size=100):
    """
    Atualiza o banco de dados usando TMDB Trending.
    """
    progress = xbmcgui.DialogProgress()
    addon = xbmcaddon.Addon()
    
    try:
        progress.create('Cinebox', 'Sincronizare prin TMDB...')
        
        # --- ETAPA 1: PREPARAÇÃO ---
        progress.update(5, 'Se inițiază actualizarea catalogului...')
        if progress.iscanceled(): return

        # --- ETAPA 2: BUSCA NO TMDB ---
        progress.update(10, 'Căutând tendințe actualizate în TMDB...')
        
        all_movies = []
        all_tvshows = []
        
        # ✅ MELHORIA: Buscar 20 páginas de tendências para garantir conteúdo novo e atualizado (~400 itens de cada)
        for p in range(1, 21):
            if progress.iscanceled(): break
            progress.update(10 + (p*4), f'Baixando página {p} de tendências...')
            try:
                all_movies.extend(fetch_trending_movies(page=p))
                all_tvshows.extend(fetch_trending_tvshows(page=p))
            except:
                continue

        total_movies = len(all_movies)
        total_tvshows = len(all_tvshows)
        total_items = total_movies + total_tvshows

        if total_items == 0:
            xbmcgui.Dialog().ok("Atentie", "Nu a fost posibil să se obțină date de la TMDB.")
            return

        # --- ETAPA 3: PROCESSAMENTO ---
        if all_movies:
            progress.update(50, f"Adăugând {total_movies} filme populare...")
            db.add_movies_bulk(all_movies)

        if all_tvshows:
            progress.update(75, f"Adăugând {total_tvshows} seriale populare...")
            db.add_tvshows_bulk(all_tvshows)

        # --- ETAPA 4: FINALIZAÇÃO ---
        if not progress.iscanceled():
            progress.update(95, "Optimizarea bazei de date...")
            update_local_popularity()
            
            progress.update(100, "Catalogul TMDB sincronizat!")
            
            current_check_dt = datetime.now(timezone.utc)
            addon.setSetting('last_update_check', current_check_dt.isoformat())
            
            xbmc.sleep(800)
            xbmcgui.Dialog().notification("Cinebox", "Catalogul TMDB Actualizat!", xbmcgui.NOTIFICATION_INFO, 5000, False)

    except Exception as e:
        xbmc.log(f"[Indexer] Eroare critica TMDB: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Eroare de Actualizare", f"Detalii: {e}")
    
    finally:
        try:
            progress.close()
        except:
            pass
        
        # Finaliza o handle do plugin
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
