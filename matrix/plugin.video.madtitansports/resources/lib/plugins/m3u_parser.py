import os
import re
import requests
import xbmc
import xbmcaddon
from ..plugin import Plugin

addon_icon = xbmcaddon.Addon().getAddonInfo('icon')
PATH = xbmcaddon.Addon().getAddonInfo("path")

class m3u(Plugin):
    name = "m3u"
    description = "add support for m3u lists"
    priority = 2
    
    def __init__(self):
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36'
        self.headers = {"User-Agent":self.user_agent, "Connection":'keep-alive', 'Accept':'audio/webm,audio/ogg,udio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5'}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_list(self, url: str):
        if url.startswith('m3u'):
            url = url.split('|')[1]
            if url.startswith("file://"):
                url = url.replace("file://", "")
                with open(os.path.join(PATH, "xml", url), 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        try:
            resp = self.session.get(url)
            resp.raise_for_status()  # Raise on HTTP errors (e.g., 404)
            return resp.content.decode('utf-8', errors='replace')  # 'replace' for bad chars
        except Exception as e:
            xbmc.log(f"M3U fetch error for {url}: {str(e)}", level=xbmc.LOGERROR)
            return ""  # Empty string fallback
    
    def parse_list(self, url: str, response):
        if url.startswith('m3u|'):
            url = url.split('|')[1]  # Clean URL if prefixed
        
        if url.endswith('.m3u') or '#EXTINF' in response:
            if url.startswith('m3ucat|'):
                cat = url.split('|')[2]
                return self.get_catlist(response, cat)
            
            # NEW: Detect if it's a "simple video playlist" (no IPTV metadata)
            # Check for tvg-* attributes or group-title in the entire response
            import re  # Ensure re is available (already imported at top)
            has_tvg = bool(re.search(r'tvg-(id|name|country|language|logo)=', response, re.IGNORECASE))
            has_group = bool(re.search(r'group-title=', response, re.IGNORECASE))
            
            if not (has_tvg or has_group):
                # It's a simple playlist (like your chunks)—treat as SINGLE playable item
                # Title: Use filename or fallback to first EXTINF title
                title_match = re.search(r'#EXTINF:.*?,(.*?)(?=\n)', response, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else (os.path.basename(url) or 'Video Playlist')
                # If it's chunks, make title generic
                if 'chunk' in title.lower() or '.ts' in response:
                    title = 'Live Recording Stream'  # Customize as needed
                
                return [
                    {
                        'type': 'item',  # Directly playable—no dir/folder
                        'title': title,
                        'link': url,  # Point to full M3U URL—Kodi plays chunks sequentially
                        'thumbnail': addon_icon
                    }
                ]
            
            # ELSE: Standard IPTV parsing (categories/channels)
            return self.categories_menu(url, response)
        
        return []  # Fallback
    
    def categories_menu(self, url, response):
        item_list = []
        for cat in self.get_categories(response):
            item_list.append(
                {
                'type': 'dir',
                'title': cat,
                'link': f'm3ucat|{url}|{cat}',
                'thumbnail': addon_icon
                }
            )
        return item_list
    
    def get_categories(self, response):
        cats = []
        cat = ''
        country = ''
        for v in re.compile(r'#EXTINF:(.+?),').findall(response):
            if 'tvg-country' in v:
                country = self.re_me(v, 'tvg-country=[\'"](.*?)[\'"]').strip()
            if 'group-title' in v:
                cat = self.re_me(v, 'group-title=[\'"](.*?)[\'"]').strip()
            if cat == '':
                if country != '':
                    cat = country
                else:
                    cat = 'Uncategorized'
            if not cat in cats:
                cats.append(cat)
        return sorted(cats)

    def EpgRegex(self, response):
        m3udata = []
        match = re.compile(r'#EXTINF:(.+?),(.*?)[\n\r]+([^\n]+)').findall(response)
        for other,channel_name,stream_url in match:
            tvg_id='';tvg_name='';tvg_country='';tvg_language='';tvg_logo='';group_title=''
            if 'tvg-id' in other:
                tvg_id = self.re_me(other, 'tvg-id=[\'"](.*?)[\'"]').strip()
            if 'tvg-name' in other:
                tvg_name = self.re_me(other, 'tvg-name=[\'"](.*?)[\'"]').strip()
            if 'tvg-country' in other:
                tvg_country = self.re_me(other, 'tvg-country=[\'"](.*?)[\'"]').strip()
            if 'tvg-language' in other:
                tvg_language = self.re_me(other, 'tvg-language=[\'"](.*?)[\'"]').strip()
            if 'tvg-logo' in other:
                tvg_logo = self.re_me(other, 'tvg-logo=[\'"](.*?)[\'"]').strip()
            if 'group-title' in other:
                group_title = self.re_me(other, 'group-title=[\'"](.*?)[\'"]').strip()
            if group_title == '':
                if tvg_country != '':
                    group_title = tvg_country
                else:
                    group_title = 'Uncategorized'
            if tvg_name == '' and channel_name != '':
                tvg_name = channel_name
            if channel_name =='' and tvg_name !='':
                channel_name = tvg_name
            if 'like gecko' in tvg_name.lower():
                continue
            if tvg_id == '':
                tvg_id = f"{''.join(tvg_name.lower().split())}.{tvg_country}"
            m3udata.append(
                {
                "tvg_id": tvg_id,
                "tvg_name": tvg_name,
                "tvg_country": tvg_country,
                "tvg_language": tvg_language,
                "tvg_logo": tvg_logo,
                "group_title": group_title,
                "channel_name": channel_name,
                "stream_url": stream_url.strip()
                }
            )
        return m3udata
        
    def get_catlist(self, response, category):
        item_list = []
        for v in self.EpgRegex(response):
            if v.get('group_title') == category:
                title = v.get('tvg_name', 'Unknown Channel')
                link = v.get('stream_url', '')
                thumbnail = v.get('tvg_logo', addon_icon)
                item_list.append(
                    {
                     'type': 'item',
                     'title': title,
                     'link': link,
                     'thumbnail': thumbnail
                    }
                )
        return item_list
    
    def re_me(self,data, re_patten):
        m = re.search(re_patten, data)
        if m is not None:
            return m.group(1)
        return ''