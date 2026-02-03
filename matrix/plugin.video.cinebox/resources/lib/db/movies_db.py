# -*- coding: utf-8 -*-
from .base_db import BaseDatabase
import json
import sqlite3

class MoviesDatabase(BaseDatabase):
    
    def add_movies_bulk(self, movies_list):
        """Bulk insert optimized with single transaction"""
        if not movies_list:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Prepare data
            data = []
            for movie in movies_list:
                title_norm = self._normalize_text(movie.get('title', ''))
                genres = movie.get('genres', []) if isinstance(movie.get('genres'), list) else []
                providers = movie.get('providers', []) if isinstance(movie.get('providers'), list) else []
                normalized_genres = [self._normalize_text(g) for g in genres]
                
                streams = movie.get('streams', [])
                if not isinstance(streams, list): streams = []
                
                data.append((
                    movie.get('tmdb_id'), movie.get('title'), movie.get('original_title'),
                    title_norm, movie.get('year'), movie.get('imdb_id'), movie.get('rating'),
                    movie.get('poster'), movie.get('backdrop'), movie.get('synopsis'),
                    movie.get('date_added'), movie.get('runtime', 0), movie.get('popularity', 0.0),
                    movie.get('revenue', 0), movie.get('collection'), json.dumps(genres),
                    json.dumps(normalized_genres), json.dumps(streams),
                    json.dumps(providers), movie.get('clearlogo'), movie.get('playcount', 0),
                    movie.get('popularity_updated') or now
                ))
            
            # Batch insert
            cursor.executemany('''
                INSERT OR REPLACE INTO movies (
                    tmdb_id, title, original_title, title_normalized, year, imdb_id, rating,
                    poster, backdrop, synopsis, date_added, runtime, popularity, revenue,
                    collection, genres, genres_normalized, streams, providers, clearlogo,
                    playcount, popularity_updated
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', data)
            
            conn.commit()
            
            # Clear relevant caches
            self._cache_delete_prefix("movies_")
        finally:
            self._release_conn(conn)
    
    def get_movie_by_id(self, tmdb_id):
        """Search specific movie (with cache)"""
        cache_key = f"movie:{tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = "SELECT * FROM movies WHERE tmdb_id = ?"
        movie = self._execute_query(sql, (int(tmdb_id),), fetch_one=True)
        
        if movie:
            self._cache_set(cache_key, movie, ttl=3600)  # 1 hora
        
        return movie
    
    def get_all_movie_ids_set(self):
        """Returns SET of IDs (ultra-fast, just the ID column)"""
        cache_key = "all_movie_ids"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM movies")
            ids = {row[0] for row in cursor.fetchall()}
            self._cache_set(cache_key, ids, ttl=600)
            return ids
        finally:
            self._release_conn(conn)
    
    def get_movies_by_genre(self, genre, page=1, items_per_page=35):
        """Search by genre (keeps LIKE for now, but with aggressive caching)"""
        normalized_genre = self._normalize_text(genre)
        cache_key = f"movies_genre:{normalized_genre}:{page}"
        
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        sql = """
            SELECT * FROM movies
            WHERE genres_normalized LIKE ?
            ORDER BY popularity DESC
            LIMIT ? OFFSET ?
        """
        
        movies = self._execute_query(sql, (f'%"{normalized_genre}"%', items_per_page, offset))
        self._cache_set(cache_key, movies, ttl=600)
        return movies
    
    def get_movies_by_popularity(self, page=1, page_size=35):
        """Top movies by popularity (long cache)"""
        cache_key = f"movies_pop:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        sql = "SELECT * FROM movies ORDER BY popularity DESC LIMIT ? OFFSET ?"
        
        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=900)  # 15 min
        return movies
    
    def update_popularity_bulk(self, updates):
        """Mass popularity update"""
        if not updates:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            data = [(u['popularity'], now, u['tmdb_id']) for u in updates]
            cursor.executemany('UPDATE movies SET popularity=?, popularity_updated=? WHERE tmdb_id=?', data)
            conn.commit()
            self._cache_delete_prefix("movies_pop:")
        finally:
            self._release_conn(conn)
    
    def get_movies_by_revenue(self, page=1, page_size=35):
        """Top by revenue (cache longo)"""
        cache_key = f"movies_revenue:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        sql = "SELECT * FROM movies ORDER BY revenue DESC LIMIT ? OFFSET ?"
        
        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=1800)  # 30 min
        return movies
    
    def get_4k_movies(self, page=1, page_size=35):
        """4K movies (medium cache)"""
        cache_key = f"movies_4k:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        sql = "SELECT * FROM movies WHERE streams LIKE '%4K%' ORDER BY popularity DESC LIMIT ? OFFSET ?"
        
        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=1200)  # 20 min
        return movies
    
    def get_all_collections(self, page=1, page_size=35):
        """Collection list (optimized query)"""
        cache_key = f"collections:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        # Optimization: We look for collections that have more than 1 film in the bank OR 
        # simply all the collections. The problem of "just a movie" may be because
        # Search collections in the local database.
        sql = """
            SELECT 
                collection,
                COUNT(*) AS total,
                MAX(poster) AS poster,
                MAX(backdrop) AS backdrop
            FROM movies
            WHERE collection IS NOT NULL AND collection != ''
            GROUP BY collection
            HAVING total > 0
            ORDER BY collection COLLATE NOCASE
            LIMIT ? OFFSET ?
        """
        
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (page_size, offset))
            results = [dict(row) for row in cursor.fetchall()]
            self._cache_set(cache_key, results, ttl=3600)
            return results
        finally:
            self._release_conn(conn)
    
    def get_movies_by_collection(self, collection_name):
        """Movies from a collection (long cache)"""
        cache_key = f"collection:{collection_name}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = "SELECT * FROM movies WHERE collection = ? ORDER BY year"
        movies = self._execute_query(sql, (collection_name,))
        self._cache_set(cache_key, movies, ttl=3600)
        return movies
    
    def get_cached_collection_meta(self, name):
        """Collection metadata (used for API posters/backdrops)"""
        cache_key = f"collection_meta:{name}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = "SELECT poster, backdrop FROM collections_meta WHERE collection_name = ?"
        result = self._execute_query(sql, (name,), fetch_one=True)
        
        if result:
            self._cache_set(cache_key, result, ttl=86400)  # 24h
        
        return result
    
    def save_collection_meta(self, name, poster, backdrop):
        """Saves collection metadata"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO collections_meta (collection_name, poster, backdrop)
                VALUES (?, ?, ?)
            """, (name, poster, backdrop))
            conn.commit()
            self._cache_delete_prefix(f"collection_meta:{name}")
        finally:
            self._release_conn(conn)
    
    def get_all_unique_years(self):
        """Unique years (super long cache)"""
        cache_key = "movies_years"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT year FROM movies WHERE year IS NOT NULL ORDER BY year DESC")
            years = [row[0] for row in cursor.fetchall()]
            self._cache_set(cache_key, years, ttl=7200)  # 2 horas
            return years
        finally:
            self._release_conn(conn)
    
    def get_movies_by_year(self, year, page=1, items_per_page=35):
        """Films by year"""
        cache_key = f"movies_year:{year}:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        sql = "SELECT * FROM movies WHERE year = ? ORDER BY rating DESC LIMIT ? OFFSET ?"
        
        movies = self._execute_query(sql, (year, items_per_page, offset))
        self._cache_set(cache_key, movies, ttl=1800)
        return movies
    
    def get_all_unique_genres(self):
        """Single genres (super long cache)"""
        cache_key = "movies_genres"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT genres FROM movies")
            all_genres = set()
            
            for (genres_json,) in cursor.fetchall():
                try:
                    genres = json.loads(genres_json) if genres_json else []
                    for g in genres:
                        if isinstance(g, str) and g.strip():
                            all_genres.add(g.strip())
                except:
                    pass
            
            result = sorted(all_genres)
            self._cache_set(cache_key, result, ttl=7200)
            return result
        finally:
            self._release_conn(conn)
    
    def get_recently_added_movies(self, page=1, page_size=35):
        """Newly Added"""
        cache_key = f"movies_recent:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        sql = "SELECT * FROM movies WHERE date_added IS NOT NULL ORDER BY date_added DESC LIMIT ? OFFSET ?"
        
        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=600)
        return movies
    
    def get_movies_by_provider(self, provider, page=1, items_per_page=35):
        """Streaming movies"""
        provider_norm = self._normalize_text(provider)
        cache_key = f"movies_provider:{provider_norm}:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        sql = """
            SELECT * FROM movies
            WHERE providers LIKE ?
            ORDER BY popularity DESC
            LIMIT ? OFFSET ?
        """
        
        movies = self._execute_query(sql, (f'%"{provider}"%', items_per_page, offset))
        self._cache_set(cache_key, movies, ttl=1200)
        return movies