# Em: resources/lib/scrapers/__init__.py
import xbmc

# --- Importa os módulos de scraper ---
from . import stremio
from . import animezey
from . import magneto_scrapers
from . import external_scrapers

# --- Função Roteadora Principal ---
def scrape_provider_sources(provider_name, provider_data, item_data, cancel_event=None):
    """
    Função "Roteadora" Principal.
    Verifica o nome do provedor e chama a função 'scrape' do módulo correto.
    """
    xbmc.log(f"[SCRAPER] Roteando para o provedor: {provider_name}", xbmc.LOGINFO)

    # Extrai season e episode AQUI, uma única vez
    season = item_data.get('season')
    episode = item_data.get('episode')
    
    # Lista de resultados
    sources = []

    try:
        
        
        if provider_name in ["Brazuca", "Torrentio", "SkyFlix", "TorrentsDB", "ICV", "WebStreamr"]:
            # Verifica se o provedor está habilitado nas configurações
            setting_id = f"provider.{provider_name.lower()}.enabled"
            from xbmcaddon import Addon
            addon = Addon('plugin.video.cinebox')
            
            # Se a configuração não existir (ex: CDFlix), o Kodi retorna False por padrão se não houver default no settings.xml
            # Mas aqui queremos garantir que se for um provedor novo que não está no settings.xml, ele seja tratado corretamente.
            try:
                if not addon.getSettingBool(setting_id):
                    # Verifica se a configuração realmente existe no settings.xml
                    # Se não existir, habilitamos por padrão para novos provedores
                    settings_content = ""
                    try:
                        import xbmcvfs
                        settings_path = xbmcvfs.translatePath('special://addon/plugin.video.cinebox/resources/settings.xml')
                        with open(settings_path, 'r') as f:
                            settings_content = f.read()
                    except: pass
                    
                    if setting_id in settings_content:
                        xbmc.log(f"[SCRAPER] Provedor {provider_name} desativado nas configurações.", xbmc.LOGINFO)
                        return []
            except:
                pass

            # Chama a função 'scrape' do módulo 'stremio.py'
            sources = stremio.scrape(
                provider_url=provider_data.get('url'),
                is_configurable=provider_data.get('configurable', False),
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode,
                cancel_event=cancel_event
            )
        
        elif provider_name == "AnimeZey":
            # Chama a função 'scrape' do módulo 'animezey.py'
            sources = animezey.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                cancel_event=cancel_event
            )
            
        elif provider_name in ["Comando.la", "ComandoTop"]:
            from . import comando
            # Chama a função 'scrape' do módulo 'comando.py'
            sources = comando.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode,
                cancel_event=cancel_event
            )  
            


        elif provider_name == "UIndex":
            from . import uindex
            sources = uindex.scrape(
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode,
                item_data=item_data,
                cancel_event=cancel_event
            )

        elif provider_name == "Perflix":
            from . import perflix
            sources = perflix.scrape(
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode,
                item_data=item_data,
                cancel_event=cancel_event
            )

        elif provider_name == "Nyaa":
            from . import nyaa
            sources = nyaa.scrape(
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode,
                item_data=item_data,
                cancel_event=cancel_event
            )

        elif provider_name == "StarckFilmes":
            from . import starckfilmes
            sources = starckfilmes.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )

        elif provider_name == "BaixarFilmes":
            from . import baixarfilmes
            sources = baixarfilmes.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode,
                cancel_event=cancel_event
            )

        elif provider_name == "Magneto":
            # Verifica qual scraper está habilitado nas configurações do Cinebox
            try:
                from resources.lib.config_manager import get_enabled_scraper
                enabled_scraper_id = get_enabled_scraper()
            except:
                enabled_scraper_id = ''
            
            # Se o usuário escolheu um scraper específico, usamos APENAS ele
            if enabled_scraper_id and enabled_scraper_id != 'script.module.magneto':
                xbmc.log(f"[SCRAPER] Usando scraper externo selecionado: {enabled_scraper_id}", xbmc.LOGINFO)
                return external_scrapers.scrape(
                    imdb_id=item_data.get('imdb_id'),
                    media_type=item_data.get('media_type'),
                    season=season,
                    episode=episode,
                    item_data=item_data,
                    cancel_event=cancel_event
                )
            
            # Se não houver seleção ou for o padrão, usa o Magneto
            xbmc.log(f"[SCRAPER] Usando Magneto como scraper padrão", xbmc.LOGINFO)
            sources = magneto_scrapers.scrape(
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode,
                item_data=item_data,
                cancel_event=cancel_event
            )

        else:
            xbmc.log(f"[SCRAPER] Provedor '{provider_name}' não reconhecido.", xbmc.LOGWARNING)
            return []
            
    except Exception as e:
        import traceback
        xbmc.log(f"[SCRAPER] Erro catastrófico ao chamar o scraper '{provider_name}': {e}", xbmc.LOGERROR)
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return []

    # Retorna as fontes encontradas
    return sources