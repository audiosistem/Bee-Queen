# In: resources/lib/favorites.py

import xbmcgui
from .db import db

def add_item_to_favorites(tmdb_id, media_type):
    """Adds item to favorites and tries to fetch data in the background if necessary."""
    try:
        from .db.db import db_instance
        
        # 1. Immediately adds to favorites table (quick action)
        db_instance.add_to_favorites(tmdb_id, media_type)
        
        # 2. Notifies the user immediately
        xbmcgui.Dialog().notification("My List", "Added successfully!", xbmcgui.NOTIFICATION_INFO, 3000)
        
        # 3. Checks if download is needed the data (only if it does not exist)
        if media_type == 'movie':
            if not db_instance.get_movie_by_id(tmdb_id):
                from .tmdb_api import get_movie_details
                data = get_movie_details(tmdb_id)
                if data: db_instance.add_movie(data)
        else:
            if not db_instance.get_tvshow_by_id(tmdb_id):
                from .tmdb_api import fetch_show_details
                data = fetch_show_details(tmdb_id)
                if data: db_instance.add_tvshow(data)
                
    except Exception as e:
        import xbmc
        xbmc.log(f"[Cinebox] Error adding favorite: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Error", "Could not add item", xbmcgui.NOTIFICATION_ERROR)

def remove_item_from_favorites(tmdb_id, media_type):
    """Calls the database to remove an item and notifies the user."""
    db.remove_from_favorites(tmdb_id, media_type)
    xbmcgui.Dialog().notification("My List", "Removed from your list.", xbmcgui.NOTIFICATION_INFO)