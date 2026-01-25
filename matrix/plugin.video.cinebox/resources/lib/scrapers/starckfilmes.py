# -*- coding: utf-8 -*-
"""
Scraper para Starck Filmes
Extrai magnet links de filmes e séries
"""
import re
import xbmc
import requests
from bs4 import BeautifulSoup


def unshuffle_string(shuffled):
    """
    Decodifica a string ofuscada do data-u
    Algoritmo reverso do JavaScript do site
    """
    try:
        length = len(shuffled)
        original = [''] * length
        used = [False] * length
        
        step = 3  # Valor do algoritmo original
        index = 0
        
        for i in range(length):
            # Encontra o próximo índice não usado
            while used[index]:
                index = (index + 1) % length
            
            used[index] = True
            original[i] = shuffled[index]
            index = (index + step) % length
        
        return ''.join(original)
    except Exception as e:
        xbmc.log(f"[Starck] Erro ao desembaralhar: {e}", xbmc.LOGERROR)
        return None


def extrair_magnet_links(soup):
    """
    Extrai TODOS os magnet links da página (pode haver múltiplas qualidades)
    Retorna lista de dicts com {magnet, quality, size}
    """
    links_encontrados = []
    
    try:
        # Encontrar TODOS os botões de download
        btns = soup.find_all('span', class_='btn-down')
        
        if not btns:
            xbmc.log("[Starck] Nenhum botão de download encontrado", xbmc.LOGWARNING)
            return links_encontrados
        
        xbmc.log(f"[Starck] Encontrados {len(btns)} botões de download", xbmc.LOGINFO)
        
        for btn in btns:
            try:
                link = btn.find('a')
                if not link:
                    continue
                
                # Extrair o data-u
                data_u = link.get('data-u')
                if not data_u:
                    continue
                
                # Decodificar usando unshuffle
                decoded = unshuffle_string(data_u)
                if not decoded or ('magnet:' not in decoded and not decoded.startswith('http')):
                    continue
                
                # Extrair qualidade e tamanho do texto do botão
                text_span = btn.find('span', class_='text')
                quality = 'HD'
                size = 'N/A'
                
                if text_span:
                    texto_completo = text_span.get_text()
                    
                    # Extrair qualidade (1080p, 720p, 2160p, etc)
                    quality_match = re.search(r'(4K|2160p|1080p|720p|480p)', texto_completo, re.IGNORECASE)
                    if quality_match:
                        quality = quality_match.group(1).upper()
                    
                    # Extrair tamanho (3.70 GB, 11.84 GB, etc)
                    size_match = re.search(r'\(([^)]+(?:GB|MB))\)', texto_completo, re.IGNORECASE)
                    if size_match:
                        size = size_match.group(1)
                
                links_encontrados.append({
                    'magnet': decoded,
                    'quality': quality,
                    'size': size
                })
                
                xbmc.log(f"[Starck] Link extraído: {quality} - {size}", xbmc.LOGINFO)
                
            except Exception as e:
                xbmc.log(f"[Starck] Erro ao processar botão: {e}", xbmc.LOGERROR)
                continue
        
        return links_encontrados
        
    except Exception as e:
        xbmc.log(f"[Starck] Erro ao extrair magnets: {e}", xbmc.LOGERROR)
        return links_encontrados


def extrair_informacoes_basicas(soup):
    """
    Extrai informações básicas do filme/série
    """
    info = {}
    
    try:
        # Título
        titulo = soup.find('h1')
        if titulo:
            info['title'] = titulo.text.strip()
        
        # IMDB
        imdb = soup.find('span', class_='sl-imdb')
        if imdb:
            info['rating'] = imdb.text.strip()
        
        # Metadados (tamanho, qualidade, etc)
        desc_div = soup.find('div', class_='post-description')
        if desc_div:
            paragrafos = desc_div.find_all('p')
            for p in paragrafos:
                spans = p.find_all('span')
                if len(spans) >= 2:
                    chave = spans[0].text.strip(':').strip().lower()
                    valor = spans[1].text.strip()
                    
                    if 'tamanho' in chave:
                        info['size'] = valor
                    elif 'qualidade' in chave and 'video' in chave:
                        info['quality'] = valor
        
        # Qualidade da tag meta
        meta = soup.find('span', class_='sl-quality')
        if meta:
            q = meta.text.strip()
            if q == 'FHD':
                info['quality_label'] = '1080p'
            elif q == 'HD':
                info['quality_label'] = '720p'
            elif q == 'UHD':
                info['quality_label'] = '4K'
            else:
                info['quality_label'] = q
    
    except Exception as e:
        xbmc.log(f"[Starck] Erro ao extrair informações: {e}", xbmc.LOGERROR)
    
    return info


def detectar_idioma_filme(soup):
    """
    Detecta o idioma do filme baseado no botão de download
    """
    try:
        btn = soup.find('span', class_='btn-down')
        if not btn:
            return ''
        
        text_span = btn.find('span', class_='text')
        if not text_span:
            return ''
        
        texto = text_span.get_text().lower()
        
        if 'dual' in texto or 'dual áudio' in texto:
            return ' DUAL'
        elif 'dublado' in texto:
            return ' DUBLADO'
        elif 'legendado' in texto:
            return ' LEGENDADO'
        
        return ''
        
    except Exception as e:
        xbmc.log(f"[Starck] Erro ao detectar idioma: {e}", xbmc.LOGERROR)
        return ''


def buscar_filme(item_data):
    """
    Busca um filme no Starck Filmes
    """
    titulo = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')
    ano = item_data.get('year', '')
    
    if not titulo:
        return []
    
    # Tentar buscar com título principal E título original (se diferente)
    titulos_para_buscar = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        titulos_para_buscar.append(titulo_original)
    
    # Adicionar variações sem caracteres especiais
    for t in list(titulos_para_buscar):
        clean_t = re.sub(r'[^\w\s]', ' ', t).strip()
        if clean_t != t:
            titulos_para_buscar.append(clean_t)
    
    xbmc.log(f"[Starck] Títulos para busca: {titulos_para_buscar}", xbmc.LOGINFO)
    
    sources = []
    
    for titulo_busca in titulos_para_buscar:
        try:
            # Normalizar título para busca
            search_query = titulo_busca.lower()
            search_query = re.sub(r'[^\w\s]', '', search_query)
            search_query = search_query.replace(' ', '+')
            
            # URL de busca
            base_url = "https://www.starckfilmes-v8.com"
            search_url = f"{base_url}/?s={search_query}"
            
            xbmc.log(f"[Starck] Buscando: {search_url}", xbmc.LOGINFO)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            try:
                response = requests.get(search_url, headers=headers, timeout=15)
                xbmc.log(f"[Starck] Resposta de {search_url}: Status {response.status_code}", xbmc.LOGINFO)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                xbmc.log(f"[Starck] Erro de rede na busca: {e}", xbmc.LOGWARNING)
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar resultados
            resultados = soup.find_all('div', class_='item')
            
            for resultado in resultados[:3]:  # Limitar a 3 resultados
                try:
                    # Link do filme
                    link_tag = resultado.find('a', class_='title')
                    if not link_tag:
                        continue
                    
                    filme_url = link_tag.get('href')
                    filme_titulo = link_tag.text.strip()
                    
                    # FILTRO DE SÉRIE RIGOROSO: Se o título contém palavras de série, pular
                    # Adicionado 'episódio', 'episodio', 'capítulo', 'capitulo'
                    if any(x in filme_titulo.lower() for x in ['temporada', 'série', 'serie', 'completa', 'episódio', 'episodio', 'capítulo', 'capitulo', 's0', 's1']):
                        xbmc.log(f"[Starck] Pulando série encontrada em busca de filme: {filme_titulo}", xbmc.LOGINFO)
                        continue
                    
                    # Verificar se o ano bate (se disponível)
                    year_span = resultado.find('span', class_='footer-year')
                    filme_ano = year_span.text.strip() if year_span else ''
                    
                    # Se temos ano, verificar compatibilidade
                    if ano and filme_ano:
                        try:
                            if abs(int(filme_ano) - int(ano)) > 1:
                                continue
                        except:
                            pass
                    
                    xbmc.log(f"[Starck] Processando: {filme_titulo} ({filme_url})", xbmc.LOGINFO)
                    
                    # Acessar página do filme
                    try:
                        filme_response = requests.get(filme_url, headers=headers, timeout=15)
                        xbmc.log(f"[Starck] Resposta da página do conteúdo: Status {filme_response.status_code}", xbmc.LOGINFO)
                        filme_response.encoding = 'utf-8'
                        filme_soup = BeautifulSoup(filme_response.text, 'html.parser')
                    except requests.exceptions.RequestException as e:
                        xbmc.log(f"[Starck] Erro de rede ao acessar página do filme: {e}", xbmc.LOGWARNING)
                        continue
                    
                    # FILTRO DE SÉRIE (PÁGINA): Verificar se a página contém a div 'epsodios' ou 'episodios'
                    if filme_soup.find('div', class_='epsodios') or filme_soup.find('div', class_='episodios') or filme_soup.find('div', id='episodios'):
                        xbmc.log(f"[Starck] Pulando página de série detectada: {filme_titulo}", xbmc.LOGINFO)
                        continue
                    
                    # FILTRO ADICIONAL: Se houver muitos magnet links com nomes de episódios
                    magnets_raw = filme_soup.find_all('span', class_='btn-down')
                    is_series_page = False
                    for btn in magnets_raw[:5]:
                        btn_text = btn.get_text().lower()
                        if re.search(r'episódio|episodio|capítulo|capitulo|ep\s?\d+|s\d+e\d+', btn_text):
                            is_series_page = True
                            break
                    
                    if is_series_page:
                        xbmc.log(f"[Starck] Pulando página com links de episódios: {filme_titulo}", xbmc.LOGINFO)
                        continue
                    
                    # Extrair TODOS os magnets (pode haver múltiplas qualidades)
                    magnets = extrair_magnet_links(filme_soup)
                    if not magnets:
                        continue
                    
                    # Extrair informações básicas
                    info = extrair_informacoes_basicas(filme_soup)
                    
                    # Detectar idioma do botão de download (usa o primeiro botão como referência)
                    sufixo_idioma = detectar_idioma_filme(filme_soup)
                    
                    # Criar um stream para cada qualidade disponível
                    for idx, mag_data in enumerate(magnets):
                        titulo_final = filme_titulo + sufixo_idioma
                        
                        # Se há múltiplas versões, adicionar identificador
                        if len(magnets) > 1:
                            titulo_final += f" [{mag_data['quality']} - {mag_data['size']}]"
                        
                        # Tenta extrair seeders do texto se disponível
                        seeds = 0
                        seed_match = re.search(r'(?:seeders|seeds|sementes|s)[:\s]*(\d+)', titulo_final, re.IGNORECASE)
                        if seed_match:
                            seeds = int(seed_match.group(1))

                        stream = {
                            'url': mag_data['magnet'],
                            'title': f"{titulo_final} (S:{seeds})",
                            'quality': mag_data['quality'],
                            'size': mag_data['size'],
                            'type': 'Torrent',
                            'seeders': seeds,
                            'extras': []
                        }
                        
                        sources.append(stream)
                        xbmc.log(f"[Starck] Stream adicionado: {titulo_final}", xbmc.LOGINFO)
                    
                except Exception as e:
                    xbmc.log(f"[Starck] Erro ao processar resultado: {e}", xbmc.LOGERROR)
                    continue
            
            # Se encontrou resultados com este título, não precisa tentar os outros
            if sources:
                break
                
        except Exception as e:
            xbmc.log(f"[Starck] Erro na busca com '{titulo_busca}': {e}", xbmc.LOGERROR)
            continue
    
    if not sources:
        xbmc.log(f"[Starck] Nenhum resultado encontrado para nenhum dos títulos", xbmc.LOGWARNING)
    
    return sources


def buscar_serie(item_data, season, episode):
    """
    Busca um episódio de série no Starck Filmes
    """
    titulo = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')
    
    if not titulo or season is None or episode is None:
        return []
    
    # Tentar buscar com título principal E título original (se diferente)
    titulos_para_buscar = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        titulos_para_buscar.append(titulo_original)
    
    # Adicionar variações sem caracteres especiais
    for t in list(titulos_para_buscar):
        clean_t = re.sub(r'[^\w\s]', ' ', t).strip()
        if clean_t != t:
            titulos_para_buscar.append(clean_t)
    
    xbmc.log(f"[Starck] Títulos para busca de série: {titulos_para_buscar}", xbmc.LOGINFO)
    
    sources = []
    
    for titulo_busca in titulos_para_buscar:
        try:
            # Normalizar título - APENAS O NOME DA SÉRIE
            search_query = titulo_busca.lower()
            search_query = re.sub(r'[^\w\s]', '', search_query)
            search_query = search_query.replace(' ', '+')
            
            # Formatação do episódio para filtro
            s_num = int(season)
            e_num = int(episode)
            s = str(s_num).zfill(2)
            e = str(e_num).zfill(2)
            ep_pattern = f"s{s}e{e}"
            
            base_url = "https://www.starckfilmes-v8.com"
            search_url = f"{base_url}/?s={search_query}"
            
            xbmc.log(f"[Starck] Buscando série: {search_url}", xbmc.LOGINFO)
            xbmc.log(f"[Starck] Procurando por: {ep_pattern}", xbmc.LOGINFO)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            try:
                response = requests.get(search_url, headers=headers, timeout=15)
                xbmc.log(f"[Starck] Resposta de {search_url}: Status {response.status_code}", xbmc.LOGINFO)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                xbmc.log(f"[Starck] Erro de rede na busca: {e}", xbmc.LOGWARNING)
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar resultados - pode ser página da temporada completa
            resultados = soup.find_all('div', class_='item')
            
            for resultado in resultados[:5]:  # Aumentar limite
                try:
                    link_tag = resultado.find('a', class_='title')
                    if not link_tag:
                        continue
                    
                    page_url = link_tag.get('href')
                    page_titulo = link_tag.text.strip()
                    
                    # Corrigir codificação do título da página se necessário
                    try:
                        page_titulo_fixed = page_titulo.encode('latin1').decode('utf-8')
                    except:
                        page_titulo_fixed = page_titulo
                    
                    xbmc.log(f"[Starck] Verificando página: {page_titulo_fixed}", xbmc.LOGINFO)
                    
                    # Acessar página
                    try:
                        page_response = requests.get(page_url, headers=headers, timeout=15)
                        # Forçar encoding para utf-8 para evitar problemas com caracteres especiais
                        page_response.encoding = 'utf-8'
                        page_soup = BeautifulSoup(page_response.text, 'html.parser')
                    except requests.exceptions.RequestException as e:
                        xbmc.log(f"[Starck] Erro de rede ao acessar página: {e}", xbmc.LOGWARNING)
                        continue
                    
                    # Procurar pela div de episódios
                    epsodios_div = page_soup.find('div', class_='epsodios')
                    
                    if epsodios_div:
                        # É uma página de temporada com vários episódios
                        xbmc.log("[Starck] Página de temporada encontrada", xbmc.LOGINFO)
                        
                        # Procurar pelo episódio específico
                        paragrafos = epsodios_div.find_all('p')
                        
                        for p in paragrafos:
                            strong = p.find('strong')
                            if not strong:
                                continue
                            
                            ep_text = strong.text.lower()
                            
                            # Padrões para encontrar o episódio
                            # "EPISÓDIO 01:", "EPISÓDIOS 01 E 02:", "EPISÓDIO 08 ao 09:", etc
                            episodio_encontrado = False
                            
                            # Método 1: Buscar por "episódio XX" (com zero à esquerda ou sem)
                            if re.search(rf'episódios?\s+0?{e_num}\b', ep_text):
                                episodio_encontrado = True
                            
                            # Método 2: Buscar por range "01 e 02", "08 ao 09", "01 a 10"
                            if not episodio_encontrado:
                                # Procurar por "episódio X e Y", "episódio X ao Y", "episódio X a Y"
                                match = re.search(r'episódios?\s+0?(\d+)\s+(?:e|ao|a)\s+0?(\d+)', ep_text)
                                if match:
                                    inicio = int(match.group(1))
                                    fim = int(match.group(2))
                                    if inicio <= e_num <= fim:
                                        episodio_encontrado = True
                            
                            # Método 3: Buscar apenas pelo número se o parágrafo for curto e contiver o número
                            if not episodio_encontrado and len(ep_text) < 20:
                                if re.search(rf'\b0?{e_num}\b', ep_text):
                                    episodio_encontrado = True
                            
                            if not episodio_encontrado:
                                continue
                            
                            xbmc.log(f"[Starck] Episódio {e_num} encontrado em: {ep_text}", xbmc.LOGINFO)
                            
                            # Extrair link do episódio
                            link = p.find('a')
                            if not link:
                                xbmc.log("[Starck] Link não encontrado no parágrafo", xbmc.LOGWARNING)
                                continue
                            
                            data_u = link.get('data-u')
                            if not data_u:
                                xbmc.log("[Starck] data-u não encontrado", xbmc.LOGWARNING)
                                continue
                            
                            # Decodificar magnet
                            magnet = unshuffle_string(data_u)
                            if not magnet or 'magnet:' not in magnet:
                                xbmc.log("[Starck] Magnet inválido após decodificação", xbmc.LOGWARNING)
                                continue
                            
                            # Extrair informações básicas da página
                            info = extrair_informacoes_basicas(page_soup)
                            
                            # Detectar idioma do H3 na div epsodios
                            sufixo_idioma = ''
                            h3 = epsodios_div.find('h3')
                            if h3:
                                h3_text = h3.get_text().lower()
                                if 'dual' in h3_text:
                                    sufixo_idioma = ' DUAL'
                                elif 'dublado' in h3_text:
                                    sufixo_idioma = ' DUBLADO'
                                elif 'legendado' in h3_text:
                                    sufixo_idioma = ' LEGENDADO'
                            
                            # Montar título (usar o título original da busca, não o do site)
                            # ✅ CORREÇÃO: Usar o título real do parágrafo para validação posterior
                            # Se o parágrafo não contiver SxxExx, o navigation.py vai descartar
                            ep_titulo = f"{titulo} {ep_text.upper()}{sufixo_idioma}"
                            
                            stream = {
                                'url': magnet,
                                'title': ep_titulo,
                                'quality': info.get('quality_label', 'HD'),
                                'size': info.get('size', 'N/A'),
                                'type': 'Torrent',
                                'seeders': 0,
                                'extras': []
                            }
                            
                            sources.append(stream)
                            xbmc.log(f"[Starck] Stream adicionado: {ep_titulo}", xbmc.LOGINFO)
                            break  # Encontrou o episódio, não precisa continuar
                    
                    else:
                        # Página individual de episódio
                        if ep_pattern in page_titulo.lower():
                            xbmc.log(f"[Starck] Processando episódio individual: {page_titulo}", xbmc.LOGINFO)
                            
                            magnets = extrair_magnet_links(page_soup)
                            if not magnets:
                                continue
                            
                            info = extrair_informacoes_basicas(page_soup)
                            sufixo_idioma = detectar_idioma_filme(page_soup)
                            
                            # Criar stream para cada qualidade (episódios raramente têm múltiplas, mas suportar)
                            for mag_data in magnets:
                                ep_titulo = page_titulo + sufixo_idioma
                                if len(magnets) > 1:
                                    ep_titulo += f" [{mag_data['quality']} - {mag_data['size']}]"
                                
                                stream = {
                                    'url': mag_data['magnet'],
                                    'title': ep_titulo,
                                    'quality': mag_data['quality'],
                                    'size': mag_data['size'],
                                    'type': 'Torrent',
                                    'seeders': 0,
                                    'extras': []
                                }
                                
                                sources.append(stream)
                    
                except Exception as e:
                    xbmc.log(f"[Starck] Erro ao processar página: {e}", xbmc.LOGERROR)
                    continue
            
            # Se encontrou resultados com este título, não precisa tentar os outros
            if sources:
                break
                
        except Exception as e:
            xbmc.log(f"[Starck] Erro na busca de série com '{titulo_busca}': {e}", xbmc.LOGERROR)
            continue
    
    if not sources:
        xbmc.log(f"[Starck] Nenhum episódio {ep_pattern} encontrado para nenhum dos títulos", xbmc.LOGWARNING)
    
    return sources


def scrape(provider_url, item_data, season=None, episode=None):
    """
    Função principal do scraper
    """
    xbmc.log("[Starck] Iniciando scraper...", xbmc.LOGINFO)
    
    media_type = item_data.get('media_type')
    
    if media_type == 'movie':
        return buscar_filme(item_data)
    elif media_type == 'tvshow':
        return buscar_serie(item_data, season, episode)
    
    return []