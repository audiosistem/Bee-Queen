# In: resources/lib/scrapers/__init__.py
import xbmc

# --- Import scraper modules ---
from . import stremio
from . import animezey
from . import magneto_scrapers
from . import external_scrapers

# --- Main Router Function ---
def scrape_provider_sources(provider_name, provider_data, item_data, cancel_event=None):
    """Main "Router" function.
    Checks the provider name and calls the 'scrape' function of the correct module."""
    xbmc.log(f"[SCRAPER] Roteando para o provedor: {provider_name}", xbmc.LOGINFO)

    # Download season and episode HERE, once
    season = item_data.get('season')
    episode = item_data.get('episode')
    
    # List of results
    sources = []

    try:
        
        
        if provider_name in ["Brazuca", "Torrentio", "SkyFlix", "TorrentsDB", "ICV", "WebStreamr"]:
            # Checks if the provider is enabled in settings
            setting_id = f"provider.{provider_name.lower()}.enabled"
            from xbmcaddon import Addon
            addon = Addon('plugin.video.cinebox')
            
            # If the setting does not exist (e.g. CDFlix), Kodi returns False by default if there is no default in settings.xml
            # But here we want to ensure that if it is a new provider that is not in settings.xml, it is handled correctly.
            try:
                if not addon.getSettingBool(setting_id):
                    # Checks if the configuration actually exists in settings.xml
                    # If it doesn't exist, we enable it by default for new providers
                    settings_content = ""
                    try:
                        import xbmcvfs
                        settings_path = xbmcvfs.translatePath('special://addon/plugin.video.cinebox/resources/settings.xml')
                        with open(settings_path, 'r') as f:
                            settings_content = f.read()
                    except: pass
                    
                    if setting_id in settings_content:
                        xbmc.log(f"[SCRAPER] Provider {provider_name} disabled in the settings.", xbmc.LOGINFO)
                        return []
            except:
                pass

            # Calls the 'scrape' function from the 'stremio.py' module
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
            # Calls the 'scrape' function from the 'animezey.py' module
            sources = animezey.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                cancel_event=cancel_event
            )
            
        elif provider_name in ["Comando.la", "ComandoTop"]:
            from . import comando
            # Calls the 'scrape' function from the 'comando.py' module
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
            # Check which scraper is enabled in the Cinebox settings
            try:
                from resources.lib.config_manager import get_enabled_scraper
                enabled_scraper_id = get_enabled_scraper()
            except:
                enabled_scraper_id = ''
            
            # If the user chose a specific scraper, we ONLY use it
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
            
            # If there is no selection or it is the default, use Magneto
            xbmc.log(f"[SCRAPER] Using Magneto as default scraper", xbmc.LOGINFO)
            sources = magneto_scrapers.scrape(
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode,
                item_data=item_data,
                cancel_event=cancel_event
            )

        else:
            xbmc.log(f"[SCRAPER] Provedor '{provider_name}'unrecognized.", xbmc.LOGWARNING)
            return []
            
    except Exception as e:
        import traceback
        xbmc.log(f"[SCRAPER] Catastrophic error when calling the scraper'{provider_name}': {e}", xbmc.LOGERROR)
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return []

    # Returns the fonts found
    return sources