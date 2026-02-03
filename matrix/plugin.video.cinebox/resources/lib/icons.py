"""Cinebox Icon System - Reuses IMDb IDs
Adds visual icons to genres and years without taking up extra space"""

# Mapping genres to icon IDs (reuses from IMDb)
# Includes names in Portuguese (TMDB) and English for maximum compatibility
GENRE_ICONS = {
    # Portuguese
    'Action': 'mOkM9Cs',
    'Adventure': 'SF329Ap',
    'Animation': 'xCJdDW7',
    'Comedy': 'Xsb1iEl',
    'Crime': 'cE3Rovc',
    'Documentary': 'DIfwy76',
    'Drama': 'n0LmfJR',
    'Family': 'UVc9gws',
    'Fantasy': 'Y4Y3EMn',
    'Foreigner': 'HUN7FxK',
    'History': 'J5EM9MB',
    'Horror': 'SCJriF0',
    'Horror': 'SCJriF0',
    'Kids': 'cMjxdqe',
    'Music': 'Qi9NcWi',
    'Mystery': '7GCK5Tg',
    'News': 'CjDP92M',
    'News': 'CjDP92M',
    'Reality': 'NZTCRcM',
    'Reality Show': 'NZTCRcM',
    'Romance': '5OZRqUX',
    'Science Fiction': 'CPanVlY',
    'Science fiction': 'CPanVlY',
    'Science Fiction and Fantasy': 'CPanVlY',
    'Soap': 'RpDSmbX',
    'Novel': 'RpDSmbX',
    'Talk': 'DB5KHJf',
    'Talk Show': 'DB5KHJf',
    'Suspense': 'ObKPLhE',
    'Thriller': 'ObKPLhE',
    'War': 'MWqQbMF',
    'War and Politics': 'MWqQbMF',
    'Western': 'MU8LKTK',
    'Western': 'MU8LKTK',
    'Cinema TV': 'b9La9Ch',

    # English (IMDb/TMDB Original)
    'Action': 'mOkM9Cs',
    'Adventure': 'SF329Ap',
    'Animation': 'xCJdDW7',
    'Comedy': 'Xsb1iEl',
    'Crime': 'cE3Rovc',
    'Documentary': 'DIfwy76',
    'Drama': 'n0LmfJR',
    'Family': 'UVc9gws',
    'Fantasy': 'Y4Y3EMn',
    'Foreign': 'HUN7FxK',
    'History': 'J5EM9MB',
    'Horror': 'SCJriF0',
    'Kids': 'cMjxdqe',
    'Music': 'Qi9NcWi',
    'Mystery': '7GCK5Tg',
    'News': 'CjDP92M',
    'Reality': 'NZTCRcM',
    'Romance': '5OZRqUX',
    'Sci-Fi': 'CPanVlY',
    'Science Fiction': 'CPanVlY',
    'Soap': 'RpDSmbX',
    'Talk': 'DB5KHJf',
    'Thriller': 'ObKPLhE',
    'War': 'MWqQbMF',
    'Western': 'MU8LKTK',
    'TV Movie': 'b9La9Ch',
}

# Default icon for genres
DEFAULT_GENRE_ICON = 'I1JJhji'  # folder icon


def get_genre_icon(genre_name):
    """Returns the icon ID for a specific genre
    
    Args:
        genre_name (str): Genre name
        
    Returns:
        str: Genre icon ID or default icon"""
    if not genre_name:
        return DEFAULT_GENRE_ICON
    
    # Mapping search (case-insensitive)
    for key, value in GENRE_ICONS.items():
        if key.lower() == genre_name.lower():
            return value
    
    # Returns default icon if not found
    return DEFAULT_GENRE_ICON


def get_year_icon():
    """Returns the icon ID for years
    
    Returns:
        str: Calendar icon ID"""
    return 'fN4GQmO'  # calendar icon


def get_icon_url(icon_id):
    """Converts an icon ID to a URL
    
    Args:
        icon_id (str): Icon ID
        
    Returns:
        str: icon URL"""
    if not icon_id:
        return ''
    
    # If it is a local file (contains .png)
    if '.png' in icon_id:
        return icon_id
    
    # If it is an ID, build the URL
    # Using the IMDb Icon Server
    return f'https://i.imgur.com/{icon_id}.png'


# Aliases for compatibility
genre_action = GENRE_ICONS.get('Action', 'mOkM9Cs')
genre_adventure = GENRE_ICONS.get('Adventure', 'SF329Ap')
genre_animation = GENRE_ICONS.get('Animation', 'xCJdDW7')
genre_comedy = GENRE_ICONS.get('Comedy', 'Xsb1iEl')
genre_crime = GENRE_ICONS.get('Crime', 'cE3Rovc')
genre_documentary = GENRE_ICONS.get('Documentary', 'DIfwy76')
genre_drama = GENRE_ICONS.get('Drama', 'n0LmfJR')
genre_family = GENRE_ICONS.get('Family', 'UVc9gws')
genre_fantasy = GENRE_ICONS.get('Fantasy', 'Y4Y3EMn')
genre_history = GENRE_ICONS.get('History', 'J5EM9MB')
genre_horror = GENRE_ICONS.get('Horror', 'SCJriF0')
genre_kids = GENRE_ICONS.get('Kids', 'cMjxdqe')
genre_music = GENRE_ICONS.get('Music', 'Qi9NcWi')
genre_mystery = GENRE_ICONS.get('Mystery', '7GCK5Tg')
genre_reality = GENRE_ICONS.get('Reality', 'NZTCRcM')
genre_romance = GENRE_ICONS.get('Romance', '5OZRqUX')
genre_scifi = GENRE_ICONS.get('Science Fiction', 'CPanVlY')
genre_thriller = GENRE_ICONS.get('Suspense', 'ObKPLhE')
genre_war = GENRE_ICONS.get('War', 'MWqQbMF')
genre_western = GENRE_ICONS.get('Western', 'MU8LKTK')

calendar = 'fN4GQmO'
