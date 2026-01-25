# Em: resources/lib/favorites.py

import xbmcgui
from .db import db

def add_item_to_favorites(tmdb_id, media_type):
    """Adiciona o item aos favoritos e tenta buscar dados em background se necessário."""
    try:
        from .db.db import db_instance
        
        # 1. Adiciona imediatamente à tabela de favoritos (ação rápida)
        db_instance.add_to_favorites(tmdb_id, media_type)
        
        # 2. Notifica o usuário imediatamente
        xbmcgui.Dialog().notification("Minha Lista", "Adicionado com sucesso!", xbmcgui.NOTIFICATION_INFO, 3000)
        
        # 3. Verifica se precisamos baixar os dados (apenas se não existirem)
        if media_type == 'movie':
            if not db_instance.get_movie_by_id(tmdb_id):
                from .tmdb_api import get_movie_details
                data = get_movie_details(tmdb_id)
                if data: db_instance.add_movie(data)
        else:
            if not db_instance.get_tvshow_by_id(tmdb_id):
                from .tmdb_api import fetch_show_details
                data = fetch_show_details(tmdb_id)
                if data: db_instance.add_tvshow(data)
                
    except Exception as e:
        import xbmc
        xbmc.log(f"[Cinebox] Erro ao adicionar favorito: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Não foi possível adicionar", xbmcgui.NOTIFICATION_ERROR)

def remove_item_from_favorites(tmdb_id, media_type):
    """Chama o banco de dados para remover um item e notifica o usuário."""
    db.remove_from_favorites(tmdb_id, media_type)
    xbmcgui.Dialog().notification("Minha Lista", "Removido da sua lista.", xbmcgui.NOTIFICATION_INFO)