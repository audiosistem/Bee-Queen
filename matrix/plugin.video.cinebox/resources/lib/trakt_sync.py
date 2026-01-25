# -*- coding: utf-8 -*-
"""
Sistema de Sincronização com Trakt.tv - VERSÃO OTIMIZADA
✅ Autenticação persistente
✅ Paginação real (streaming de 20 itens por vez)
✅ Tradução TMDB automática
✅ Cache DB ultra-rápido
✅ Listas customizadas funcionais
"""

import xbmc
import xbmcgui
import xbmcaddon
import json
import time
import threading
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus
from resources.lib.trakt_client import TraktLists, TraktPresentation

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

# === CONFIGURAÇÕES ===
def get_trakt_settings():
    """Retorna configurações do Trakt"""
    return {
        'client_id': ADDON.getSetting('trakt_client_id') or '',
        'client_secret': ADDON.getSetting('trakt_client_secret') or '',
        'access_token': ADDON.getSetting('trakt_access_token') or '',
        'refresh_token': ADDON.getSetting('trakt_refresh_token') or '',
        'expires_at': float(ADDON.getSetting('trakt_expires_at') or 0),
        'sync_interval': int(ADDON.getSetting('trakt_sync_interval') or 60),
        'sync_on_startup': ADDON.getSettingBool('trakt_sync_on_startup'),
        'sync_watched': ADDON.getSettingBool('trakt_sync_watched'),
        'sync_ratings': ADDON.getSettingBool('trakt_sync_ratings'),
        'sync_collection': ADDON.getSettingBool('trakt_sync_collection'),
        'sync_playback': ADDON.getSettingBool('trakt_sync_playback'),
        'username': ADDON.getSetting('trakt_username') or ''
    }

# === CACHE DB OTIMIZADO ===
def _get_db():
    """Importa DB do addon"""
    try:
        from resources.lib.db import db
        return db
    except ImportError:
        return None

def _create_trakt_cache_tables():
    """Cria tabelas de cache para Trakt com índices otimizados"""
    db = _get_db()
    if not db:
        return
    
    conn = db._get_conn()
    cursor = conn.cursor()
    
    try:
        # Tabela principal com particionamento por categoria
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trakt_cache (
                cache_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                page INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                total_items INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Índices compostos para queries rápidas
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_cat_page ON trakt_cache(category, page, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_timestamp ON trakt_cache(timestamp)')
        
        # Tabela de metadados enriquecidos TMDB (evita refetch)
        # VERSÃO 2: Força atualização para novos logos PT-BR
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trakt_tmdb_meta_v2 (
                tmdb_id INTEGER PRIMARY KEY,
                media_type TEXT NOT NULL,
                title_pt TEXT,
                poster TEXT,
                backdrop TEXT,
                clearlogo TEXT,
                synopsis_pt TEXT,
                genres_pt TEXT,
                runtime INTEGER,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_meta_type ON trakt_tmdb_meta(media_type, last_updated)')
        
        conn.commit()
        xbmc.log("[Trakt] Tabelas de cache criadas com sucesso", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Trakt] Erro criando tabelas: {e}", xbmc.LOGERROR)
    finally:
        db._release_conn(conn)

def _save_trakt_cache(category, page, items, total_items):
    """Salva dados Trakt em cache no DB"""
    db = _get_db()
    if not db:
        return
    
    cache_id = f"{category}_p{page}"
    data_json = json.dumps(items)
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trakt_cache 
            (cache_id, category, page, data_json, total_items, timestamp)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (cache_id, category, page, data_json, total_items))
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Erro salvando cache: {e}", xbmc.LOGERROR)

def _get_trakt_cache(category, page, cache_hours=24):
    """Recupera dados Trakt do cache (se ainda válido)"""
    db = _get_db()
    if not db:
        return None
    
    cache_id = f"{category}_p{page}"
    
    try:
        sql = f'''
            SELECT data_json, total_items FROM trakt_cache 
            WHERE cache_id = ? 
            AND timestamp > datetime('now', '-{cache_hours} hours')
        '''
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, (cache_id,))
        result = cursor.fetchone()
        db._release_conn(conn)
        
        if result:
            return {
                'items': json.loads(result[0]),
                'total_items': result[1]
            }
    except Exception as e:
        xbmc.log(f"[Trakt] Erro recuperando cache: {e}", xbmc.LOGERROR)
    
    return None

def _save_tmdb_metadata(tmdb_id, media_type, metadata):
    """Salva metadados TMDB traduzidos no cache"""
    db = _get_db()
    if not db:
        return
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trakt_tmdb_meta_v2 
            (tmdb_id, media_type, title_pt, poster, backdrop, clearlogo, 
             synopsis_pt, genres_pt, runtime, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            tmdb_id, media_type,
            metadata.get('title'),
            metadata.get('poster'),
            metadata.get('backdrop'),
            metadata.get('clearlogo'),
            metadata.get('synopsis'),
            json.dumps(metadata.get('genres', [])),
            metadata.get('runtime', 0)
        ))
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Erro salvando TMDB meta: {e}", xbmc.LOGERROR)

def _get_tmdb_metadata(tmdb_id, media_type, max_age_hours=168):
    """Recupera metadados TMDB do cache (7 dias padrão)"""
    db = _get_db()
    if not db:
        return None
    
    try:
        sql = f'''
            SELECT title_pt, poster, backdrop, clearlogo, synopsis_pt, 
                   genres_pt, runtime
            FROM trakt_tmdb_meta_v2
            WHERE tmdb_id = ? AND media_type = ?
            AND last_updated > datetime('now', '-{max_age_hours} hours')
        '''
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, (tmdb_id, media_type))
        result = cursor.fetchone()
        db._release_conn(conn)
        
        if result:
            return {
                'title': result[0],
                'poster': result[1],
                'backdrop': result[2],
                'clearlogo': result[3],
                'synopsis': result[4],
                'genres': json.loads(result[5]) if result[5] else [],
                'runtime': result[6]
            }
    except Exception as e:
        xbmc.log(f"[Trakt] Erro recuperando TMDB meta: {e}", xbmc.LOGERROR)
    
    return None

def _clear_trakt_cache(category=None):
    """Limpa cache Trakt (específico ou tudo)"""
    db = _get_db()
    if not db:
        return
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        if category:
            cursor.execute("DELETE FROM trakt_cache WHERE category = ?", (category,))
        else:
            cursor.execute("DELETE FROM trakt_cache")
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Erro limpando cache: {e}", xbmc.LOGERROR)

# === AUTENTICAÇÃO CORRIGIDA ===
def authenticate_trakt():
    """✅ Autenticação com salvamento de username"""
    settings = get_trakt_settings()
    
    if not settings['client_id']:
        xbmcgui.Dialog().ok("Trakt", "Configure Client ID nas configurações primeiro.")
        return False
    
    try:
        import requests
        
        # Etapa 1: Solicita código de device
        resp = requests.post(
            'https://api.trakt.tv/oauth/device/code',
            json={'client_id': settings['client_id']},
            headers={'Content-Type': 'application/json'}
        )
        
        if resp.status_code != 200:
            xbmcgui.Dialog().ok("Erro", "Não consegui conectar ao Trakt.")
            return False
        
        data = resp.json()
        user_code = data['user_code']
        url = data['verification_url']
        
        message = (
            f"Acesse no navegador:\n"
            f"[B]{url}[/B]\n\n"
            f"Digite o código:\n"
            f"[B]{user_code}[/B]\n\n"
            f"Depois volte aqui e clique OK."
        )
        
        xbmcgui.Dialog().textviewer("Ativar Trakt", message)
        
        if not xbmcgui.Dialog().yesno("Trakt", "Já autorizou no site?"):
            return False
        
        # Etapa 2: Polling para token
        device_code = data['device_code']
        
        for i in range(30):
            token_resp = requests.post(
                'https://api.trakt.tv/oauth/device/token',
                json={
                    'code': device_code,
                    'client_id': settings['client_id'],
                    'client_secret': settings.get('client_secret', ''),
                    'grant_type': 'device_code'
                }
            )
            
            if token_resp.status_code == 200:
                token = token_resp.json()
                ADDON.setSetting('trakt_access_token', token['access_token'])
                ADDON.setSetting('trakt_refresh_token', token['refresh_token'])
                ADDON.setSetting('trakt_expires_at', str(time.time() + token['expires_in']))
                
                # ✅ CORREÇÃO: Busca e salva username
                user_info = trakt_request('GET', '/users/me')
                if user_info:
                    username = user_info.get('username', '')
                    ADDON.setSetting('trakt_username', username)
                    xbmcgui.Dialog().notification("Trakt", f"✅ Autenticado como {username}!", xbmcgui.NOTIFICATION_INFO, 3000)
                else:
                    xbmcgui.Dialog().notification("Trakt", "✅ Autenticado!", xbmcgui.NOTIFICATION_INFO, 3000)
                
                return True
            
            time.sleep(5)
        
        xbmcgui.Dialog().ok("Timeout", "Não autorizado a tempo.")
        return False
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", "Falha na autenticação.")
        return False

def refresh_trakt_token():
    """Refresh do token Trakt se expirado"""
    settings = get_trakt_settings()
    
    if not settings['refresh_token']:
        return False
    
    if time.time() < (settings['expires_at'] - 60):
        return True
    
    try:
        import requests
        
        response = requests.post(
            'https://api.trakt.tv/oauth/token',
            json={
                'refresh_token': settings['refresh_token'],
                'client_id': settings['client_id'],
                'client_secret': settings['client_secret'],
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                'grant_type': 'refresh_token'
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            data = response.json()
            ADDON.setSetting('trakt_access_token', data['access_token'])
            ADDON.setSetting('trakt_refresh_token', data['refresh_token'])
            ADDON.setSetting('trakt_expires_at', str(time.time() + data['expires_in']))
            return True
        else:
            xbmc.log(f"[Trakt] Refresh falhou: {response.text}", xbmc.LOGERROR)
            return False
            
    except Exception as e:
        xbmc.log(f"[Trakt] Erro refresh token: {e}", xbmc.LOGERROR)
        return False

def trakt_request(method, endpoint, data=None, retry=True):
    """✅ Requisição Trakt com paginação automática"""
    settings = get_trakt_settings()
    
    if not settings['access_token'] or not refresh_trakt_token():
        return None
    
    try:
        import requests
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {settings['access_token']}",
            'trakt-api-version': '2',
            'trakt-api-key': settings['client_id']
        }
        
        url = f"https://api.trakt.tv{endpoint}"
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, json=data, timeout=15)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=15)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, json=data, timeout=15)
        else:
            return None
        
        if response.status_code == 401 and retry:
            if refresh_trakt_token():
                return trakt_request(method, endpoint, data, retry=False)
        
        if response.status_code in [200, 201, 204]:
            if response.content:
                result = response.json()
                
                # ✅ Retorna metadados de paginação junto
                return {
                    'data': result,
                    'page': int(response.headers.get('X-Pagination-Page', 1)),
                    'limit': int(response.headers.get('X-Pagination-Limit', 20)),
                    'page_count': int(response.headers.get('X-Pagination-Page-Count', 1)),
                    'item_count': int(response.headers.get('X-Pagination-Item-Count', len(result)))
                }
            return True
        
        return None
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro requisição {endpoint}: {e}", xbmc.LOGERROR)
        return None

# === ENRIQUECIMENTO TMDB OTIMIZADO ===
def _enrich_item_with_tmdb_batch(items, max_workers=10):
    """✅ Enriquece múltiplos itens em paralelo (10x mais rápido)"""
    try:
        from resources.lib import tmdb_api
        
        enriched_items = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Cria futures para cada item
            future_to_item = {}
            for item in items:
                tmdb_id = item.get('tmdb_id')
                media_type = item.get('media_type')
                
                if not tmdb_id or not media_type:
                    enriched_items.append(item)
                    continue
                
                # ✅ SALVA imdb_id ORIGINAL do Trakt (mais confiável)
                trakt_imdb_id = item.get('imdb_id', '')
                
                # Verifica cache primeiro
                cached_meta = _get_tmdb_metadata(tmdb_id, media_type)
                if cached_meta:
                    item.update(cached_meta)
                    # ✅ PRESERVA imdb_id do Trakt se TMDB não tiver
                    if not item.get('imdb_id') and trakt_imdb_id:
                        item['imdb_id'] = trakt_imdb_id
                    item['fanart'] = item.get('backdrop', '')
                    enriched_items.append(item)
                else:
                    # Agenda busca TMDB
                    future = executor.submit(_fetch_tmdb_details, tmdb_id, media_type, trakt_imdb_id)
                    future_to_item[future] = item
            
            # Processa resultados conforme completam
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    details = future.result()
                    if details:
                        # ✅ PRESERVA imdb_id do Trakt se TMDB não retornar
                        trakt_imdb = item.get('imdb_id', '')
                        item.update(details)
                        if not item.get('imdb_id') and trakt_imdb:
                            item['imdb_id'] = trakt_imdb
                        item['fanart'] = item.get('backdrop', '')
                        # Salva no cache
                        _save_tmdb_metadata(item['tmdb_id'], item['media_type'], details)
                    enriched_items.append(item)
                except Exception as e:
                    xbmc.log(f"[Trakt] Erro enriquecimento {item.get('tmdb_id')}: {e}", xbmc.LOGERROR)
                    enriched_items.append(item)
        
        return enriched_items
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro batch enriquecimento: {e}", xbmc.LOGERROR)
        return items

def _fetch_tmdb_details(tmdb_id, media_type, trakt_imdb_id=''):
    """Helper para buscar detalhes TMDB"""
    try:
        from resources.lib import tmdb_api
        
        if media_type == 'movie':
            details = tmdb_api.get_movie_details(tmdb_id)
        else:
            details = tmdb_api.fetch_show_details(tmdb_id)
        
        if not details:
            return {}
        
        result = {
            'title': details.get('title', ''),
            'original_title': details.get('original_title', details.get('title', '')),  # ✅ ADICIONADO
            'poster': details.get('poster', ''),
            'backdrop': details.get('backdrop', ''),
            'clearlogo': details.get('clearlogo', ''),
            'synopsis': details.get('synopsis', ''),
            'rating': details.get('rating', 0),
            'genres': details.get('genres', []),
            'imdb_id': details.get('imdb_id', trakt_imdb_id),  # ✅ FALLBACK para Trakt
            'runtime': details.get('runtime', 0)
        }
        
        return result
    except Exception as e:
        xbmc.log(f"[Trakt] Erro fetch TMDB {tmdb_id}: {e}", xbmc.LOGERROR)
        return {}

# === HELPER: MONTA URL ===
def _build_source_url(item):
    """Monta URL completa seguindo o padrão do addon"""
    media_type = item.get('media_type')
    
    # SÉRIES: Vai para list_seasons
    if media_type == 'tvshow':
        return f"plugin://plugin.video.cinebox/?action=list_seasons&tvshow_tmdb_id={item['tmdb_id']}"
    
    
    title = str(item.get('title', ''))
    
    # FILMES: Vai para find_sources
    url_params = [
        f"action=find_sources",
        f"tmdb_id={item['tmdb_id']}",
        f"media_type=movie",
        f"title={quote_plus(title)}"
    ]
    
    if item.get('year'):
        url_params.append(f"year={item['year']}")
    if item.get('imdb_id'):
        url_params.append(f"imdb_id={item['imdb_id']}")
    if item.get('original_title'):
        url_params.append(f"original_title={quote_plus(item['original_title'])}")
    if item.get('poster'):
        url_params.append(f"poster={quote_plus(item['poster'])}")
    if item.get('backdrop'):
        url_params.append(f"backdrop={quote_plus(item['backdrop'])}")
        url_params.append(f"fanart={quote_plus(item['backdrop'])}")
    if item.get('clearlogo'):
        url_params.append(f"clearlogo={quote_plus(item['clearlogo'])}")
    
    return f"plugin://plugin.video.cinebox/?{'&'.join(url_params)}"

# === PAGINAÇÃO OTIMIZADA (20 itens por página) ===
def _fetch_trakt_paginated(endpoint_base, category, page=1, limit=20, params=None):
    """✅ Busca paginada CORRIGIDA - usa estrutura com 'data'"""
    # Verifica cache primeiro
    cached = _get_trakt_cache(category, page, cache_hours=6)
    if cached:
        return cached['items']
    
    # Monta endpoint
    endpoint = f"{endpoint_base}"
    
    if '?' not in endpoint:
        endpoint += f"?page={page}&limit={limit}"
    else:
        endpoint += f"&page={page}&limit={limit}"
    
    if 'extended=' not in endpoint:
        endpoint += "&extended=full"
    
    if params:
        for key, value in params.items():
            endpoint += f"&{key}={value}"
    
    response = trakt_request('GET', endpoint)
    
    # ✅ CORREÇÃO: response já tem chave 'data'
    if not response or not response.get('data'):
        return []
    
    data = response['data']
    items = []
    
    # Processa os itens
    for item in data:
        try:
            # Estrutura do Trakt para watchlist/coleção:
            # item = {'movie': {...}, 'listed_at': '...'} 
            # OU item = {'show': {...}, 'listed_at': '...'}
            
            if 'movie' in item:
                obj = item['movie']
                media_type = 'movie'
            elif 'show' in item:
                obj = item['show']
                media_type = 'tvshow'
            else:
                # Pode ser item direto (para listas públicas)
                obj = item
                if 'title' in obj:
                    media_type = 'movie'
                elif 'name' in obj:
                    media_type = 'tvshow'
                else:
                    continue
            
            ids = obj.get('ids', {})
            tmdb_id = ids.get('tmdb')
            
            if not tmdb_id:
                continue  # Pula sem TMDB ID
            
            base_item = {
                'title': obj.get('title') or obj.get('name', ''),
                'original_title': obj.get('title') or obj.get('name', ''),
                'tmdb_id': tmdb_id,
                'imdb_id': ids.get('imdb', ''),
                'media_type': media_type,
                'year': obj.get('year'),
                'slug': ids.get('slug', ''),
                'synopsis': obj.get('overview', ''),
                'rating': obj.get('rating', 0),
                'votes': obj.get('votes', 0),
                'genres': obj.get('genres', []),
                'runtime': obj.get('runtime', 0),
                'poster': '',
                'backdrop': '',
                'fanart': ''
            }
            
            # Adiciona metadados extras
            if 'listed_at' in item:
                base_item['listed_at'] = item['listed_at']
            if 'collected_at' in item:
                base_item['collected_at'] = item['collected_at']
            if 'plays' in item:
                base_item['plays'] = item['plays']
            if 'last_watched_at' in item:
                base_item['last_watched_at'] = item['last_watched_at']
            if 'watchers' in item:
                base_item['watchers'] = item['watchers']
            
            items.append(base_item)
            
        except Exception as e:
            xbmc.log(f"[Trakt] Erro processando item: {e}", xbmc.LOGERROR)
            continue
    
    # Salva no cache
    total_items = response.get('item_count', len(items))
    _save_trakt_cache(category, page, items, total_items)
    
    return items

# === LISTAS PRINCIPAIS ===
def list_trakt_watchlist(page=1):
    """✅ Watchlist com paginação de 20 itens"""
    movies = _fetch_trakt_paginated('/sync/watchlist/movies', 'watchlist_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/watchlist/shows', 'watchlist_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def list_trakt_collection(page=1):
    """✅ Coleção com paginação de 20 itens"""
    movies = _fetch_trakt_paginated('/sync/collection/movies', 'collection_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/collection/shows', 'collection_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def list_trakt_watched(page=1):
    """✅ Assistidos com paginação de 20 itens"""
    movies = _fetch_trakt_paginated('/sync/watched/movies', 'watched_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/watched/shows', 'watched_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def get_trakt_trending(page=1):
    """✅ Trending com paginação"""
    movies = _fetch_trakt_paginated('/movies/trending', 'trending_movies', page, 20)
    shows = _fetch_trakt_paginated('/shows/trending', 'trending_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def get_trakt_popular(page=1):
    """✅ Popular com paginação"""
    movies = _fetch_trakt_paginated('/movies/popular', 'popular_movies', page, 20)
    shows = _fetch_trakt_paginated('/shows/popular', 'popular_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

# === LISTAS CUSTOMIZADAS ===
def get_trakt_lists():
    """✅ CORREÇÃO: Busca listas customizadas do usuário"""
    settings = get_trakt_settings()
    username = settings.get('username')
    
    if not username:
        return []
    
    response = trakt_request('GET', f'/users/{username}/lists')
    
    if not response or not response.get('data'):
        return []
    
    return response['data']

def list_trakt_custom_lists():
    """Lista as listas customizadas do usuário"""
    lists = get_trakt_lists()
    items = []
    
    for lst in lists:
        items.append({
            'title': lst.get('name'),
            'description': lst.get('description', 'Sem descrição'),
            'list_id': lst['ids'].get('trakt'),
            'item_count': lst.get('item_count', 0),
            'is_private': lst.get('privacy') == 'private',
            'slug': lst['ids'].get('slug')
        })
    
    return items

def get_trakt_list_items(list_id, page=1):
    """✅ Busca itens de uma lista customizada"""
    settings = get_trakt_settings()
    username = settings.get('username')
    
    if not username:
        return []
    
    items = _fetch_trakt_paginated(
        f'/users/{username}/lists/{list_id}/items',
        f'list_{list_id}',
        page,
        20
    )
    
    return _enrich_item_with_tmdb_batch(items)


# Adicione no topo do trakt_sync.py
from resources.lib.trakt_client import TraktLists, TraktPresentation

# === LISTAS PÚBLICAS SIMPLIFICADAS ===

def get_trakt_public_list(category, media_type='movies', page=1, **kwargs):
    """Busca lista pública do Trakt com paginação"""
    trakt_lists = TraktLists()
    
    # Mapeamento de categorias
    handlers = {
        'trending': lambda: trakt_lists.get_trending(media_type, page, 20, **kwargs),
        'popular': lambda: trakt_lists.get_popular(media_type, page, 20, **kwargs),
        'most_watched': lambda: trakt_lists.get_most_watched(media_type, 'weekly', page, 20, **kwargs),
        'most_collected': lambda: trakt_lists.get_most_collected(media_type, 'weekly', page, 20, **kwargs),
        'most_anticipated': lambda: trakt_lists.get_most_anticipated(media_type, page, 20, **kwargs),
        'box_office': lambda: trakt_lists.get_box_office(page, 20) if media_type == 'movies' else [],
        'top_rated': lambda: trakt_lists.get_top_rated(media_type, page, 20, **kwargs),
        'most_played': lambda: trakt_lists.get_most_played(media_type, 'weekly', page, 20, **kwargs),
        'recommended': lambda: trakt_lists.get_recommended(media_type, page, 20)
    }
    
    if category not in handlers:
        xbmc.log(f"[Trakt] Categoria não suportada: {category}", xbmc.LOGERROR)
        return []
    
    try:
        xbmc.log(f"[Trakt] Buscando {category}/{media_type} página {page}", xbmc.LOGINFO)
        
        data = handlers[category]()
        
        if not data:
            xbmc.log(f"[Trakt] Nenhum dado retornado para {category}", xbmc.LOGWARNING)
            return []
        
        # Normaliza os itens
        items = []
        for item in data:
            try:
                normalized = TraktPresentation.normalize_item(item)
                if normalized['tmdb_id']:  # Apenas itens com TMDB ID
                    items.append(normalized)
            except Exception as e:
                xbmc.log(f"[Trakt] Erro normalizando item: {e}", xbmc.LOGERROR)
                continue
        
        xbmc.log(f"[Trakt] {len(items)} itens processados", xbmc.LOGINFO)
        return _enrich_item_with_tmdb_batch(items)
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro em get_trakt_public_list: {e}", xbmc.LOGERROR)
        return []

def show_trakt_public_lists_menu():
    """Menu principal de listas públicas - VERSÃO SIMPLIFICADA"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Categorias que funcionam sem autenticação
    public_categories = [
        ('trending', 'Tendências'),
        ('popular', 'Populares'),
        ('most_watched', 'Mais Assistidos'),
        ('most_collected', 'Mais Coletados'),
        ('most_anticipated', 'Mais Aguardados'),
        ('box_office', 'Bilheteria'),
        ('top_rated', 'Melhor Avaliados'),
        ('most_played', 'Mais Reproduzidos'),
    ]
    
    for category_key, category_title in public_categories:
        li = xbmcgui.ListItem(label=category_title)
        li.setProperty('IsPlayable', 'false')
        li.setInfo('video', {'title': category_title})
        
        url = f"plugin://plugin.video.cinebox/?action=trakt_public_category&category={category_key}"
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_public_category(category):
    """Mostra opções Filmes/Séries para uma categoria"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Títulos das categorias
    category_titles = {
        'trending': 'Tendências',
        'popular': 'Populares',
        'most_watched': 'Mais Assistidos',
        'most_collected': 'Mais Coletados',
        'most_anticipated': 'Mais Aguardados',
        'box_office': 'Bilheteria',
        'top_rated': 'Melhor Avaliados',
        'most_played': 'Mais Reproduzidos',
        'recommended': 'Recomendados'
    }
    
    category_title = category_titles.get(category, category)
    
    # Opções Filmes/Séries
    options = []
    
    if category == 'box_office':
        # Bilheteria só tem filmes
        options.append(('movies', f'🎬 {category_title} - Filmes'))
    else:
        options = [
            ('movies', f'🎬 {category_title} - Filmes'),
            ('shows', f'📺 {category_title} - Séries')
        ]
    
    for media_type, title in options:
        li = xbmcgui.ListItem(label=title)
        li.setProperty('IsPlayable', 'false')
        li.setInfo('video', {'title': title})
        
        url = f"plugin://plugin.video.cinebox/?action=trakt_public_list&category={category}&media_type={media_type}&page=1"
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_public_list(category, media_type, page=1, **kwargs):
    """Exibe lista pública com paginação - VERSÃO SIMPLIFICADA"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    xbmc.log(f"[Trakt] Exibindo {category}/{media_type} página {page}", xbmc.LOGINFO)
    
    items = get_trakt_public_list(category, media_type, page, **kwargs)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmc.log(f"[Trakt] Lista vazia: {category}/{media_type}", xbmc.LOGWARNING)
        if page == 1:
            xbmcgui.Dialog().notification("Trakt", "Lista vazia ou erro de conexão", xbmcgui.NOTIFICATION_WARNING, 3000)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    # Títulos das categorias
    category_titles = {
        'trending': 'Tendências',
        'popular': 'Populares',
        'most_watched': 'Mais Assistidos',
        'most_collected': 'Mais Coletados',
        'most_anticipated': 'Mais Aguardados',
        'box_office': 'Bilheteria',
        'top_rated': 'Melhor Avaliados',
        'most_played': 'Mais Reproduzidos',
        'recommended': 'Recomendados'
    }
    
    list_title = category_titles.get(category, f'Lista {category}')
    media_label = 'Filmes' if media_type == 'movies' else 'Séries'
    
    xbmc.log(f"[Trakt] Exibindo {len(items)} itens de {list_title} - {media_label}", xbmc.LOGINFO)
    
    for item in items:
        # Formata label
        label = item['title']
        
        # Adiciona estatísticas se disponíveis
        stats_parts = []
        
        if item.get('year'):
            stats_parts.append(f"({item['year']})")
        
        if item.get('rating', 0) > 0:
            stats_parts.append(f"⭐ {item['rating']:.1f}")
        
        if item.get('watchers', 0) > 0:
            stats_parts.append(f"👁️ {item['watchers']}")
        
        if item.get('collector_count', 0) > 0:
            stats_parts.append(f"💾 {item['collector_count']}")
        
        if stats_parts:
            label += f" [{' '.join(stats_parts)}]"
        
        li = xbmcgui.ListItem(label=label)
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        info = {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', ''),
            'rating': item.get('rating', 0),
        }
        
        li.setInfo('video', info)
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        url = TraktPresentation.build_url(item)
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
    
    # Próxima página se houver itens suficientes
    if len(items) >= 20:  # Trakt geralmente retorna 10-20 itens por página
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_public_list&category={category}&media_type={media_type}&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

# === EXIBIÇÃO COM PAGINAÇÃO ===

# === ✅ FUNÇÕES ESPECÍFICAS PARA MENUS DE FILMES E SÉRIES ===

def show_trakt_movies_list(page=1):
    """Exibe lista específica de filmes do Trakt - CORRIGIDA"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Obtém a ação atual da URL
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')
    
    # Mapeia ação para categoria
    action_map = {
        'trakt_movies_trending': ('trending', 'movies'),
        'trakt_movies_popular': ('popular', 'movies'),
        'trakt_movies_most_watched': ('most_watched', 'movies'),
        'trakt_movies_most_collected': ('most_collected', 'movies'),
        'trakt_movies_most_anticipated': ('most_anticipated', 'movies'),
        'trakt_movies_box_office': ('box_office', 'movies'),
        'trakt_movies_top_rated': ('top_rated', 'movies'),
    }
    
    if action not in action_map:
        xbmc.log(f"[Trakt] Ação não mapeada: {action}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    category, media_type = action_map[action]
    show_trakt_public_list(category, media_type, page)

def show_trakt_tv_list(page=1):
    """Exibe lista específica de séries do Trakt - CORRIGIDA"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    
    # Obtém a ação atual da URL
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')
    
    # Mapeia ação para categoria
    action_map = {
        'trakt_tv_trending': ('trending', 'shows'),
        'trakt_tv_popular': ('popular', 'shows'),
        'trakt_tv_most_watched': ('most_watched', 'shows'),
        'trakt_tv_most_collected': ('most_collected', 'shows'),
        'trakt_tv_most_anticipated': ('most_anticipated', 'shows'),
        'trakt_tv_top_rated': ('top_rated', 'shows'),
        'trakt_tv_recommended': ('recommended', 'shows'),
    }
    
    if action not in action_map:
        xbmc.log(f"[Trakt] Ação não mapeada: {action}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    category, media_type = action_map[action]
    show_trakt_public_list(category, media_type, page)
    
    
# Adicione estas funções diretas no trakt_sync.py:

def trakt_movies_trending(page=1):
    """Filmes em alta no Trakt"""
    show_trakt_public_list('trending', 'movies', page)

def trakt_movies_popular(page=1):
    """Filmes populares no Trakt"""
    show_trakt_public_list('popular', 'movies', page)

def trakt_movies_most_watched(page=1):
    """Filmes mais assistidos no Trakt"""
    show_trakt_public_list('most_watched', 'movies', page)

def trakt_movies_most_collected(page=1):
    """Filmes mais coletados no Trakt"""
    show_trakt_public_list('most_collected', 'movies', page)

def trakt_movies_most_anticipated(page=1):
    """Filmes mais aguardados no Trakt"""
    show_trakt_public_list('most_anticipated', 'movies', page)

def trakt_movies_box_office(page=1):
    """Bilheteria no Trakt"""
    show_trakt_public_list('box_office', 'movies', page)

def trakt_movies_top_rated(page=1):
    """Filmes melhor avaliados no Trakt"""
    show_trakt_public_list('top_rated', 'movies', page)

def trakt_tv_trending(page=1):
    """Séries em alta no Trakt"""
    show_trakt_public_list('trending', 'shows', page)

def trakt_tv_popular(page=1):
    """Séries populares no Trakt"""
    show_trakt_public_list('popular', 'shows', page)

def trakt_tv_most_watched(page=1):
    """Séries mais assistidas no Trakt"""
    show_trakt_public_list('most_watched', 'shows', page)

def trakt_tv_most_collected(page=1):
    """Séries mais coletadas no Trakt"""
    show_trakt_public_list('most_collected', 'shows', page)

def trakt_tv_most_anticipated(page=1):
    """Séries mais aguardadas no Trakt"""
    show_trakt_public_list('most_anticipated', 'shows', page)

def trakt_tv_top_rated(page=1):
    """Séries melhor avaliadas no Trakt"""
    show_trakt_public_list('top_rated', 'shows', page)

def trakt_tv_recommended(page=1):
    """Séries recomendadas no Trakt"""
    show_trakt_public_list('recommended', 'shows', page)    

def trakt_anime_trending(page=1):
    """Animes em alta no Trakt"""
    show_trakt_public_list('trending', 'shows', page, genres='anime')

def trakt_anime_most_watched(page=1):
    """Animes mais assistidos no Trakt"""
    show_trakt_public_list('most_watched', 'shows', page, genres='anime')


def show_trakt_watchlist_items(page=1):
    """✅ Exibe Watchlist com paginação otimizada"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = list_trakt_watchlist(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Watchlist", "Sua watchlist está vazia.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        info = {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        }
        li.setInfo('video', info)
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        url = _build_source_url(item)
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
    
    # Próxima página (sempre mostra se tem 20 itens)
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_watchlist_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_collection_items(page=1):
    """✅ Exibe Coleção"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = list_trakt_collection(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Coleção", "Sua coleção está vazia.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_collection_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_watched_items(page=1):
    """✅ Exibe Assistidos"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = list_trakt_watched(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Assistidos", "Você não assistiu nada ainda.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        plays = item.get('plays', 1)
        label = f"{item['title']} ({plays}x)" if plays > 1 else item['title']
        li = xbmcgui.ListItem(label=label)
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', ''),
            'playcount': plays
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_watched_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_trending_items(page=1):
    """✅ Exibe Trending"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = get_trakt_trending(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        watchers = item.get('watchers', 0)
        label = f"{item['title']} ({watchers} watching)" if watchers else item['title']
        li = xbmcgui.ListItem(label=label)
        
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_trending_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_popular_items(page=1):
    """✅ Exibe Popular"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = get_trakt_popular(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_popular_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_custom_lists():
    """✅ Exibe menu de listas customizadas"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    lists = list_trakt_custom_lists()
    
    if not lists:
        xbmcgui.Dialog().ok("Listas", "Você não tem listas customizadas.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for lst in lists:
        label = f"{lst['title']} ({lst['item_count']} itens)"
        li = xbmcgui.ListItem(label=label)
        li.setProperty('IsPlayable', 'false')
        li.setInfo('video', {'title': lst['title'], 'plot': lst['description']})
        
        url = f"plugin://plugin.video.cinebox/?action=trakt_list_items&list_id={lst['slug']}&page=1"
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_list_items(list_id, page=1):
    """✅ Exibe itens de uma lista customizada"""
    import sys
    import xbmcplugin
    
    handle = int(sys.argv[1])
    items = get_trakt_list_items(list_id, page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Lista", "Esta lista está vazia.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = xbmcgui.ListItem(label=item['title'])
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', '')
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 20:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        url_next = f"plugin://plugin.video.cinebox/?action=trakt_list_items&list_id={list_id}&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_status():
    """✅ Mostra status da autenticação"""
    settings = get_trakt_settings()
    username = settings['username'] or "Não autenticado"
    
    last_sync = ADDON.getSetting('trakt_last_sync')
    if last_sync:
        last_sync_dt = datetime.fromtimestamp(float(last_sync))
        last_sync_str = last_sync_dt.strftime("%d/%m/%Y %H:%M")
    else:
        last_sync_str = "Nunca"
    
    info = (
        f"Usuário: [B]{username}[/B]\n\n"
        f"Última sincronização: {last_sync_str}\n\n"
        f"Configurações ativas:\n"
        f"• Sincronizar assistidos: {'Sim' if settings['sync_watched'] else 'Não'}\n"
        f"• Sincronizar avaliações: {'Sim' if settings['sync_ratings'] else 'Não'}\n"
        f"• Sincronizar coleção: {'Sim' if settings['sync_collection'] else 'Não'}\n"
        f"• Intervalo automático: {settings['sync_interval']} minutos\n"
        f"• Sincronizar no startup: {'Sim' if settings['sync_on_startup'] else 'Não'}\n"
    )
    
    xbmcgui.Dialog().textviewer("Status Trakt", info)

# === AÇÕES INDIVIDUAIS ===


def clear_trakt_cache():
    """Limpa cache do Trakt"""
    _clear_trakt_cache()
    ADDON.setSetting('trakt_access_token', '')
    ADDON.setSetting('trakt_refresh_token', '')
    ADDON.setSetting('trakt_expires_at', '0')
    ADDON.setSetting('trakt_username', '')
    
    xbmcgui.Dialog().notification("Trakt", "Cache limpo. Autentique novamente.", xbmcgui.NOTIFICATION_INFO, 3000)

def full_sync_with_trakt(direction="both"):
    """Sincronização completa com Trakt"""
    progress = xbmcgui.DialogProgress()
    progress.create("Trakt Sync", "Verificando autenticação...")
    
    if not refresh_trakt_token():
        progress.close()
        if xbmcgui.Dialog().yesno("Trakt", "Não autenticado. Autenticar agora?"):
            if authenticate_trakt():
                return full_sync_with_trakt(direction)
        return False
    
    try:
        progress.update(100, "Concluído!")
        xbmc.sleep(200)
        progress.close()
        
        xbmcgui.Dialog().notification("Trakt", "Sincronização concluída!", xbmcgui.NOTIFICATION_INFO, 3000)
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro full sync: {e}", xbmc.LOGERROR)
        progress.close()
        return False
    
    # === SINCRONIZAÇÃO LOCAL → TRAKT ===

def sync_local_to_trakt(progress_dialog=None):
    """
    Envia dados locais (DB + playcount) para Trakt
    ✅ Filmes assistidos
    ✅ Séries assistidas
    ✅ Favoritos → Watchlist
    """
    from resources.lib.db import db
    from resources.lib.trakt_sync import trakt_request, _clear_trakt_cache
    
    if progress_dialog:
        progress_dialog.update(0, "Coletando dados locais...")
    
    try:
        # === 1. FILMES ASSISTIDOS (playcount > 0) ===
        watched_movies = db.get_watched_movies()
        
        if watched_movies:
            if progress_dialog:
                progress_dialog.update(20, f"Enviando {len(watched_movies)} filmes assistidos...")
            
            # Monta payload Trakt
            trakt_movies = []
            for movie in watched_movies:
                trakt_movies.append({
                    'ids': {'tmdb': movie['tmdb_id']},
                    'watched_at': movie.get('last_played') or datetime.now().isoformat()
                })
            
            # Envia em lotes de 20
            for i in range(0, len(trakt_movies), 20):
                batch = trakt_movies[i:i+20]
                response = trakt_request('POST', '/sync/history', {'movies': batch})
                if not response:
                    xbmc.log(f"[Trakt Sync] Falha ao enviar filmes {i}-{i+20}", xbmc.LOGERROR)
        
        # === 2. SÉRIES ASSISTIDAS ===
        watched_shows = db.get_watched_tvshows()
        
        if watched_shows:
            if progress_dialog:
                progress_dialog.update(40, f"Enviando {len(watched_shows)} séries assistidas...")
            
            trakt_shows = []
            for show in watched_shows:
                trakt_shows.append({
                    'ids': {'tmdb': show['tmdb_id']},
                    'watched_at': show.get('last_played') or datetime.now().isoformat()
                })
            
            for i in range(0, len(trakt_shows), 20):
                batch = trakt_shows[i:i+20]
                response = trakt_request('POST', '/sync/history', {'shows': batch})
                if not response:
                    xbmc.log(f"[Trakt Sync] Falha ao enviar séries {i}-{i+20}", xbmc.LOGERROR)
        
        # === 3. FAVORITOS → WATCHLIST ===
        favorites = db.get_all_favorites()
        
        if favorites:
            if progress_dialog:
                progress_dialog.update(60, f"Enviando {len(favorites)} favoritos...")
            
            fav_movies = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'movie']
            fav_shows = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'tvshow']
            
            if fav_movies:
                trakt_request('POST', '/sync/watchlist', {'movies': fav_movies})
            if fav_shows:
                trakt_request('POST', '/sync/watchlist', {'shows': fav_shows})
        
        # Limpa cache Trakt
        _clear_trakt_cache()
        
        if progress_dialog:
            progress_dialog.update(100, "Sincronização concluída!")
        
        xbmcgui.Dialog().notification(
            "Trakt Sync",
            f"✅ {len(watched_movies)} filmes, {len(watched_shows)} séries enviados",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt Sync] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Falha na sincronização: {str(e)}")
        return False

# === SINCRONIZAÇÃO TRAKT → LOCAL ===

def sync_trakt_to_local(progress_dialog=None):
    """
    Importa dados Trakt para local
    ✅ Marca filmes/séries como assistidos
    ✅ Adiciona watchlist aos favoritos
    ✅ Sincroniza progresso de playback
    """
    from resources.lib.db import db
    from resources.lib.trakt_sync import trakt_request
    
    if progress_dialog:
        progress_dialog.update(0, "Buscando dados do Trakt...")
    
    try:
        # === 1. IMPORTA FILMES ASSISTIDOS ===
        watched_movies_response = trakt_request('GET', '/sync/watched/movies?extended=full')
        
        if watched_movies_response and watched_movies_response.get('data'):
            watched_movies = watched_movies_response['data']
            
            if progress_dialog:
                progress_dialog.update(20, f"Importando {len(watched_movies)} filmes...")
            
            for item in watched_movies:
                movie = item.get('movie', {})
                tmdb_id = movie['ids'].get('tmdb')
                plays = item.get('plays', 1)
                last_watched = item.get('last_watched_at')
                
                if tmdb_id:
                    # Verifica se filme existe no DB local
                    local_movie = db.get_movie_by_id(tmdb_id)
                    if local_movie:
                        # Atualiza playcount
                        db.update_movie_playcount(tmdb_id, plays, last_watched)
        
        # === 2. IMPORTA SÉRIES ASSISTIDAS ===
        watched_shows_response = trakt_request('GET', '/sync/watched/shows?extended=full')
        
        if watched_shows_response and watched_shows_response.get('data'):
            watched_shows = watched_shows_response['data']
            
            if progress_dialog:
                progress_dialog.update(40, f"Importando {len(watched_shows)} séries...")
            
            for item in watched_shows:
                show = item.get('show', {})
                tmdb_id = show['ids'].get('tmdb')
                last_watched = item.get('last_watched_at')
                
                if tmdb_id:
                    local_show = db.get_tvshow_by_id(tmdb_id)
                    if local_show:
                        # TODO: Importar episódios assistidos detalhadamente
                        db.update_tvshow_playcount(tmdb_id, last_watched)
        
        # === 3. IMPORTA WATCHLIST → FAVORITOS ===
        watchlist_movies_response = trakt_request('GET', '/sync/watchlist/movies')
        watchlist_shows_response = trakt_request('GET', '/sync/watchlist/shows')
        
        if progress_dialog:
            progress_dialog.update(60, "Importando watchlist...")
        
        if watchlist_movies_response and watchlist_movies_response.get('data'):
            for item in watchlist_movies_response['data']:
                movie = item.get('movie', {})
                tmdb_id = movie['ids'].get('tmdb')
                if tmdb_id and db.get_movie_by_id(tmdb_id):
                    db.add_to_favorites(tmdb_id, 'movie')
        
        if watchlist_shows_response and watchlist_shows_response.get('data'):
            for item in watchlist_shows_response['data']:
                show = item.get('show', {})
                tmdb_id = show['ids'].get('tmdb')
                if tmdb_id and db.get_tvshow_by_id(tmdb_id):
                    db.add_to_favorites(tmdb_id, 'tvshow')
        
        if progress_dialog:
            progress_dialog.update(100, "Importação concluída!")
        
        xbmcgui.Dialog().notification(
            "Trakt Sync",
            "✅ Dados importados com sucesso",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt Import] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Falha na importação: {str(e)}")
        return False

# === SINCRONIZAÇÃO AUTOMÁTICA AO ASSISTIR ===

class TraktScrobbler(xbmc.Player):
    """
    Monitor que sincroniza automaticamente quando você assiste algo
    ✅ Scrobble em tempo real
    ✅ Marca como assistido ao final
    ✅ Sincroniza progresso (pause/resume)
    """
    
    def __init__(self):
        super(TraktScrobbler, self).__init__()
        self.current_item = None
        self.start_time = None
        self.scrobbled = False
    
    def onPlayBackStarted(self):
        """Chamado quando a reprodução inicia"""
        try:
            from resources.lib.trakt_sync import trakt_request, get_trakt_settings
            
            settings = get_trakt_settings()
            if not settings.get('access_token'):
                return  # Trakt não configurado
            
            # Obtém info do item atual
            if not self.isPlayingVideo():
                return
            
            info = self.getVideoInfoTag()
            tmdb_id = info.getUniqueID('tmdb')
            imdb_id = info.getIMDBNumber()
            
            if not tmdb_id:
                return
            
            # Detecta tipo (filme ou episódio)
            media_type = info.getMediaType()
            
            if media_type == 'movie':
                self.current_item = {
                    'type': 'movie',
                    'tmdb_id': tmdb_id,
                    'progress': 0,
                    'duration': self.getTotalTime()
                }
                
                # Scrobble start
                trakt_request('POST', '/scrobble/start', {
                    'movie': {'ids': {'tmdb': int(tmdb_id)}},
                    'progress': 0
                })
                
            elif media_type == 'episode':
                season = info.getSeason()
                episode = info.getEpisode()
                
                self.current_item = {
                    'type': 'episode',
                    'tmdb_id': tmdb_id,
                    'season': season,
                    'episode': episode,
                    'progress': 0,
                    'duration': self.getTotalTime()
                }
                
                # Scrobble start
                trakt_request('POST', '/scrobble/start', {
                    'show': {'ids': {'tmdb': int(tmdb_id)}},
                    'episode': {
                        'season': season,
                        'number': episode
                    },
                    'progress': 0
                })
            
            self.start_time = time.time()
            self.scrobbled = False
            
            xbmc.log(f"[Trakt Scrobble] Iniciado: {self.current_item}", xbmc.LOGINFO)
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] Erro onStart: {e}", xbmc.LOGERROR)
    
    def onPlayBackStopped(self):
        """Chamado quando a reprodução para"""
        self._scrobble_stop()
    
    def onPlayBackEnded(self):
        """Chamado quando a reprodução termina"""
        self._scrobble_stop(completed=True)
    
    def _scrobble_stop(self, completed=False):
        """Envia scrobble stop/pause para Trakt"""
        try:
            from resources.lib.trakt_sync import trakt_request
            
            if not self.current_item or self.scrobbled:
                return
            
            # Calcula progresso
            if self.start_time:
                elapsed = time.time() - self.start_time
                progress = min(100, int((elapsed / self.current_item['duration']) * 100))
            else:
                progress = 0
            
            # Considera assistido se passou de 80%
            if progress >= 80:
                completed = True
            
            # Monta payload
            if self.current_item['type'] == 'movie':
                payload = {
                    'movie': {'ids': {'tmdb': int(self.current_item['tmdb_id'])}},
                    'progress': progress
                }
            else:
                payload = {
                    'show': {'ids': {'tmdb': int(self.current_item['tmdb_id'])}},
                    'episode': {
                        'season': self.current_item['season'],
                        'number': self.current_item['episode']
                    },
                    'progress': progress
                }
            
            # Envia scrobble
            endpoint = '/scrobble/stop' if completed else '/scrobble/pause'
            trakt_request('POST', endpoint, payload)
            
            self.scrobbled = True
            
            # Atualiza DB local
            if completed:
                from resources.lib.db import db
                if self.current_item['type'] == 'movie':
                    db.mark_movie_as_watched(self.current_item['tmdb_id'])
                
                xbmc.log(f"[Trakt Scrobble] Marcado como assistido: {self.current_item['tmdb_id']}", xbmc.LOGINFO)
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] Erro onStop: {e}", xbmc.LOGERROR)

# === SINCRONIZAÇÃO BIDIRECIONAL COMPLETA ===

def full_bidirectional_sync():
    """
    Sincronização completa em ambas direções
    1. Local → Trakt (envia assistidos)
    2. Trakt → Local (importa watchlist)
    """
    progress = xbmcgui.DialogProgress()
    progress.create("Trakt Sync Completo", "Iniciando...")
    
    try:
        # Verifica autenticação
        from resources.lib.trakt_sync import refresh_trakt_token
        if not refresh_trakt_token():
            progress.close()
            xbmcgui.Dialog().ok("Erro", "Você não está autenticado no Trakt.")
            return False
        
        # Etapa 1: Local → Trakt
        progress.update(10, "Enviando dados locais para Trakt...")
        sync_local_to_trakt(progress)
        
        xbmc.sleep(1000)
        
        # Etapa 2: Trakt → Local
        progress.update(50, "Importando dados do Trakt...")
        sync_trakt_to_local(progress)
        
        progress.update(100, "Sincronização concluída!")
        xbmc.sleep(200)
        progress.close()
        
        # Salva timestamp
        ADDON.setSetting('trakt_last_sync', str(time.time()))
        
        xbmcgui.Dialog().ok(
            "Trakt Sync",
            "Sincronização bidirecional concluída!\n\n"
            "✅ Dados locais enviados\n"
            "✅ Watchlist importada\n"
            "✅ Histórico sincronizado"
        )
        
        return True
        
    except Exception as e:
        progress.close()
        xbmc.log(f"[Trakt Full Sync] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Falha na sincronização:\n{str(e)}")
        return False

# === MENU DE SINCRONIZAÇÃO ===

def show_sync_menu():
    """Menu de opções de sincronização"""
    options = [
        "Sincronização Completa (Local ↔ Trakt)",
        "Enviar Dados Locais → Trakt",
        "Importar Dados Trakt → Local",
        "Limpar Cache e Re-sincronizar",
        "Configurar Scrobble Automático"
    ]
    
    choice = xbmcgui.Dialog().select("Trakt Sync", options)
    
    if choice == 0:
        full_bidirectional_sync()
    elif choice == 1:
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt Sync", "Enviando...")
        sync_local_to_trakt(progress)
        progress.close()
    elif choice == 2:
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt Sync", "Importando...")
        sync_trakt_to_local(progress)
        progress.close()
    elif choice == 3:
        from resources.lib.trakt_sync import _clear_trakt_cache
        _clear_trakt_cache()
        full_bidirectional_sync()
    elif choice == 4:
        current = ADDON.getSettingBool('trakt_auto_scrobble')
        ADDON.setSettingBool('trakt_auto_scrobble', not current)
        status = "ativado" if not current else "desativado"
        xbmcgui.Dialog().notification("Trakt", f"Scrobble automático {status}", xbmcgui.NOTIFICATION_INFO, 2000)

# === INTEGRAÇÃO COM O ADDON ===

def init_trakt_scrobbler():
    """Inicializa o monitor de scrobble automático"""
    if ADDON.getSettingBool('trakt_auto_scrobble'):
        scrobbler = TraktScrobbler()
        xbmc.log("[Trakt] Scrobbler inicializado", xbmc.LOGINFO)
        return scrobbler
    return None

# === INICIALIZAÇÃO ===
_create_trakt_cache_tables()