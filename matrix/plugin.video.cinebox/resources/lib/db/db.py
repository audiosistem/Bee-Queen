# -*- coding: utf-8 -*-
"""
db.py - Main interface to the database
✅ Inherits from BaseDatabase
✅ Compatible with Trakt Sync
✅ Optimized functions
"""

from .base_db import BaseDatabase
from .movies_db import MoviesDatabase
from .tvshows_db import TVShowsDatabase
import xbmc
import json
import time

# ============ GLOBAL INSTANCE ============
class db(MoviesDatabase, TVShowsDatabase):
    """Wrapper for the database with specific methods"""
    
    def __init__(self):
        super().__init__()
        xbmc.log("[DB] Initialized db instance", xbmc.LOGINFO)
    
    # ============ SPECIFIC METHODS FOR TRAKT ============
    

    
    def add_movie(self, movie_data):
        """Add or update movie in DB"""
        try:
            # Prepare data
            tmdb_id = movie_data.get('tmdb_id')
            title = movie_data.get('title', '')
            original_title = movie_data.get('original_title', title)
            year = movie_data.get('year', 0)
            imdb_id = movie_data.get('imdb_id', '')
            rating = movie_data.get('rating', 0.0)
            poster = movie_data.get('poster', '')
            backdrop = movie_data.get('backdrop', '')
            synopsis = movie_data.get('synopsis', '')
            runtime = movie_data.get('runtime', 0)
            popularity = movie_data.get('popularity', 0.0)
            revenue = movie_data.get('revenue', 0)
            collection = movie_data.get('collection', '')
            genres = json.dumps(movie_data.get('genres', []))
            streams = json.dumps(movie_data.get('streams', []))
            providers = json.dumps(movie_data.get('providers', []))
            clearlogo = movie_data.get('clearlogo', '')
            
            # Normalizations
            title_normalized = self._normalize_text(title)
            genres_normalized = self._normalize_text(' '.join(movie_data.get('genres', [])))
            
            sql = """
                INSERT OR REPLACE INTO movies (
                    tmdb_id, title, original_title, title_normalized,
                    year, imdb_id, rating, poster, backdrop, synopsis,
                    runtime, popularity, revenue, collection, genres,
                    genres_normalized, streams, providers, clearlogo,
                    date_added
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            params = (
                tmdb_id, title, original_title, title_normalized,
                year, imdb_id, rating, poster, backdrop, synopsis,
                runtime, popularity, revenue, collection, genres,
                genres_normalized, streams, providers, clearlogo
            )
            
            self._execute_query(sql, params, fetch_all=False, fetch_one=False)
            
            # Clear cache
            self._cache_delete_prefix(f"movie_{tmdb_id}")
            self._cache_delete_prefix("movies_list")
            
            return True
            
        except Exception as e:
            xbmc.log(f"[DB] Error adding movie {tmdb_id}: {e}", xbmc.LOGERROR)
            return False
    
    def add_tvshow(self, tvshow_data):
        """Add or update series in DB"""
        try:
            tmdb_id = tvshow_data.get('tmdb_id')
            title = tvshow_data.get('title', '')
            original_title = tvshow_data.get('original_title', title)
            year = tvshow_data.get('year', 0)
            imdb_id = tvshow_data.get('imdb_id', '')
            poster = tvshow_data.get('poster', '')
            backdrop = tvshow_data.get('backdrop', '')
            synopsis = tvshow_data.get('synopsis', '')
            certification = tvshow_data.get('certification', '')
            popularity = tvshow_data.get('popularity', 0.0)
            rating = tvshow_data.get('rating', 0.0)
            genres = json.dumps(tvshow_data.get('genres', []))
            providers = json.dumps(tvshow_data.get('providers', []))
            seasons_data = json.dumps(tvshow_data.get('seasons_data', []))
            clearlogo = tvshow_data.get('clearlogo', '')
            banner = tvshow_data.get('banner', '')
            landscape = tvshow_data.get('landscape', '')
            season_count = tvshow_data.get('season_count', 0)
            episodes_count = tvshow_data.get('episodes_count', 0)
            status = tvshow_data.get('status', '')
            
            # Normalizations
            title_normalized = self._normalize_text(title)
            genres_normalized = self._normalize_text(' '.join(tvshow_data.get('genres', [])))
            
            sql = """
                INSERT OR REPLACE INTO tvshows (
                    tmdb_id, title, original_title, title_normalized,
                    year, imdb_id, poster, backdrop, synopsis, certification,
                    popularity, rating, genres, genres_normalized, providers,
                    seasons_data, clearlogo, banner, landscape, season_count,
                    episodes_count, status, date_added
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            params = (
                tmdb_id, title, original_title, title_normalized,
                year, imdb_id, poster, backdrop, synopsis, certification,
                popularity, rating, genres, genres_normalized, providers,
                seasons_data, clearlogo, banner, landscape, season_count,
                episodes_count, status
            )
            
            self._execute_query(sql, params, fetch_all=False, fetch_one=False)
            
            # Limpa cache
            self._cache_delete_prefix(f"tvshow_{tmdb_id}")
            self._cache_delete_prefix("tvshows_list")
            
            return True
            
        except Exception as e:
            xbmc.log(f"[DB] Error adding series {tmdb_id}: {e}", xbmc.LOGERROR)
            return False
    
    def remove_from_favorites(self, tmdb_id, media_type):
        """Remove dos favoritos"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM favorites 
                WHERE tmdb_id = ? AND media_type = ?
            """, (tmdb_id, media_type))
            
            conn.commit()
            self._cache_delete_prefix("favorites")
            return True
        finally:
            self._release_conn(conn)
    
    def is_favorite(self, tmdb_id, media_type):
        """Check if you are a favorite"""
        sql = """
            SELECT 1 FROM favorites 
            WHERE tmdb_id = ? AND media_type = ?
            LIMIT 1
        """
        result = self._execute_query(sql, (tmdb_id, media_type), fetch_one=True)
        return bool(result)
    

    
    def save_season_cache(self, tvshow_tmdb_id, season_number, season_data):
        """Save season cache"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO seasons_cache 
                (tvshow_tmdb_id, season_number, name, overview, poster, 
                 air_date, episode_count, vote_average)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tvshow_tmdb_id, season_number,
                season_data.get('name', ''),
                season_data.get('overview', ''),
                season_data.get('poster', ''),
                season_data.get('air_date', ''),
                season_data.get('episode_count', 0),
                season_data.get('vote_average', 0.0)
            ))
            
            conn.commit()
            return True
        finally:
            self._release_conn(conn)
    
    def get_season_cache(self, tvshow_tmdb_id, season_number):
        """Seasonal cache search"""
        sql = """
            SELECT * FROM seasons_cache 
            WHERE tvshow_tmdb_id = ? AND season_number = ?
        """
        return self._execute_query(sql, (tvshow_tmdb_id, season_number), fetch_one=True)
    
    def save_episode_cache(self, tvshow_tmdb_id, season_number, episode_number, episode_data):
        """Save episode cache"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO episodes_cache 
                (tvshow_tmdb_id, season_number, episode_number, 
                 name, overview, still_path, air_date, vote_average, runtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tvshow_tmdb_id, season_number, episode_number,
                episode_data.get('name', ''),
                episode_data.get('overview', ''),
                episode_data.get('still_path', ''),
                episode_data.get('air_date', ''),
                episode_data.get('vote_average', 0.0),
                episode_data.get('runtime', 0)
            ))
            
            conn.commit()
            return True
        finally:
            self._release_conn(conn)
    
    def get_episode_cache(self, tvshow_tmdb_id, season_number, episode_number):
        """Search episode cache"""
        sql = """
            SELECT * FROM episodes_cache 
            WHERE tvshow_tmdb_id = ? 
            AND season_number = ? 
            AND episode_number = ?
        """
        return self._execute_query(sql, (tvshow_tmdb_id, season_number, episode_number), fetch_one=True)
    
    def save_collection_meta(self, collection_name, poster, backdrop):
        """Saves collection metadata"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO collections_meta 
                (collection_name, poster, backdrop)
                VALUES (?, ?, ?)
            """, (collection_name, poster, backdrop))
            
            conn.commit()
            return True
        finally:
            self._release_conn(conn)
    
    def get_collection_meta(self, collection_name):
        """Fetch collection metadata"""
        sql = """
            SELECT * FROM collections_meta 
            WHERE collection_name = ?
        """
        return self._execute_query(sql, (collection_name,), fetch_one=True)
    
    # ============ STATISTICS METHODS ============
    
    def get_stats(self):
        """Returns bank statistics"""
        stats = {}
        
        # Movie count
        sql_movies = "SELECT COUNT(*) as count FROM movies"
        result = self._execute_query(sql_movies, fetch_one=True)
        stats['movies'] = result['count'] if result else 0
        
        # Series count
        sql_tvshows = "SELECT COUNT(*) as count FROM tvshows"
        result = self._execute_query(sql_tvshows, fetch_one=True)
        stats['tvshows'] = result['count'] if result else 0
        
        # Favorites count
        sql_favs = "SELECT COUNT(*) as count FROM favorites"
        result = self._execute_query(sql_favs, fetch_one=True)
        stats['favorites'] = result['count'] if result else 0
        
        # Count of movies watched
        sql_watched = "SELECT COUNT(*) as count FROM movies WHERE playcount > 0"
        result = self._execute_query(sql_watched, fetch_one=True)
        stats['watched_movies'] = result['count'] if result else 0
        
        return stats

    def get_total_movies_count(self):
        """Returns the total number of films in the bank"""
        sql = "SELECT COUNT(*) as count FROM movies"
        result = self._execute_query(sql, fetch_one=True)
        return result['count'] if result else 0

    def get_total_tvshows_count(self):
        """Returns the total number of series in the bank"""
        sql = "SELECT COUNT(*) as count FROM tvshows"
        result = self._execute_query(sql, fetch_one=True)
        return result['count'] if result else 0

    # ============ TRAKT COMPATIBILITY METHODS ============
    
    def get_last_played_movies(self, limit=10):
        """Recently played movies"""
        sql = """
            SELECT * FROM movies 
            WHERE date_added IS NOT NULL 
            ORDER BY date_added DESC 
            LIMIT ?
        """
        return self._execute_query(sql, (limit,))
    
    def get_last_played_tvshows(self, limit=10):
        """Recently played series"""
        sql = """
            SELECT * FROM tvshows 
            WHERE date_added IS NOT NULL 
            ORDER BY date_added DESC 
            LIMIT ?
        """
        return self._execute_query(sql, (limit,))

# ============ GLOBAL INSTANCE ============
db_instance = db()

# ============ CONVENIENCE FUNCTIONS ============
# (For compatibility with existing code)

def get_watched_movies():
    """Compatibility: Returns watched films"""
    return db_instance.get_watched_movies()

def get_watched_tvshows():
    """Compatibility: Returns watched series"""
    return db_instance.get_watched_tvshows()

def add_to_favorites(tmdb_id, media_type):
    """Compatibility: Add to favorites"""
    return db_instance.add_to_favorites(tmdb_id, media_type)

def remove_from_favorites(tmdb_id, media_type):
    """Compatibility: Remove from favorites"""
    return db_instance.remove_from_favorites(tmdb_id, media_type)

def is_favorite(tmdb_id, media_type):
    """Compatibility: Check if you are a favorite"""
    return db_instance.is_favorite(tmdb_id, media_type)

def get_all_favorites():
    """Compatibility: Returns all favorites"""
    return db_instance.get_all_favorites()

def get_movie_by_id(tmdb_id):
    """Compatibility: Search movie"""
    return db_instance.get_movie_by_id(tmdb_id)

def get_tvshow_by_id(tmdb_id):
    """Compatibility: Search series"""
    return db_instance.get_tvshow_by_id(tmdb_id)

def add_movies_bulk(movies_list):
    """Compatibility: Add movies in batch"""
    return db_instance.add_movies_bulk(movies_list)

def add_tvshows_bulk(tvshows_list):
    """Compatibility: Add series in batch"""
    return db_instance.add_tvshows_bulk(tvshows_list)

def get_all_movie_ids_set():
    """Compatibility: Returns movie IDs"""
    return db_instance.get_all_movie_ids_set()

def get_all_tvshow_ids_set():
    """Compatibility: Returns series IDs"""
    return db_instance.get_all_tvshow_ids_set()

def clear_database():
    """Compatibility: Cleans the database"""
    return db_instance.clear_database()

def update_movie_playcount(tmdb_id, playcount, last_played=None):
    """Compatibility: Updates movie playcount"""
    return db_instance.update_movie_playcount(tmdb_id, playcount, last_played)

def update_tvshow_playcount(tmdb_id, last_played=None):
    """Compatibility: Updates series playcount"""
    return db_instance.update_tvshow_playcount(tmdb_id, last_played)

def mark_movie_as_watched(tmdb_id):
    """Compatibility: Mark movie as watched"""
    return db_instance.mark_movie_as_watched(tmdb_id)

# ============ INTEGRATION TESTING ============
if __name__ == '__main__':
    # Quick test (only runs if run directly)
    print("✅ db.py successfully loaded!")
    print(f"✅ Created db instance: {db_instance}")