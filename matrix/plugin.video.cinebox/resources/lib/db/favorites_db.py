# -*- coding: utf-8 -*-
import sqlite3
from .base_db import BaseDatabase

class FavoritesDatabase(BaseDatabase):
    
    def add_to_favorites(self, tmdb_id, media_type):
        """Add to favorites (com cache invalidation)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO favorites (tmdb_id, media_type) VALUES (?, ?)",
                (tmdb_id, media_type)
            )
            conn.commit()
            
            # Invalidates relevant caches
            self._cache_delete_prefix("favorites")
        finally:
            self._release_conn(conn)
    
    def remove_from_favorites(self, tmdb_id, media_type):
        """Remove favorite (com cache invalidation)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM favorites WHERE tmdb_id = ? AND media_type = ?",
                (tmdb_id, media_type)
            )
            conn.commit()
            
            # Invalidates relevant caches
            self._cache_delete_prefix("favorites")
        finally:
            self._release_conn(conn)
    
    def is_favorite(self, tmdb_id, media_type):
        """Checks if item is favorite (useful for UI)"""
        cache_key = f"is_fav:{tmdb_id}:{media_type}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM favorites WHERE tmdb_id = ? AND media_type = ? LIMIT 1",
                (tmdb_id, media_type)
            )
            result = cursor.fetchone() is not None
            self._cache_set(cache_key, result, ttl=300)  # 5 min
            return result
        finally:
            self._release_conn(conn)
    
    def get_all_favorites(self):
        """
        Search ALL favorites (movies + series) with optimized JOIN.
        Returns unified list ordered by date added (newest first).
        """
        cache_key = "favorites_all"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        # Query optimized with UNION ALL (faster than 2 separate queries)
        sql = """
            SELECT 
                m.tmdb_id, m.title, m.original_title, m.year, m.rating,
                m.poster, m.backdrop, m.synopsis, m.imdb_id,
                m.clearlogo, m.genres, m.runtime, m.collection,
                'movie' as media_type
            FROM favorites f
            JOIN movies m ON f.tmdb_id = m.tmdb_id
            WHERE f.media_type = 'movie'
            
            UNION ALL
            
            SELECT
                t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                t.poster, t.backdrop, t.synopsis, t.imdb_id,
                t.clearlogo, t.genres, 0 as runtime, '' as collection,
                'tvshow' as media_type
            FROM favorites f
            JOIN tvshows t ON f.tmdb_id = t.tmdb_id
            WHERE f.media_type = 'tvshow'
            
            ORDER BY media_type, title
        """
        
        results = self._execute_query(sql, ())
        self._cache_set(cache_key, results, ttl=300)  # 5 min
        return results
    
    def get_favorites_by_type(self, media_type):
        """
        Search favorites filtered by type (movie ou tvshow).
        Faster than get_all_favorites() when you only need one type.
        """
        cache_key = f"favorites_{media_type}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        if media_type == 'movie':
            sql = """
                SELECT m.*, 'movie' as media_type
                FROM favorites f
                JOIN movies m ON f.tmdb_id = m.tmdb_id
                WHERE f.media_type = 'movie'
                ORDER BY m.title
            """
        else:  # tvshow
            sql = """
                SELECT t.*, 'tvshow' as media_type
                FROM favorites f
                JOIN tvshows t ON f.tmdb_id = t.tmdb_id
                WHERE f.media_type = 'tvshow'
                ORDER BY t.title
            """
        
        results = self._execute_query(sql, ())
        self._cache_set(cache_key, results, ttl=300)  # 5 min
        return results
    
    def get_favorites_count(self):
        """Returns quick count of favorites (useful for statistics)"""
        cache_key = "favorites_count"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN media_type = 'movie' THEN 1 ELSE 0 END) as movies,
                    SUM(CASE WHEN media_type = 'tvshow' THEN 1 ELSE 0 END) as tvshows,
                    COUNT(*) as total
                FROM favorites
            """)
            row = cursor.fetchone()
            result = {
                'movies': row[0] or 0,
                'tvshows': row[1] or 0,
                'total': row[2] or 0
            }
            self._cache_set(cache_key, result, ttl=300)
            return result
        finally:
            self._release_conn(conn)
    
    def clear_all_favorites(self):
        """Remove ALL bookmarks (useful for reset)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM favorites")
            conn.commit()
            self._cache_delete_prefix("favorites")
        finally:
            self._release_conn(conn)