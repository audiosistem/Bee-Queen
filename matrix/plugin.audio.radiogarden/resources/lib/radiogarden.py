# -*- coding: utf-8 -*-
"""
Radio Garden API Client
Unofficial client for accessing Radio Garden API
"""

import requests
import json
import xbmc
import urllib3

# Desativar avisos de requisições inseguras (SSL)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RadioGardenAPI:
    """Client for Radio Garden API"""
    
    BASE_URL = "https://radio.garden/api"
    
    # Mapeamento expandido de nomes de países em português para inglês para melhor busca
    COUNTRY_TRANSLATIONS = {
        'brasil': 'brazil',
        'portugal': 'portugal',
        'espanha': 'spain',
        'frança': 'france',
        'alemanha': 'germany',
        'itália': 'italy',
        'reino unido': 'united kingdom',
        'estados unidos': 'united states',
        'argentina': 'argentina',
        'méxico': 'mexico',
        'japão': 'japan',
        'china': 'china',
        'índia': 'india',
        'rússia': 'russia',
        'canadá': 'canada',
        'austrália': 'australia',
        'angola': 'angola',
        'moçambique': 'mozambique',
        'cabo verde': 'cape verde',
        'guiné-bissau': 'guinea-bissau',
        'timor leste': 'east timor',
        'suíça': 'switzerland',
        'suécia': 'sweden',
        'noruega': 'norway',
        'dinamarca': 'denmark',
        'holanda': 'netherlands',
        'bélgica': 'belgium',
        'áustria': 'austria'
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://radio.garden/',
            'Origin': 'https://radio.garden'
        })

    def log(self, msg, level=xbmc.LOGINFO):
        try:
            xbmc.log(f"Radio Garden Addon: {msg}", level)
        except:
            pass
    
    def search(self, query):
        """Buscar países, cidades e estações de rádio com suporte bilíngue aprimorado"""
        try:
            self.log(f"Iniciando busca por: {query}")
            
            # Tentar busca original
            results = self._perform_search(query)
            
            # Aprimoramento: Se a busca for curta ou não retornar país, tentar variações
            query_lower = query.lower().strip()
            
            # Verificar se a query está no mapeamento de tradução
            if query_lower in self.COUNTRY_TRANSLATIONS:
                english_query = self.COUNTRY_TRANSLATIONS[query_lower]
                if english_query != query_lower:
                    self.log(f"Tentando busca em inglês para país: {english_query}")
                    english_results = self._perform_search(english_query)
                    # Mesclar resultados, priorizando países
                    for res in english_results:
                        if res.get('type') == 'country':
                            if not any(r.get('country_id') == res.get('country_id') for r in results):
                                results.insert(0, res)
            
            return results
            
        except Exception as e:
            self.log(f"Erro na busca: {str(e)}", xbmc.LOGERROR)
            return []
    
    def _perform_search(self, query):
        """Realizar busca na API"""
        url = f"{self.BASE_URL}/search"
        params = {'q': query}
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        if 'hits' in data and 'hits' in data['hits']:
            hits = data['hits']['hits']
            for hit in hits:
                source = hit.get('_source', {})
                result_type = source.get('type', '')
                page = source.get('page', {})
                
                if not page: continue
                
                result = {
                    'type': result_type,
                    'title': page.get('title', 'Sem título'),
                    'subtitle': page.get('subtitle', ''),
                    'url': page.get('url', ''),
                    'count': page.get('count', 0),
                    'map': page.get('map', ''),
                    'code': source.get('code', '')
                }
                
                if result_type == 'channel':
                    channel_id = page.get('url', '').split('/')[-1]
                    result['channel_id'] = channel_id
                
                if result_type == 'place':
                    result['place_id'] = page.get('map', '')
                
                if result_type == 'country':
                    country_url = page.get('url', '')
                    if country_url:
                        country_id = country_url.split('/')[-1]
                        result['country_id'] = country_id
                
                results.append(result)
        
        return results
    
    def get_country_channels(self, country_id):
        """Obter canais de um país específico"""
        return self._get_channels_from_page(country_id)
    
    def get_place_channels(self, place_id):
        """Obter canais de um local específico (cidade)"""
        # Tentar endpoint direto primeiro
        channels = self._get_channels_from_direct_endpoint(place_id)
        if not channels:
            channels = self._get_channels_from_page(place_id)
        return channels

    def _get_channels_from_direct_endpoint(self, page_id):
        """Tenta obter canais do endpoint /channels"""
        try:
            url = f"{self.BASE_URL}/ara/content/page/{page_id}/channels"
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return self._parse_channel_list(data.get('data', {}).get('content', []))
        except:
            pass
        return []

    def _get_channels_from_page(self, page_id):
        """Obtém canais da estrutura de página genérica"""
        try:
            url = f"{self.BASE_URL}/ara/content/page/{page_id}"
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return self._parse_channel_list(data.get('data', {}).get('content', []))
        except:
            pass
        return []

    def _parse_channel_list(self, content):
        """Extrai canais de diferentes estruturas de conteúdo da API"""
        channels = []
        seen_ids = set()
        
        for section in content:
            items = section.get('items', [])
            for item in items:
                page = item.get('page', {})
                if item.get('type') == 'channel' or page.get('type') == 'channel':
                    url = page.get('url', '')
                    if not url: continue
                    
                    cid = url.split('/')[-1]
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        channels.append({
                            'type': 'channel',
                            'channel_id': cid,
                            'title': page.get('title', 'Sem título'),
                            'subtitle': page.get('subtitle', '')
                        })
        return channels
    
    def get_stream_url(self, channel_id):
        """Obter URL do stream de áudio"""
        return f"{self.BASE_URL}/ara/content/listen/{channel_id}/channel.mp3"
    
    def get_geolocation(self):
        """Obter geolocalização do usuário baseada no IP"""
        try:
            url = f"{self.BASE_URL}/geo"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            self.log(f"Geolocalização obtida: {data.get('city', 'Unknown')}, {data.get('country_code', 'Unknown')}")
            return data
        except Exception as e:
            self.log(f"Erro ao obter geolocalização: {str(e)}", xbmc.LOGERROR)
            return None
    
    def get_nearby_places(self):
        """Obter lista de lugares próximos"""
        try:
            url = f"{self.BASE_URL}/ara/content/places"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            places = data.get('data', {}).get('list', [])
            self.log(f"Total de lugares obtidos: {len(places)}")
            return places
        except Exception as e:
            self.log(f"Erro ao obter lugares próximos: {str(e)}", xbmc.LOGERROR)
            return []
    
    def find_closest_place(self, user_lat, user_lon, places):
        """Encontrar o lugar mais próximo baseado nas coordenadas do usuário"""
        import math
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            """Calcular distância entre dois pontos usando fórmula de Haversine"""
            R = 6371  # Raio da Terra em km
            
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            
            a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            return R * c
        
        closest_place = None
        min_distance = float('inf')
        
        for place in places:
            geo = place.get('geo', [])
            if len(geo) == 2:
                place_lon, place_lat = geo[0], geo[1]
                distance = haversine_distance(user_lat, user_lon, place_lat, place_lon)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_place = place
        
        if closest_place:
            self.log(f"Lugar mais próximo: {closest_place.get('title')} ({min_distance:.2f} km)")
        
        return closest_place
    
    def get_local_stations(self):
        """Obter estações de rádio locais baseadas na geolocalização (expandido para 50km)"""
        try:
            geo_data = self.get_geolocation()
            if not geo_data: return None, []
            
            user_lat = geo_data.get('latitude')
            user_lon = geo_data.get('longitude')
            if not user_lat or not user_lon: return None, []
            
            places = self.get_nearby_places()
            if not places: return None, []
            
            # Encontrar lugares num raio de 50km
            nearby_place_ids = []
            import math
            
            def haversine(lat1, lon1, lat2, lon2):
                R = 6371
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

            # Filtrar lugares próximos (raio de 50km)
            places_with_dist = []
            for p in places:
                geo = p.get('geo', [])
                if len(geo) == 2:
                    dist = haversine(user_lat, user_lon, geo[1], geo[0])
                    if dist <= 50: # 50 km de raio
                        places_with_dist.append((dist, p))
            
            # Ordenar por distância
            places_with_dist.sort(key=lambda x: x[0])
            
            all_channels = []
            seen_channel_ids = set()
            
            # Pegar canais dos lugares mais próximos (limite de 10 cidades para não demorar)
            for dist, place in places_with_dist[:10]:
                place_id = place.get('id')
                channels = self.get_place_channels(place_id)
                for c in channels:
                    cid = c.get('channel_id')
                    if cid and cid not in seen_channel_ids:
                        seen_channel_ids.add(cid)
                        # Adicionar nome da cidade ao subtítulo para clareza
                        if place.get('title'):
                            c['subtitle'] = f"{place.get('title')} - {c.get('subtitle', '')}".strip(' -')
                        all_channels.append(c)
            
            return geo_data.get('city', 'Local'), all_channels
            
        except Exception as e:
            self.log(f"Erro ao obter estações locais: {str(e)}", xbmc.LOGERROR)
            return None, []
