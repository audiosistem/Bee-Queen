# -*- coding: utf-8 -*-
from base import Stremio
import requests, re

class Stremio2(Stremio):
    def __init__(self):
        super().__init__()
        self.base_url = ""
        self.provider = ""
        self.timeout = 10 
        self.should_verify = False
        # Listă de cuvinte sau domenii pe care vrei să le blochezi (Blacklist)
        self.blocked_domains = [] 

    def _process_item(self, item):
        sources_list = []
        if not item or not isinstance(item, dict): return []
        streams = item.get('streams', [])
        
        for s in streams:
            video_url = s.get('url') or s.get('externalUrl')
            if not video_url: continue

            # --- FILTRU DOMENII BLOCATE ---
            # Dacă orice cuvânt din lista de blocați se află în URL, sărim peste sursă
            if any(domain.lower() in video_url.lower() for domain in self.blocked_domains):
                continue 

            # Verificare sursă activă
            file_type = self.check_url(video_url)
            if not file_type: continue 

            title = s.get('title', '')
            raw_name = s.get('name', 'Sursă')
            t_up = title.upper().replace('\n', ' ')

            # --- 1. CURĂȚARE NUME SERVER ---
            clean_server = re.sub(r'\d{3,4}[pP]', '', raw_name)
            clean_server = re.sub(r'\|\s*(WEB|WEB-DL|BluRay|BRRip|HDRIP).*', '', clean_server, flags=re.I)
            clean_server = re.sub(r'[^\w\s\[\]\-].*', '', clean_server).strip()
            clean_server = clean_server.rstrip('-').strip()

            # --- 2. REZOLUȚIE & RANK ---
            res_match = re.search(r'(\d{3,4}P|4K|2160P|1080P|720P)', t_up)
            q_val = res_match.group(1).lower() if res_match else "720p"
            res_label, res_rank = ("4K", 4) if "2160" in q_val or "4k" in q_val else (("FULL HD", 3) if "1080" in q_val else (("HD", 2) if "720" in q_val else ("SD", 1)))

            # --- 3. TEHNOLOGII IMAGINE ---
            img_list = []
            if any(x in t_up for x in [" DV", ".DV.", "DOVI", "DOLBY VISION"]): img_list.append("DV")
            if "HDR10+" in t_up: img_list.append("HDR10+")
            elif "HDR10" in t_up: img_list.append("HDR10")
            elif "HDR" in t_up: img_list.append("HDR")
            img_tech = " " + " ".join(img_list) if img_list else ""

            # --- 4. CODECURI ---
            v_codec = "HEVC" if any(x in t_up for x in ["HEVC", "H265", "X265"]) else "H264"
            a_codec = "AAC"
            if "ATMOS" in t_up: a_codec = "ATMOS"
            elif any(x in t_up for x in ["DD+", "EAC3", "DDP"]): a_codec = "DDP"
            elif "DTS" in t_up: a_codec = "DTS"

            # --- 5. DIMENSIUNE ---
            size_bytes = s.get('behaviorHints', {}).get('videoSize')
            if not size_bytes:
                s_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|MB)', t_up)
                if s_match:
                    val, unit = float(s_match.group(1)), s_match.group(2).upper()
                    size_bytes = val * (1024**3 if unit == 'GB' else 1024**2)
            
            size_gb = size_bytes / (1024**3) if size_bytes else 0
            size_display = f"{size_gb:.2f} GB" if size_gb >= 1 else f"{int(size_bytes/(1024**2))} MB" if size_bytes else ""

            # --- CONSTRUCȚIE LABEL-URI ---
            # Protecție la splitlines pentru a evita eroarea "surse active"
            title_parts = title.split('\n')
            label_top = f"[COLOR white]{title_parts[0].strip() if title_parts else 'Sursă'}[/COLOR]"
            p_file_name = getattr(self, 'provider', 'SURSA').upper()
            
            parts = [f"[COLOR yellow]{res_label}{img_tech}[/COLOR]", f"[COLOR orange]{v_codec}[/COLOR]", f"[COLOR cyan]{a_codec}[/COLOR]"]
            if size_display: parts.append(f"[COLOR green]{size_display}[/COLOR]")
            parts.append(f"[COLOR white]{clean_server}[/COLOR]")
            parts.append(f"[COLOR steelblue]{p_file_name}[/COLOR]")
            
            label_bottom = " | ".join(parts)

            sources_list.append({
                "label_top": label_top,
                "label_bottom": label_bottom,
                "url": f"{video_url}|User-Agent=Stremio/1.6.4",
                "filetype": file_type,
                "res_rank": res_rank,
                "size_bytes": size_bytes or 0
            })
        # Sortare descrescătoare obligatorie
        sources_list.sort(key=lambda x: (x['res_rank'], x['size_bytes']), reverse=True)
        return sources_list

    def _build_url(self, m_type, id_format):
        """ Logica de URL inteligent pentru a evita dublarea /stream/ """
        base = self.base_url.rstrip('/')
        path = "" if "/stream" in base else "/stream"
        return f"{base}{path}/{m_type}/{id_format}.json"

    def movie(self, title, year, imdb, simple_info, info):
        try:
            url = self._build_url("movie", imdb)
            r = requests.get(url, timeout=self.timeout)
            return self._process_item(r.json()) if r.status_code == 200 else []
        except: return []

    def episode(self, simple_info, info):
        try:
            imdb = info.get('info', {}).get('imdb_id') or info.get('info', {}).get('tvshow.imdb_id')
            sid = f"{imdb}:{simple_info['season_number']}:{simple_info['episode_number']}"
            url = self._build_url("series", sid)
            r = requests.get(url, timeout=self.timeout)
            return self._process_item(r.json()) if r.status_code == 200 else []
        except: return []
