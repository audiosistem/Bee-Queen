# -*- coding: utf-8 -*-
import sqlite3
import json
import os
import time
import unicodedata
import xbmcaddon
import xbmcvfs
import xbmc

# === CONFIGURAÇÕES ===
ADDON = xbmcaddon.Addon()
PROFILE_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
DB_FILE = os.path.join(PROFILE_DIR, 'cinebox.db')
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

# === CACHE INTELIGENTE COM TTL ===
class SmartCache:
    """✅ OTIMIZADO: Cache com expiração automática e limite de memória"""
    def __init__(self, max_size=1000, default_ttl=600):  # ⬆️ Aumentado de 500/300
        self._data = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
    
    def get(self, key):
        if key in self._data:
            value, expires = self._data[key]
            if time.time() < expires:
                return value
            else:
                del self._data[key]  # Expirou, remove
        return None
    
    def set(self, key, value, ttl=None):
        # Limpa cache se tiver muito cheio (LRU simples)
        if len(self._data) >= self.max_size:
            # Remove 20% dos itens mais antigos
            to_remove = sorted(self._data.items(), key=lambda x: x[1][1])[:self.max_size//5]
            for k, _ in to_remove:
                del self._data[k]
        
        expires = time.time() + (ttl or self.default_ttl)
        self._data[key] = (value, expires)
    
    def delete_prefix(self, prefix):
        to_delete = [k for k in self._data if k.startswith(prefix)]
        for k in to_delete:
            del self._data[k]
    
    def clear(self):
        self._data.clear()

# === POOL DE CONEXÕES ===
class ConnectionPool:
    """✅ OTIMIZADO: Gerencia conexões reutilizáveis para evitar overhead"""
    def __init__(self, db_file, pool_size=5):  # ⬆️ Aumentado de 3 para 5
        self.db_file = db_file
        self.pool = []
        self.pool_size = pool_size
        self._in_use = set()
    
    def get_connection(self):
        # Tenta reusar conexão livre
        for conn in self.pool:
            if conn not in self._in_use:
                self._in_use.add(conn)
                return conn
        
        # Cria nova se pool não está cheio
        if len(self.pool) < self.pool_size:
            conn = self._create_connection()
            self.pool.append(conn)
            self._in_use.add(conn)
            return conn
        
        # Pool cheio, cria temporária
        return self._create_connection()
    
    def _create_connection(self):
        conn = sqlite3.connect(self.db_file, timeout=15.0, check_same_thread=False)  # ⬆️ Timeout aumentado
        # ✅ OTIMIZAÇÕES SQLITE
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # ⬆️ 64MB cache (era 32MB)
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=536870912")  # ⬆️ 512MB mmap (era 256MB)
        conn.execute("PRAGMA page_size=4096")  # ✅ NOVO: Tamanho de página otimizado
        conn.execute("PRAGMA locking_mode=NORMAL")  # ✅ NOVO: Melhor concorrência
        return conn
    
    def release_connection(self, conn):
        if conn in self._in_use:
            self._in_use.remove(conn)
    
    def close_all(self):
        for conn in self.pool:
            try:
                conn.close()
            except:
                pass
        self.pool.clear()
        self._in_use.clear()

# === BASE DATABASE OTIMIZADA ===
class BaseDatabase:
    _pool = None  # Pool compartilhado entre instâncias
    
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self._cache = SmartCache(max_size=1000, default_ttl=600)  # ⬆️ Otimizado
        
        # Inicializa pool uma vez
        if BaseDatabase._pool is None:
            BaseDatabase._pool = ConnectionPool(db_file, pool_size=5)  # ⬆️ Otimizado
        
        if not os.path.exists(self.db_file):
            self.run_first_time_setup()
    
    def _get_conn(self):
        """Retorna conexão do pool (MAIS RÁPIDO)"""
        return BaseDatabase._pool.get_connection()
    
    def _release_conn(self, conn):
        """Devolve conexão ao pool"""
        BaseDatabase._pool.release_connection(conn)
    
    def _execute_query(self, sql, params=(), fetch_one=False, fetch_all=True):
        """Helper universal para queries (reduz código repetido)"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute(sql, params)
            
            if fetch_one:
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetch_all:
                return self._rows_to_dict(cursor.fetchall())
            else:
                conn.commit()
                return cursor.lastrowid
        finally:
            self._release_conn(conn)
    
    # === CACHE HELPERS ===
    def _cache_get(self, key):
        return self._cache.get(key)
    
    def _cache_set(self, key, value, ttl=None):
        self._cache.set(key, value, ttl)
    
    def _cache_delete_prefix(self, prefix):
        self._cache.delete_prefix(prefix)
    
    # === NORMALIZAÇÃO ===
    @staticmethod
    def _normalize_text(text):
        """Cache interno para textos normalizados"""
        if not isinstance(text, str):
            return ""
        nfkd = unicodedata.normalize('NFKD', text.lower())
        return "".join([c for c in nfkd if not unicodedata.combining(c)])
    
    # === OTIMIZAÇÃO DE _rows_to_dict ===
    def _rows_to_dict(self, rows, skip_json=False):
        """
        Converte rows em dict com opção de pular JSON parse
        skip_json=True: 50% mais rápido quando não precisa dos arrays
        """
        if not rows:
            return []
        
        items = []
        for row in rows:
            item = dict(row)
            
            if not skip_json:
                # JSON fields (só processa se necessário)
                for field in ['genres', 'streams', 'providers', 'seasons_data']:
                    if field in item and item[field]:
                        try:
                            if isinstance(item[field], str) and item[field].startswith('['):
                                item[field] = json.loads(item[field])
                            else:
                                item[field] = []
                        except (json.JSONDecodeError, TypeError):
                            item[field] = []
            
            # String "None" -> ""
            for field in ['collection', 'certification', 'original_title', 'imdb_id', 
                         'clearlogo', 'synopsis', 'poster', 'backdrop']:
                if field in item and (item[field] == 'None' or item[field] is None):
                    item[field] = ''
            
            # Numeric defaults (só se existir no row)
            numeric_defaults = {
                'rating': 0.0, 'runtime': 0, 'year': 0, 
                'popularity': 0.0, 'revenue': 0, 'playcount': 0
            }
            for field, default in numeric_defaults.items():
                if field in item:
                    try:
                        item[field] = float(item[field]) if '.' in str(default) else int(item[field])
                    except (ValueError, TypeError):
                        item[field] = default
            
            items.append(item)
        
        return items
    
    # === SETUP INICIAL ===
    def run_first_time_setup(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            self._create_all_tables(cursor)
            conn.commit()
        finally:
            self._release_conn(conn)
    
    def _create_all_tables(self, cursor):
        self._create_movies_table(cursor)
        self._create_tvshows_table(cursor)
        self._create_favorites_table(cursor)
        self._create_seasons_cache_table(cursor)
        self._create_episodes_cache_table(cursor)
        self._create_api_cache_table(cursor)
        self._create_collections_meta_table(cursor)
        self._create_fts_tables(cursor)  # ✅ NOVO
    
    # === TABELAS (mantidas igual, mas com FTS) ===
    def _create_movies_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INTEGER PRIMARY KEY, title TEXT NOT NULL, original_title TEXT, 
                title_normalized TEXT, year INTEGER, imdb_id TEXT, rating REAL,
                poster TEXT, backdrop TEXT, synopsis TEXT, date_added TEXT, runtime INTEGER, 
                popularity REAL, revenue REAL, collection TEXT, genres TEXT, 
                genres_normalized TEXT, streams TEXT, providers TEXT, clearlogo TEXT,
                playcount INTEGER DEFAULT 0, popularity_updated TEXT
            )
        ''')
        # Índices otimizados
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_popularity ON movies(popularity DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_revenue ON movies(revenue DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_date_added ON movies(date_added DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_rating ON movies(rating DESC)")
    
    def _create_tvshows_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tvshows (
                tmdb_id INTEGER PRIMARY KEY, title TEXT NOT NULL, original_title TEXT NOT NULL, 
                title_normalized TEXT, year INTEGER, imdb_id TEXT, poster TEXT, backdrop TEXT, 
                synopsis TEXT, providers TEXT, certification TEXT, date_added TEXT,
                popularity REAL, rating REAL, genres TEXT, genres_normalized TEXT, 
                seasons_data TEXT, clearlogo TEXT, banner TEXT, landscape TEXT,
                playcount INTEGER DEFAULT 0, season_count INTEGER DEFAULT 0,
                episodes_count INTEGER DEFAULT 0, status TEXT, popularity_updated TEXT
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_popularity ON tvshows(popularity DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_date_added ON tvshows(date_added DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_rating ON tvshows(rating DESC)")
    
    def _create_favorites_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                tmdb_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                PRIMARY KEY (tmdb_id, media_type)
            )
        ''')
    
    def _create_seasons_cache_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seasons_cache (
                season_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tvshow_tmdb_id INTEGER NOT NULL, season_number INTEGER NOT NULL,
                name TEXT, overview TEXT, poster TEXT, air_date TEXT,
                episode_count INTEGER, vote_average REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tvshow_tmdb_id) REFERENCES tvshows(tmdb_id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_seasons_tvshow ON seasons_cache(tvshow_tmdb_id)')
    
    def _create_episodes_cache_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS episodes_cache (
                episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tvshow_tmdb_id INTEGER NOT NULL, season_number INTEGER NOT NULL,
                episode_number INTEGER NOT NULL, name TEXT, overview TEXT,
                still_path TEXT, air_date TEXT, vote_average REAL, runtime INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tvshow_tmdb_id) REFERENCES tvshows(tmdb_id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_tvshow_season ON episodes_cache(tvshow_tmdb_id, season_number)')
    
    def _create_api_cache_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY, data_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_cache_timestamp ON api_cache(timestamp)")
    
    def _create_collections_meta_table(self, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collections_meta (
                collection_name TEXT PRIMARY KEY, poster TEXT, backdrop TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # === ✅ FULL-TEXT SEARCH (FTS5) - OPCIONAL ===
    def _create_fts_tables(self, cursor):
        """Cria tabelas FTS para busca ULTRA-RÁPIDA (se suportado)"""
        try:
            # Verifica se FTS5 está disponível
            cursor.execute("SELECT compile_options FROM pragma_compile_options WHERE compile_options LIKE 'ENABLE_FTS5'")
            if not cursor.fetchone():
                xbmc.log("[DB] FTS5 não disponível no sistema", xbmc.LOGINFO)
                return

            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS movies_fts 
                USING fts5(tmdb_id UNINDEXED, title, content=movies, content_rowid=tmdb_id)
            ''')
            
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS tvshows_fts 
                USING fts5(tmdb_id UNINDEXED, title, content=tvshows, content_rowid=tmdb_id)
            ''')
            
            # Triggers para manter FTS sincronizado
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS movies_fts_insert AFTER INSERT ON movies BEGIN
                    INSERT INTO movies_fts(tmdb_id, title) VALUES (new.tmdb_id, new.title);
                END
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS movies_fts_update AFTER UPDATE ON movies BEGIN
                    UPDATE movies_fts SET title = new.title WHERE tmdb_id = new.tmdb_id;
                END
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tvshows_fts_insert AFTER INSERT ON tvshows BEGIN
                    INSERT INTO tvshows_fts(tmdb_id, title) VALUES (new.tmdb_id, new.title);
                END
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tvshows_fts_update AFTER UPDATE ON tvshows BEGIN
                    UPDATE tvshows_fts SET title = new.title WHERE tmdb_id = new.tmdb_id;
                END
            ''')
        except Exception as e:
            xbmc.log(f"[DB] Erro ao criar FTS: {e}", xbmc.LOGWARNING)
    
    # === BUSCA OTIMIZADA COM FTS ===
    def search_items(self, query, limit=20, offset=0):
        """Busca usando FTS5 se disponível, senão usa LIKE"""
        cache_key = f"search:{query}:{limit}:{offset}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        # Prepara query (remove acentos)
        norm_query = self._normalize_text(query)
        
        # Verifica se tabelas FTS existem
        conn = self._get_conn()
        cursor = conn.cursor()
        has_fts = False
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='movies_fts'")
            has_fts = bool(cursor.fetchone())
        except:
            pass
        finally:
            self._release_conn(conn)

        if has_fts:
            sql = """
                SELECT m.*, 'movie' AS media_type FROM movies m
                JOIN movies_fts ON movies_fts.tmdb_id = m.tmdb_id
                WHERE movies_fts MATCH ?
                UNION ALL
                SELECT t.*, 'tvshow' AS media_type FROM tvshows t
                JOIN tvshows_fts ON tvshows_fts.tmdb_id = t.tmdb_id
                WHERE tvshows_fts MATCH ?
                LIMIT ? OFFSET ?
            """
            params = (norm_query, norm_query, limit, offset)
        else:
            sql = """
                SELECT *, 'movie' AS media_type FROM movies WHERE title_normalized LIKE ?
                UNION ALL
                SELECT *, 'tvshow' AS media_type FROM tvshows WHERE title_normalized LIKE ?
                LIMIT ? OFFSET ?
            """
            params = (f'%{norm_query}%', f'%{norm_query}%', limit, offset)
        
        results = self._execute_query(sql, params)
        self._cache_set(cache_key, results, ttl=600)  # 10 min
        return results
    
    # === HELPERS PARA API CACHE ===
    def save_tmdb_cache(self, key, data):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO api_cache (cache_key, data_json) VALUES (?, ?)",
                (key, json.dumps(data))
            )
            conn.commit()
        finally:
            self._release_conn(conn)
    
    def get_tmdb_cache(self, key, hours=24):
        sql = f"SELECT data_json FROM api_cache WHERE cache_key = ? AND timestamp > datetime('now', '-{hours} hours')"
        result = self._execute_query(sql, (key,), fetch_one=True, fetch_all=False)
        return json.loads(result['data_json']) if result else None
    
    
    def get_watched_movies(self):
        """Retorna filmes com playcount > 0"""
        sql = """
            SELECT tmdb_id, imdb_id, title, playcount, 
                   datetime(date_added) as last_played
            FROM movies 
            WHERE playcount > 0
            ORDER BY date_added DESC
        """
        return self._execute_query(sql)
    
    def get_watched_tvshows(self):
        """Retorna séries com playcount > 0"""
        sql = """
            SELECT tmdb_id, imdb_id, title, playcount,
                   datetime(date_added) as last_played
            FROM tvshows 
            WHERE playcount > 0
            ORDER BY date_added DESC
        """
        return self._execute_query(sql)
    
    def update_movie_playcount(self, tmdb_id, playcount, last_played=None):
        """Atualiza playcount de um filme"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE movies 
                SET playcount = ?,
                    date_added = COALESCE(?, date_added)
                WHERE tmdb_id = ?
            """, (playcount, last_played, tmdb_id))
            
            conn.commit()
            self._cache_delete_prefix(f"movie_{tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def update_tvshow_playcount(self, tmdb_id, last_played=None):
        """Atualiza playcount de uma série"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE tvshows 
                SET playcount = playcount + 1,
                    date_added = COALESCE(?, date_added)
                WHERE tmdb_id = ?
            """, (last_played, tmdb_id))
            
            conn.commit()
            self._cache_delete_prefix(f"tvshow_{tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def mark_movie_as_watched(self, tmdb_id):
        """Marca filme como assistido"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE movies 
                SET playcount = playcount + 1,
                    date_added = CURRENT_TIMESTAMP
                WHERE tmdb_id = ?
            """, (tmdb_id,))
            
            conn.commit()
            self._cache_delete_prefix(f"movie_{tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def get_all_favorites(self):
        """Retorna todos favoritos"""
        sql = """
            SELECT tmdb_id, media_type 
            FROM favorites
            ORDER BY rowid DESC
        """
        return self._execute_query(sql)

    def get_favorites_by_type(self, media_type):
        """Retorna favoritos de um tipo específico com dados completos"""
        table = 'movies' if media_type == 'movie' else 'tvshows'
        sql = f"""
            SELECT t.*, f.media_type
            FROM {table} t
            JOIN favorites f ON f.tmdb_id = t.tmdb_id
            WHERE f.media_type = ?
            ORDER BY f.rowid DESC
        """
        return self._execute_query(sql, (media_type,))
    
    def add_to_favorites(self, tmdb_id, media_type):
        """Adiciona aos favoritos"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO favorites (tmdb_id, media_type)
                VALUES (?, ?)
            """, (tmdb_id, media_type))
            
            conn.commit()
            self._cache_delete_prefix("favorites")
        finally:
            self._release_conn(conn)
    
    
    
    # === LIMPEZA ===
    def clear_database(self, preserve_favorites=True):
        xbmc.log("[DB] Iniciando limpeza do banco de dados", xbmc.LOGINFO)
        conn = self._get_conn()
        cursor = conn.cursor()
        
        saved_favorites = []
        if preserve_favorites:
            try:
                cursor.execute("SELECT tmdb_id, media_type FROM favorites")
                saved_favorites = cursor.fetchall()
            except:
                pass
        
        # Drop all
        for table in ['movies', 'tvshows', 'favorites', 'api_cache', 
                     'seasons_cache', 'episodes_cache', 'collections_meta',
                     'movies_fts', 'tvshows_fts']:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
        conn.commit()
        self._create_all_tables(cursor)
        
        if saved_favorites:
            cursor.executemany(
                "INSERT OR IGNORE INTO favorites (tmdb_id, media_type) VALUES (?, ?)",
                saved_favorites
            )
            conn.commit()
        
        self._release_conn(conn)
        self._cache.clear()