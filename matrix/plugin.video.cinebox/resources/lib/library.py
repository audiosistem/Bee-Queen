# -*- coding: utf-8 -*-
"""
Integração com Biblioteca do Kodi - VERSÃO CORRIGIDA ANDROID/TV
Gerenciamento completo de .strm e .nfo com caminhos acessíveis
"""

import os
import json
import shutil
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()

# === CONFIGURAÇÕES - CAMINHOS ACESSÍVEIS ===
def get_library_paths():
    """Retorna os caminhos das bibliotecas (compatível com Android/TV)"""
    
    # Usa caminhos ACESSÍVEIS pelo Kodi (configurações removidas)
    addon_profile = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    movies_path = os.path.join(addon_profile, 'library', 'movies')
    tvshows_path = os.path.join(addon_profile, 'library', 'tvshows')
    
    # Garante que os caminhos estão traduzidos
    movies_path = xbmcvfs.translatePath(movies_path)
    tvshows_path = xbmcvfs.translatePath(tvshows_path)
    
    return movies_path, tvshows_path

def ensure_library_folders():
    """Cria pastas da biblioteca se não existirem"""
    movies_path, tvshows_path = get_library_paths()
    
    for path in [movies_path, tvshows_path]:
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)
            xbmc.log(f"[Library] Pasta criada: {path}", xbmc.LOGINFO)
    
    return movies_path, tvshows_path

def check_library_access():
    """Verifica se o Kodi consegue acessar as pastas da biblioteca"""
    movies_path, tvshows_path = get_library_paths()
    
    test_file_movie = os.path.join(movies_path, '.test')
    test_file_tv = os.path.join(tvshows_path, '.test')
    
    try:
        # Testa escrita em filmes
        with open(test_file_movie, 'w') as f:
            f.write('test')
        xbmcvfs.delete(test_file_movie)
        
        # Testa escrita em séries
        with open(test_file_tv, 'w') as f:
            f.write('test')
        xbmcvfs.delete(test_file_tv)
        
        return True
    except Exception as e:
        xbmc.log(f"[Library] ERRO DE ACESSO: {e}", xbmc.LOGERROR)
        return False

def setup_library_sources():
    """Adiciona as pastas da biblioteca como fontes no Kodi"""
    movies_path, tvshows_path = get_library_paths()
    
    # Verifica se precisa configurar
    sources_xml = xbmcvfs.translatePath('special://userdata/sources.xml')
    
    # Cria sources.xml se não existir
    if not xbmcvfs.exists(sources_xml):
        sources_content = '''<sources>
    <programs>
        <default pathversion="1"></default>
    </programs>
    <video>
        <default pathversion="1"></default>
    </video>
    <music>
        <default pathversion="1"></default>
    </music>
    <pictures>
        <default pathversion="1"></default>
    </pictures>
    <files>
        <default pathversion="1"></default>
    </files>
    <games>
        <default pathversion="1"></default>
    </games>
</sources>'''
        try:
            with open(sources_xml, 'w', encoding='utf-8') as f:
                f.write(sources_content)
        except:
            pass
    
    # Mensagem para o usuário
    dialog = xbmcgui.Dialog()
    dialog.ok(
        "Configurar Biblioteca",
        f"[B]IMPORTANTE:[/B] Adicione estas pastas no Kodi:",
        f"[B]Filmes:[/B] {movies_path}",
        f"[B]Séries:[/B] {tvshows_path}"
    )
    
    return True

def sanitize_filename(name):
    """Remove caracteres inválidos"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.strip()

# === OPERAÇÕES COM KODI (JSON-RPC) ===
def get_all_library_movies():
    """Busca TODOS os filmes da biblioteca do Kodi via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetMovies",
        "params": {"properties": ["file"]},
        "id": 1
    }
    result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
    return result.get('result', {}).get('movies', [])

def get_all_library_tvshows():
    """Busca TODAS as séries da biblioteca do Kodi via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetTVShows",
        "params": {"properties": ["file"]},
        "id": 1
    }
    result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
    return result.get('result', {}).get('tvshows', [])

def remove_movie_from_kodi(movieid):
    """Remove filme da biblioteca do Kodi via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.RemoveMovie",
        "params": {"movieid": movieid},
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(query))

def remove_tvshow_from_kodi(tvshowid):
    """Remove série da biblioteca do Kodi via JSON-RPC"""
    query = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.RemoveTVShow",
        "params": {"tvshowid": tvshowid},
        "id": 1
    }
    xbmc.executeJSONRPC(json.dumps(query))

# === CRIAÇÃO DE ARQUIVOS ===
def create_strm_file(filepath, plugin_url):
    """Cria arquivo .strm"""
    try:
        directory = os.path.dirname(filepath)
        if not xbmcvfs.exists(directory):
            xbmcvfs.mkdirs(directory)
        
        # Usa caminho traduzido
        translated_path = xbmcvfs.translatePath(filepath)
        
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(plugin_url)
        
        # Verifica se foi criado
        if not xbmcvfs.exists(filepath):
            xbmc.log(f"[Library] AVISO: .strm não foi criado: {filepath}", xbmc.LOGWARNING)
            return False
        
        return True
    except Exception as e:
        xbmc.log(f"[Library] Erro ao criar .strm: {e}", xbmc.LOGERROR)
        return False

def create_movie_nfo(filepath, movie_data):
    """Cria .nfo para filme"""
    try:
        nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>{movie_data.get('title', '')}</title>
    <originaltitle>{movie_data.get('original_title', '')}</originaltitle>
    <rating>{movie_data.get('rating', 0.0)}</rating>
    <year>{movie_data.get('year', '')}</year>
    <plot>{movie_data.get('synopsis', '')}</plot>
    <runtime>{movie_data.get('runtime', 0)}</runtime>
    <thumb>{movie_data.get('poster', '')}</thumb>
    <fanart>{movie_data.get('backdrop', '')}</fanart>
    <uniqueid type="tmdb" default="true">{movie_data.get('tmdb_id', '')}</uniqueid>
    <uniqueid type="imdb">{movie_data.get('imdb_id', '')}</uniqueid>
"""
        genres = movie_data.get('genres', [])
        if isinstance(genres, list):
            for genre in genres:
                nfo_content += f"    <genre>{genre}</genre>\n"
        nfo_content += "</movie>"
        
        translated_path = xbmcvfs.translatePath(filepath)
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        return True
    except Exception as e:
        xbmc.log(f"[Library] Erro ao criar .nfo: {e}", xbmc.LOGERROR)
        return False

def create_tvshow_nfo(filepath, show_data):
    """Cria .nfo para série"""
    try:
        nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
    <title>{show_data.get('title', '')}</title>
    <originaltitle>{show_data.get('original_title', '')}</originaltitle>
    <rating>{show_data.get('rating', 0.0)}</rating>
    <year>{show_data.get('year', '')}</year>
    <plot>{show_data.get('synopsis', '')}</plot>
    <thumb>{show_data.get('poster', '')}</thumb>
    <fanart>{show_data.get('backdrop', '')}</fanart>
    <uniqueid type="tmdb" default="true">{show_data.get('tmdb_id', '')}</uniqueid>
    <uniqueid type="imdb">{show_data.get('imdb_id', '')}</uniqueid>
"""
        genres = show_data.get('genres', [])
        if isinstance(genres, list):
            for genre in genres:
                nfo_content += f"    <genre>{genre}</genre>\n"
        nfo_content += "</tvshow>"
        
        translated_path = xbmcvfs.translatePath(filepath)
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        return True
    except Exception as e:
        xbmc.log(f"[Library] Erro ao criar tvshow.nfo: {e}", xbmc.LOGERROR)
        return False

def create_episode_nfo(filepath, episode_data, show_data):
    """Cria .nfo para episódio"""
    try:
        nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
    <title>{episode_data.get('name', '')}</title>
    <showtitle>{show_data.get('title', '')}</showtitle>
    <season>{episode_data.get('season_number', 1)}</season>
    <episode>{episode_data.get('episode_number', 1)}</episode>
    <plot>{episode_data.get('overview', '')}</plot>
    <aired>{episode_data.get('air_date', '')}</aired>
    <rating>{episode_data.get('vote_average', 0.0)}</rating>
    <thumb>{episode_data.get('still_path', '')}</thumb>
    <uniqueid type="tmdb" default="true">{show_data.get('tmdb_id', '')}</uniqueid>
</episodedetails>"""
        
        translated_path = xbmcvfs.translatePath(filepath)
        with open(translated_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)
        return True
    except Exception as e:
        xbmc.log(f"[Library] Erro ao criar episode.nfo: {e}", xbmc.LOGERROR)
        return False

import urllib.parse

import urllib.parse
import xbmc, xbmcgui, xbmcvfs, os

# === HELPERS DE VERIFICAÇÃO ===

def is_in_library(movie_data, media_type):
    """Verifica se o item já existe na biblioteca física (Rápido)"""
    try:
        movies_path, tvshows_path = get_library_paths()
        title = sanitize_filename(movie_data.get('title', 'Unknown'))
        
        if media_type == 'movie':
            year = movie_data.get('year', '')
            folder_name = f"{title} ({year})" if year else title
            check_path = os.path.join(movies_path, folder_name)
        else:
            check_path = os.path.join(tvshows_path, title)
            
        return xbmcvfs.exists(check_path)
    except:
        return False

# === ADICIONAR À BIBLIOTECA ===

def add_movie_to_library(movie_data, show_notification=True):
    """Adiciona filme à biblioteca incluindo artes na URL do plugin"""
    try:
        movies_path, _ = ensure_library_folders()
        
        title = sanitize_filename(movie_data.get('title', 'Unknown'))
        year = movie_data.get('year', '')
        folder_name = f"{title} ({year})" if year else title
        movie_folder = os.path.join(movies_path, folder_name)
        
        if not xbmcvfs.exists(movie_folder):
            xbmcvfs.mkdirs(movie_folder)

        # Extração das artes
        poster = movie_data.get('poster', '')
        backdrop = movie_data.get('backdrop', '') or movie_data.get('fanart', '')
        clearlogo = movie_data.get('clearlogo', '')

        plugin_url = (
            f"plugin://plugin.video.cinebox/"
            f"?action=find_sources"
            f"&media_type=movie"
            f"&tmdb_id={movie_data.get('tmdb_id')}"
            f"&imdb_id={movie_data.get('imdb_id', '')}"
            f"&title={urllib.parse.quote_plus(str(movie_data.get('title', '')))}"
            f"&year={year}"
            f"&poster={urllib.parse.quote_plus(str(poster))}"
            f"&backdrop={urllib.parse.quote_plus(str(backdrop))}"
            f"&clearlogo={urllib.parse.quote_plus(str(clearlogo))}"
        )
        
        strm_file = os.path.join(movie_folder, f"{folder_name}.strm")
        nfo_file = os.path.join(movie_folder, "movie.nfo")
        
        if not create_strm_file(strm_file, plugin_url): return False
        if not create_movie_nfo(nfo_file, movie_data): return False
        
        if show_notification:
            xbmcgui.Dialog().notification("Biblioteca", f"{title} adicionado!", xbmcgui.NOTIFICATION_INFO, 3000)
        
        xbmc.log(f"[Library] Filme adicionado: {title}", xbmc.LOGINFO)
        return True
        
    except Exception as e:
        xbmc.log(f"[Library] Erro ao adicionar filme: {e}", xbmc.LOGERROR)
        return False

def add_tvshow_to_library(show_data, show_notification=True):
    """Adiciona série à biblioteca"""
    try:
        _, tvshows_path = ensure_library_folders()
        
        raw_title = show_data.get('title', 'Unknown')
        title = sanitize_filename(raw_title)
        show_folder = os.path.join(tvshows_path, title)
        
        if not xbmcvfs.exists(show_folder):
            xbmcvfs.mkdirs(show_folder)
        
        if show_notification:
            xbmcgui.Dialog().notification("Biblioteca", f"Sincronizando: {raw_title}", xbmcgui.NOTIFICATION_INFO, 2000)

        tvshow_nfo = os.path.join(show_folder, "tvshow.nfo")
        if not create_tvshow_nfo(tvshow_nfo, show_data):
            return False
        
        from resources.lib.db import db
        from resources.lib.tmdb_api import get_tvshow_seasons, get_season_episodes
        
        tmdb_id = show_data.get('tmdb_id')
        seasons = db.get_cached_seasons(tmdb_id) or get_tvshow_seasons(tmdb_id) or []
        
        episodes_added = 0
        
        # Otimização: Encoding das artes uma única vez fora do loop
        poster = urllib.parse.quote_plus(str(show_data.get('poster', '')))
        backdrop = urllib.parse.quote_plus(str(show_data.get('backdrop', '') or show_data.get('fanart', '')))
        clearlogo = urllib.parse.quote_plus(str(show_data.get('clearlogo', '')))
        encoded_title = urllib.parse.quote_plus(str(raw_title))

        for season in seasons:
            season_number = season.get('season_number', 0)
            if season_number == 0: continue
            
            season_folder = os.path.join(show_folder, f"Season {str(season_number).zfill(2)}")
            if not xbmcvfs.exists(season_folder):
                xbmcvfs.mkdirs(season_folder)
            
            episodes = db.get_cached_episodes(tmdb_id, season_number) or get_season_episodes(tmdb_id, season_number) or []
            
            for episode in episodes:
                ep_number = episode.get('episode_number', 0)
                ep_name = f"S{str(season_number).zfill(2)}E{str(ep_number).zfill(2)}"
                
                plugin_url = (
                    f"plugin://plugin.video.cinebox/?action=find_sources&media_type=tvshow"
                    f"&tmdb_id={tmdb_id}&imdb_id={show_data.get('imdb_id', '')}&title={encoded_title}"
                    f"&poster={poster}&backdrop={backdrop}&clearlogo={clearlogo}"
                    f"&season={season_number}&episode={ep_number}"
                )
                
                strm_file = os.path.join(season_folder, f"{ep_name}.strm")
                nfo_file = os.path.join(season_folder, f"{ep_name}.nfo")
                
                if create_strm_file(strm_file, plugin_url):
                    create_episode_nfo(nfo_file, episode, show_data)
                    episodes_added += 1
        
        if show_notification:
            xbmcgui.Dialog().notification("Biblioteca", f"{raw_title} finalizada!", xbmcgui.NOTIFICATION_INFO, 3000)

        xbmc.log(f"[Library] Série adicionada: {title} ({episodes_added} episódios)", xbmc.LOGINFO)
        return True
        
    except Exception as e:
        xbmc.log(f"[Library] Erro ao adicionar série: {e}", xbmc.LOGERROR)
        return False

# === SINCRONIZAR BIBLIOTECA (USADO PELO SERVICE.PY) ===    
    
def sync_library_silently():
    """Verifica o banco local e garante que tudo está na biblioteca física sem alertas"""
    from resources.lib.db import db
    
    # 1. Sincronizar Filmes
    all_movies = db.get_all_movie_ids_set()
    for tmdb_id in all_movies:
        movie_data = db.get_movie_by_id(tmdb_id)
        if movie_data and not is_in_library(movie_data, 'movie'):
            add_movie_to_library(movie_data, show_notification=False)

    # 2. Sincronizar Séries
    all_series = db.get_all_tvshow_ids_set()
    for tmdb_id in all_series:
        show_data = db.get_tvshow_by_id(tmdb_id)
        if show_data and not is_in_library(show_data, 'tvshow'):
            add_tvshow_to_library(show_data, show_notification=False)
    

# === LIMPAR BIBLIOTECA (REFATORADO) ===
def clear_library():
    """Remove TODOS os itens da biblioteca (método COMPLETO corrigido)"""
    if not xbmcgui.Dialog().yesno(
        "Limpar Biblioteca",
        "ATENÇÃO: Isso vai DELETAR TUDO da biblioteca!",
        "Tem certeza?"
    ):
        return False
    
    progress = xbmcgui.DialogProgressBG()
    progress.create("Limpando Biblioteca", "Iniciando...")
    
    try:
        # === PASSO 0: Parar scanners ===
        progress.update(5, message="Parando scanners...")
        xbmc.executebuiltin('CancelLibraryScan')
        xbmc.sleep(1000)
        
        # === PASSO 1: Remove da biblioteca do Kodi (JSON-RPC completo) ===
        progress.update(10, message="Removendo filmes do Kodi...")
        
        # Remove TODOS os filmes (não apenas do Cinebox)
        movies = get_all_library_movies()
        for idx, movie in enumerate(movies):
            progress.update(10 + int((idx/len(movies))*20) if movies else 10, 
                          message=f"Removendo filme {idx+1}/{len(movies)}...")
            remove_movie_from_kodi(movie['movieid'])
            xbmc.sleep(50)
        
        progress.update(30, message="Removendo séries do Kodi...")
        
        # Remove TODAS as séries
        tvshows = get_all_library_tvshows()
        for idx, tvshow in enumerate(tvshows):
            progress.update(30 + int((idx/len(tvshows))*20) if tvshows else 30,
                          message=f"Removendo série {idx+1}/{len(tvshows)}...")
            remove_tvshow_from_kodi(tvshow['tvshowid'])
            xbmc.sleep(100)  # Mais tempo para séries
        
        # === PASSO 2: Limpa database do Kodi ===
        progress.update(50, message="Limpando database...")
        
        # Comando para limpar database completamente
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "VideoLibrary.Clean",
            "params": {"showdialogs": False},
            "id": 1
        }))
        xbmc.sleep(2000)
        
        # === PASSO 3: Deleta arquivos físicos COMPLETAMENTE ===
        progress.update(60, message="Deletando arquivos...")
        
        movies_path, tvshows_path = get_library_paths()
        
        # Função robusta de remoção
        def force_delete_folder(path):
            try:
                if xbmcvfs.exists(path):
                    # Tenta deletar via shutil primeiro
                    shutil.rmtree(xbmcvfs.translatePath(path), ignore_errors=True)
                    xbmc.sleep(500)
                    
                    # Tenta deletar arquivo por arquivo
                    dirs, files = xbmcvfs.listdir(path)
                    for file in files:
                        try:
                            xbmcvfs.delete(os.path.join(path, file))
                        except:
                            pass
                    
                    # Tenta deletar novamente
                    if xbmcvfs.exists(path):
                        xbmcvfs.rmdir(path, force=True)
            except:
                pass
        
        force_delete_folder(movies_path)
        force_delete_folder(tvshows_path)
        
        # Recria pastas vazias
        xbmcvfs.mkdirs(movies_path)
        xbmcvfs.mkdirs(tvshows_path)
        
        # === PASSO 4: Limpeza AGGRESSIVA de cache ===
        progress.update(75, message="Limpando caches profundos...")
        
        # Limpa vários tipos de cache
        cache_paths = [
            'special://temp/archive_cache/',
            'special://temp/library/',
            'special://userdata/Thumbnails/',
            'special://userdata/Database/Textures*.db'
        ]
        
        for cache_path in cache_paths:
            try:
                xbmc.executebuiltin(f'CleanLibrary({cache_path}, true)')
            except:
                pass
        
        # Executa múltiplas limpezas
        for i in range(5):
            xbmc.executebuiltin('CleanLibrary(video)')
            xbmc.sleep(500)
        
        # Limpeza via JSON-RPC
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "VideoLibrary.Clean",
            "params": {"content": "video", "showdialogs": False},
            "id": 1
        }))
        
        # === PASSO 5: Remove fontes do sources.xml ===
        progress.update(85, message="Removendo fontes...")
        
        try:
            sources_xml = xbmcvfs.translatePath('special://userdata/sources.xml')
            if xbmcvfs.exists(sources_xml):
                with open(sources_xml, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Remove referências às pastas
                import re
                content = re.sub(r'<path.*?</path>', '', content, flags=re.DOTALL)
                
                with open(sources_xml, 'w', encoding='utf-8') as f:
                    f.write(content)
        except:
            pass
        
        # === PASSO 6: Atualizações finais ===
        progress.update(90, message="Forçando atualização...")
        
        # Atualiza biblioteca vazia
        xbmc.executebuiltin('UpdateLibrary(video)')
        xbmc.sleep(3000)
        
        # Limpa novamente
        xbmc.executebuiltin('CleanLibrary(video)')
        xbmc.sleep(1000)
        
        # Recarrega skin DUAS vezes
        xbmc.executebuiltin('ReloadSkin()')
        xbmc.sleep(1000)
        xbmc.executebuiltin('ReloadSkin()')
        
        progress.update(95, message="Reiniciando serviços...")
        
        # Reinicia serviços de vídeo
        xbmc.executebuiltin('RestartVideoLibrary')
        xbmc.sleep(2000)
        
        progress.update(100, message="Concluído!")
        xbmc.sleep(1000)
        progress.close()
        
        # Mensagem final com instruções
        xbmcgui.Dialog().ok(
            "Biblioteca Completamente Limpa",
            "✅ Todos os itens foram removidos!",
            "",
            "Se ainda aparecer algo:",
            "1. Reinicie o Kodi completamente",
            "2. Vá em Configurações > Media > Limpar biblioteca",
            "3. Execute 'Atualizar biblioteca' novamente"
        )
        
        # Sugere reinício
        if xbmcgui.Dialog().yesno("Reiniciar", "Recomendado: Reiniciar o Kodi agora?"):
            xbmc.executebuiltin('RestartApp')
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Library] Erro ao limpar: {e}", xbmc.LOGERROR)
        progress.close()
        xbmcgui.Dialog().ok(
            "Erro na Limpeza",
            f"Erro: {str(e)}",
            "Tente:",
            "1. Reinicie o Kodi",
            "2. Vá em Configurações > Media",
            "3. Execute 'Limpar biblioteca' manualmente"
        )
        return False

# === ADICIONAR TUDO (EM MASSA) ===
def add_all_movies_to_library(*args, **kwargs):
    """Adiciona todos os filmes"""
    from resources.lib.db import db
    
    # Verifica acesso primeiro
    if not check_library_access():
        if xbmcgui.Dialog().yesno(
            "Problema de Acesso",
            "Não consigo acessar as pastas da biblioteca.",
            "Deseja configurar as fontes agora?"
        ):
            setup_library_sources()
        return False
    
    all_movie_ids = db.get_all_movie_ids_set()
    if not all_movie_ids:
        xbmcgui.Dialog().ok("Biblioteca", "Nenhum filme encontrado.")
        return False
    
    total = len(all_movie_ids)
    if not xbmcgui.Dialog().yesno("Adicionar Todos", f"Adicionar {total} filmes?"):
        return False
    
    progress = xbmcgui.DialogProgressBG()
    progress.create("Cinebox", "Adicionando filmes...")
    
    added = 0
    for idx, tmdb_id in enumerate(all_movie_ids, 1):
        progress.update(int((idx / total) * 100), message=f"Filme {idx}/{total}")
        movie_data = db.get_movie_by_id(tmdb_id)
        if movie_data and add_movie_to_library(movie_data):
            added += 1
        if idx % 10 == 0:
            xbmc.sleep(100)
    
    progress.close()
    
    if xbmcgui.Dialog().yesno("Concluído", f"{added} filmes adicionados", "Atualizar biblioteca?"):
        xbmc.executebuiltin('UpdateLibrary(video)')
    
    return True

def add_all_tvshows_to_library(*args, **kwargs):
    """Adiciona todas as séries"""
    from resources.lib.db import db
    
    # Verifica acesso primeiro
    if not check_library_access():
        if xbmcgui.Dialog().yesno(
            "Problema de Acesso",
            "Não consigo acessar as pastas da biblioteca.",
            "Deseja configurar as fontes agora?"
        ):
            setup_library_sources()
        return False
    
    all_tvshow_ids = db.get_all_tvshow_ids_set()
    if not all_tvshow_ids:
        xbmcgui.Dialog().ok("Biblioteca", "Nenhuma série encontrada.")
        return False
    
    total = len(all_tvshow_ids)
    if not xbmcgui.Dialog().yesno("Adicionar Todas", f"Adicionar {total} séries?", "Pode demorar MUITO!"):
        return False
    
    progress = xbmcgui.DialogProgressBG()
    progress.create("Cinebox", "Adicionando séries...")
    
    added = 0
    for idx, tmdb_id in enumerate(all_tvshow_ids, 1):
        progress.update(int((idx / total) * 100), message=f"Série {idx}/{total}")
        show_data = db.get_tvshow_by_id(tmdb_id)
        if show_data and add_tvshow_to_library(show_data):
            added += 1
        if idx % 5 == 0:
            xbmc.sleep(200)
    
    progress.close()
    
    if xbmcgui.Dialog().yesno("Concluído", f"{added} séries adicionadas", "Atualizar biblioteca?"):
        xbmc.executebuiltin('UpdateLibrary(video)')
    
    return True

# === MENU ===
def show_library_menu(*args, **kwargs):
    """Menu de gerenciamento"""
    from resources.lib.db import db
    
    # Mostra caminhos para o usuário
    movies_path, tvshows_path = get_library_paths()
    
    total_movies = len(db.get_all_movie_ids_set())
    total_tvshows = len(db.get_all_tvshow_ids_set())
    
    options = [
        f"Adicionar Filmes ({total_movies})",
        f"Adicionar Séries ({total_tvshows})",
        "Adicionar Tudo",
        "Limpar Biblioteca",
        "Atualizar Kodi",
        "Ver Caminhos da Biblioteca",
        "Configurar Fontes",
        "Cancelar"
    ]
    
    choice = xbmcgui.Dialog().select("Biblioteca", options)
    
    if choice == 0:
        add_all_movies_to_library()
    elif choice == 1:
        add_all_tvshows_to_library()
    elif choice == 2:
        add_all_movies_to_library()
        add_all_tvshows_to_library()
    elif choice == 3:
        clear_library()
    elif choice == 4:
        xbmc.executebuiltin('UpdateLibrary(video)')
    elif choice == 5:
        xbmcgui.Dialog().textviewer(
            "Caminhos da Biblioteca",
            f"FILMES:\n{movies_path}\n\nSÉRIES:\n{tvshows_path}\n\n"
            f"Adicione estas pastas como fontes no Kodi:\n"
            f"Configurações > Media > Biblioteca > Videos > Adicionar fonte..."
        )
    elif choice == 6:
        setup_library_sources()


def update_kodi_library(media_type='video', *args, **kwargs):
    """Atualiza biblioteca do Kodi"""
    xbmc.executebuiltin('UpdateLibrary(video)')
    xbmc.sleep(2000)
    xbmc.executebuiltin('CleanLibrary(video)')

def get_library_stats():
    """Retorna estatísticas"""
    import glob
    movies_path, tvshows_path = get_library_paths()
    
    try:
        movies_count = len(glob.glob(os.path.join(xbmcvfs.translatePath(movies_path), '**', '*.strm'), recursive=True))
        tvshows_count = len([d for d in os.listdir(xbmcvfs.translatePath(tvshows_path)) if os.path.isdir(os.path.join(xbmcvfs.translatePath(tvshows_path), d))])
        episodes_count = len(glob.glob(os.path.join(xbmcvfs.translatePath(tvshows_path), '**', '*.strm'), recursive=True))
        
        return {'movies': movies_count, 'tvshows': tvshows_count, 'episodes': episodes_count}
    except:
        return {'movies': 0, 'tvshows': 0, 'episodes': 0}

def remove_from_library(tmdb_id=None, media_type=None, *args, **kwargs):

    """Remove item individual"""
    # Implementação simplificada - use clear_library() para remoção completa
    return False