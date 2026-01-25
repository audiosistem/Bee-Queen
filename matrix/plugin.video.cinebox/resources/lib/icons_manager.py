"""
Gerenciador de Ícones para Gêneros e Anos - Cinebox Plugin
Adiciona ícones visuais aos gêneros de filmes, séries e animes
E aos anos de lançamento
"""

import os
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

# Mapeamento de gêneros para ícones
GENRE_ICONS = {
    'Ação': os.path.join(ICON_PATH, 'genres', 'action.png'),
    'Aventura': os.path.join(ICON_PATH, 'genres', 'adventure.png'),
    'Animação': os.path.join(ICON_PATH, 'genres', 'animation.png'),
    'Comédia': os.path.join(ICON_PATH, 'genres', 'comedy.png'),
    'Crime': os.path.join(ICON_PATH, 'genres', 'crime.png'),
    'Documentário': os.path.join(ICON_PATH, 'genres', 'documentary.png'),
    'Drama': os.path.join(ICON_PATH, 'genres', 'drama.png'),
    'Família': os.path.join(ICON_PATH, 'genres', 'family.png'),
    'Fantasia': os.path.join(ICON_PATH, 'genres', 'fantasy.png'),
    'Ficção Científica': os.path.join(ICON_PATH, 'genres', 'scifi.png'),
    'Ficção científica': os.path.join(ICON_PATH, 'genres', 'scifi.png'),
    'História': os.path.join(ICON_PATH, 'genres', 'history.png'),
    'Horror': os.path.join(ICON_PATH, 'genres', 'horror.png'),
    'Mistério': os.path.join(ICON_PATH, 'genres', 'mystery.png'),
    'Música': os.path.join(ICON_PATH, 'genres', 'music.png'),
    'Romance': os.path.join(ICON_PATH, 'genres', 'romance.png'),
    'Suspense': os.path.join(ICON_PATH, 'genres', 'thriller.png'),
    'Thriller': os.path.join(ICON_PATH, 'genres', 'thriller.png'),
    'Guerra': os.path.join(ICON_PATH, 'genres', 'war.png'),
    'Western': os.path.join(ICON_PATH, 'genres', 'western.png'),
    'Infantil': os.path.join(ICON_PATH, 'genres', 'kids.png'),
    'Reality': os.path.join(ICON_PATH, 'genres', 'reality.png'),
}

# Ícone padrão para gêneros
DEFAULT_GENRE_ICON = os.path.join(ICON_PATH, 'genres', 'default.png')


def get_genre_icon(genre_name):
    """
    Retorna o caminho do ícone para um gênero específico
    
    Args:
        genre_name (str): Nome do gênero
        
    Returns:
        str: Caminho do ícone do gênero ou ícone padrão
    """
    if not genre_name:
        return DEFAULT_GENRE_ICON
    
    # Procura no mapeamento
    icon_path = GENRE_ICONS.get(genre_name)
    if icon_path and os.path.exists(icon_path):
        return icon_path
    
    # Tenta com variações de capitalização
    for key, value in GENRE_ICONS.items():
        if key.lower() == genre_name.lower():
            if os.path.exists(value):
                return value
    
    # Retorna ícone padrão se não encontrar
    return DEFAULT_GENRE_ICON


def get_year_icon(year):
    """
    Retorna o caminho do ícone para um ano específico
    
    Args:
        year (int or str): Ano de lançamento
        
    Returns:
        str: Caminho do ícone do ano
    """
    if not year:
        return os.path.join(ICON_PATH, 'years', 'default.png')
    
    year_str = str(year)
    year_icon = os.path.join(ICON_PATH, 'years', f'{year_str}.png')
    
    # Se existir ícone específico do ano, retorna
    if os.path.exists(year_icon):
        return year_icon
    
    # Caso contrário, retorna ícone padrão
    return os.path.join(ICON_PATH, 'years', 'default.png')


def add_genre_icon_to_item(list_item, genre_name):
    """
    Adiciona ícone de gênero a um ListItem do Kodi
    
    Args:
        list_item: xbmcgui.ListItem
        genre_name (str): Nome do gênero
    """
    try:
        icon = get_genre_icon(genre_name)
        if icon and os.path.exists(icon):
            list_item.setArt({'icon': icon})
    except Exception as e:
        import xbmc
        xbmc.log(f"[Cinebox] Erro ao adicionar ícone de gênero: {e}", xbmc.LOGWARNING)


def add_year_icon_to_item(list_item, year):
    """
    Adiciona ícone de ano a um ListItem do Kodi
    
    Args:
        list_item: xbmcgui.ListItem
        year (int or str): Ano de lançamento
    """
    try:
        icon = get_year_icon(year)
        if icon and os.path.exists(icon):
            list_item.setArt({'icon': icon})
    except Exception as e:
        import xbmc
        xbmc.log(f"[Cinebox] Erro ao adicionar ícone de ano: {e}", xbmc.LOGWARNING)
