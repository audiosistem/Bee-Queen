import xbmcaddon
addon = xbmcaddon.Addon()

import xbmcaddon
import random

# Initializare addon Kodi
addon = xbmcaddon.Addon()

# Configuratii URL pentru TMDB
BASE_URL = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w500"

API_KEYS_LIST = [
    "74f3ce931d65ebda1f77ef24eac2625f",
    "edde6b5e41246ab79a2697cd125e1781",
    "8ad3c21a92a64da832c559d58cc63ab4"
]

API_KEY = random.choice(API_KEYS_LIST)

def log_key_info():
    import xbmc
    xbmc.log(f"DEBUG: Addon-ul foloseste cheia TMDB care incepe cu: {API_KEY[:5]}", xbmc.LOGINFO)

