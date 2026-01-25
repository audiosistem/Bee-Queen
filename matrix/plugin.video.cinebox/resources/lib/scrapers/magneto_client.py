# -*- coding: utf-8 -*-
import re
import requests
from urllib.parse import unquote_plus

class MagnetoClient:
    @staticmethod
    def request(url, timeout=10):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    @staticmethod
    def parseDOM(html, name, attrs=None, ret=None):
        if attrs is None: attrs = {}
        
        # Simplificação do parseDOM do Magneto usando regex
        if name == 'tr':
            pattern = r'<tr[^>]*>(.*?)</tr>'
        elif name == 'td':
            pattern = r'<td[^>]*>(.*?)</td>'
        elif name == 'a':
            if ret == 'href':
                pattern = r'<a[^>]*href=["\'](.*?)["\'][^>]*>'
            else:
                pattern = r'<a[^>]*>(.*?)</a>'
        else:
            pattern = f'<{name}[^>]*>(.*?)</{name}>'
            
        results = re.findall(pattern, html, re.S | re.I)
        return results

def get_release_quality(name, url):
    name = name.lower()
    if any(x in name for x in ['2160p', '4k', 'uhd']): return '4K', ['4K']
    if any(x in name for x in ['1080p', 'fhd']): return '1080p', ['1080p']
    if any(x in name for x in ['720p', 'hd']): return '720p', ['720p']
    return 'SD', ['SD']
