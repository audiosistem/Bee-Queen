"""Icon Manager for Genres and Years - Cinebox Plugin
Adds visual icons to film, series and anime genres
And the years of release"""

import os
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

# Mapping genres to icons
GENRE_ICONS = {
    'Action': os.path.join(ICON_PATH, 'genres', 'action.png'),
    'Adventure': os.path.join(ICON_PATH, 'genres', 'adventure.png'),
    'Animation': os.path.join(ICON_PATH, 'genres', 'animation.png'),
    'Comedy': os.path.join(ICON_PATH, 'genres', 'comedy.png'),
    'Crime': os.path.join(ICON_PATH, 'genres', 'crime.png'),
    'Documentary': os.path.join(ICON_PATH, 'genres', 'documentary.png'),
    'Drama': os.path.join(ICON_PATH, 'genres', 'drama.png'),
    'Family': os.path.join(ICON_PATH, 'genres', 'family.png'),
    'Fantasy': os.path.join(ICON_PATH, 'genres', 'fantasy.png'),
    'Science Fiction': os.path.join(ICON_PATH, 'genres', 'scifi.png'),
    'Science fiction': os.path.join(ICON_PATH, 'genres', 'scifi.png'),
    'History': os.path.join(ICON_PATH, 'genres', 'history.png'),
    'Horror': os.path.join(ICON_PATH, 'genres', 'horror.png'),
    'Mystery': os.path.join(ICON_PATH, 'genres', 'mystery.png'),
    'Music': os.path.join(ICON_PATH, 'genres', 'music.png'),
    'Romance': os.path.join(ICON_PATH, 'genres', 'romance.png'),
    'Suspense': os.path.join(ICON_PATH, 'genres', 'thriller.png'),
    'Thriller': os.path.join(ICON_PATH, 'genres', 'thriller.png'),
    'War': os.path.join(ICON_PATH, 'genres', 'war.png'),
    'Western': os.path.join(ICON_PATH, 'genres', 'western.png'),
    'Kids': os.path.join(ICON_PATH, 'genres', 'kids.png'),
    'Reality': os.path.join(ICON_PATH, 'genres', 'reality.png'),
}

# Default icon for genres
DEFAULT_GENRE_ICON = os.path.join(ICON_PATH, 'genres', 'default.png')


def get_genre_icon(genre_name):
    """Returns the icon path for a specific genre
    
    Args:
        genre_name (str): Genre name
        
    Returns:
        str: Genre icon path or default icon"""
    if not genre_name:
        return DEFAULT_GENRE_ICON
    
    # Mapping search
    icon_path = GENRE_ICONS.get(genre_name)
    if icon_path and os.path.exists(icon_path):
        return icon_path
    
    # Try with capitalization variations
    for key, value in GENRE_ICONS.items():
        if key.lower() == genre_name.lower():
            if os.path.exists(value):
                return value
    
    # Returns default icon if not found
    return DEFAULT_GENRE_ICON


def get_year_icon(year):
    """Returns the icon path for a specific year
    
    Args:
        year (int or str): Year of release
        
    Returns:
        str: Year icon path"""
    if not year:
        return os.path.join(ICON_PATH, 'years', 'default.png')
    
    year_str = str(year)
    year_icon = os.path.join(ICON_PATH, 'years', f'{year_str}.png')
    
    # If there is a year-specific icon, return
    if os.path.exists(year_icon):
        return year_icon
    
    # Otherwise, return default icon
    return os.path.join(ICON_PATH, 'years', 'default.png')


def add_genre_icon_to_item(list_item, genre_name):
    """Add gender icon to a Kodi ListItem
    
    Args:
        list_item: xbmcgui.ListItem
        genre_name (str): Genre name"""
    try:
        icon = get_genre_icon(genre_name)
        if icon and os.path.exists(icon):
            list_item.setArt({'icon': icon})
    except Exception as e:
        import xbmc
        xbmc.log(f"[Cinebox] Error adding gender icon: {e}", xbmc.LOGWARNING)


def add_year_icon_to_item(list_item, year):
    """Add year icon to a Kodi ListItem
    
    Args:
        list_item: xbmcgui.ListItem
        year (int or str): Year of release"""
    try:
        icon = get_year_icon(year)
        if icon and os.path.exists(icon):
            list_item.setArt({'icon': icon})
    except Exception as e:
        import xbmc
        xbmc.log(f"[Cinebox] Error adding year icon: {e}", xbmc.LOGWARNING)
