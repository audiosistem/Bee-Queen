# VERSÃO CORRIGIDA - ORIGINAL_TITLE PARA SÉRIES

import re
import requests
import json
import xbmc
import traceback
import threading
import unicodedata
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, parse_qs

# --- Imports do Pacote ---
from .session import USER_AGENT
from .utils import guess_quality_from_name, get_anime_search_codes, format_size, normalize_for_compare
from ..debug_logger import logger

# --- Configurações e Exceções Personalizadas ---
class AnimeZeyScraperError(Exception):
    """Exceção base para o scraper AnimeZey"""
    pass

class ScraperConfig:
    """Configurações centralizadas do scraper"""
    MAX_THREADS = 8
    REQUEST_TIMEOUT = 25
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    STOP_WORDS = {
        'a', 'an', 'the', 'e', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas',
        'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
        'por', 'para', 'com', 'sem', 'sob', 'sobre', 'to', 'of', 'in', 'on',
        'at', 'for', 'from', 'with', 'by', 'and', 'or', 'but', 'até'
    }

# --- Decorators para Retry ---
def with_retry(max_retries=3, delay=1):
    """Decorator para retry automático em falhas de rede"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.Timeout, 
                       requests.exceptions.ConnectionError,
                       requests.exceptions.ChunkedEncodingError) as e:
                    if attempt == max_retries - 1:
                        raise
                    xbmc.log(f"🔄 Tentativa {attempt + 1}/{max_retries} falhou, aguardando {delay}s...", xbmc.LOGWARNING)
                    time.sleep(delay * (attempt + 1))
                except Exception as e:
                    raise
            return None
        return wrapper
    return decorator

# --- Funções Auxiliares ---
@with_retry(max_retries=ScraperConfig.MAX_RETRIES, delay=ScraperConfig.RETRY_DELAY)
def _post_to_animezey(url, payload):
    """Função melhorada para POST requests com retry"""
    headers = {
        "accept": "*/*",
        "accept-language": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,mt;q=0.5",
        "content-type": "application/json",
        "sec-ch-ua": "\"Microsoft Edge\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "Referer": url,
        "User-Agent": USER_AGENT
    }
    
    try:
        headers.pop("Cookie", None)
        logger.network(url, method='POST')
        response = requests.post(url, headers=headers, json=payload, 
                               timeout=ScraperConfig.REQUEST_TIMEOUT)
        logger.network(url, method='POST', status=response.status_code, response=response.text if response.status_code != 200 else "OK")
        response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            xbmc.log(f"[animezey] ❌ Resposta não é JSON de {url}: {e}", xbmc.LOGERROR)
            logger.scraper_error("AnimeZey", f"Invalid JSON: {e}", url)
            return None
            
    except requests.exceptions.HTTPError as http_err:
        status = getattr(http_err.response, 'status_code', 'N/A')
        text = getattr(http_err.response, 'text', str(http_err))[:500]
        xbmc.log(f"[animezey] ⚠️ HTTP Error {status} em {url}: {text}", xbmc.LOGWARNING)
        logger.scraper_error("AnimeZey", f"HTTP Error {status}: {text}", url)
        return None
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[animezey] ⚠️ Request Error em {url}: {str(e)}", xbmc.LOGWARNING)
        logger.scraper_error("AnimeZey", f"Request Error: {e}", url)
        return None
    except Exception as e:
        xbmc.log(f"[animezey] ❌ Erro Geral em {url}: {str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)
        logger.scraper_error("AnimeZey", f"General Error: {e}", url)
        return None

def remove_accents(input_str):
    """Remove acentos de forma segura"""
    if not input_str:
        return ""
    try:
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    except Exception:
        return input_str

def extract_year_from_filename(filename):
    """Extrai ano do nome do arquivo (1900-2099)"""
    if not filename:
        return None
    
    filename_lower = filename.lower()
    
    # Padrão 1: Entre pontos, espaços, underscores ou hífens
    match = re.search(r'[\.\s_\-\(](19\d{2}|20\d{2})[\.\s_\-\)]', filename_lower)
    if match:
        return int(match.group(1))
    
    # Padrão 2: No início ou fim do nome
    match = re.search(r'^(19\d{2}|20\d{2})[\.\s_\-]|[\.\s_\-](19\d{2}|20\d{2})$', filename_lower)
    if match:
        year = match.group(1) or match.group(2)
        return int(year)
    
    return None

def remove_articles(text):
    """Remove artigos do início do texto (The, A, An, O, A, Os, As)"""
    if not text:
        return text
    
    # Remove artigos em inglês e português do INÍCIO
    text = re.sub(r'^(the|a|an|o|a|os|as)\s+', '', text, flags=re.IGNORECASE)
    return text.strip()

def calculate_title_similarity(file_name, target_title, original_title=None, media_type='movie'):
    """
    Calcula similaridade entre o nome do arquivo e os títulos buscados.
    Para FILMES: Exige que o título esteja NO INÍCIO do nome do arquivo.
    Para SÉRIES: Mais flexível, aceita título OU original_title em QUALQUER PARTE do nome.
    Retorna score de 0 a 100.
    """
    file_norm = normalize_for_compare(file_name)
    target_norm = normalize_for_compare(target_title)
    
    # Remove ano dos títulos para comparação justa
    target_norm_clean = re.sub(r'\d{4}', '', target_norm).strip()
    
    # NOVO: Remove artigos para melhor comparação
    target_norm_no_article = remove_articles(target_norm_clean)
    
    # Para filmes: pega só os primeiros 100 caracteres
    # Para séries: usa o nome completo
    file_search = file_norm[:100] if media_type == 'movie' else file_norm
    
    score = 0
    matched_title = None
    
    # SÉRIES: Busca mais flexível (aceita título em qualquer parte)
    if media_type == 'tvshow':
        # Tenta match com target_title (com e sem artigo)
        if target_norm_clean and target_norm_clean in file_search:
            score = 100
            matched_title = target_title
        elif target_norm_no_article and target_norm_no_article in file_search:
            score = 100
            matched_title = target_title
        
        # Se não achou, tenta com original_title
        if original_title and score < 100:
            original_norm = normalize_for_compare(original_title)
            original_norm_clean = re.sub(r'\d{4}', '', original_norm).strip()
            original_norm_no_article = remove_articles(original_norm_clean)
            
            if original_norm_clean and original_norm_clean in file_search:
                score = 100
                matched_title = original_title
            elif original_norm_no_article and original_norm_no_article in file_search:
                score = 100
                matched_title = original_title
    
    # FILMES: Busca mais flexível
    else:
        # 1. MATCH NO INÍCIO OU QUALQUER PARTE (Threshold 100 se no início, 80 se contido)
        if target_norm_clean:
            pattern = r'^[^\w]{0,5}' + re.escape(target_norm_clean) + r'[^\w]+'
            if re.search(pattern, file_search) or file_search.startswith(target_norm_clean):
                score = 100
                matched_title = target_title
            elif target_norm_clean in file_search:
                score = 85
                matched_title = target_title
        
        # Tenta sem artigo também
        if score < 85 and target_norm_no_article:
            pattern = r'^[^\w]{0,5}' + re.escape(target_norm_no_article) + r'[^\w]+'
            if re.search(pattern, file_search) or file_search.startswith(target_norm_no_article):
                score = 100
                matched_title = target_title
            elif target_norm_no_article in file_search:
                score = 85
                matched_title = target_title
        
        # 2. Testar com título original (também no início)
        if original_title and score < 100:
            original_norm = normalize_for_compare(original_title)
            original_norm_clean = re.sub(r'\d{4}', '', original_norm).strip()
            original_norm_no_article = remove_articles(original_norm_clean)
            
            if original_norm_clean and original_norm_clean != target_norm_clean:
                pattern = r'^[^\w]{0,5}' + re.escape(original_norm_clean) + r'[^\w]+'
                if re.search(pattern, file_search):
                    score = 100
                    matched_title = original_title
                elif file_search.startswith(original_norm_clean):
                    score = 100
                    matched_title = original_title
            
            # Tenta sem artigo
            if score < 100 and original_norm_no_article:
                pattern = r'^[^\w]{0,5}' + re.escape(original_norm_no_article) + r'[^\w]+'
                if re.search(pattern, file_search):
                    score = 100
                    matched_title = original_title
                elif file_search.startswith(original_norm_no_article):
                    score = 100
                    matched_title = original_title
    
    return score

# --- Classe Principal do Scraper ---
class AnimeZeyScraper:
    """Scraper AnimeZey otimizado com matching rigoroso"""
    
    def __init__(self, provider_url, item_data, cancel_event=None):
        self.provider_url = provider_url
        self.item_data = item_data
        self.cancel_event = cancel_event
        self.log_prefix = "[animezey.scraper]"
        self.found_files = []
        self.processed_files = set()
        self.lock = threading.Lock()
        
        # Configurações
        self.setup_domains()
        self.setup_item_data()
        
    def setup_domains(self):
        """Configura domínios de forma robusta"""
        try:
            parsed = urlparse(self.provider_url)
            self.search_domain = parsed.netloc or "1.animezey23112022.workers.dev"
            self.download_domain = "animezey16082023.animezey16082023.workers.dev"
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Erro configurando domínios: {e}", xbmc.LOGWARNING)
            self.search_domain = "1.animezey23112022.workers.dev"
            self.download_domain = "animezey16082023.animezey16082023.workers.dev"
    
    def setup_item_data(self):
        """Prepara e valida os dados do item"""
        self.title = self.item_data.get('title', '').strip()
        self.original_title = self.item_data.get('original_title', '').strip()
        self.media_type = self.item_data.get('media_type', '').lower()
        try:
            self.year = int(self.item_data.get('year'))
        except (ValueError, TypeError):
            self.year = None
        
        if not self.title:
            raise AnimeZeyScraperError("Item data sem 'title'")
            
        # Preparar dados de episódio se for série
        self.season = self.episode = None
        if self.media_type == 'tvshow':
            try:
                self.season = int(self.item_data.get('season', 1))
                self.episode = int(self.item_data.get('episode', 1))
            except (ValueError, TypeError):
                raise AnimeZeyScraperError("Season/episode inválidos")
    
    def _get_base_titles(self):
        """Obtém títulos base para busca"""
        titles = []
        
        # Remover ano do título
        title_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.title).strip()
        if title_no_year:
            titles.append(title_no_year)
            
        if self.original_title:
            original_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.original_title).strip()
            if (original_no_year and title_no_year and 
                original_no_year.lower() != title_no_year.lower()):
                titles.append(original_no_year)
            elif not title_no_year and original_no_year:
                titles.append(original_no_year)
                
        return titles
    
    def generate_search_variations(self):
        """Gera variações de busca simplificadas (só busca títulos principais)"""
        variations = []
        
        base_titles = self._get_base_titles()
        
        for title in base_titles:
            if not title:
                continue
            
            # Original
            variations.append(title)
            
            # Sem acentos
            no_accent = remove_accents(title)
            if no_accent and no_accent != title:
                variations.append(no_accent)
        
        return list(set(filter(None, variations)))
    
    def _fetch_page(self, search_query):
        """Busca uma página individual"""
        try:
            search_url = f"https://{self.search_domain}/1:search"
            payload = {"q": search_query}
            
            response = _post_to_animezey(search_url, payload)
            
            if response and 'data' in response and 'files' in response['data']:
                files = response['data'].get('files', [])
                return files
                
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro buscando '{search_query}': {e}", xbmc.LOGERROR)
        
        return []
    
    def _add_new_files(self, files):
        """Adiciona novos arquivos à lista global"""
        new_files = []
        for file_data in files:
            file_id = file_data.get('id')
            if file_id and file_id not in self.processed_files:
                self.processed_files.add(file_id)
                new_files.append(file_data)
                self.found_files.append(file_data)
        return new_files
    
    def generate_search_queries(self, search_names):
        """Gera queries de busca baseadas no tipo de mídia"""
        queries = set()
        
        if self.media_type == 'tvshow':
            ep_codes = get_anime_search_codes(self.season, self.episode)
            
            for search_name in search_names:
                for ep_code in ep_codes:
                    queries.add(f"{search_name} {ep_code}")
                        
        else:  # movie
            for search_name in search_names:
                # Busca com ano
                if self.year:
                    queries.add(f"{search_name} {self.year}")
                # Busca sem ano também
                queries.add(search_name)
        
        return list(queries)
    
    def parallel_search(self, queries):
        """Busca paralela usando ThreadPoolExecutor"""
        start_time = time.time()
        
        def process_query(query):
            if self.cancel_event and self.cancel_event.is_set():
                return 0
            try:
                files = self._fetch_page(query)
                if files:
                    with self.lock:
                        new_files = self._add_new_files(files)
                return len(files)
            except Exception as e:
                xbmc.log(f"{self.log_prefix} ❌ Erro em '{query}': {e}", xbmc.LOGERROR)
                return 0
        
        total_files = 0
        with ThreadPoolExecutor(max_workers=ScraperConfig.MAX_THREADS) as executor:
            future_to_query = {executor.submit(process_query, query): query for query in queries}
            
            for future in as_completed(future_to_query):
                if self.cancel_event and self.cancel_event.is_set():
                    # Tenta cancelar os futuros restantes
                    for f in future_to_query:
                        f.cancel()
                    break
                try:
                    file_count = future.result()
                    total_files += file_count
                except Exception as exc:
                    xbmc.log(f"{self.log_prefix} ❌ Exceção: {exc}", xbmc.LOGERROR)
        
        return total_files
    
    def _check_episode_match(self, file_name, file_norm):
        """
        Verifica se o episódio bate (para séries).
        RIGOROSO: Só aceita o episódio EXATO solicitado.
        """
        # A) Bloqueio de Temporada Errada
        current_s_tag = f"s{str(self.season).zfill(2)}"
        other_seasons = [f"s{str(i).zfill(2)}" for i in range(1, 50) if i != self.season]
        
        for s_tag in other_seasons:
            if s_tag in file_norm:
                return False, f"temporada errada: {s_tag}"
        
        # B) Procurar padrões de episódio PRECISOS
        episode_patterns = [
            # S01E02, s01e02
            rf's{str(self.season).zfill(2)}e{str(self.episode).zfill(2)}',
            # S1E2, s1e2 (sem zero à esquerda)
            rf's{self.season}e{self.episode}\b',
            # 1x02, 01x02
            rf'{str(self.season).zfill(2)}x{str(self.episode).zfill(2)}',
            rf'{self.season}x{str(self.episode).zfill(2)}',
            # - 02 -, .02., _02_ (episódio isolado, MUITO CUIDADO)
            rf'[\.\-_\s]0*{self.episode}[\.\-_\s]',
        ]
        
        for pattern in episode_patterns:
            if re.search(pattern, file_norm, re.IGNORECASE):
                # VALIDAÇÃO EXTRA: Garantir que NÃO é outro episódio
                # Ex: S01E02 não deve aceitar S01E21 ou S01E12
                
                # Procurar todos os padrões de episódio no nome
                all_ep_matches = re.findall(r's\d+e(\d+)', file_norm, re.IGNORECASE)
                if all_ep_matches:
                    # Pegar o primeiro episódio encontrado
                    first_ep = int(all_ep_matches[0])
                    if first_ep == self.episode:
                        return True, f"episódio correto: E{self.episode:02d}"
                    else:
                        return False, f"episódio errado: E{first_ep:02d} != E{self.episode:02d}"
                else:
                    # Não achou padrão S01E02, mas achou outro padrão
                    return True, f"pattern match: {pattern}"
        
        return False, f"episódio {self.episode} não encontrado"
    
    def matches_filters(self, file_name):
        """
        Função ULTRA RIGOROSA de matching.
        Para FILMES: Exige título no início + ano EXATO.
        Para SÉRIES: Aceita título/original_title em qualquer parte + episódio EXATO.
        """
        if not file_name:
            return False, 0
        
        file_norm = normalize_for_compare(file_name)
        
        # LOG DEBUG: Mostrar o que está sendo comparado
        if self.media_type == 'tvshow':
            xbmc.log(
                f"{self.log_prefix} 🔍 Comparando: '{file_norm[:80]}' com '{self.title}' e '{self.original_title}'",
                xbmc.LOGDEBUG
            )
        
        # 1. CALCULAR SIMILARIDADE DO TÍTULO
        similarity = calculate_title_similarity(
            file_name, 
            self.title, 
            self.original_title,
            self.media_type  # NOVO: passa o tipo de mídia
        )
        
        # Para FILMES: Threshold reduzido para 80 para aceitar títulos que não estão no início
        if self.media_type == 'movie':
            if similarity < 80:
                xbmc.log(
                    f"{self.log_prefix} ❌ Rejeitado (similaridade baixa {similarity}): {file_name[:80]}", 
                    xbmc.LOGDEBUG
                )
                return False, similarity
            
            # 2. VALIDAÇÃO ULTRA RIGOROSA DE ANO
            if self.year:
                file_year = extract_year_from_filename(file_name)
                
                # Se não achou o ano no arquivo, REJEITA
                if not file_year:
                    xbmc.log(
                        f"{self.log_prefix} ❌ Rejeitado (sem ano no nome): {file_name[:80]}", 
                        xbmc.LOGDEBUG
                    )
                    return False, similarity
                
                # Ano deve ser próximo (tolerância de ±1 para lidar com lançamentos de virada de ano)
                if abs(file_year - self.year) > 1:
                    xbmc.log(
                        f"{self.log_prefix} ❌ Rejeitado (ano {file_year} longe de {self.year}): {file_name[:80]}", 
                        xbmc.LOGDEBUG
                    )
                    return False, similarity
                
                # Ano correto: bonus
                similarity += 10
            else:
                # Se não tem ano para validar, aceita mas sem bonus
                xbmc.log(
                    f"{self.log_prefix} ⚠️ Aviso: filme sem ano para validar - {file_name[:80]}", 
                    xbmc.LOGWARNING
                )
        
        elif self.media_type == 'tvshow':
            # Para séries: threshold 70 (mais flexível com original_title)
            if similarity < 70:
                xbmc.log(
                    f"{self.log_prefix} ❌ Rejeitado por baixa similaridade ({similarity:.0f}%): {file_name[:80]}", 
                    xbmc.LOGDEBUG
                )
                return False, similarity
            
            # Verificar episódio
            ep_match, ep_reason = self._check_episode_match(file_name, file_norm)
            
            if not ep_match:
                xbmc.log(
                    f"{self.log_prefix} ❌ Rejeitado: {ep_reason} - {file_name[:80]}", 
                    xbmc.LOGDEBUG
                )
                return False, similarity
            
            similarity += 20
        
        # 3. ACEITO!
        xbmc.log(
            f"{self.log_prefix} ✅ Aceito (score {similarity:.0f}%): {file_name[:80]}", 
            xbmc.LOGINFO
        )
        
        return True, similarity
    
    def build_download_link(self, link_part):
        """Constrói link de download completo"""
        if not link_part or not link_part.startswith('/'):
            return None
            
        try:
            path_part, query_string = link_part.split('?', 1)
            params = parse_qs(query_string)
            
            file_id = params.get('file', [None])[0]
            if not file_id:
                return None
                
            query_params = {'file': file_id}
            
            # Adicionar parâmetros opcionais
            for param in ['expiry', 'mac']:
                value = params.get(param, [None])[0]
                if value:
                    query_params[param] = value
            
            encoded_query = urlencode(query_params)
            return f"https://{self.download_domain}{path_part}?{encoded_query}"
            
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Erro construindo link: {e}", xbmc.LOGWARNING)
            return None
    
    def _detect_language_from_filename(self, file_name):
        """Detecta idioma do arquivo"""
        if not file_name:
            return 'PT-BR'
        
        fn = file_name.lower()
        
        # DUAL (prioridade máxima)
        if any(w in fn for w in ['dual', 'multi']):
            return 'DUAL'
        
        # Dublado explícito
        if any(w in fn for w in ['dublado', 'dub ', 'pt-br', 'ptbr']):
            return 'PT-BR'
        
        # Legendado explícito
        if any(w in fn for w in ['legendado', '[leg]', 'subs', '[eng]', 'subbed', 'english only']):
            return 'LEG'
        
        # Grupos internacionais
        if any(w in fn for w in ['subsplease', 'erai-raws', 'yify', 'rarbg', 'nyaa', '[judas]']):
            return 'LEG'
        
        # Fallback: AnimeZey é BR por padrão
        return 'PT-BR'
    
    def filter_and_process_files(self):
        """Filtra e processa os arquivos encontrados"""
        matched_results = []
        seen_links = set()
        valid_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts')
        
        xbmc.log(f"{self.log_prefix} 🔍 Iniciando filtro de {len(self.found_files)} arquivos...", xbmc.LOGINFO)
        
        # LOG: Mostrar título e episódio buscado
        if self.media_type == 'tvshow':
            xbmc.log(
                f"{self.log_prefix} 🎯 BUSCANDO: '{self.title}' (original: '{self.original_title}') S{self.season:02d}E{self.episode:02d}", 
                xbmc.LOGINFO
            )
        else:
            xbmc.log(
                f"{self.log_prefix} 🎯 BUSCANDO: '{self.title}' ({self.year})", 
                xbmc.LOGINFO
            )
        
        for file_data in self.found_files:
            file_name = file_data.get('name', '').strip()
            
            # LOG DEBUG: Mostrar TODOS os arquivos encontrados (para séries)
            if self.media_type == 'tvshow':
                xbmc.log(
                    f"{self.log_prefix} 📄 Testando: {file_name[:100]}", 
                    xbmc.LOGDEBUG
                )
            
            # Pular se não for vídeo válido
            if (not file_name or 
                file_data.get('mimeType') == 'application/vnd.google-apps.folder' or
                not any(file_name.lower().endswith(ext) for ext in valid_extensions)):
                continue
            
            # Aplicar filtros COM SCORE
            matches, score = self.matches_filters(file_name)
            if not matches:
                continue
            
            # Construir link de download
            link_part = file_data.get('link')
            download_link = self.build_download_link(link_part)
            
            if download_link and download_link not in seen_links:
                seen_links.add(download_link)
                
                # Detectar idioma
                detected_language = self._detect_language_from_filename(file_name)
                
                # Preparar metadados
                quality = guess_quality_from_name(file_name) or "HD"
                
                matched_results.append({
                    'url': download_link,
                    'quality': quality,
                    'type': 'Direto',
                    'title': file_name,  # Nome completo para detecção de idioma
                    'release_title': file_name,
                    'label': f"{file_name} [{quality}]",
                    'size': format_size(file_data.get('size', 0)) or '',
                    'peers': 'N/A',
                    'seeders': 'N/A', 
                    'provider': 'AnimeZey',
                    'languages': detected_language,
                    '_score': score  # Score interno para ordenação
                })
        
        xbmc.log(f"{self.log_prefix} 📊 Filtro concluído: {len(matched_results)} arquivos aceitos", xbmc.LOGINFO)
        return matched_results

    
    
    def scrape(self):
        """Método principal do scraper"""
        start_time = time.time()
        
        try:
            # 1. Gerar variações de busca
            search_names = self.generate_search_variations()
            
            search_suffix = f" S{self.season:02d}E{self.episode:02d}" if self.media_type == 'tvshow' else f" ({self.year})" if self.year else ""
            xbmc.log(f"{self.log_prefix} 🔎 Buscando '{self.title}'{search_suffix} - {len(search_names)} variações", xbmc.LOGINFO)
            
            # 2. Gerar queries de busca
            queries = self.generate_search_queries(search_names)
            xbmc.log(f"{self.log_prefix} 📊 {len(queries)} queries únicas geradas", xbmc.LOGINFO)
            
            # 3. Busca paralela
            self.parallel_search(queries)
            
            if not self.found_files:
                xbmc.log(f"{self.log_prefix} ⚠️ Nenhum arquivo encontrado", xbmc.LOGINFO)
                return []
            
            xbmc.log(f"{self.log_prefix} 🔍 {len(self.found_files)} arquivos únicos encontrados", xbmc.LOGINFO)
            
            # 4. Filtragem RIGOROSA
            matched_results = self.filter_and_process_files()
            
            # 5. Ordenar por score + qualidade
            if matched_results:
                quality_order = {'4K': 0, '1080p': 1, '720p': 2, 'HD': 3, 'SD': 4}
                matched_results.sort(
                    key=lambda x: (-x.get('_score', 0), quality_order.get(x['quality'], 99))
                )
                
                # Remover campo interno de score
                for result in matched_results:
                    result.pop('_score', None)
                
                result_suffix = f" S{self.season:02d}E{self.episode:02d}" if self.media_type == 'tvshow' else ""
                xbmc.log(f"{self.log_prefix} ✅ {len(matched_results)} links válidos para '{self.title}'{result_suffix}", xbmc.LOGINFO)
            else:
                xbmc.log(f"{self.log_prefix} ❌ Nenhum arquivo correspondeu aos filtros", xbmc.LOGINFO)
            
            return matched_results
            
        except AnimeZeyScraperError as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro do Scraper: {e}", xbmc.LOGERROR)
            return []
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro Geral: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            return []

# --- Função de Interface ---
def scrape(provider_url, item_data, cancel_event=None):
    """Interface para compatibilidade"""
    try:
        scraper = AnimeZeyScraper(provider_url, item_data, cancel_event)
        return scraper.scrape()
    except Exception as e:
        xbmc.log(f"[animezey.scrape] ❌ Erro: {e}", xbmc.LOGERROR)
        return []