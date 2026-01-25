# resources/lib/tmdb_api.py
# -*- coding: utf-8 -*-
import requests
import xbmc
import xbmcaddon
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from .db import db

ADDON = xbmcaddon.Addon()
TMDB_API_KEY = ADDON.getSetting("tmdb_api")
TMDB_LANG = ADDON.getSetting("tmdb_language") or "pt-BR"
BASE_URL = "https://api.themoviedb.org/3"

# --- CONFIGURAÇÕES DE IMAGEM ---
IMG_POSTER = "https://image.tmdb.org/t/p/w500"
IMG_BACKDROP = "https://image.tmdb.org/t/p/original"

# --- SESSION REUTILIZÁVEL (GRANDE MELHORIA) ---
# Reutilizar conexões HTTP é MUITO mais rápido que criar novas a cada request
_session = None
_request_cache = {}  # Cache em memória para requisições repetidas
_cache_max_size = 100

def get_session():
    """Retorna uma sessão HTTP reutilizável com pool de conexões OTIMIZADO."""
    global _session
    if _session is None:
        _session = requests.Session()
        # ✅ OTIMIZAÇÃO: Pool maior e retry com backoff
        from requests.adapters import Retry
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=30,  # ⬆️ Aumentado de 20 para 30
            pool_maxsize=30,      # ⬆️ Aumentado de 20 para 30
            max_retries=retry_strategy,
            pool_block=False
        )
        _session.mount('https://', adapter)
        _session.mount('http://', adapter)
        # ✅ OTIMIZAÇÃO: Adiciona compressão gzip
        _session.headers.update({
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    return _session

def _get_cached_request(url, params):
    """✅ NOVO: Cache em memória para requisições repetidas."""
    cache_key = f"{url}_{str(sorted(params.items()))}"
    if cache_key in _request_cache:
        return _request_cache[cache_key]
    return None

def _set_cached_request(url, params, data):
    """✅ NOVO: Salva requisição no cache em memória."""
    global _request_cache
    cache_key = f"{url}_{str(sorted(params.items()))}"
    # Limita tamanho do cache
    if len(_request_cache) >= _cache_max_size:
        # Remove 20% dos itens mais antigos (FIFO simples)
        keys_to_remove = list(_request_cache.keys())[:_cache_max_size // 5]
        for k in keys_to_remove:
            del _request_cache[k]
    _request_cache[cache_key] = data

# --- MAPAS DE GÊNEROS (Unificados) ---
GENRES_MAP = {
    'movie': {28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia", 36: "História", 27: "Terror", 10402: "Música", 9648: "Mistério", 10749: "Romance", 878: "Ficção científica", 10770: "Cinema TV", 53: "Suspense", 10752: "Guerra", 37: "Faroeste"},
    'tv': {10759: 'Ação e Aventura', 16: 'Animação', 35: 'Comédia', 80: 'Crime', 99: 'Documentário', 18: 'Drama', 10751: 'Família', 10762: 'Infantil', 9648: 'Mistério', 10763: 'Notícias', 10764: 'Reality Show', 10765: 'Ficção Científica e Fantasia', 10766: 'Novela', 10767: 'Talk Show', 10768: 'Guerra e Política', 37: 'Faroeste'}
}

# --- FUNÇÕES INTERNAS (Helpers) ---

def _normalize_item(item, media_type, extra=None):
    """Padroniza os campos para filmes e séries em um único lugar."""
    is_movie = media_type == 'movie'
    extra = extra or {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'collection': ''}
    
    g_ids = item.get('genre_ids', [])
    g_map = GENRES_MAP.get('movie' if is_movie else 'tv', {})
    g_names = [g_map.get(gid) for gid in g_ids if gid in g_map]

    backdrop = item.get('backdrop_path')
    
    # Extrai informações da coleção (apenas para filmes)
    collection_name = extra.get('collection', '')
    if not collection_name and is_movie:
        collection_info = item.get('belongs_to_collection')
        if collection_info:
            collection_name = collection_info.get('name', '')
        
    # Se ainda não tem coleção, verifica se o título sugere uma (ex: "Harry Potter and...")
    # Mas o TMDB geralmente é bom nisso. O importante é garantir que não seja None.
    if collection_name is None:
        collection_name = ''
    
    return {
        'tmdb_id': item.get('id'),
        'imdb_id': extra.get('imdb_id'),
        'title': item.get('title' if is_movie else 'name'),
        'original_title': item.get('original_title' if is_movie else 'original_name'),
        'genres': g_names or [g.get('name') for g in item.get('genres', [])],
        'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
        'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'fanart': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'clearlogo': extra.get('clearlogo'),
        'providers': extra.get('providers'),
        'synopsis': item.get('overview', ''),
        'year': (item.get('release_date' if is_movie else 'first_air_date') or '0000')[:4],
        'rating': item.get('vote_average', 0.0),
        'runtime': extra.get('runtime', 0),
        'collection': collection_name,
        'media_type': 'movie' if is_movie else 'tvshow'
    }

def _fetch_tmdb_extra(item, media_type):
    """Busca logos, providers e IDs externos em um único hit (para Threads)."""
    tmdb_id = item.get('id')
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "append_to_response": "external_ids,images,watch/providers",
        "include_image_language": "pt,en,null"
    }
    try:
        # USA SESSÃO REUTILIZÁVEL + TIMEOUT OTIMIZADO
        res = get_session().get(url, params=params, timeout=2.5).json()
        logos = res.get('images', {}).get('logos', [])
        clearlogo_path = ''
        if logos:
            # 1. Tenta encontrar PT-BR
            pt_logo = next((l for l in logos if l.get('iso_639_1') == 'pt'), None)
            clearlogo_path = pt_logo['file_path'] if pt_logo else logos[0]['file_path']
        watch = res.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []
        
        # Extrai informações da coleção (apenas para filmes)
        collection_name = ''
        if media_type == 'movie':
            collection_info = res.get('belongs_to_collection')
            collection_name = collection_info.get('name') if collection_info else ''
        
        return {
            'imdb_id': res.get('external_ids', {}).get('imdb_id', ''),
            'clearlogo': f"{IMG_POSTER}{clearlogo_path}" if clearlogo_path else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'runtime': res.get('runtime', 0) if media_type == 'movie' else 0,
            'collection': collection_name
        }
    except Exception as e:
        xbmc.log(f"[TMDB] Erro extra {tmdb_id}: {str(e)}", xbmc.LOGDEBUG)
        return {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'collection': ''}

def _fetch_extras_batch(items, media_type):
    """
    OTIMIZAÇÃO CRÍTICA: Busca extras em paralelo com melhor controle.
    Usa ThreadPoolExecutor de forma mais eficiente.
    """
    if not items:
        return []
    
    # ✅ OTIMIZAÇÃO: Workers dinâmicos baseado no tamanho da lista
    max_workers = min(8, max(3, len(items) // 4))  # Entre 3 e 8 workers
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit todas as tarefas mantendo a ordem
        future_to_index = {
            executor.submit(_fetch_tmdb_extra, item, media_type): idx 
            for idx, item in enumerate(items)
        }
        
        # Inicializa lista com None para manter ordem
        results = [None] * len(items)
        
        # Coleta resultados conforme completam (mais rápido)
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result(timeout=5)
            except Exception as e:
                xbmc.log(f"[TMDB] Timeout/erro em extra: {e}", xbmc.LOGDEBUG)
                results[idx] = {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0}
        
        # Preenche qualquer resultado faltante
        for i in range(len(results)):
            if results[i] is None:
                results[i] = {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0}
        
        return results

# --- FUNÇÕES PÚBLICAS DE LISTAGEM ---

def fetch_trending(media_type='movie', page=1):
    """Função genérica para Trending de filmes ou séries - OTIMIZADA."""
    cache_key = f"trending_{media_type}_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: 
        return cached

    url = f"{BASE_URL}/trending/{media_type}/day"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        # USA SESSÃO + TIMEOUT OTIMIZADO
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])

        # DEBUG: Verifique se os IDs estão corretos
        xbmc.log(f"[TMDB DEBUG] Trending IDs: {[item.get('id') for item in data]}", xbmc.LOGDEBUG)
        
        # OTIMIZAÇÃO: Só busca extras se realmente necessário
        extra_results = _fetch_extras_batch(data, media_type)
        
        # DEBUG: Verifique extras IDs
        xbmc.log(f"[TMDB DEBUG] Extras IDs: {[extra.get('imdb_id', 'NO_ID') for extra in extra_results]}", xbmc.LOGDEBUG)

        # Normaliza o resultado final
        results = []
        for item, extra in zip(data, extra_results):
            # Verificação de segurança
            if item.get('id') and extra.get('imdb_id'):
                # Pode adicionar verificação aqui
                pass
            normalized = _normalize_item(item, media_type, extra)
            results.append(normalized)
            
            # DEBUG: Log para identificar problemas
            xbmc.log(f"[TMDB DEBUG] Item {item.get('id')} -> {normalized.get('title')}", xbmc.LOGDEBUG)

        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Trending {media_type}: {str(e)}", xbmc.LOGERROR)
        return []

# Wrappers para manter compatibilidade
def fetch_trending_movies(page=1): 
    return fetch_trending('movie', page)

def fetch_trending_tvshows(page=1): 
    return fetch_trending('tv', page)

def fetch_popular_movies(page=1):
    """Busca filmes populares."""
    cache_key = f"popular_movies_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/movie/popular"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG, "region": "BR"}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Popular Movies: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_top_rated_movies(page=1):
    """Busca filmes melhor avaliados."""
    cache_key = f"top_rated_movies_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/movie/top_rated"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG, "region": "BR"}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Top Rated Movies: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_now_playing_movies(page=1):
    """Busca filmes em exibição nos cinemas."""
    cache_key = f"now_playing_movies_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/movie/now_playing"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG, "region": "BR"}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Now Playing Movies: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_popular_tvshows(page=1):
    """Busca séries populares."""
    cache_key = f"popular_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/tv/popular"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Popular TV: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_top_rated_tvshows(page=1):
    """Busca séries melhor avaliadas."""
    cache_key = f"top_rated_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: return cached

    url = f"{BASE_URL}/tv/top_rated"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Top Rated TV: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_airing_today_tvshows(page=1):
    """Busca séries que passam hoje."""
    cache_key = f"airing_today_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    url = f"{BASE_URL}/tv/airing_today"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Airing Today TV: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_on_the_air_tvshows(page=1):
    """Busca séries que estão no ar (esta semana)."""
    cache_key = f"on_the_air_tvshows_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    url = f"{BASE_URL}/tv/on_the_air"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        extra_results = _fetch_extras_batch(data, 'tv')
        results = [_normalize_item(item, 'tv', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro On The Air TV: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_upcoming_movies(page=1):
    """Busca filmes que serão lançados em breve usando o endpoint oficial de upcoming."""
    cache_key = f"upcoming_movies_v2_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    # O endpoint /movie/upcoming é mais confiável para o que o usuário quer
    url = f"{BASE_URL}/movie/upcoming"
    params = {
        "api_key": TMDB_API_KEY, 
        "page": page, 
        "language": TMDB_LANG, 
        "region": "BR"
    }
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        
        # Se falhar ou vier vazio, tenta via discover como fallback
        if not data:
            from datetime import datetime, timedelta
            now = datetime.now().strftime('%Y-%m-%d')
            future = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            return fetch_discover('movie', page=page, 
                                 **{'primary_release_date.gte': now,
                                    'primary_release_date.lte': future,
                                    'sort_by': 'popularity.desc'})

        extra_results = _fetch_extras_batch(data, 'movie')
        results = [_normalize_item(item, 'movie', extra) for item, extra in zip(data, extra_results)]
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Upcoming Movies: {str(e)}", xbmc.LOGERROR)
        return []

def fetch_upcoming_tvshows(page=1):
    """Busca séries que estão para estrear ou com novos episódios."""
    cache_key = f"upcoming_tvshows_v2_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=12)
    if cached: return cached

    # Para TV, usamos discover filtrando por séries que estreiam a partir de hoje
    from datetime import datetime, timedelta
    now = datetime.now().strftime('%Y-%m-%d')
    future = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
    
    try:
        # Séries que estreiam em breve, ordenadas por popularidade para evitar lixo
        results = fetch_discover('tv', page=page, 
                                **{'first_air_date.gte': now,
                                   'first_air_date.lte': future,
                                   'sort_by': 'popularity.desc'})
        
        if results: db.save_tmdb_cache(cache_key, results)
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Upcoming TV: {str(e)}", xbmc.LOGERROR)
        return []

def search_tmdb(query, page=1):
    """Busca unificada (Filmes e Séries) - OTIMIZADA."""
    url = f"{BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY, 
        "query": query, 
        "language": TMDB_LANG, 
        "page": page,
        "include_adult": "false"
    }
    
    try:
        # USA SESSÃO
        r = get_session().get(url, params=params, timeout=5)
        data = r.json().get('results', [])
        
        # Filtra apenas o que interessa
        filtered = [i for i in data if i.get('media_type') in ['movie', 'tv']]

        # CRÍTICO: Para busca, extras são menos importantes
        # Você pode até desabilitar se quiser velocidade máxima
        extra_results = _fetch_extras_batch(filtered[:10], None)  # Limita a 10 primeiros
        extra_results += [{'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0}] * (len(filtered) - 10)

        return [
            _normalize_item(item, item['media_type'], extra) 
            for item, extra in zip(filtered, extra_results)
        ]
        
    except Exception as e:
        xbmc.log(f"[TMDB SEARCH] Erro: {str(e)}", xbmc.LOGERROR)
        return []

# --- FUNÇÕES DE POPULARIDADE LOCAL ---

def update_local_popularity():
    """Sincroniza popularidade - OTIMIZADA."""
    _sync_popularity('movie', db.get_all_movie_ids_set(), db.update_popularity_bulk)
    _sync_popularity('tv', db.get_all_tvshow_ids_set(), db.update_tv_popularity_bulk)

def _sync_popularity(media_type, local_ids, update_func):
    """Lógica auxiliar para baixar popularidade - OTIMIZADA."""
    if not local_ids: 
        return
    
    popular_tmdb = []
    
    # OTIMIZAÇÃO: Busca paralela de páginas
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for p in range(1, 4):
            url = f"{BASE_URL}/{media_type}/popular"
            params = {"api_key": TMDB_API_KEY, "page": p}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                popular_tmdb.extend(r.json().get('results', []))
            except:
                continue

    # Filtra apenas os que temos no banco local
    updates = [
        {'tmdb_id': i['id'], 'popularity': i['popularity']} 
        for i in popular_tmdb if i['id'] in local_ids
    ]

    if updates:
        update_func(updates)
        xbmc.log(f"[Cinebox] Popularidade de {len(updates)} {media_type}s atualizada.", xbmc.LOGINFO)

# --- FUNÇÕES DE DETALHES (INDEXER/DB) ---

def get_movie_details(tmdb_id):
    """Busca detalhes completos de um filme - OTIMIZADA."""
    url = f"{BASE_URL}/movie/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "append_to_response": "external_ids,images,credits,watch/providers",
        "include_image_language": "pt,en,null"
    }
    
    try:
        # USA SESSÃO
        r = get_session().get(url, params=params, timeout=8)
        item = r.json()
        
        logos = item.get('images', {}).get('logos', [])
        clearlogo_path = ''
        if logos:
            pt_logo = next((l for l in logos if l.get('iso_639_1') == 'pt'), None)
            clearlogo_path = pt_logo['file_path'] if pt_logo else logos[0]['file_path']
        watch = item.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []
        
        # Extrai informações da coleção
        collection_info = item.get('belongs_to_collection')
        collection_name = collection_info.get('name') if collection_info else ''
        
        return {
            'tmdb_id': item.get('id'),
            'imdb_id': item.get('external_ids', {}).get('imdb_id'),
            'title': item.get('title'),
            'original_title': item.get('original_title'),
            'year': item.get('release_date', '0000')[:4],
            'rating': item.get('vote_average', 0.0),
            'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}" if item.get('backdrop_path') else '',
            'synopsis': item.get('overview', ''),
            'runtime': item.get('runtime', 0),
            'popularity': item.get('popularity', 0.0),
            'revenue': item.get('revenue', 0),
            'collection': collection_name,
            'genres': [g.get('name') for g in item.get('genres', [])],
            'clearlogo': f"{IMG_POSTER}{clearlogo_path}" if clearlogo_path else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'popularity_updated': None,
            'cast': [c.get('name') for c in item.get('credits', {}).get('cast', [])[:5]],
            'directors': [c.get('name') for c in item.get('credits', {}).get('crew', []) if c.get('job') == 'Director']
        }
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro detalhes filme {tmdb_id}: {str(e)}", xbmc.LOGERROR)
        return None

def _enrich_seasons_with_images(seasons, tmdb_id):
    """Simplificado: Apenas garante que os dados básicos existam."""
    if not seasons:
        return []
    
    for season in seasons:
        if 'poster_path' in season and season['poster_path']:
            season['poster'] = f"{IMG_POSTER}{season['poster_path']}"
        # TMDB não fornece backdrop para temporadas individuais
        # O backdrop será definido pela série no tvshows.py
    return seasons

def fetch_show_details(tmdb_id):
    """Busca detalhes completos de uma série - OTIMIZADA."""
    if not tmdb_id: 
        return None
        
    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "append_to_response": "external_ids,images,credits",
        "include_image_language": "pt,en,null"
    }
    
    try:
        # USA SESSÃO
        response = get_session().get(url, params=params, timeout=8)
        response.raise_for_status()
        show_data = response.json()
        
        seasons_raw = show_data.get('seasons', [])
        logos = show_data.get('images', {}).get('logos', [])
        clearlogo_path = ''
        if logos:
            pt_logo = next((l for l in logos if l.get('iso_639_1') == 'pt'), None)
            clearlogo_path = pt_logo['file_path'] if pt_logo else logos[0]['file_path']
        
        return {
            'tmdb_id': show_data.get('id'),
            'clearlogo': f"{IMG_POSTER}{clearlogo_path}" if clearlogo_path else '',
            'imdb_id': show_data.get('external_ids', {}).get('imdb_id'),
            'title': show_data.get('name'),
            'original_title': show_data.get('original_name'),
            'year': show_data.get('first_air_date', '')[:4],
            'poster': f"{IMG_POSTER}{show_data.get('poster_path')}" if show_data.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{show_data.get('backdrop_path')}" if show_data.get('backdrop_path') else '',
            'synopsis': show_data.get('overview'),
            'popularity': show_data.get('popularity'),
            'rating': show_data.get('vote_average'),
            'certification': show_data.get('content_ratings', {}).get('results', [{}])[0].get('rating', 'N/A'),
            'genres': [g.get('name') for g in show_data.get('genres', [])], 
            'number_of_seasons': show_data.get('number_of_seasons', 0),
            'number_of_episodes': show_data.get('number_of_episodes', 0),
            'status': show_data.get('status'),
            'tagline': show_data.get('tagline'),
            'seasons_data': show_data.get('seasons', []),
            'cast': [c.get('name') for c in show_data.get('credits', {}).get('cast', [])[:5]],
            'created_by': [c.get('name') for c in show_data.get('created_by', [])]
        }
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar detalhes da série {tmdb_id}: {e}", xbmc.LOGERROR)
        return None

def fetch_tvshows_list(list_type, page=1):
    """Busca listas simples de séries - OTIMIZADA."""
    endpoint_map = {
        'popular': 'tv/popular',
        'top_rated': 'tv/top_rated',
        'on_the_air': 'tv/on_the_air',
        'trending': 'trending/tv/week' 
    }
    endpoint = endpoint_map.get(list_type, 'tv/popular')
    url = f"{BASE_URL}/{endpoint}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
    
    try:
        # USA SESSÃO
        response = get_session().get(url, params=params, timeout=5)
        data = response.json()
        
        normalized_shows = []
        for show in data.get('results', []):
            g_ids = show.get('genre_ids', [])
            g_names = [GENRES_MAP['tv'].get(gid, 'Desconhecido') for gid in g_ids]
            
            normalized_shows.append({
                'tmdb_id': show.get('id'),
                'title': show.get('name'),
                'original_title': show.get('original_name'),
                'year': show.get('first_air_date', '')[:4],
                'poster': f"{IMG_POSTER}{show.get('poster_path')}" if show.get('poster_path') else '',
                'backdrop': f"{IMG_BACKDROP}{show.get('backdrop_path')}" if show.get('backdrop_path') else '',
                'synopsis': show.get('overview'),
                'popularity': show.get('popularity'),
                'rating': show.get('vote_average'),
                'genres': g_names
            })
        return normalized_shows
        
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar lista {list_type}: {e}", xbmc.LOGERROR)
        return []

@lru_cache(maxsize=128)
def get_collection_art(collection_name):
    """Busca arte de coleção - OTIMIZADA com CACHE."""
    url = f"{BASE_URL}/search/collection"
    params = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        results = r.json().get('results', [])
        if results:
            poster = results[0].get('poster_path')
            backdrop = results[0].get('backdrop_path')
            return {
                'poster': f"{IMG_BACKDROP}{poster}" if poster else '',
                'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else ''
            }
    except:
        pass
    return None

def fetch_popular_movies_pages(pages=5):
    """Busca páginas populares - OTIMIZADA."""
    all_movies = []
    
    # OTIMIZAÇÃO: Busca paralela
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for page in range(1, pages + 1):
            url = f"{BASE_URL}/movie/popular"
            params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                data = r.json().get('results', [])
                for item in data:
                    all_movies.append({
                        'tmdb_id': item.get('id'),
                        'title': item.get('title'),
                        'original_title': item.get('original_title'),
                        'year': item.get('release_date', '0000')[:4],
                        'rating': item.get('vote_average'),
                        'poster': f"{IMG_POSTER}{item.get('poster_path')}",
                        'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}",
                        'synopsis': item.get('overview'),
                        'popularity': item.get('popularity'),
                        'popularity_updated': None
                    })
            except:
                continue
                
    return all_movies

def get_tvshow_seasons(tmdb_id):
    """Busca temporadas de uma série - OTIMIZADA."""
    if not tmdb_id:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        seasons = data.get('seasons', [])
        
        formatted_seasons = []
        for season in seasons:
            formatted_seasons.append({
                'season_number': season.get('season_number', 0),
                'name': season.get('name', ''),
                'overview': season.get('overview', ''),
                'poster_path': season.get('poster_path', ''),
                'air_date': season.get('air_date', ''),
                'episode_count': season.get('episode_count', 0),
                'vote_average': season.get('vote_average', 0.0)
            })
        
        return formatted_seasons
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro ao buscar temporadas {tmdb_id}: {e}", xbmc.LOGERROR)
        return []

def get_season_episodes(tmdb_id, season_number):
    """Busca episódios de uma temporada - OTIMIZADA."""
    if not tmdb_id or season_number is None:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}/season/{season_number}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        episodes = data.get('episodes', [])
        
        formatted_episodes = []
        for episode in episodes:
            formatted_episodes.append({
                'episode_number': episode.get('episode_number', 0),
                'name': episode.get('name', ''),
                'overview': episode.get('overview', ''),
                'still_path': episode.get('still_path', ''),
                'air_date': episode.get('air_date', ''),
                'vote_average': episode.get('vote_average', 0.0),
                'runtime': episode.get('runtime', 0)
            })
        
        return formatted_episodes
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro ao buscar episódios {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []
def fetch_anime_discover(media_type='tv', page=1, **kwargs):
    """Função específica para Discover de Animes usando a keyword 210024."""
    kwargs['with_keywords'] = '210024'
    return fetch_discover(media_type, page, **kwargs)

def fetch_discover(media_type='movie', page=1, **kwargs):
    """Função genérica para Discover (Gêneros, Anos, etc) - OTIMIZADA."""
    cache_key = f"discover_{media_type}_p{page}_{json.dumps(kwargs, sort_keys=True)}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: 
        return cached

    url = f"{BASE_URL}/discover/{media_type}"
    params = {
        "api_key": TMDB_API_KEY, 
        "page": page, 
        "language": TMDB_LANG,
        "sort_by": "popularity.desc",
        "include_adult": "false"
    }
    params.update(kwargs)
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        data = r.json().get('results', [])
        
        extra_results = _fetch_extras_batch(data, media_type)
        
        results = []
        for item, extra in zip(data, extra_results):
            normalized = _normalize_item(item, media_type, extra)
            results.append(normalized)

        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Discover {media_type}: {str(e)}", xbmc.LOGERROR)
        return []

def get_genres_list(media_type='movie'):
    """Retorna a lista de gêneros oficial do TMDB."""
    url = f"{BASE_URL}/genre/{media_type}/list"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    try:
        r = get_session().get(url, params=params, timeout=3)
        return r.json().get('genres', [])
    except:
        return []

def get_collection_art(collection_name):
    """Busca artes de uma coleção pelo nome no TMDB."""
    url = f"{BASE_URL}/search/collection"
    params = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}
    try:
        r = get_session().get(url, params=params, timeout=3)
        results = r.json().get('results', [])
        if results:
            col = results[0]
            return {
                'poster': f"{IMG_POSTER}{col.get('poster_path')}" if col.get('poster_path') else '',
                'backdrop': f"{IMG_BACKDROP}{col.get('backdrop_path')}" if col.get('backdrop_path') else ''
            }
    except:
        pass
    return None

def get_collection_movies(collection_name):
    """Busca todos os filmes de uma coleção pelo nome no TMDB."""
    # 1. Busca o ID da coleção
    url_search = f"{BASE_URL}/search/collection"
    params_search = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url_search, params=params_search, timeout=5)
        results = r.json().get('results', [])
        if not results:
            return []
        
        collection_id = results[0].get('id')
        if not collection_id:
            return []
            
        # 2. Busca os detalhes da coleção (que contém os filmes)
        url_details = f"{BASE_URL}/collection/{collection_id}"
        params_details = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
        
        r_details = get_session().get(url_details, params=params_details, timeout=5)
        collection_data = r_details.json()
        parts = collection_data.get('parts', [])
        
        if not parts:
            return []
            
        # 3. Busca extras para cada filme da coleção (opcional, mas recomendado para ter imdb_id)
        extra_results = _fetch_extras_batch(parts, 'movie')
        
        results = []
        for item, extra in zip(parts, extra_results):
            normalized = _normalize_item(item, 'movie', extra)
            # Garante que o nome da coleção esteja correto
            normalized['collection'] = collection_name
            results.append(normalized)
            
        return results
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro ao buscar filmes da coleção {collection_name}: {e}", xbmc.LOGERROR)
        return []

def fetch_popular_collections(page=1):
    """
    Busca coleções populares de forma massiva.
    Explora múltiplas páginas de filmes populares para extrair coleções.
    """
    page = int(page)
    collections = {}
    
    # Para cada página solicitada pelo usuário, vamos olhar 4 páginas do TMDB
    # Aumentamos para 4 para garantir que tenhamos itens suficientes após a filtragem
    start_tmdb_page = ((page - 1) * 4) + 1
    end_tmdb_page = start_tmdb_page + 4
    
    try:
        # 1. Busca filmes de múltiplas páginas em paralelo
        all_movies = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for p in range(start_tmdb_page, end_tmdb_page):
                url_pop = f"{BASE_URL}/movie/popular"
                params_pop = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": p}
                futures.append(executor.submit(get_session().get, url_pop, params=params_pop, timeout=5))
            
            for future in as_completed(futures):
                try:
                    res = future.result().json()
                    all_movies.extend(res.get('results', []))
                except:
                    continue

        if not all_movies:
            return []

        # 2. Extrai IDs de filmes únicos
        unique_movies = {m['id']: m for m in all_movies if m.get('id')}.values()
        
        # 3. Busca extras em lote para descobrir quais pertencem a coleções
        movie_list = list(unique_movies)[:100] # Aumentado para 100
        extra_results = _fetch_extras_batch(movie_list, 'movie')
        
        for item, extra in zip(movie_list, extra_results):
            col_name = extra.get('collection')
            if col_name:
                # Normalização rigorosa para evitar duplicatas
                norm_name = col_name.strip().lower()
                if norm_name not in collections:
                    # Busca arte da coleção (com cache interno do get_collection_art)
                    art = get_collection_art(col_name)
                    collections[norm_name] = {
                        'collection': col_name,
                        'poster': art['poster'] if art else '',
                        'backdrop': art['backdrop'] if art else ''
                    }
        
        # Ordena por nome
        sorted_collections = sorted(collections.values(), key=lambda x: x['collection'])
        
        # ✅ FILTRAGEM GLOBAL DE DUPLICATAS ENTRE PÁGINAS
        # Usamos um cache temporário no banco de dados para saber o que já foi exibido
        from .db.db import db_instance as db
        final_collections = []
        
        # Normalização extra para remover palavras comuns que causam duplicatas falsas
        def super_norm(n):
            import re
            n = n.lower()
            n = re.sub(r' - coleção| - saga| coleção| saga| collection| anthology| trilogy', '', n)
            return n.strip()

        for col in sorted_collections:
            name = col['collection']
            snorm = super_norm(name)
            
            # Verifica se já foi mostrado nesta sessão (usando cache do banco como flag)
            cache_key = f"col_shown_{snorm}"
            if page == 1:
                # Na página 1, sempre mostramos e marcamos
                db.save_collection_meta(cache_key, "1", "")
                final_collections.append(col)
            else:
                # Nas outras páginas, só mostramos se não estiver no cache
                if not db.get_collection_meta(cache_key):
                    db.save_collection_meta(cache_key, "1", "")
                    final_collections.append(col)
                
        return final_collections

    except Exception as e:
        xbmc.log(f"[TMDB API] Erro massivo ao buscar coleções: {e}", xbmc.LOGERROR)
        return []
