# -*- coding: utf-8 -*-
import xbmc
import xbmcvfs
import os
import json

def get_config_path():
    """
    Retorna o caminho do arquivo de configuração JSON.
    Usa o ID do addon para garantir o caminho correto no profile.
    """
    try:
        # Tenta obter o ID dinamicamente, fallback para o ID padrão se falhar
        import xbmcaddon
        addon_id = xbmcaddon.Addon().getAddonInfo('id')
    except:
        addon_id = 'plugin.video.cinebox'
        
    try:
        profile_path = xbmcvfs.translatePath(f'special://profile/addon_data/{addon_id}/')
    except AttributeError:
        profile_path = xbmc.translatePath(f'special://profile/addon_data/{addon_id}/')
    
    # Criar diretório se não existir
    if not os.path.exists(profile_path):
        try:
            os.makedirs(profile_path)
        except:
            pass
    
    return os.path.join(profile_path, 'scraper_config.json')

def load_config():
    """
    Carrega a configuração do arquivo JSON.
    """
    config_path = get_config_path()
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                xbmc.log(f"[ConfigManager] Configuração carregada: {config}", xbmc.LOGINFO)
                return config
        except Exception as e:
            xbmc.log(f"[ConfigManager] Erro ao carregar config: {e}", xbmc.LOGERROR)
    
    # Retornar configuração padrão (Magneto)
    return {'enabled_scraper': 'script.module.magneto'}

def save_config(config):
    """
    Salva a configuração no arquivo JSON.
    """
    config_path = get_config_path()
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        xbmc.log(f"[ConfigManager] Configuração salva: {config}", xbmc.LOGINFO)
        return True
    except Exception as e:
        xbmc.log(f"[ConfigManager] Erro ao salvar config: {e}", xbmc.LOGERROR)
        return False

def get_enabled_scraper():
    """
    Retorna o scraper externo habilitado.
    Sempre recarrega do arquivo para evitar cache.
    """
    config = load_config()
    scraper = config.get('enabled_scraper', 'script.module.magneto')
    xbmc.log(f"[ConfigManager] Scraper habilitado retornado: {scraper}", xbmc.LOGINFO)
    return scraper

def set_enabled_scraper(scraper_id):
    """
    Define o scraper externo habilitado.
    """
    config = load_config()
    config['enabled_scraper'] = scraper_id
    return save_config(config)
