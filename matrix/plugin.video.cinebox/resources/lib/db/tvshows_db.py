# -*- coding: utf-8 -*-
from .base_db import BaseDatabase
import json
import sqlite3
import xbmc

class TVShowsDatabase(BaseDatabase):
    
    def add_tvshows_bulk(self, tvshows_list):
        """Bulk insert otimizado para séries"""
        if not tvshows_list:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            data = []
            for show in tvshows_list:
                original_title = show.get('original_title') or show.get('title', 'N/A')
                title_norm = self._normalize_text(original_title)
                genres = show.get('genres', []) if isinstance(show.get('genres'), list) else []
                normalized_genres = [self._normalize_text(g) for g in genres]
                
                data.append((
                    show.get('tmdb_id'), show.get('title'), original_title, title_norm,
                    show.get('year'), show.get('imdb_id'), show.get('poster'),
                    show.get('backdrop'), show.get('synopsis'),
                    json.dumps(show.get('providers', [])), show.get('certification'),
                    show.get('date_added'), show.get('popularity', 0.0), show.get('rating', 0.0),
                    json.dumps(genres), json.dumps(normalized_genres),
                    json.dumps(show.get('seasons_data', [])), show.get('clearlogo'),
                    show.get('banner'), show.get('landscape'), show.get('playcount', 0),
                    show.get('season_count', 0), show.get('episodes_count', 0),
                    show.get('status'), show.get('popularity_updated') or now
                ))
            
            cursor.executemany('''
                INSERT OR REPLACE INTO tvshows (
                    tmdb_id, title, original_title, title_normalized, year, imdb_id,
                    poster, backdrop, synopsis, providers, certification, date_added,
                    popularity, rating, genres, genres_normalized, seasons_data,
                    clearlogo, banner, landscape, playcount, season_count,
                    episodes_count, status, popularity_updated
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', data)
            
            conn.commit()
            
            # Limpa caches relevantes
            self._cache_delete_prefix("tv_")
            self._cache_delete_prefix("tvshow:")
        finally:
            self._release_conn(conn)
    
    def get_tvshow_by_id(self, tmdb_id):
        """Busca série específica (com cache)"""
        cache_key = f"tvshow:{tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = "SELECT * FROM tvshows WHERE tmdb_id = ?"
        show = self._execute_query(sql, (int(tmdb_id),), fetch_one=True)
        
        if show:
            self._cache_set(cache_key, show, ttl=3600)  # 1 hora
        
        return show
    
    def get_all_tvshow_ids_set(self):
        """Retorna SET de IDs (ultra-rápido)"""
        cache_key = "all_tvshow_ids"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM tvshows")
            ids = {row[0] for row in cursor.fetchall() if row[0]}
            self._cache_set(cache_key, ids, ttl=600)
            return ids
        except Exception as e:
            xbmc.log(f"[DB ERROR] Falha ao buscar IDs de séries: {e}", xbmc.LOGERROR)
            return set()
        finally:
            self._release_conn(conn)
    
    def update_tv_popularity_bulk(self, updates):
        """Atualização em massa de popularidade"""
        if not updates:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            data = [(u['popularity'], now, u['tmdb_id']) for u in updates]
            cursor.executemany('UPDATE tvshows SET popularity=?, popularity_updated=? WHERE tmdb_id=?', data)
            conn.commit()
            self._cache_delete_prefix("tv_pop:")
        finally:
            self._release_conn(conn)
    
    # === CACHE DE TEMPORADAS E EPISÓDIOS ===
    
    def get_cached_seasons(self, tvshow_tmdb_id, max_age_hours=72):
        """Busca temporadas do cache local (com TTL)"""
        cache_key = f"seasons:{tvshow_tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = """
            SELECT * FROM seasons_cache 
            WHERE tvshow_tmdb_id = ? 
            AND last_updated > datetime('now', ?)
        """
        
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (tvshow_tmdb_id, f'-{max_age_hours} hours'))
            results = [dict(row) for row in cursor.fetchall()]
            
            if results:
                self._cache_set(cache_key, results, ttl=max_age_hours * 3600)
            
            return results if results else None
        finally:
            self._release_conn(conn)
    
    def save_seasons_cache(self, tvshow_tmdb_id, seasons_data_list):
        """Salva temporadas no cache (batch otimizado)"""
        if not seasons_data_list:
            return
        
        xbmc.log(f"[CACHE] Salvando {len(seasons_data_list)} temporadas para {tvshow_tmdb_id}", xbmc.LOGINFO)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Limpa cache antigo
            cursor.execute("DELETE FROM seasons_cache WHERE tvshow_tmdb_id = ?", (tvshow_tmdb_id,))
            
            # Prepara novos dados
            data = []
            for season in seasons_data_list:
                poster = f"https://image.tmdb.org/t/p/w500{season.get('poster_path')}" if season.get('poster_path') else None
                data.append((
                    tvshow_tmdb_id,
                    season.get('season_number', season.get('number', 0)),
                    season.get('name'),
                    season.get('overview'),
                    poster,
                    season.get('air_date'),
                    season.get('episode_count'),
                    season.get('vote_average', 0.0)
                ))
            
            # Insert em lote
            cursor.executemany('''
                INSERT INTO seasons_cache (
                    tvshow_tmdb_id, season_number, name, overview, poster,
                    air_date, episode_count, vote_average
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
            
            conn.commit()
            
            # Limpa cache de memória
            self._cache_delete_prefix(f"seasons:{tvshow_tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def get_cached_episodes(self, tvshow_tmdb_id, season_number, max_age_hours=72):
        """Busca episódios do cache local"""
        cache_key = f"episodes:{tvshow_tmdb_id}:{season_number}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = """
            SELECT * FROM episodes_cache
            WHERE tvshow_tmdb_id = ? AND season_number = ?
            AND last_updated > datetime('now', ?)
        """
        
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (tvshow_tmdb_id, season_number, f'-{max_age_hours} hours'))
            results = [dict(row) for row in cursor.fetchall()]
            
            if results:
                self._cache_set(cache_key, results, ttl=max_age_hours * 3600)
            
            return results if results else None
        finally:
            self._release_conn(conn)
    
    def save_episodes_cache(self, tvshow_tmdb_id, season_number, episodes_data_list):
        """Salva episódios no cache (batch otimizado)"""
        if not episodes_data_list:
            return
        
        xbmc.log(f"[CACHE] Salvando {len(episodes_data_list)} episódios para S{season_number}", xbmc.LOGINFO)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Limpa cache antigo
            cursor.execute(
                "DELETE FROM episodes_cache WHERE tvshow_tmdb_id = ? AND season_number = ?",
                (tvshow_tmdb_id, season_number)
            )
            
            # Prepara novos dados
            data = []
            for ep in episodes_data_list:
                data.append((
                    tvshow_tmdb_id,
                    season_number,
                    ep.get('episode_number'),
                    ep.get('name'),
                    ep.get('overview'),
                    ep.get('still_path'),
                    ep.get('air_date'),
                    ep.get('vote_average', 0.0),
                    ep.get('runtime', 0)
                ))
            
            # Insert em lote
            cursor.executemany('''
                INSERT INTO episodes_cache (
                    tvshow_tmdb_id, season_number, episode_number, name, overview,
                    still_path, air_date, vote_average, runtime
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
            
            conn.commit()
            
            # Limpa cache de memória
            self._cache_delete_prefix(f"episodes:{tvshow_tmdb_id}:{season_number}")
        finally:
            self._release_conn(conn)
    
    # === LISTAGENS ===
    
    def get_all_unique_tvshow_genres(self):
        """Gêneros únicos de séries (cache super longo)"""
        cache_key = "tv_genres"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT genres FROM tvshows")
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
    
    def get_tvshows_by_genre(self, genre, page=1, items_per_page=20):
        """Séries por gênero"""
        normalized_genre = self._normalize_text(genre)
        cache_key = f"tv_genre:{normalized_genre}:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        sql = """
            SELECT * FROM tvshows
            WHERE genres_normalized LIKE ?
            ORDER BY popularity DESC
            LIMIT ? OFFSET ?
        """
        
        shows = self._execute_query(sql, (f'%"{normalized_genre}"%', items_per_page, offset))
        self._cache_set(cache_key, shows, ttl=600)
        return shows
    
    def get_recently_added_tvshows(self, page, page_size):
        """Recém-adicionadas"""
        cache_key = f"tv_recent:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (int(page) - 1) * page_size
        sql = "SELECT * FROM tvshows WHERE date_added IS NOT NULL ORDER BY date_added DESC LIMIT ? OFFSET ?"
        
        shows = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, shows, ttl=600)
        return shows
    
    def get_kids_tvshows(self, page, page_size):
        """Séries infantis"""
        cache_key = f"tv_kids:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        sql = """
            SELECT * FROM tvshows
            WHERE certification IN ('L', '10', '12') OR genres LIKE '%Kids%'
            ORDER BY popularity DESC
            LIMIT ? OFFSET ?
        """
        
        shows = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, shows, ttl=1200)
        return shows
    
    def get_tvshows_by_popularity(self, page=1, page_size=20):
        """Top séries por popularidade"""
        cache_key = f"tv_pop:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (int(page) - 1) * page_size
        sql = "SELECT * FROM tvshows ORDER BY popularity DESC LIMIT ? OFFSET ?"
        
        shows = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, shows, ttl=900)
        return shows
    
    def get_tvshows_by_provider(self, provider, page=1, items_per_page=20):
        """Séries por streaming"""
        cache_key = f"tv_provider:{provider}:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        sql = """
            SELECT * FROM tvshows
            WHERE providers LIKE ?
            ORDER BY popularity DESC
            LIMIT ? OFFSET ?
        """
        
        shows = self._execute_query(sql, (f'%"{provider}"%', items_per_page, offset))
        self._cache_set(cache_key, shows, ttl=1200)
        return shows
    
    def get_all_unique_providers(self):
        """Provedores únicos (cache longo + normalização)"""
        cache_key = "tv_providers"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        # Mapa de normalização
        provider_map = {
            "netflix": "Netflix",
            "netflix basic with ads": "Netflix",
            "amazon": "Amazon Prime Video",
            "prime video": "Amazon Prime Video",
            "amazon prime video": "Amazon Prime Video",
            "amazon with ads": "Amazon Prime Video",
            "hbo": "Max",
            "hbo max": "Max",
            "max": "Max",
            "max channel": "Max",
            "disney plus": "Disney Plus",
            "paramount plus": "Paramount Plus",
            "apple tv+": "Apple TV+",
            "apple tv plus": "Apple TV+",
            "crunchyroll": "Crunchyroll",
            "globoplay": "Globoplay",
            "looke": "Looke",
            "peacock": "Peacock",
            "hulu": "Hulu",
            "discovery+": "Discovery+",
        }
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT providers FROM tvshows")
            all_providers = set()
            
            for (providers_json,) in cursor.fetchall():
                try:
                    providers = json.loads(providers_json) if providers_json else []
                    for provider in providers:
                        normalized = provider.strip().lower()
                        if normalized in provider_map:
                            all_providers.add(provider_map[normalized])
                except:
                    pass
            
            result = sorted(all_providers)
            self._cache_set(cache_key, result, ttl=7200)
            return result
        finally:
            self._release_conn(conn)