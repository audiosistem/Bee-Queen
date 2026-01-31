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
                            'channel_id': cid,
                            'title': page.get('title', 'Sem título'),
                            'subtitle': page.get('subtitle', '')
                        })
        return channels
    
    def get_stream_url(self, channel_id):
        """Obter URL do stream de áudio"""
        return f"{self.BASE_URL}/ara/content/listen/{channel_id}/channel.mp3"
