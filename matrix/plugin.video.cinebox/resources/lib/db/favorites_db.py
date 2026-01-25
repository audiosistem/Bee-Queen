# -*- coding: utf-8 -*-
import sqlite3
from .base_db import BaseDatabase

class FavoritesDatabase(BaseDatabase):
    
    def add_to_favorites(self, tmdb_id, media_type):
        """Adiciona favorito (com cache invalidation)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO favorites (tmdb_id, media_type) VALUES (?, ?)",
                (tmdb_id, media_type)
            )
            conn.commit()
            
            # Invalida caches relevantes
            self._cache_delete_prefix("favorites")
        finally:
            self._release_conn(conn)
    
    def remove_from_favorites(self, tmdb_id, media_type):
        """Remove favorito (com cache invalidation)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM favorites WHERE tmdb_id = ? AND media_type = ?",
                (tmdb_id, media_type)
            )
            conn.commit()
            
            # Invalida caches relevantes
            self._cache_delete_prefix("favorites")
        finally:
            self._release_conn(conn)
    
    def is_favorite(self, tmdb_id, media_type):
        """Verifica se item é favorito (útil para UI)"""
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
        Busca TODOS os favoritos (filmes + séries) com JOIN otimizado.
        Retorna lista unificada ordenada por data de adição (mais recente primeiro).
        """
        cache_key = "favorites_all"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        # Query otimizada com UNION ALL (mais rápido que 2 queries separadas)
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
        Busca favoritos filtrados por tipo (movie ou tvshow).
        Mais rápido que get_all_favorites() quando só precisa de um tipo.
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
        """Retorna contagem rápida de favoritos (útil para estatísticas)"""
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
        """Remove TODOS os favoritos (útil para reset)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM favorites")
            conn.commit()
            self._cache_delete_prefix("favorites")
        finally:
            self._release_conn(conn)