# -*- coding: utf-8 -*-
import xbmc

def enriquecer_sinopse_filme(data, plot_original):
    if not plot_original: return ""
    info = []
    
    # Direção
    diretores = data.get('directors', [])
    if diretores:
        info.append("[COLOR yellow]Direcție:[/COLOR] %s" % ", ".join(diretores[:2]))
    
    # Elenco
    elenco = data.get('cast', [])
    if elenco:
        info.append("[COLOR yellow]Lista:[/COLOR] %s" % ", ".join(elenco[:3]))
    
    # Duração
    runtime = data.get('runtime', 0)
    if runtime > 0:
        info.append("[COLOR yellow]Durata:[/COLOR] %dh %02dmin" % (runtime // 60, runtime % 60))
    
    if info:
        return "%s\n\n[B]%s[/B]" % (plot_original, " | ".join(info))
    return plot_original

def enriquecer_sinopse_serie(data, plot_original):
    if not plot_original: return ""
    info = []
    
    # Criadores
    criadores = data.get('created_by', [])
    if criadores:
        info.append("[COLOR yellow]Creator:[/COLOR] %s" % ", ".join(criadores[:2]))
    
    # Elenco
    elenco = data.get('cast', [])
    if elenco:
        info.append("[COLOR yellow]Lista:[/COLOR] %s" % ", ".join(elenco[:3]))
    
    # Temporadas/Episódios
    seasons = data.get('number_of_seasons')
    episodes = data.get('number_of_episodes')
    if seasons:
        info.append("[COLOR yellow]%d Sezoane[/COLOR]" % seasons)
    
    # Status
    status = data.get('status')
    if status:
        status_map = {
            'Returning Series': 'În afișaj',
            'Ended': 'Finalizat',
            'Canceled': 'Anulat',
            'In Production': 'În productie'
        }
        info.append("[COLOR yellow]Status:[/COLOR] %s" % status_map.get(status, status))
        
    if info:
        return "%s\n\n[B]%s[/B]" % (plot_original, " | ".join(info))
    return plot_original

def enriquecer_sinopse_episodio(ep_data, plot_original):
    if not plot_original: plot_original = "Sinopsis indisponibil."
    info = []
    
    # Nota
    rating = ep_data.get('vote_average')
    if rating and rating > 0:
        info.append("[COLOR yellow]Nota:[/COLOR] %.1f/10" % rating)
    
    # Data (Formato Brasileiro DD/MM/AAAA)
    aired = ep_data.get('air_date')
    if aired and "-" in aired:
        try:
            parts = aired.split("-")
            aired_br = "%s/%s/%s" % (parts[2], parts[1], parts[0])
            info.append("[COLOR yellow]Lansare:[/COLOR] %s" % aired_br)
        except:
            info.append("[COLOR yellow]Lansare:[/COLOR] %s" % aired)
    elif aired:
        info.append("[COLOR yellow]Lansare:[/COLOR] %s" % aired)

    # Contagem de episódios (para temporadas)
    ep_count = ep_data.get('episode_count')
    if ep_count:
        info.append("[COLOR yellow]Episoade:[/COLOR] %d" % ep_count)

    # Duração (para episódios)
    runtime = ep_data.get('runtime')
    if runtime:
        info.append("[COLOR yellow]Durata:[/COLOR] %d min" % runtime)
        
    if info:
        return "%s\n\n[B]%s[/B]" % (plot_original, " | ".join(info))
    return plot_original
