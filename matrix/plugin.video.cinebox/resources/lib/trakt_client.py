# resources/lib/trakt_client.py
# -*- coding: utf-8 -*-
"""Organized Trakt Client - Based on the Jacktook framework
✅ Functional public lists
✅ Correct pagination
✅ Clean structure"""

import xbmc
import xbmcgui
import xbmcaddon
import json
import time
from urllib.parse import quote_plus

ADDON = xbmcaddon.Addon()

class TraktAPI:
    """Base client for Trakt requests"""
    
    def __init__(self):
        self.settings = self._get_settings()
        self.base_url = "https://api.trakt.tv"
    
    def _get_settings(self):
        return {
            'client_id': ADDON.getSetting('trakt_client_id') or '',
            'client_secret': ADDON.getSetting('trakt_client_secret') or '',
            'access_token': ADDON.getSetting('trakt_access_token') or '',
            'refresh_token': ADDON.getSetting('trakt_refresh_token') or '',
            'expires_at': float(ADDON.getSetting('trakt_expires_at') or 0),
            'username': ADDON.getSetting('trakt_username') or ''
        }
    
    def _get_headers(self, auth_required=False):
        headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.settings['client_id'] if self.settings['client_id'] else 'f0b9cd2de131c900f5bb03a0a5776342'
        }
        
        if auth_required and self.settings['access_token']:
            headers['Authorization'] = f"Bearer {self.settings['access_token']}"
        
        return headers
    
    def request(self, method, endpoint, params=None, auth_required=False):
        """Request generic para Trakt"""
        try:
            import requests
            
            url = f"{self.base_url}{endpoint}"
            headers = self._get_headers(auth_required)
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=15)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=params, timeout=15)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, json=params, timeout=15)
            else:
                return None
            
            if response.status_code in [200, 201, 204]:
                if response.content:
                    return response.json()
                return True
            
            xbmc.log(f"[Trakt] Error {response.status_code} em {endpoint}", xbmc.LOGERROR)
            return None
            
        except Exception as e:
            xbmc.log(f"[Trakt] Error request {endpoint}: {e}", xbmc.LOGERROR)
            return None
    
    def get_public_list(self, endpoint, params=None, **kwargs):
        """Get public list (does not require auth)"""
        params = params or {}
        params['extended'] = 'full'
        if kwargs:
            params.update(kwargs)
        
        return self.request('GET', endpoint, params, auth_required=False)

class TraktLists:
    """Trakt List Management"""
    
    def __init__(self):
        self.api = TraktAPI()
    
    def get_trending(self, media_type='movies', page=1, limit=30, **kwargs):
        """Trending list (public)"""
        endpoint = f'/{media_type}/trending'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params, **kwargs)
    
    def get_popular(self, media_type='movies', page=1, limit=30, **kwargs):
        """Popular (public) list"""
        endpoint = f'/{media_type}/popular'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params, **kwargs)
    
    def get_most_watched(self, media_type='movies', period='weekly', page=1, limit=30, **kwargs):
        """Most watched (public)"""
        endpoint = f'/{media_type}/watched/{period}'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params, **kwargs)
    
    def get_most_collected(self, media_type='movies', period='weekly', page=1, limit=30, **kwargs):
        """Most collected (public)"""
        endpoint = f'/{media_type}/collected/{period}'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params, **kwargs)
    
    def get_most_anticipated(self, media_type='movies', page=1, limit=30, **kwargs):
        """Most anticipated (public)"""
        endpoint = f'/{media_type}/anticipated'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params, **kwargs)
    
    def get_box_office(self, page=1, limit=30):
        """Box office (public) - films only"""
        endpoint = '/movies/boxoffice'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params)
    
    def get_recommended(self, media_type='movies', page=1, limit=30):
        """Recommended (requires auth)"""
        endpoint = f'/recommendations/{media_type}'
        params = {'page': page, 'limit': limit}
        return self.api.request('GET', endpoint, params, auth_required=True)
    
    def get_top_rated(self, media_type='movies', page=1, limit=30, **kwargs):
        """Top rated (public)"""
        endpoint = f'/{media_type}/rated'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params, **kwargs)
    
    def get_most_played(self, media_type='movies', period='weekly', page=1, limit=30, **kwargs):
        """Most played (public)"""
        endpoint = f'/{media_type}/played/{period}'
        params = {'page': page, 'limit': limit}
        return self.api.get_public_list(endpoint, params, **kwargs)

class TraktPresentation:
    """Presentation of Trakt results"""
    
    @staticmethod
    def normalize_item(item):
        """Normalizes Trakt item to standard format"""
        # Detects whether it is a movie or series
        if 'movie' in item:
            media_type = 'movie'
            obj = item['movie']
            extra = item
        elif 'show' in item:
            media_type = 'tvshow'
            obj = item['show']
            extra = item
        else:
            # Can be a direct item
            obj = item
            extra = {}
            media_type = 'movie' if 'title' in obj else 'tvshow'
        
        ids = obj.get('ids', {})
        
        return {
            'title': obj.get('title') or obj.get('name', ''),
            'original_title': obj.get('title') or obj.get('name', ''),
            'tmdb_id': ids.get('tmdb'),
            'imdb_id': ids.get('imdb', ''),
            'media_type': media_type,
            'year': obj.get('year'),
            'slug': ids.get('slug', ''),
            'synopsis': obj.get('overview', ''),
            'rating': obj.get('rating', 0),
            'votes': obj.get('votes', 0),
            'genres': obj.get('genres', []),
            'runtime': obj.get('runtime', 0),
            'watchers': extra.get('watchers', 0),
            'play_count': extra.get('play_count', 0),
            'collector_count': extra.get('collector_count', 0),
            'list_count': extra.get('list_count', 0),
            'revenue': extra.get('revenue', 0),
            # Added to support arts
            'poster': item.get('poster', ''),
            'backdrop': item.get('backdrop', ''),
            'clearlogo': item.get('clearlogo', '')
        }
    
    @staticmethod
    def build_url(item):
        """Build URL for item"""
        media_type = item.get('media_type')
        
        # For series
        if media_type == 'tvshow':
            url = f"plugin://plugin.video.cinebox/?action=list_seasons&tvshow_tmdb_id={item['tmdb_id']}"
            # Add arts to the series URL
            if item.get('poster'): url += f"&poster={quote_plus(item['poster'])}"
            if item.get('backdrop'): url += f"&backdrop={quote_plus(item['backdrop'])}"
            if item.get('clearlogo'): url += f"&clearlogo={quote_plus(item['clearlogo'])}"
            return url
        
        # For movies
        title = str(item.get('title', ''))
        url_params = [
            f"action=find_sources",
            f"tmdb_id={item['tmdb_id']}",
            f"media_type=movie",
            f"title={quote_plus(title)}"
        ]
        
        if item.get('year'):
            url_params.append(f"year={item['year']}")
        if item.get('imdb_id'):
            url_params.append(f"imdb_id={item['imdb_id']}")
            
        # Add artwork to movie URLs
        if item.get('poster'):
            url_params.append(f"poster={quote_plus(item['poster'])}")
        if item.get('backdrop'):
            url_params.append(f"backdrop={quote_plus(item['backdrop'])}")
        if item.get('clearlogo'):
            url_params.append(f"clearlogo={quote_plus(item['clearlogo'])}")
        
        return f"plugin://plugin.video.cinebox/?{'&'.join(url_params)}"