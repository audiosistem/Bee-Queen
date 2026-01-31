# -*- coding: utf-8 -*-
"""
Favorites Manager for Radio Garden Add-on
Manages user's favorite radio stations
"""

import os
import json
import xbmcaddon
import xbmcvfs


class FavoritesManager:
    """Gerenciador de estações favoritas"""
    
    def __init__(self):
        addon = xbmcaddon.Addon()
        profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
        
        # Garantir que o diretório existe
        if not xbmcvfs.exists(profile_path):
            xbmcvfs.mkdirs(profile_path)
        
        self.favorites_file = os.path.join(profile_path, 'favorites.json')
    
    def load_favorites(self):
        """Carregar lista de favoritos"""
        if not xbmcvfs.exists(self.favorites_file):
            return []
        
        try:
            with open(self.favorites_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    
    def save_favorites(self, favorites):
        """Salvar lista de favoritos"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def add_favorite(self, channel_id, title, subtitle=''):
        """Adicionar estação aos favoritos"""
        favorites = self.load_favorites()
        
        # Verificar se já existe
        for fav in favorites:
            if fav.get('channel_id') == channel_id:
                return False  # Já existe
        
        # Adicionar novo favorito
        favorites.append({
            'channel_id': channel_id,
            'title': title,
            'subtitle': subtitle
        })
        
        return self.save_favorites(favorites)
    
    def remove_favorite(self, channel_id):
        """Remover estação dos favoritos"""
        favorites = self.load_favorites()
        favorites = [f for f in favorites if f.get('channel_id') != channel_id]
        return self.save_favorites(favorites)
    
    def is_favorite(self, channel_id):
        """Verificar se uma estação é favorita"""
        favorites = self.load_favorites()
        return any(f.get('channel_id') == channel_id for f in favorites)
    
    def get_favorites(self):
        """Obter lista de favoritos"""
        return self.load_favorites()
