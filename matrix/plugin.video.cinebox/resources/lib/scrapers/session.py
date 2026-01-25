# Em: resources/lib/scrapers/session.py
import requests
import xbmc
import traceback

try:
    # --- ✅ A MUDANÇA ESTÁ AQUI ✅ ---
    # Tenta importar o módulo específico do Kodi (cloudscraper2)
    # e o renomeia (alias) para "cloudscraper"
    import cloudscraper2 as cloudscraper
    # --- FIM DA MUDANÇA ---
    
    SCRAPER_INSTANCE = cloudscraper.create_scraper()

except ImportError as e:  # Captura a exceção
    # Se o cloudscraper2 não estiver instalado OU se uma dependência (como js2py) faltar
    SCRAPER_INSTANCE = requests

except Exception as e: # Captura qualquer OUTRO erro
    SCRAPER_INSTANCE = requests


# --- Constantes de Rede ---
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# ✅ OTIMIZAÇÃO: Timeout padrão para scrapers
DEFAULT_TIMEOUT = 5

HTML_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',  # ✅ NOVO: Compressão
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://google.com/'
}