
# -*- coding: utf-8 -*-
import sys
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
import json
import re
# from .db import db
from .utils import create_video_item
from . import scrapers
from .dialogs import DialogSelecaoFontes
from .resolver import CineboxResolverWindow
from urllib.parse import urlencode, unquote_plus, quote_plus
import urllib.request
import re
import threading
import time
import subprocess




# --- Configurações Essenciais ---
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ADDON = xbmcaddon.Addon()
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"

# --- Mapeamento de Idiomas (se ainda precisar) ---
FLAG_TO_LANG = { '🇧🇷': 'BR', '🇵🇹': 'PT', '🇺🇸': 'EN', '🇬🇧': 'EN', '🇪🇸': 'ES', 'RO': 'RO' }
def extract_languages_from_title(title: str):
    languages = []
    flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', title)
    for flag in flags:
        lang = FLAG_TO_LANG.get(flag)
        if lang and lang not in languages:
            languages.append(lang)
    return languages if languages else ['N/A']

def parse_stream_title(title):
    """Extrai detalhes do título da fonte do Torrentio."""
    details = {}
    details['release_title'] = title.split('\n')[0].strip()
    size_match = re.search(r'\[\s*(\d+\.?\d*\s*(GB|MB))\s*\]', title, re.IGNORECASE)
    if size_match: details['size'] = size_match.group(1)
    peers_match = re.search(r'👤\s*(\d+)', title)
    if peers_match: details['peers'] = peers_match.group(1)
    provider_match = re.search(r'⚙️\s*([^\n]+)', title)
    if provider_match: details['provider'] = provider_match.group(1).strip()
    return details
    
def show_main_menu(menu_structure):
    """Cria e exibe os itens do menu principal na tela."""
    xbmcplugin.setPluginCategory(HANDLE, 'Meniu Principal')
    fanart_addon = ADDON.getAddonInfo('fanart')
    

    for item in menu_structure:

        li = xbmcgui.ListItem(label=item['title'])
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        
        # --- BLOCO ADICIONADO PARA MOSTRAR O ÍCONE ---
        from .icons import get_icon_url
        icon = item.get('icon')
        if icon:
            # Suporta IDs de ícones do IMDb
            if isinstance(icon, str) and len(icon) < 15 and not icon.endswith('.png'):
                # É um ID de ícone, converte para URL
                icon_url = get_icon_url(icon)
                li.setArt({'thumb': icon_url, 'icon': icon_url})
            else:
                # É um caminho local
                li.setArt({'thumb': icon, 'icon': icon})
        # ----------------------------------------------
        
        # Adiciona Plot/Descrição se existir
        plot = item.get('plot', '')
        if plot:
            li.setInfo('video', {'plot': plot})
        
        # Arctic Fuse 2 usa propriedades para identificar menus especiais
        if item['action'] == 'favorites_menu':
            li.setProperty('IsSpecial', 'true')
            
        url = get_url(action=item['action'])
        
        # ✅ CORREÇÃO: Se a ação for abrir configurações, não deve ser tratado como pasta
        is_folder = True
        if item['action'] == 'open_settings':
            is_folder = False
            
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)
        
    # Finaliza o diretório para que os itens apareçam na tela.
    xbmcplugin.endOfDirectory(HANDLE)
    
# Em navigation.py

def show_my_list_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Lista Mea")
    fanart_addon = ADDON.getAddonInfo('fanart')
    # Algumas skins como Arctic Fuse 2 preferem 'movies' ou 'tvshows' para renderizar widgets corretamente
    # mas como este é um menu de pastas, vamos usar 'files' ou deixar o padrão se 'folder' falhar.
    xbmcplugin.setContent(HANDLE, 'files')

    items = [
        ("Filme", get_url(action="favorites_movies"), 'DefaultMovies.png'),
        ("Seriale", get_url(action="favorites_tvshows"), 'DefaultTVShows.png')
    ]

    for label, url, icon in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': icon, 'thumb': icon})
        if fanart_addon:
            li.setArt({'fanart': fanart_addon})
        
        # Adicionar propriedades que skins modernas usam para identificar o tipo de conteúdo
        li.setProperty('IsPlayable', 'false')
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def show_favorite_movies():
    xbmcplugin.setPluginCategory(HANDLE, "Lista Mea • Filme")
    xbmcplugin.setContent(HANDLE, 'movies')

    try:
        from .db.db import db_instance
        favorites = db_instance.get_favorites_by_type('movie')

        if not favorites:
            xbmcgui.Dialog().notification("Lista Mea", "Nu am gasit nici un film", xbmcgui.NOTIFICATION_INFO)
            return xbmcplugin.endOfDirectory(HANDLE, False)

        for item in favorites:
            from .movies import _create_movie_item_tuple
            url, li, is_folder = _create_movie_item_tuple(item)
            # Forçar mediatype para garantir que a skin reconheça
            li.setInfo('video', {'mediatype': 'movie'})
            # Propriedade extra para skins modernas
            li.setProperty('mediatype', 'movie')
            xbmcplugin.addDirectoryItem(HANDLE, url, li, is_folder)
    except Exception as e:
        xbmc.log(f"[Cinebox] Eroare la listarea filmelor preferate: {e}", xbmc.LOGERROR)

    xbmcplugin.endOfDirectory(HANDLE)

def show_favorite_tvshows():
    xbmcplugin.setPluginCategory(HANDLE, "Lista Mea • Seriale")
    xbmcplugin.setContent(HANDLE, 'tvshows')

    try:
        from .db.db import db_instance
        favorites = db_instance.get_favorites_by_type('tvshow')

        if not favorites:
            xbmcgui.Dialog().notification("Lista Mea", "Nu am gasit nici un serial", xbmcgui.NOTIFICATION_INFO)
            return xbmcplugin.endOfDirectory(HANDLE, False)

        for item in favorites:
            from .tvshows import _create_show_tuple
            url, li, is_folder = _create_show_tuple(item)
            # Forçar mediatype e garantir que séries sejam tratadas como pastas se necessário
            li.setInfo('video', {'mediatype': 'tvshow'})
            # Propriedade extra para skins modernas
            li.setProperty('mediatype', 'tvshow')
            
            # Arctic Fuse 2 e outras skins modernas exigem que séries sejam pastas para abrir temporadas
            # Se a URL não for de detalhes, ela DEVE ser uma pasta
            if 'action=show_details' not in url:
                is_folder = True
                
            xbmcplugin.addDirectoryItem(HANDLE, url, li, is_folder)
    except Exception as e:
        xbmc.log(f"[Cinebox] Eroare la afisare seriale gasite: {e}", xbmc.LOGERROR)

    xbmcplugin.endOfDirectory(HANDLE)



   
    
def _fetch_json_from_url(url):
    """✅ OTIMIZADO: Função auxiliar para baixar um JSON de uma URL."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept-Encoding': 'gzip, deflate'  # ✅ NOVO: Compressão
        })
        # ✅ OTIMIZAÇÃO: Timeout reduzido de 15s para 8s
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        xbmc.log(f"[ERROR] Esuare descarcare JSON de la {url}: {e}", xbmc.LOGERROR)
    return None


def search(query=None, page=1):
    page = int(page)
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE

    # 1. Input de busca
    if not query:
        keyboard = xbmc.Keyboard('', 'Cautare Filme sau Seriale')
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            query = keyboard.getText().strip()
        else:
            return

    if not query:
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Cautare: {query}')
    fanart_addon = ADDON.getAddonInfo('fanart')
    xbmcplugin.setContent(HANDLE, 'movies')

    from .tmdb_api import search_tmdb
    from .movies import _create_movie_item_tuple
    from .tvshows import _create_show_tuple
    # from .db import db

    items = []
    used_tmdb_ids = set()

    # 2. BUSCA LOCAL (sem quebrar assinatura)
    try:
        from .db.db import db_instance
        local_results = db_instance.search_items(query)
    except Exception as e:
        xbmc.log(f"[Cinebox] Erroare cautare locala: {e}", xbmc.LOGERROR)
        local_results = []

    # paginação manual local
    local_page = local_results[offset: offset + PAGE_SIZE]

    for item in local_page:
        tmdb_id = item.get('tmdb_id')
        if tmdb_id:
            used_tmdb_ids.add(str(tmdb_id))

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    # 3. BUSCA TMDB (complementar)
    tmdb_results = search_tmdb(query, page=page) or []

    for item in tmdb_results:
        tmdb_id = str(item.get('id'))
        if tmdb_id in used_tmdb_ids:
            continue

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    if not items:
        xbmcgui.Dialog().notification("Descarcare", f'Nu am gasit "{query}"')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))

    # 4. Próxima página
    if len(items) >= PAGE_SIZE:
        next_url = get_url(
            action='search',
            query=query,
            page=page + 1
        )
        li = xbmcgui.ListItem(label='[COLOR red]Pagina Urmatoare >>[/COLOR]')
        li.setArt({'thumb': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)



# --- Providers com Ordem Prioritária ---
PROVIDERS = {
    "Brazuca": {
        "url": "https://94c8cb9f702d-brazuca-torrents.baby-beamup.club",
        "configurable": False,
        "priority": 1  # 🥇 PRIMEIRO - Brazuca
    },
    "AnimeZey": {
        "url": "https://1.animezey23112022.workers.dev", 
        "configurable": False, 
        "priority": 3  # 🥇 PRIMEIRO - AnimeZey
    },

    "SkyFlix": {
        "url": "https://da5f663b4690-skyflixfork16.baby-beamup.club",
        "configurable": False, 
        "priority": 1  # 🥈 SEGUNDO - SkyFlix
    },
    "Torrentio": {
        "url": "https://torrentio.strem.fun",
        "configurable": True,
        "priority": 2  # 🥈 SEGUNDO - Torrentio
    },
    "TorrentsDB": {
        "url": "https://torrentsdb.com",
        "configurable": False,
        "priority": 2  # Torrent - TorrentsDB
    },
    "ICV": {
        "url": "https://icv.stremio.dpdns.org/eyJ0bWRiX2tleSI6IjU0NjJmNzg0NjlmM2Q4MGJmNTIwMTY0NTI5NGMxNmU0IiwidXNlX2NvcnNhcm9uZXJvIjp0cnVlLCJ1c2VfdWluZGV4IjpmYWxzZSwidXNlX2tuYWJlbiI6dHJ1ZSwidXNlX3RvcnJlbnRnYWxheHkiOmZhbHNlLCJ1c2VfdG9ycmVudGlvIjp0cnVlLCJ1c2VfbWVkaWFmdXNpb24iOnRydWUsInVzZV9jb21ldCI6dHJ1ZSwidXNlX3JhcmJnIjp0cnVlLCJmdWxsX2l0YSI6ZmFsc2UsImRiX29ubHkiOmZhbHNlLCJ1c2VfZ2xvYmFsX2NhY2hlIjp0cnVlfQ==/manifest.json",
        "configurable": False,
        "priority": 2  # Torrent - ICV
    },
    "WebStreamr": {
        "url": "https://webstreamr.hayd.uk",
        "configurable": False,
        "priority": 1  # Link Direto - WebStreamr
    },
    "ComandoTop": {
        "url": "https://comandofilmestop.site",
        "configurable": False,
        "priority": 3  # 🥉 TERCEIRO - ComandoTop
    },

    "UIndex": {
        "url": "https://uindex.org",
        "configurable": False,
        "priority": 6
    },
    "Perflix": {
        "url": "https://da5f663b4690-skyflixfork16.baby-beamup.club",
        "configurable": False,
        "priority": 2
    },
    "Nyaa": {
        "url": "https://nyaa.si",
        "configurable": False,
        "priority": 10
    },
    "StarckFilmes": {
        "url": "https://www.starckfilmes-v8.com",
        "configurable": False,
        "priority": 3
    },
    "BaixarFilmes": {
        "url": "https://baixafilmestorrent.org",
        "configurable": False,
        "priority": 3
    },
    "Magneto": {
        "url": "magneto",
        "configurable": False,
        "priority": 1
    }
}





# --- 1. FUNÇÕES DE SUPORTE (DEVEM VIR ANTES) ---

def extrair_idiomas_do_titulo(titulo, extras=None, provider=None):
    """
    Extrai idiomas do título de forma precisa e retorna indicadores de texto compatíveis.
    """
    if not titulo: return '[COLOR grey]N/A[/COLOR]'
    t = titulo.lower()
    
    # Indicadores de texto com cores para melhor visualização
    tags = {
        'PT-BR': '[COLOR green][BR][/COLOR]',
        'DUAL': '[COLOR yellow][DUAL][/COLOR]',
        'LEG': '[COLOR white][EN][/COLOR]',
        'ITA': '[COLOR cyan][IT][/COLOR]',
        'SPA': '[COLOR orange][ES][/COLOR]',
        'FRE': '[COLOR blue][FR][/COLOR]',
        'GER': '[COLOR grey][DE][/COLOR]',
        'JAP': '[COLOR pink][JP][/COLOR]'
    }

    # 1. Verificação de termos de áudio original/inglês
    is_original = any(x in t for x in ['english', '.eng.', ' eng ', 'original', 'subbed', 'legendado', '.leg.', ' subs '])
    
    # 2. Verificação de termos de dublagem/português/dual
    is_dubbed = any(x in t for x in ['dublado', '.dub.', ' dub ', 'portugues', 'português', 'pt-br', 'pt-pt', ' pt ', ' pt-pt ', 'nacional', 'portugal']) or '🇧🇷' in titulo or '🇵🇹' in titulo
    is_dual = any(x in t for x in ['dual', 'multi', 'tri-audio'])

    # 3. Lógica de decisão por Provedor e Título
    
    # Provedores que costumam ser PT-BR
    provedores_br = ['SkyFlix', 'Brazuca', 'ComandoTop', 'AnimeZey', 'WebStreamr', 'Fonte Local']
    
    # Caso especial: Italiano (ICV)
    if provider == 'ICV' or '.ita.' in t or ' italiano ' in t:
        if is_original or is_dual: return f"{tags['ITA']}{tags['LEG']} DUAL"
        return f"{tags['ITA']} ITA"

    # Se for DUAL, marcamos como DUAL independente do provedor
    if is_dual:
        return f"{tags['DUAL']} DUAL"
    
    # Se for um provedor brasileiro, a prioridade é PT-BR a menos que diga explicitamente English
    if provider in provedores_br:
        if is_original and not is_dubbed:
            return f"{tags['LEG']} LEG"
        # Se não for explicitamente original, assumimos PT-BR para sites brasileiros
        return f"{tags['PT-BR']} PT-BR"

    # Se for um provedor internacional (Torrentio, etc)
    if is_dubbed:
        return f"{tags['PT-BR']} PT-BR"
    
    # Outros Idiomas específicos
    if 'spa' in t or 'spaniola' in t: return f"{tags['SPA']} SPA"
    if 'fre' in t or 'franceza' in t: return f"{tags['FRE']} FRE"
    if 'ger' in t or 'germana' in t: return f"{tags['GER']} GER"
    if 'jap' in t or 'japoneza' in t: return f"{tags['JAP']} JAP"
    
    # BLOQUEIO DE IDIOMAS INDESEJADOS (Polonês, Indiano, Russo, etc.)
    # Se encontrar qualquer um destes termos, marcamos como BLOQUEADO para descarte total
    # Adicionando termos mais específicos para polonês e outros idiomas europeus
    blocked_terms = [
        'hindi', 'tamil', 'telugu', 'kannada', 'malayalam', 'punjabi', 'bengali', 'urdu', 'marathi', 
        'gujarati', 'bhojpuri', 'assamese', 'odia', 'sanskrit', 'nepali', 'sinhala', 'russian', 'rus', 
        'chinese', 'chi', 'kor', 'korean', 'polish', 'polski', 'poland', 'polska', '.pl.', ' pl ', 
        'lektor', 'dubbing', 'napisy', 'pl-dub', 'pl-sub', 'czech', 'hungarian', 'bulgarian', 
        'turkish', 'arabic', 'hebrew', 'nordic', 'swedish', 'danish', 'norwegian', 'finnish'
    ]
    
    # Se for um provedor brasileiro, somos mais permissivos com termos genéricos
    # Mas se for Torrentio/Internacional, o bloqueio é rigoroso
    if any(x in t for x in blocked_terms):
        # Exceção: Se o título também contiver PT-BR ou DUBLADO de forma clara, podemos permitir
        # mas para polonês (lektor/pl) o bloqueio deve ser absoluto
        if any(x in t for x in ['lektor', 'polski', 'pl-dub', 'pl-sub', '.pl.', ' pl ']):
            return 'BLOQUEADO'
        
        # Se não for explicitamente PT-BR, bloqueia
        if not is_dubbed and not is_dual:
            return 'BLOQUEADO'
    
    # Padrão para Torrentio e outros internacionais
    # Se chegamos aqui e não é um provedor BR, e não detectamos nada, marcamos como LEG
    # Mas se o título for muito estranho ou tiver flags de outros países, bloqueamos
    if provider not in provedores_br and not is_original and not is_dubbed:
        # Se tiver flags de outros países (exceto US/UK/BR/PT), bloqueia
        other_flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', titulo)
        for flag in other_flags:
            if flag not in ['🇧🇷', '🇵🇹', '🇺🇸', '🇬🇧']:
                return 'BLOQUEADO'
                
    return f"{tags['LEG']} LEG"

def get_color_seeders(val, stream_type):
    if stream_type == 'Direct' or val == 999:
        return "[COLOR cyan]LINK DIRECT[/COLOR]", 999
    try:
        v = int(val)
        # ✅ ALTERAÇÃO: Cor definida como amarelo (yellow) conforme solicitado
        color = "yellow"
        return f"[COLOR {color}]{v}[/COLOR]", v
    except:
        return "[COLOR grey]S:0[/COLOR]", 0

def get_color_quality(q):
    q = q.upper()
    if '4K' in q or '2160P' in q: return f"[COLOR gold]{q}[/COLOR]", 4
    if '1080P' in q: return f"[COLOR blue]{q}[/COLOR]", 3
    if '720P' in q: return f"[COLOR orange]{q}[/COLOR]", 2
    return f"[COLOR grey]{q}[/COLOR]", 1

def extrair_codec_hdr(raw_title):
    t = raw_title.lower()

    source = ""
    if any(x in t for x in ['web-dl', 'webdl', 'webrip']):
        source = "web-dl"
    elif any(x in t for x in ['bluray', 'blu-ray', 'bdrip', 'bdremux']):
        source = "bluray"
    elif 'hdrip' in t:
        source = "hdrip"
    elif 'dvdrip' in t:
        source = "dvdrip"
    elif '3d' in t:
        source = "3d"
    elif 'cam' in t:
        source = "cam"
    elif re.search(r'\bts\b', t):
        source = "ts"

    codec = ""
    if any(x in t for x in ('h265', 'x265', 'hevc')):
        codec = "HEVC"
    elif any(x in t for x in ('h264', 'x264', 'avc')):
        codec = "AVC"

    hdr = ""
    if 'hdr' in t:
        hdr = "HDR"
    elif '10bit' in t or '10-bit' in t:
        hdr = "10bit"

    return codec, hdr, source



def extrair_audio(raw_title):
    t = raw_title.lower()

    canais = ""
    if re.search(r'7[\.\s]?1', t):
        canais = "7.1"
    elif re.search(r'5[\.\s]?1', t):
        canais = "5.1"
    elif re.search(r'2[\.\s]?0', t):
        canais = "2.0"

    codec = ""
    if 'atmos' in t:
        codec = "Atmos"
    elif 'truehd' in t:
        codec = "TrueHD"
    elif 'dts' in t:
        codec = "DTS"
    elif 'dd+' in t or 'eac3' in t:
        codec = "DD+"
    elif 'ac3' in t or 'dd5' in t:
        codec = "AC3"
    elif 'aac' in t:
        codec = "AAC"
    elif 'mp3' in t:
        codec = "MP3"

    return " ".join(x for x in (codec, canais) if x)


def validar_episodio_no_titulo(titulo, season, episode):
    """
    Valida se o título do arquivo contém a temporada e o episódio solicitados.
    """
    if not season or not episode:
        return True
        
    t = titulo.lower()
    s = int(season)
    e = int(episode)
    
    # ✅ 1. VALIDAÇÃO RIGOROSA DE TEMPORADA
    # Se o título contém "S02" e pedimos "S01", deve ser descartado IMEDIATAMENTE
    # Procuramos por padrões S\d+ ou Season \d+ ou Temporada \d+
    # Usamos findall para pegar todas as menções de temporada e garantir que NENHUMA conflita
    seasons_found = re.findall(r'(?:s|season|temporada|t|temp\.?)\s*(\d+)', t)
    if seasons_found:
        # Se encontrou alguma temporada, TODAS devem ser a correta ou o título deve ser descartado
        # Isso evita que "The Pitt S02E06" seja aceito para a Temporada 1
        if not any(int(found_s) == s for found_s in seasons_found):
            return False

    # ✅ 2. VALIDAÇÃO DE EPISÓDIO
    # Padrões comuns: S01E05, 1x05, S1E5, 01x05, etc.
    # Adicionamos \b para garantir que o número seja exato (evita E06 aceitar E061)
    patterns = [
        r's%02de%02d\b' % (s, e),
        r's%de%02d\b' % (s, e),
        r's%de%d\b' % (s, e),
        r'%02dx%02d\b' % (s, e),
        r'%dx%02d\b' % (s, e),
        r'%dx%d\b' % (s, e),
        r'season\s*%d\s*episode\s*%d\b' % (s, e),
        r'episódio\s*0?%d\b' % e,
        r'episodio\s*0?%d\b' % e,
        r'ep\s*0?%d\b' % e
    ]
    
    for pattern in patterns:
        if re.search(pattern, t):
            # Verificação extra: se achou um padrão de episódio, garante que não há OUTRO episódio conflitante
            # Ex: "S01E05-E06" aceita tanto 5 quanto 6. Mas "S01E05" não aceita 6.
            all_eps = re.findall(r'(?:e|ep|episódio|episodio|x)\s*(\d+)', t)
            if all_eps:
                if any(int(found_e) == e for found_e in all_eps):
                    return True
                else:
                    return False
            return True
            
    # ✅ 3. VERIFICAÇÃO DE PACKS / TEMPORADA COMPLETA
    # Se o título diz "Temporada Completa" ou apenas "S01", aceitamos se não houver conflito de episódio
    season_patterns = [
        r's%02d\b' % s,
        r's%d\b' % s,
        r'season\s*%02d\b' % s,
        r'season\s*%d\b' % s,
        r'temporada\s*%02d\b' % s,
        r'temporada\s*%d\b' % s,
        r't%02d\b' % s,
        r't%d\b' % s
    ]
    
    for pattern in season_patterns:
        if re.search(pattern, t):
            # Se achou a temporada, verifica se não está apontando para OUTRO episódio
            other_ep = re.search(r'(?:e|ep|episódio|episodio|x)\s*(\d+)', t)
            if other_ep:
                if int(other_ep.group(1)) == e:
                    return True
                else:
                    return False # É outro episódio na mesma temporada
            return True # É um pack da temporada correta
            
    return False


# --- 2. FUNÇÃO PRINCIPAL ---

def find_and_play_sources(item_data, autoplay=None, season=None, episode=None):
    import time

    media_type = item_data.get('media_type')
    imdb_id = item_data.get('imdb_id')
    
    # ✅ CORREÇÃO: Garante que season e episode sejam extraídos do item_data se não passados
    if season is None: season = item_data.get('season')
    if episode is None: episode = item_data.get('episode')

    if not media_type:
        xbmcgui.Dialog().ok("Eroare", "Date insuficiente.")
        return

    # ==========================================================
    # 1. PROCESSAMENTO DE STREAM (INALTERADO)
    # ==========================================================
    def process_single_stream(stream, is_local=False, p_name='Sursă locală', p_priority=999):
        # Suporte para Magneto e outros scrapers externos
        hoster_name = stream.get('hoster', p_name)
        provider_name = stream.get('provider', p_name)
        
        # ✅ VALIDAÇÃO DE EPISÓDIO (Para evitar resultados falsos em episódios não lançados)
        if media_type == 'tvshow' and season and episode:
            # ✅ IMPORTANTE: Prioriza o release_title (nome real do arquivo) para validação
            # Alguns scrapers colocam o título da série no 'title', o que engana a validação
            raw_title_to_check = stream.get('release_title') or stream.get('title') or stream.get('name') or ""
            
            if not validar_episodio_no_titulo(raw_title_to_check, season, episode):
                # Se for um provedor de torrent, a validação é obrigatória
                is_torrent_check = "elementum" in (stream.get('url') or "") or stream.get('server_name', '').upper() == 'TORRENT' or re.match(r'^[a-fA-F0-9]{40}$', stream.get('url') or "") or (stream.get('url') or "").startswith('magnet:')
                
                if is_torrent_check:
                    xbmc.log(f"[Cinebox] ❌ Rezultat respins (Episodul nu corespunde): {raw_title_to_check}", xbmc.LOGINFO)
                    return None

        # Se o stream já trouxer um hoster específico (como Viper, Coco, etc.), usamos ele
        # Caso contrário, usamos o nome do provedor que iniciou a busca (p_name)
        if 'hoster' in stream:
            hoster_name = stream['hoster']
            provider_name = stream.get('provider', hoster_name)

        url = stream.get('url') or stream.get('infoHash')
        if not url:
            return None

        # ✅ OBTÉM O TÍTULO BRUTO PARA DETECÇÃO DE IDIOMA (MUITO IMPORTANTE)
        raw_title = stream.get('title') or stream.get('name') or ""
        
        # ✅ DETECTA IDIOMA NO TÍTULO BRUTO ANTES DE QUALQUER LIMPEZA
        idiomas_detectados = extrair_idiomas_do_titulo(raw_title, stream.get('extras', []), provider_name)
        
        # ✅ BLOQUEIO CRÍTICO: Se o idioma for marcado como BLOQUEADO, ignoramos a fonte completamente
        if idiomas_detectados == 'BLOQUEADO':
            return None

        # Prioriza o release_title se ele existir e for válido para exibição
        if stream.get('release_title') and len(stream['release_title']) > 5:
            display_title = stream['release_title']
        else:
            display_title = raw_title
    
        # Limpeza do título de exibição (display_title)
        display_title = re.sub(r'👤\s*\d+', '', display_title)
        display_title = re.sub(r'S:\s*\d+', '', display_title)
        display_title = re.sub(r'\[\s*\d+\.?\d*\s*(?:GB|MB)\s*\]', '', display_title, flags=re.IGNORECASE)
        display_title = re.sub(r'⚙️\s*[^\n]+$', '', display_title)
        display_title = ' '.join(display_title.split()).strip()
    
        if len(display_title) > 80:
            display_title = display_title[:77] + '...'
    
        if not display_title:
            nome_base = item_data.get('title') or 'Vídeo'
            ano = item_data.get('year') or ''
            if item_data.get('season') and item_data.get('episode'):
                s = str(item_data['season']).zfill(2)
                e = str(item_data['episode']).zfill(2)
                display_title = f"{nome_base} S{s}E{e}"
            else:
                display_title = f"{nome_base} ({ano})" if ano else nome_base

        if is_local:
            is_torrent = "elementum" in url or stream.get('server_name', '').upper() == 'TORRENT'
            stype = 'Torrent' if is_torrent else 'Direto'
        else:
            stype = stream.get('type', 'Direct')
            if re.match(r'^[a-fA-F0-9]{40}$', url) or url.startswith('magnet:'):
                stype = 'Torrent'
            if provider_name == 'WebStreamr':
                stype = 'Direct'

        # Tenta extrair seeders de vários formatos comuns (👤, S:, Seeds:, Sementes:)
        # O Torrentio costuma usar 👤 seguido do número de peers/seeds
        # Também verificamos o campo 'name' e 'description' que o Stremio usa
        text_to_check = f"{raw_title} {stream.get('name', '')} {stream.get('description', '')}"
        
        # LOG DE DEPURAÇÃO PARA SEEDS
        if provider_name == 'Torrentio' or '👤' in text_to_check:
            clean_text = text_to_check.replace('\n', ' ')
            xbmc.log("[Cinebox DEBUG] Provider: %s | Text: %s" % (provider_name, clean_text), xbmc.LOGINFO)
        
        # ✅ MELHORIA: Regex mais abrangente para capturar seeds em diversos formatos
        # 1. Procura por ícone de usuário ou labels comuns seguidos de número
        seed_match = re.search(r'(?:👤|S:|Seeds:|Sementes:|Seeders:)\s*(\d+)', text_to_check, re.IGNORECASE)
        
        if not seed_match:
            # 2. Procura por número seguido de labels comuns (ex: "10 Seeds")
            seed_match = re.search(r'(\d+)\s*(?:Seeds|Sementes|Seeders)', text_to_check, re.IGNORECASE)
            
        if not seed_match:
            # 3. Procura por padrão Torrentio/Stremio comum em descriptions: "👤 10" ou "S: 10"
            # Às vezes o ícone está colado no número
            seed_match = re.search(r'👤(\d+)', text_to_check)

        # ✅ OBTÉM O VALOR FINAL DOS SEEDS
        if seed_match:
            s_val_raw = seed_match.group(1)
        else:
            # Fallback para campos diretos do dicionário
            s_val_raw = stream.get('seeders', stream.get('seeds', stream.get('s', 0)))
            
        # Garante que s_val seja um número válido para evitar erros no int(s_val)
        try:
            s_val = int(s_val_raw)
        except:
            s_val = 0
            
        if stype == 'Direct':
            s_val = 999

        # ✅ MELHORIA: Extração de tamanho (Size) mais robusta
        size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB|GiB|MiB))', text_to_check, re.IGNORECASE)
        if not size_match:
            # Tenta formato sem espaço: "1.5GB"
            size_match = re.search(r'(\d+(?:\.\d+)?(?:GB|MB|GiB|MiB))', text_to_check, re.IGNORECASE)
            
        size_str = size_match.group(1) if size_match else stream.get('size', '')
        if size_str == 'N/A': size_str = ''

        # ✅ MELHORIA: Extração de qualidade mais abrangente
        q_match = re.search(r'(4K|2160p|1080p|720p|480p|SD)', raw_title, re.IGNORECASE)
        if not q_match:
            # Tenta no texto completo se não achou no título
            q_match = re.search(r'(4K|2160p|1080p|720p|480p|SD)', text_to_check, re.IGNORECASE)
            
        q_str = q_match.group(1).upper() if q_match else str(stream.get('quality', 'HD')).upper()

        codec, hdr, source = extrair_codec_hdr(raw_title)
        audio = extrair_audio(raw_title)
        video_info = " ".join(x for x in (codec, hdr, audio) if x)

        seed_label, seed_score = get_color_seeders(s_val, stype)
        qual_label, qual_score = get_color_quality(q_str)

        # LOG FINAL DE PROCESSAMENTO
        xbmc.log("[Cinebox DEBUG] Final Result -> Title: %s | Seeds: %s | Score: %s" % (display_title, s_val, seed_score), xbmc.LOGINFO)

        return {
            'url': url,
            'display_title': display_title,
            'raw_title': raw_title,
            'quality_label': qual_label,
            'seeders_label': seed_label,
            'size': size_str,
            'provider': provider_name,
            'hoster': hoster_name,
            'languages': idiomas_detectados,

            # PNG PROPERTIES
            'codec': codec.lower() if codec else '',
            'hdr': hdr.lower() if hdr else '',
            'audio': audio.lower() if audio else '',
            'source': source,

            # fallback texto
            'video_info': video_info,

            # ordenação
            'p_priority': p_priority,
            'q_score': qual_score,
            's_score': int(s_val),
            'seeders': int(s_val)
        }

    # ==========================================================
    # 2. BUSY DIALOG + THREADS INTELIGENTE
    # ==========================================================
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')

    provider_results = {}
    completed = 0
    lock = threading.Lock()

    start_time = time.time()
    pDialog = None

    # Variável para sinalizar cancelamento para as threads
    cancel_event = threading.Event()

    def fetch_thread(name, data):
        nonlocal completed
        try:
            # Passamos o cancel_event para o scraper se ele suportar, 
            # ou apenas checamos antes de começar
            if cancel_event.is_set(): return
            
            found = scrapers.scrape_provider_sources(name, data, item_data, cancel_event)
            
            if cancel_event.is_set(): return
            
            if found:
                with lock:
                    provider_results[name] = found
        except:
            pass
        finally:
            with lock:
                completed += 1

    # Normalização de nomes para bater com o settings.xml
    def is_provider_enabled(name):
        # Mapeamento manual para garantir que os nomes batam com o settings.xml
        mapping = {
            "ComandoTop": "comandotop",
            "Mico-Leão": "mico-leão",

            "SkyFlix": "skyflix",
            "Brazuca": "brazuca",
            "Torrentio": "torrentio",
            "UIndex": "uindex",
            "Perflix": "perflix",
            "Nyaa": "nyaa",
            "StarckFilmes": "starckfilmes",
            "AnimeZey": "animezey",
            "Magneto": "magneto"
        }
        setting_id = f"provider.{mapping.get(name, name.lower())}.enabled"
        enabled = ADDON.getSettingBool(setting_id)
        xbmc.log(f"[Cinebox] Verificare Provider {name} ({setting_id}): {enabled}", xbmc.LOGINFO)
        return enabled

    active_providers = [
        (n, d) for n, d in PROVIDERS.items()
        if is_provider_enabled(n)
    ]

    threads = []
    total_threads = len(active_providers)
    

    for name, data in active_providers:
        if name != 'AnimeZey' and not imdb_id:
            with lock:
                completed += 1
            continue

        t = threading.Thread(target=fetch_thread, args=(name, data))
        t.start()
        threads.append(t)

    # Loop de monitoramento
    # Aumentamos o tempo máximo de espera para 60 segundos para dar tempo aos scrapers externos
    cancelled_by_user = False
    while completed < total_threads and (time.time() - start_time) < 60:
        elapsed = time.time() - start_time

        # Cria progress BG apenas se demorar
        if elapsed > 0.7 and not pDialog:
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create("CINEBOX [COLOR red]TrainAgain[/COLOR]", "[COLOR yellow]Căutarea surselor pe servere...[/COLOR]")

        if pDialog:
            # Calcula percentagem proporcional ao tempo: se completou 50% das threads, mostra 50%
            # Se nenhuma thread completou, usa tempo como fallback
            if total_threads > 0:
                completed_percent = int((completed / total_threads) * 100)
            else:
                completed_percent = 0
            
            # Se threads completaram, usa esse percentual, senao usa tempo como fallback
            if completed_percent > 0:
                percent = min(completed_percent, 99)
            else:
                # Fallback: 1% a cada 0.3 segundos se nenhuma thread completou ainda
                percent = min(int((elapsed / 0.3) * 1), 99)
            
            pDialog.update(
                percent,
                message="[COLOR yellow]Căutarea surselor pe servere...[/COLOR]"
            )
        
        # ✅ CORRIGIDO: Verifica se o usuário cancelou via Dialog ou se a janela de busy foi fechada
        # No Kodi, DialogProgressBG tem iscanceled() que retorna True se o usuário cancelou
        if xbmc.Monitor().abortRequested():
            xbmc.log("[Cinebox] Anulare detectată de utilizator (abortRequested)", xbmc.LOGINFO)
            cancel_event.set()
            cancelled_by_user = True
            break
        
        # Verifica se o DialogProgressBG foi cancelado
        if pDialog:
            try:
                if pDialog.iscanceled():
                    xbmc.log("[Cinebox] Anulare detectată de utilizator (DialogProgressBG.iscanceled)", xbmc.LOGINFO)
                    cancel_event.set()
                    cancelled_by_user = True
                    break
            except:
                pass
        
        # Adicionalmente, verificar se a janela de busy foi fechada pelo usuário (cancelamento manual)
        if not xbmcgui.Window(10000).getProperty('busydialognocancel.active') == 'true' and elapsed > 1.0:
             # Se a janela sumiu e não terminamos, provavelmente foi cancelada
             # Nota: busydialognocancel não é facilmente detectável, mas abortRequested() cobre a maioria dos casos.
             pass

        xbmc.sleep(100)

    # ✅ CORRIGIDO: Se foi cancelado, aguarda threads com timeout curto
    if cancelled_by_user:
        xbmc.log("[Cinebox] Așteptând fire de execuție cu timeout scurt (2s)...", xbmc.LOGINFO)
        for t in threads:
            t.join(timeout=2.0)  # Aguarda no máximo 2 segundos por thread
    else:
        # Aguarda normalmente se não foi cancelado
        for t in threads:
            t.join()

    if pDialog:
        # Atualiza para 100% antes de fechar
        pDialog.update(100, message="[COLOR yellow]Căutând surse pe servere...[/COLOR]")
        xbmc.log("[Cinebox] Căutarea serverelor a fost finalizată: 100%", xbmc.LOGINFO)
        time.sleep(0.3)  # Mostra 100% por um breve momento
        pDialog.close()

    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    
    # CORRIGIDO: Se foi cancelado, retorna imediatamente sem mostrar dialogo
    if cancelled_by_user:
        xbmc.log("[Cinebox] Căutare anulată de utilizator, încheiere find_and_play_sources", xbmc.LOGINFO)
        # NOVO: Limpar playlist e parar player
        try:
            # Limpa a playlist do Kodi
            xbmc.executebuiltin('Playlist.Clear')
            xbmc.log("[Cinebox] Playlist.Clear executado", xbmc.LOGINFO)
            time.sleep(0.3)
            # Para o player completamente
            xbmc.executebuiltin('PlayerControl(stop)')
            xbmc.log("[Cinebox] PlayerControl(stop) executado", xbmc.LOGINFO)
            time.sleep(0.5)
            # Retorna False para indicar falha
            xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=False, listitem=xbmcgui.ListItem())
            xbmc.log("[Cinebox] setResolvedUrl(succeeded=False) chamado", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Cinebox] Eroare la oprirea playerului: {e}", xbmc.LOGWARNING)
        return

    # ==========================================================
    # 3. CONSOLIDAÇÃO (INALTERADO)
    # ==========================================================
    final_list = []
    seen_urls = set()

    for s in item_data.get('streams', []):
        p = process_single_stream(s, is_local=True)
        if p:
            # Verificação extra de segurança para bloqueio
            if p.get('languages') == 'BLOQUEADO':
                continue
            final_list.append(p)
            seen_urls.add(p['url'])

    for name, data in active_providers:
        if name in provider_results:
            xbmc.log(f"[Cinebox] Adăugând {len(provider_results[name])} rezultatele furnizorului {name}", xbmc.LOGINFO)
            for s in provider_results[name]:
                p = process_single_stream(s, False, name, data.get('priority', 999))
                if p:
                    # Verificação extra de segurança para bloqueio
                    if p.get('languages') == 'BLOQUEADO':
                        xbmc.log(f"[Cinebox] 🚫 Sursă blocată (Limbă nedorită): {p.get('display_title')}", xbmc.LOGINFO)
                        continue
                    if p['url'] not in seen_urls:
                        final_list.append(p)
                        seen_urls.add(p['url'])

    if not final_list:
        xbmcgui.Dialog().notification("Cinebox", "Nicio sursă găsită pe servere.", xbmcgui.NOTIFICATION_INFO, 5000)
        # ✅ CORREÇÃO DEFINITIVA: Evita "Playback failed" când nu există surse
        try:
            xbmc.executebuiltin('PlayerControl(stop)')
            xbmc.executebuiltin('Playlist.Clear')
            fake_item = xbmcgui.ListItem(path="")
            fake_item.setProperty('IsPlayable', 'false')
            xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=True, listitem=fake_item)
            xbmc.log("[Cinebox] Nicio sursă: setResolvedUrl(succeeded=True) cu element gol pentru a evita eroarea", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Cinebox] Eroare la finalizarea căutării goale: {e}", xbmc.LOGWARNING)
        return

    final_list.sort(key=lambda x: (x['p_priority'], -x['q_score'], -x['s_score']))

    # ==========================================================
    # 4. DIÁLOGO / AUTOPLAY (INALTERADO)
    # ==========================================================
    url_escolhida = None

    # Verifica se o Autoplay deve ser aplicado para este tipo de mídia
    should_autoplay = False
    
    # ✅ PRIORIDADE: Se o autoplay foi passado via parâmetro (TMDbHelper), usa ele
    if autoplay is not None:
        should_autoplay = True if str(autoplay).lower() == 'true' else False
    
    # Caso contrário, usa a configuração do addon
    elif xbmcaddon.Addon().getSettingBool('playback.autoplay'):
        _addon = xbmcaddon.Addon()
        autoplay_type = _addon.getSetting('playback.autoplay_type')
        if autoplay_type == 'Ambos':
            should_autoplay = True
        elif autoplay_type == 'Filme' and media_type == 'movie':
            should_autoplay = True
        elif autoplay_type == 'Seriale' and (media_type == 'tvshow' or media_type == 'episode' or media_type == 'tvshow'):
            should_autoplay = True

    if should_autoplay:
        _addon = xbmcaddon.Addon()
        # 1. Filtro de Resolução Máxima
        max_res = _addon.getSetting('playback.max_resolution').upper()
        res_map = {'4K': 4, '1080P': 3, '720P': 2, 'SD': 1}
        max_score = res_map.get(max_res, 3)
        
        filtered_res = [s for s in final_list if s['q_score'] <= max_score]
        if not filtered_res: filtered_res = final_list # Fallback se nada sobrar
        
        # 2. Filtro de Prioridade de Idioma
        lang_priority = _addon.getSetting('playback.language_priority') # 'Dublado' ou 'Legendado'
        
        # Separar a lista em categorias de idioma
        # O bloqueio já foi feito na extração (continue), mas garantimos aqui também
        filtered_res_clean = [s for s in filtered_res if s['languages'] != 'BLOQUEADO']
        
        # Se não sobrou nada após o bloqueio, usamos a lista original como último recurso (fallback de segurança)
        if not filtered_res_clean:
            filtered_res_clean = filtered_res
        
        dublados = [s for s in filtered_res_clean if ('PT-BR' in s['languages'] or 'DUAL' in s['languages'])]
        legendados = [s for s in filtered_res_clean if 'LEG' in s['languages'] and 'PT-BR' not in s['languages'] and 'DUAL' not in s['languages']]
        
        # Para 'outros', incluímos o que sobrou (outros idiomas permitidos como EN, ES, etc.)
        outros = [s for s in filtered_res_clean if s not in dublados and s not in legendados]
        
        if lang_priority == 'Dublado':
            ordered_autoplay = dublados + legendados + outros
        else:
            ordered_autoplay = legendados + dublados + outros
            
        if ordered_autoplay:
            url_escolhida = ordered_autoplay[0]['url']
            xbmc.log(f"[Cinebox] Redare automată selectată: {ordered_autoplay[0]['display_title']} (Res: {max_res}, Prioritate: {lang_priority})", xbmc.LOGINFO)
        else:
            url_escolhida = final_list[0]['url']
            xbmc.log(f"[Cinebox] Redare Automata: Eșec la sortare, se folosește prima sursă disponibilă", xbmc.LOGINFO)
    else:
        labels = [
            f"{s['quality_label']} | {s['languages']} | {s['seeders_label']} | {s['size']} | {s['provider']}"
            for s in final_list
        ]

        try:
            from resources.lib.dialogs import DialogSelecaoFontes
            dialog = DialogSelecaoFontes(
                'dialog_cinebox_fullscreen.xml',
                ADDON.getAddonInfo('path'),
                fontes=final_list,
                item_data=item_data
            )
            dialog.doModal()
            # NOVO: Verifica se foi cancelado
            if dialog.cancelled:
                xbmc.log("[Cinebox] Dialogul de selecție a fost anulat, încheind", xbmc.LOGINFO)
                # ✅ CORREÇÃO DEFINITIVA: Evita "Playback failed" ao cancelar
                try:
                    # 1. Para qualquer tentativa de reprodução em curso
                    xbmc.executebuiltin('PlayerControl(stop)')
                    xbmc.executebuiltin('Playlist.Clear')
                    
                    # 2. Cria um ListItem fake que parece válido mas não tem URL
                    # Isso engana o Kodi fazendo-o pensar que a reprodução foi "concluída" ou "ignorada" sem erro
                    fake_item = xbmcgui.ListItem(path="")
                    fake_item.setProperty('IsPlayable', 'false')
                    
                    # 3. Informa sucesso ao Kodi para suprimir o diálogo de erro
                    xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=True, listitem=fake_item)
                    xbmc.log("[Cinebox] Anulare curată: setResolvedUrl(succeeded=True) cu element gol", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[Cinebox] Eroare la anularea curată: {e}", xbmc.LOGWARNING)
                url_escolhida = None
            else:
                url_escolhida = dialog.escolha
            del dialog
        except:
            sel = xbmcgui.Dialog().select(
                f"Fontes: {final_list[0]['display_title']}", labels
            )
            if sel >= 0:
                url_escolhida = final_list[sel]['url']

    # ==========================================================
    # 5. RESOLVER
    # ==========================================================
    if url_escolhida:
        # ✅ CORREÇÃO: Garante que o clearlogo da série seja passado para o resolvedor
        if item_data.get('media_type') == 'tvshow' and not item_data.get('clearlogo'):
            if item_data.get('tvshow.clearlogo'):
                item_data['clearlogo'] = item_data['tvshow.clearlogo']

        resolver = CineboxResolverWindow(
            "resolver_window.xml",
            ADDON.getAddonInfo('path'),
            "Default",
            "1080i",
            source_url=url_escolhida,
            item_data=item_data,
            handle=int(sys.argv[1])
        )
        resolver.doModal()
        return # Impede que o código continue para o playback padrão do Kodi


def play_url(url, item_info):
    """
    Função para reproduzir uma URL, tratando Torrents (Elementum) com seleção
    automática de episódio e links diretos com headers (AnimeZey).
    """
    if not url:
        return

    try:
        handle = int(sys.argv[1])
    except (IndexError, ValueError) as e:
        xbmc.log(f"[Cinebox] Eroare: Script apelat fără un handle valid: {e}", xbmc.LOGERROR)
        return

    final_url = url
    is_torrent = False

    # --- 1. Lógica de Torrent ---
    if url.startswith('magnet:'):
        is_torrent = True
        magnet_uri = url
    elif len(url) == 40 and not url.startswith('http') and ' ' not in url:
        is_torrent = True
        magnet_uri = f"magnet:?xt=urn:btih:{url}"
    elif 'elementum' in url:
        is_torrent = True
        magnet_uri = url

    if is_torrent:
        if magnet_uri.startswith('plugin://'):
            final_url = magnet_uri
        else:
            encoded_uri = urllib.parse.quote_plus(magnet_uri)
            media_type = item_info.get('media_type')
            tmdb_id = item_info.get('tmdb_id')
            
            final_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
            
            if tmdb_id:
                final_url += f"&tmdb={tmdb_id}"

            # Lógica para séries
            if media_type == 'tvshow':
                season = item_info.get('season')
                episode = item_info.get('episode')
                
                # ✅ CORREÇÃO: Garante que o clearlogo da série seja passado para o resolvedor
                if not item_info.get('clearlogo') and item_info.get('tvshow.clearlogo'):
                    item_info['clearlogo'] = item_info['tvshow.clearlogo']
                
                if season is not None and episode is not None:
                    final_url += f"&season={season}&episode={episode}"
                    xbmc.log(f"[Cinebox] Construind link Elementum (Seriale S/E): {final_url}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[Cinebox] Construind link Elementum (Seriale): {final_url}", xbmc.LOGINFO)
            else:
                xbmc.log(f"[Cinebox] Construind link Elementum (Filme): {final_url}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[Cinebox] Rezolvare link direct: {final_url}", xbmc.LOGINFO)

    # --- 2. Cria o ListItem ---
    play_item = xbmcgui.ListItem(path=final_url)

    # --- 3. Metadados ---
    info_labels = {
        'title': item_info.get('episode_title', item_info.get('title', 'Playback')),
        'originaltitle': item_info.get('original_title'),
        'year': item_info.get('year'),
        'plot': item_info.get('plot', item_info.get('overview', '')),
        'season': item_info.get('season'),
        'episode': item_info.get('episode'),
        'tvshowtitle': item_info.get('title') if item_info.get('media_type') == 'tvshow' else '',
        'mediatype': item_info.get('media_type', 'video'),
        'imdbnumber': item_info.get('imdb_id'),
        'duration': int(item_info.get('runtime', 0)) * 60,
        'genre': " / ".join(item_info.get('genres', [])),
    }
    play_item.setInfo('video', info_labels)
    
    play_item.setArt({
        'thumb': item_info.get('episode_poster') or item_info.get('poster') or '',
        'poster': item_info.get('poster') or '',
        'fanart': item_info.get('backdrop') or '',
    })

    # --- 4. Lógica de Headers para AnimeZey ---
    animezey_domains = ['animezey23112022.workers.dev', 'animezey16082023.workers.dev', '1.animezeydl.workers.dev']
    if not is_torrent and any(domain in final_url.lower() for domain in animezey_domains):
        
        play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
        play_item.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')

        referer_header = final_url
        headers_str = (
            f"Referer={referer_header}\r\n"
            f"User-Agent={USER_AGENT}\r\n"
        )
        play_item.setProperty('inputstream.ffmpegdirect.headers', headers_str)

    # --- 5. Resolve a URL ---
    play_item.setProperty('IsPlayable', 'true')
    play_item.setContentLookup(False)

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)
    
    # --- ✅ 6. MONITORAMENTO ELEMENTUM E SCROBBLE ---
    def monitor_playback_and_elementum():
        player = xbmc.Player()
        is_elementum = "plugin.video.elementum" in final_url
        start_time = time.time()
        
        # Monitora início do playback e fecha diálogos do Elementum
        while not player.isPlaying():
            if xbmc.Monitor().abortRequested():
                xbmc.log("[Cinebox] Abort detectat in navigation.py, opresc Elementum", xbmc.LOGINFO)
                if is_elementum:
                    try:
                        subprocess.run(['pkill', '-f', 'elementum'], timeout=2)
                    except:
                        pass
                    try:
                        subprocess.run(['killall', 'elementum'], timeout=2)
                    except:
                        pass
                return
            
            if time.time() - start_time > 120: # Timeout 2 min
                break
                
            if is_elementum:
                # Não fecha os diálogos aqui se o CineboxResolverWindow estiver ativo
                # O fechamento será tratado pela janela de resolução customizada
                xbmc.executebuiltin('Dialog.Close(10101, true)')
                xbmc.executebuiltin('Dialog.Close(10151, true)')
            
            xbmc.sleep(500)
            
        # Se o scrobble estiver ativo, continua o monitoramento
        if ADDON.getSettingBool('trakt_auto_scrobble'):
            _delayed_trakt_scrobble(item_info)

    threading.Thread(target=monitor_playback_and_elementum, daemon=True).start()


def play_url(url, item_info):
    """
    Função para reproduzir uma URL, tratando Torrents (Elementum) com seleção
    automática de episódio e links diretos com headers (AnimeZey).
    """
    if not url:
        return

    try:
        handle = int(sys.argv[1])
    except (IndexError, ValueError) as e:
        xbmc.log(f"[Cinebox] Eroare: Script apelat fără un identificator valid: {e}", xbmc.LOGERROR)
        return

    final_url = url
    is_torrent = False

    # --- 1. Lógica de Torrent ---
    if url.startswith('magnet:'):
        is_torrent = True
        magnet_uri = url
    elif len(url) == 40 and not url.startswith('http') and ' ' not in url:
        is_torrent = True
        magnet_uri = f"magnet:?xt=urn:btih:{url}"
    elif 'elementum' in url:
        is_torrent = True
        magnet_uri = url

    if is_torrent:
        if magnet_uri.startswith('plugin://'):
            final_url = magnet_uri
        else:
            encoded_uri = urllib.parse.quote_plus(magnet_uri)
            media_type = item_info.get('media_type')
            tmdb_id = item_info.get('tmdb_id')
            
            final_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
            
            if tmdb_id:
                final_url += f"&tmdb={tmdb_id}"

            # Lógica para séries
            if media_type == 'tvshow':
                season = item_info.get('season')
                episode = item_info.get('episode')
                
                # ✅ CORREÇÃO: Garante que o clearlogo da série seja passado para o resolvedor
                if not item_info.get('clearlogo') and item_info.get('tvshow.clearlogo'):
                    item_info['clearlogo'] = item_info['tvshow.clearlogo']
                
                if season is not None and episode is not None:
                    final_url += f"&season={season}&episode={episode}"
                    xbmc.log(f"[Cinebox] Construind link Elementum (Seriale S/E): {final_url}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[Cinebox] Construind link Elementum (Seriale): {final_url}", xbmc.LOGINFO)
            else:
                xbmc.log(f"[Cinebox] Construind link Elementum (Filme): {final_url}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[Cinebox] Rezolvarea linkului direct: {final_url}", xbmc.LOGINFO)

    # --- 2. Cria o ListItem ---
    play_item = xbmcgui.ListItem(path=final_url)

    # --- 3. Metadados ---
    info_labels = {
        'title': item_info.get('episode_title', item_info.get('title', 'Playback')),
        'originaltitle': item_info.get('original_title'),
        'year': item_info.get('year'),
        'plot': item_info.get('plot', item_info.get('overview', '')),
        'season': item_info.get('season'),
        'episode': item_info.get('episode'),
        'tvshowtitle': item_info.get('title') if item_info.get('media_type') == 'tvshow' else '',
        'mediatype': item_info.get('media_type', 'video'),
        'imdbnumber': item_info.get('imdb_id'),
        'duration': int(item_info.get('runtime', 0)) * 60,
        'genre': " / ".join(item_info.get('genres', [])),
    }
    play_item.setInfo('video', info_labels)
    
    play_item.setArt({
        'thumb': item_info.get('episode_poster') or item_info.get('poster') or '',
        'poster': item_info.get('poster') or '',
        'fanart': item_info.get('backdrop') or '',
    })

    # --- 4. Lógica de Headers para AnimeZey ---
    animezey_domains = ['animezey23112022.workers.dev', 'animezey16082023.workers.dev', '1.animezeydl.workers.dev']
    if not is_torrent and any(domain in final_url.lower() for domain in animezey_domains):
        
        play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
        play_item.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')

        referer_header = final_url
        headers_str = (
            f"Referer={referer_header}\r\n"
            f"User-Agent={USER_AGENT}\r\n"
        )
        play_item.setProperty('inputstream.ffmpegdirect.headers', headers_str)

    # --- 5. Resolve a URL ---
    play_item.setProperty('IsPlayable', 'true')
    play_item.setContentLookup(False)

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)
    
    # --- ✅ 6. MONITORAMENTO ELEMENTUM E SCROBBLE ---
    def monitor_playback_and_elementum():
        player = xbmc.Player()
        is_elementum = "plugin.video.elementum" in final_url
        start_time = time.time()
        
        # Monitora início do playback e fecha diálogos do Elementum
        while not player.isPlaying():
            if xbmc.Monitor().abortRequested():
                xbmc.log("[Cinebox] Abort detectat in navigation.py, oprire Elementum", xbmc.LOGINFO)
                if is_elementum:
                    try:
                        subprocess.run(['pkill', '-f', 'elementum'], timeout=2)
                    except:
                        pass
                    try:
                        subprocess.run(['killall', 'elementum'], timeout=2)
                    except:
                        pass
                return
            
            if time.time() - start_time > 120: # Timeout 2 min
                break
                
            if is_elementum:
                # Não fecha os diálogos aqui se o CineboxResolverWindow estiver ativo
                # O fechamento será tratado pela janela de resolução customizada
                xbmc.executebuiltin('Dialog.Close(10101, true)')
                xbmc.executebuiltin('Dialog.Close(10151, true)')
            
            xbmc.sleep(500)
            
        # Se o scrobble estiver ativo, continua o monitoramento
        if ADDON.getSettingBool('trakt_auto_scrobble'):
            _delayed_trakt_scrobble(item_info)

    threading.Thread(target=monitor_playback_and_elementum, daemon=True).start()


def _delayed_trakt_scrobble(item_info):
    """
    Monitora playback e scrobla quando terminar (compatível com Elementum)
    """
    import time
    
    xbmc.log("[Trakt Scrobble] Se inițiază monitorizarea...", xbmc.LOGINFO)
    
    # Aguarda player iniciar (máx 30s)
    player_started = False
    for i in range(30):
        if xbmc.Player().isPlaying():
            player_started = True
            xbmc.log(f"[Trakt Scrobble] Player detectat după {i}s", xbmc.LOGINFO)
            break
        time.sleep(1)
    
    if not player_started:
        xbmc.log("[Trakt Scrobble] Timeout: player nu a început în 30s", xbmc.LOGWARNING)
        return
    
    player = xbmc.Player()
    media_type = item_info.get('media_type')
    tmdb_id = item_info.get('tmdb_id')
    
    if not tmdb_id:
        xbmc.log("[Trakt Scrobble] Fără ID TMDB, se anulează", xbmc.LOGWARNING)
        return
    
    # Aguarda término do playback
    start_time = time.time()
    total_time = 0
    last_position = 0
    
    try:
        # Monitora enquanto está tocando
        while player.isPlaying():
            try:
                total_time = player.getTotalTime()
                last_position = player.getTime()
            except:
                pass
            time.sleep(5)
        
        # Calcula progresso real
        elapsed = time.time() - start_time
        
        if total_time > 0:
            # Usa a maior posição alcançada
            progress = (max(last_position, elapsed) / total_time) * 100
        else:
            # Fallback: se assistiu mais de 5 minutos, considera válido
            progress = 100 if elapsed > 300 else 0
        
        xbmc.log(f"[Trakt Scrobble] Progresso: {progress:.1f}% (tempo: {elapsed:.0f}s, duração: {total_time:.0f}s)", xbmc.LOGINFO)
        
        # Só marca se assistiu pelo menos 80% OU mais de 15 minutos
        if progress < 80 and elapsed < 900:
            xbmc.log(f"[Trakt Scrobble] Progres insuficient ({progress:.0f}%), nu marchează", xbmc.LOGINFO)
            return
        
        # Marca como assistido no Trakt
        from resources.lib.trakt_sync import trakt_request
        
        if media_type == 'movie':
            payload = {
                'movies': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'watched_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                }]
            }
            desc = item_info.get('title', 'Filme')
            
        elif media_type == 'tvshow':
            season = item_info.get('season')
            episode = item_info.get('episode')
            
            if not season or not episode:
                xbmc.log("[Trakt Scrobble] Serial S/E, abandoneaza", xbmc.LOGWARNING)
                return
            
            payload = {
                'shows': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'seasons': [{
                        'number': int(season),
                        'episodes': [{
                            'number': int(episode),
                            'watched_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                        }]
                    }]
                }]
            }
            desc = f"{item_info.get('title', 'Série')} S{str(season).zfill(2)}E{str(episode).zfill(2)}"
        else:
            xbmc.log(f"[Trakt Scrobble] Tip necunoscut: {media_type}", xbmc.LOGWARNING)
            return
        
        # Envia para Trakt
        response = trakt_request('POST', '/sync/history', payload)
        
        if response:
            xbmc.log(f"[Trakt Scrobble] ✅ Marcat ca vizionat: {desc}", xbmc.LOGINFO)
            xbmcgui.Dialog().notification("Trakt", f"✅ {desc}", xbmcgui.NOTIFICATION_INFO, 2000)
        else:
            xbmc.log(f"[Trakt Scrobble] ❌ Eroare la programare: {desc}", xbmc.LOGERROR)
        
    except Exception as e:
        xbmc.log(f"[Trakt Scrobble] Eroare în timpul monitorizării: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


def view_debug_log():
    """Exibe o conteúdo do log de debug em um diálogo."""
    from .debug_logger import logger
    content = logger.get_log_content(1000)
    xbmcgui.Dialog().textviewer("Cinebox Debug Log", content)

def clear_debug_log():
    """Limpa o arquivo de log de debug."""
    from .debug_logger import logger
    if logger.clear_log():
        xbmcgui.Dialog().notification("Cinebox", "Jurnal curatat cu succes!")
    else:
        xbmcgui.Dialog().notification("Cinebox", "Eroare la curățarea jurnalului!", xbmcgui.NOTIFICATION_ERROR)

def export_debug_log():
    """Exporta o log de debug para uma pasta escolhida pelo usuário."""
    from .debug_logger import logger
    import xbmcvfs
    
    if not os.path.exists(logger.log_file):
        xbmcgui.Dialog().ok("Cinebox", "Niciun jurnal de exportat.")
        return

    export_path = xbmcgui.Dialog().browse(3, 'Alegeți folderul pentru a exporta jurnalul', 'files')
    if export_path:
        dest = os.path.join(export_path, 'cinebox_debug_export.log')
        if xbmcvfs.copy(logger.log_file, dest):
            xbmcgui.Dialog().ok("Cinebox", f"Log exportat cu succes în:\n{dest}")
        else:
            xbmcgui.Dialog().ok("Cinebox", "Eroare la exportarea jurnalului.")
