# -*- coding: utf-8 -*-
import sys
import os
import urllib.parse
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmc
import xbmcvfs
addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
lib_path = os.path.join(addon_path, 'resources', 'lib').replace('\\', '/')
providers_path = os.path.join(lib_path, 'surse').replace('\\', '/')
if lib_path not in sys.path: sys.path.insert(0, lib_path)
if providers_path not in sys.path: sys.path.insert(0, providers_path)
try:
    import movies
    import tvshows
    import subtitles
    import api_config
    import addon_logic 
    import cache_manager 
    from base import Stremio
except ImportError as e:
    xbmc.log(f"[CinemaCity] Eroare Import: {str(e)}", xbmc.LOGERROR)
def manage_sources():
    xbmc.executebuiltin("Dialog.Close(all, true)")
    while True:
        try:
            if not os.path.exists(providers_path): os.makedirs(providers_path)
            active_providers = [f[:-3] for f in os.listdir(providers_path) if f.endswith('.py') and not f.startswith('__')]
        except: active_providers = []
        if not active_providers:
            xbmcgui.Dialog().ok("[COLOR gold]Cinema City[/COLOR]", "[COLOR red]Nu exista surse.[/COLOR]"); break
        labels = [f"{p.upper()} - {'[COLOR green]ACTIV[/COLOR]' if addon.getSetting(f'enable_{p}') != 'false' else '[COLOR red]OPRIT[/COLOR]'}" for p in active_providers]
        sel = xbmcgui.Dialog().select("[COLOR gold]Gestionare Surse[/COLOR]", labels)
        if sel == -1: break
        p_name = active_providers[sel]
        addon.setSetting(f"enable_{p_name}", "false" if addon.getSetting(f"enable_{p_name}") != "false" else "true")
        xbmc.sleep(100)
def play_video(params, handle):
    tmdb_id, m_type = params.get('tmdb_id'), params.get('type')
    season, episode = params.get('season'), params.get('episode')
    title = params.get('title', 'Video')
    progress = xbmcgui.DialogProgress()
    progress.create("[COLOR gold]Cinema City[/COLOR]", "[COLOR lightblue]Cautare surse...[/COLOR]")
    imdb_id = None
    try:
        ext_url = f"{api_config.BASE_URL}/{'tv' if m_type=='tv' else 'movie'}/{tmdb_id}/external_ids?api_key={api_config.API_KEY}"
        imdb_id = movies.get_tmdb_json(ext_url).get('imdb_id')
    except: pass
    if not imdb_id:
        progress.close()
        xbmcgui.Dialog().notification("[COLOR red]Eroare[/COLOR]", "[COLOR white]ID IMDB negasit[/COLOR]", xbmcgui.NOTIFICATION_ERROR); return
    all_results, failed_sources = [], []
    try:
        active_providers = [f[:-3] for f in os.listdir(providers_path) if f.endswith('.py') and not f.startswith('__') and addon.getSetting(f"enable_{f[:-3]}") != "false"]
    except: active_providers = []
    total_initial = len(active_providers)
    pending_sources = [p.upper() for p in active_providers]
    for i, current_mod_name in enumerate(active_providers):
        if progress.iscanceled(): break
        current_display = current_mod_name.upper()
        if pending_sources: pending_sources.pop(0)
        remaining_text = "Scanare: [COLOR yellow]{}[/COLOR]\n[COLOR grey]Urmeaza: {}[/COLOR]\nErori: {}".format(
            current_display, ", ".join(pending_sources) if pending_sources else "[COLOR green]Finalizare...[/COLOR]", "[COLOR red]"+", ".join(failed_sources)+"[/COLOR]" if failed_sources else "0"
        )
        progress.update(int((i / total_initial) * 100), remaining_text)
        try:
            mod = __import__(f"surse.{current_mod_name}", fromlist=['sources'])
            found = mod.sources().get_sources(imdb_id, m_type, season, episode)
            if found: all_results.extend(found)
            else: failed_sources.append(current_display)
        except: failed_sources.append(current_display)
    subtitles.setup_subs_folder()
    found_subs = subtitles.search_subtitles(imdb_id, season, episode)
    downloaded_subs = []
    if found_subs:
        for s in found_subs:
            path = subtitles.download_subtitle(s, subtitles.subs_path)
            if path: downloaded_subs.append(path)
    progress.close()
    if not all_results:
        xbmcgui.Dialog().ok("[COLOR gold]Cinema City[/COLOR]", "[COLOR red]Nu s-au gasit surse active.[/COLOR]"); return
    all_results.sort(key=lambda x: (x.get('res_rank', 0), x.get('size_bytes', 0)), reverse=True)
    
    line1 = f"[COLOR deepskyblue]{title}[/COLOR]"
    if m_type == 'tv': line1 += f" [COLOR steelblue]- S{season}E{episode}[/COLOR]"    
    line2 = f"[COLOR lightblue]Surse active găsite:[/COLOR] [COLOR white]{len(all_results)}[/COLOR]"    
    
    sel = xbmcgui.Dialog().select(f"{line1}\n{line2}", [f"{s['label_top']}\n{s['label_bottom']}" for s in all_results])
    if sel == -1: return
    list_item = Stremio.get_listitem(all_results[sel])
    list_item.setInfo('video', {'title': title, 'imdbnumber': imdb_id, 'season': int(season or 0), 'episode': int(episode or 0)})
    xbmcplugin.setResolvedUrl(handle, True, list_item)
    if downloaded_subs:
        monitor, player = xbmc.Monitor(), xbmc.Player()
        for _ in range(60):
            if monitor.abortRequested() or player.isPlaying(): break
            xbmc.sleep(1000)
        if player.isPlaying():
            xbmc.sleep(2000)
            xbmcgui.Dialog().notification("[COLOR gold]Subtitrari[/COLOR]", f"[COLOR green]S-au incarcat {len(downloaded_subs)} subtitrari[/COLOR]", xbmcgui.NOTIFICATION_INFO, 3000)
            for sub in downloaded_subs: player.setSubtitles(sub)
def main():
    try:
        base_url, handle = sys.argv[0], int(sys.argv[1])
        params = dict(urllib.parse.parse_qsl(sys.argv[2].lstrip('?')))
    except: return
    
    act = params.get('action')
    
    if not act:
        menu = [
            ('[COLOR white]Filme[/COLOR]', 'movies_pop'), 
            ('[COLOR white]Seriale[/COLOR]', 'tvshows_pop'), 
            ('[COLOR white]Cautare[/COLOR]', 'search_all'),
            ('[COLOR white][B]Server 4K[/B][/COLOR]', 'server_menu'),            
            ('[COLOR orange]Gestionare Surse[/COLOR]', 'manage')
        ]
        for l, a in menu: xbmcplugin.addDirectoryItem(handle, f"{base_url}?action={a}", xbmcgui.ListItem(label=l), True)
    
    elif act == 'search_all':
        options = ["[COLOR white]Caută în FILME[/COLOR]", "[COLOR white]Caută în SERIALE[/COLOR]"]
        sel = xbmcgui.Dialog().select("[COLOR gold]Alege categoria de căutare:[/COLOR]", options)
        if sel != -1:
            q = xbmcgui.Dialog().input('Introduceți textul...', type=xbmcgui.INPUT_ALPHANUM)
            if q:
                if sel == 0: movies.list_movies(handle, base_url, '1', query=q)
                else: tvshows.list_tvshows(handle, base_url, '1', query=q)

    elif act == 'movies':
        movies.list_movies(handle, base_url, params.get('page', '1'), params.get('query'))
    
    elif act == 'tvshows':
        tvshows.list_tvshows(handle, base_url, params.get('page', '1'), params.get('query'))

    elif act == 'server_menu':
        cats = [
            ('Filme 4K', 'list_f4k'), ('Seriale 4K', 'list_s4k'), 
            ('Filme', 'list_fs'), ('Seriale', 'list_ss'),
            ('[COLOR orange]Caută FILME pe Server[/COLOR]', 'search_movies_server'),
            ('[COLOR orange]Caută SERIALE pe Server[/COLOR]', 'search_tv_server'),
            ('[COLOR cyan]Recente pe Server[/COLOR]', 'news_menu'),            
            ('[COLOR yellow]Actualizare Server[/COLOR]', 'update_cache_manual')
        ]
        for l, a in cats: 
            xbmcplugin.addDirectoryItem(handle, f"{base_url}?action={a}&page=1", xbmcgui.ListItem(label=l), True)
            
    elif act == 'news_menu':
        news_cats = [
            ('Noutăți Filme 4K', 'list_news_f4k'),
            ('Noutăți Seriale 4K', 'list_news_s4k'),
            ('Noutăți Filme', 'list_news_fs'),
            ('Noutăți Seriale', 'list_news_ss')
        ]
        for l, a in news_cats:
            u = f"{base_url}?action={a}&page=1"
            xbmcplugin.addDirectoryItem(handle, u, xbmcgui.ListItem(label=l), True)
        xbmcplugin.endOfDirectory(handle)

    elif act == 'tvshows_pop': tvshows.list_tvshows(handle, base_url, params.get('page', '1'))
    elif act == 'list_seasons': tvshows.list_seasons(handle, base_url, params.get('tv_id'), params.get('title'))
    elif act == 'list_episodes': tvshows.list_episodes(handle, base_url, params.get('tv_id'), params.get('season_num'), params.get('title'))
    elif act == 'movies_pop': movies.list_movies(handle, base_url, params.get('page', '1'))
    elif act == 'manage': manage_sources()
    elif act == 'play': play_video(params, handle)
    elif act == 'list_f4k': addon_logic.list_f4k(handle, base_url, params)
    elif act == 'list_s4k': addon_logic.list_s4k(handle, base_url, params)
    elif act == 'list_fs': addon_logic.list_fs(handle, base_url, params)
    elif act == 'list_ss': addon_logic.list_ss(handle, base_url, params)
    elif act == 'list_news_f4k': 
        addon_logic.process_server(handle, base_url, params, "http://69.154.203.11:8008/4kmovies/", "movie", "f4k_struct")       
    elif act == 'list_news_s4k': 
        addon_logic.process_server(handle, base_url, params, "http://69.154.203.11:8008/4ktvshows/", "tv", "s4k_struct")        
    elif act == 'list_news_fs':  
        addon_logic.process_server(handle, base_url, params, "http://69.154.203.11:8008/movies/", "movie", "fs_struct")       
    elif act == 'list_news_ss':  
        addon_logic.process_server(handle, base_url, params, "http://69.154.203.11:8008/tvshows/", "tv", "ss_struct")       
    elif act == 'search_movies_server': addon_logic.search_hybrid(handle, base_url, params, 'movie')
    elif act == 'search_tv_server': addon_logic.search_hybrid(handle, base_url, params, 'tv')
    elif act == 'list_movie_files': addon_logic.list_movie_files(handle, base_url, params)
    elif act == 'list_server_seasons': addon_logic.list_server_seasons(handle, base_url, params)
    elif act == 'list_server_episodes': addon_logic.list_server_episodes(handle, base_url, params)
    elif act == 'list_episode_files': addon_logic.list_episode_files(handle, base_url, params)
    elif act == 'play_direct': addon_logic.play_direct(handle, params)
    elif act == 'update_cache_manual': cache_manager.update_all_databases()
    
    xbmcplugin.endOfDirectory(handle)

if __name__ == '__main__':
    main()
