# Em: resources/lib/db/__init__.py

from .movies_db import MoviesDatabase
from .tvshows_db import TVShowsDatabase
from .favorites_db import FavoritesDatabase
import xbmc

# ✅ 2. Adicione-o à lista de "habilidades" da classe principal
class Database(MoviesDatabase, TVShowsDatabase, FavoritesDatabase):
    def __init__(self):
        super().__init__()

db = Database()