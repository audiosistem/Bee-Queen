"""
Sistema de Ícones para Cinebox - Reutiliza IDs do IMDb
Adiciona ícones visuais aos gêneros e anos sem ocupar espaço extra
"""

# Mapeamento de gêneros para IDs de ícones (reutiliza do IMDb)
# Inclui nomes em Português (TMDB) e Inglês para máxima compatibilidade
GENRE_ICONS = {
    # Português
    'Ação': 'mOkM9Cs',
    'Aventura': 'SF329Ap',
    'Animação': 'xCJdDW7',
    'Comédia': 'Xsb1iEl',
    'Crime': 'cE3Rovc',
    'Documentário': 'DIfwy76',
    'Drama': 'n0LmfJR',
    'Família': 'UVc9gws',
    'Fantasia': 'Y4Y3EMn',
    'Estrangeiro': 'HUN7FxK',
    'História': 'J5EM9MB',
    'Horror': 'SCJriF0',
    'Terror': 'SCJriF0',
    'Infantil': 'cMjxdqe',
    'Música': 'Qi9NcWi',
    'Mistério': '7GCK5Tg',
    'Notícia': 'CjDP92M',
    'Notícias': 'CjDP92M',
    'Reality': 'NZTCRcM',
    'Reality Show': 'NZTCRcM',
    'Romance': '5OZRqUX',
    'Ficção Científica': 'CPanVlY',
    'Ficção científica': 'CPanVlY',
    'Ficção Científica e Fantasia': 'CPanVlY',
    'Soap': 'RpDSmbX',
    'Novela': 'RpDSmbX',
    'Talk': 'DB5KHJf',
    'Talk Show': 'DB5KHJf',
    'Suspense': 'ObKPLhE',
    'Thriller': 'ObKPLhE',
    'Guerra': 'MWqQbMF',
    'Guerra e Política': 'MWqQbMF',
    'Western': 'MU8LKTK',
    'Faroeste': 'MU8LKTK',
    'Cinema TV': 'b9La9Ch',

    # Inglês (IMDb/TMDB Original)
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

# Ícone padrão para gêneros
DEFAULT_GENRE_ICON = 'I1JJhji'  # folder icon


def get_genre_icon(genre_name):
    """
    Retorna o ID do ícone para um gênero específico
    
    Args:
        genre_name (str): Nome do gênero
        
    Returns:
        str: ID do ícone do gênero ou ícone padrão
    """
    if not genre_name:
        return DEFAULT_GENRE_ICON
    
    # Procura no mapeamento (case-insensitive)
    for key, value in GENRE_ICONS.items():
        if key.lower() == genre_name.lower():
            return value
    
    # Retorna ícone padrão se não encontrar
    return DEFAULT_GENRE_ICON


def get_year_icon():
    """
    Retorna o ID do ícone para anos
    
    Returns:
        str: ID do ícone de calendário
    """
    return 'fN4GQmO'  # calendar icon


def get_icon_url(icon_id):
    """
    Converte um ID de ícone para uma URL
    
    Args:
        icon_id (str): ID do ícone
        
    Returns:
        str: URL do ícone
    """
    if not icon_id:
        return ''
    
    # Se for um arquivo local (contém .png)
    if '.png' in icon_id:
        return icon_id
    
    # Se for um ID, constrói a URL
    # Usando o servidor de ícones do IMDb
    return f'https://i.imgur.com/{icon_id}.png'


# Aliases para compatibilidade
genre_action = GENRE_ICONS.get('Ação', 'mOkM9Cs')
genre_adventure = GENRE_ICONS.get('Aventura', 'SF329Ap')
genre_animation = GENRE_ICONS.get('Animação', 'xCJdDW7')
genre_comedy = GENRE_ICONS.get('Comédia', 'Xsb1iEl')
genre_crime = GENRE_ICONS.get('Crime', 'cE3Rovc')
genre_documentary = GENRE_ICONS.get('Documentário', 'DIfwy76')
genre_drama = GENRE_ICONS.get('Drama', 'n0LmfJR')
genre_family = GENRE_ICONS.get('Família', 'UVc9gws')
genre_fantasy = GENRE_ICONS.get('Fantasia', 'Y4Y3EMn')
genre_history = GENRE_ICONS.get('História', 'J5EM9MB')
genre_horror = GENRE_ICONS.get('Horror', 'SCJriF0')
genre_kids = GENRE_ICONS.get('Infantil', 'cMjxdqe')
genre_music = GENRE_ICONS.get('Música', 'Qi9NcWi')
genre_mystery = GENRE_ICONS.get('Mistério', '7GCK5Tg')
genre_reality = GENRE_ICONS.get('Reality', 'NZTCRcM')
genre_romance = GENRE_ICONS.get('Romance', '5OZRqUX')
genre_scifi = GENRE_ICONS.get('Ficção Científica', 'CPanVlY')
genre_thriller = GENRE_ICONS.get('Suspense', 'ObKPLhE')
genre_war = GENRE_ICONS.get('Guerra', 'MWqQbMF')
genre_western = GENRE_ICONS.get('Western', 'MU8LKTK')

calendar = 'fN4GQmO'
