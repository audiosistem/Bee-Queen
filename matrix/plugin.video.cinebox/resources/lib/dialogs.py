# -*- coding: utf-8 -*-
import xbmcgui
import xbmc
import re

ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92

class DialogSelecaoFontes(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.item_data = kwargs.get('item_data')
        self.escolha = None
        self.todas_as_fontes = kwargs.get('fontes', [])
        
        # === LISTITEMS CACHE (OTIMIZATION) ===
        self._listitem_cache = {}
        
        # NEW: Flag to track cancellation
        self.cancelled = False
        
        # === PRE-PROCESS QUALITIES/LANGUAGES/PROVIDERS ===
        self._pre_processar_filtros()
        
        # Current filters
        self.filtro_atual = "All"
        self.filtro_idioma_atual = "All"
        self.filtro_provedor_atual = "All"
    
    def _pre_processar_filtros(self):
        """Preprocess ALL sources ONCE in init.
        Extracts qualities, languages ​​and providers."""
        qualidades_set = set()
        idiomas_set = set()
        provedores_set = set()
        
        for fonte in self.todas_as_fontes:
            # Standardized quality
            q = self._normalizar_qualidade(fonte.get('quality_label', ''))
            qualidades_set.add(q)
            
            # Languages ​​- Simplified and robust menu logic
            langs = fonte.get('languages', 'LEG')
            # Manual mapping to ensure clean menu names
            if 'EN-US' in langs or '[EN]' in langs: idiomas_set.add('EN-US')
            if 'PT-BR' in langs or '[BR]' in langs: idiomas_set.add('PT-BR')
            if 'DUAL' in langs or '[DUAL]' in langs: idiomas_set.add('DUAL')
            if 'LEG' in langs or '[EN]' in langs: idiomas_set.add('LEG')
            if 'ITA' in langs or '[IT]' in langs: idiomas_set.add('ITA')
            if 'SPA' in langs or '[ES]' in langs: idiomas_set.add('SPA')
            if 'FRE' in langs or '[FR]' in langs: idiomas_set.add('FRE')
            if 'GER' in langs or '[DE]' in langs: idiomas_set.add('GER')
            if 'JAP' in langs or '[JP]' in langs: idiomas_set.add('JAP')
            
            # Provider
            provider = fonte.get('provider', '').strip()
            if provider:
                provedores_set.add(provider)
        
        # Order qualities
        ordem_qualidade = ["4K", "1080p", "720p", "SD", "CAM", "scr", "sd", "Others"]
        self.qualidades_disponiveis = ["All"] + sorted(
            qualidades_set,
            key=lambda q: ordem_qualidade.index(q) if q in ordem_qualidade else 99
        )
        
        self.idiomas_disponiveis = ["All"] + sorted(idiomas_set)
        if len(self.idiomas_disponiveis) == 1:
            self.idiomas_disponiveis.append("Original")
        
        self.provedores_disponiveis = ["All"] + sorted(provedores_set)
    
    @staticmethod
    def limpar_tags_kodi(texto):
        """Remove Kodi tags (, [B], etc) robustly"""
        if not texto:
            return ""
        # Remove tags [COLOR hex], [COLOR name], [/COLOR], [B], [/B], [I], [/I]
        texto = re.sub(r'\[COLOR.*?\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[/COLOR\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[/?B\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[/?I\]', '', texto, flags=re.IGNORECASE)
        return texto.strip()
    
    def _normalizar_qualidade(self, q_string):
        """Normalize quality string (with cache)"""
        q_clean = self.limpar_tags_kodi(q_string).upper()
        
        # Check order (more specific first)
        if '4K' in q_clean or '2160' in q_clean:
            return "4K"
        if '1080' in q_clean:
            return "1080p"
        if '720' in q_clean:
            return "720p"
        if 'CAM' in q_clean or 'CAMRIP' in q_clean:
            return "CAM"
        if 'SCR' in q_clean or 'SCREENER' in q_clean:
            return "scr"
        if '480' in q_clean or 'SD' in q_clean or 'DVD' in q_clean:
            return "sd"
        
        # If you did not identify any of the qualities above, return "Others"
        # This will make Kodi look for resolution/Outros.png
        return "Others"
    
    def _criar_listitem(self, fonte):
        """Creates ListItem with optimized cache and label."""
       # Unique key for cache
        cache_key = str(fonte.get('url', '')) or str(id(fonte))
    
        if cache_key in self._listitem_cache:
            return self._listitem_cache[cache_key]
    
        # Create new ListItem
        li = xbmcgui.ListItem(label="")  # Empty label, let's set it later
    
        # Properties (keep for filters/other uses)
        qualidade_limpa = self._normalizar_qualidade(fonte.get('quality_label', ''))
        
        # Helper to guarantee string
        def s(v): return str(v) if v is not None else ""

        li.setProperty('quality', s(qualidade_limpa))
        li.setProperty('release_title', s(fonte.get('display_title')))
        # Ensures that 'seeders' only has the number for the XML, while 'seeders_label' has the color
        seeds_raw = str(fonte.get('seeders', '0'))
        # ✅ FORCES THE VALUE IN PROPERTY TO XML
        li.setProperty('seeders', seeds_raw)
        li.setProperty('seeders_label', s(fonte.get('seeders_label')))
        li.setProperty('size', s(fonte.get('size')))
        li.setProperty('provider', s(fonte.get('provider')))
        li.setProperty('hoster', s(fonte.get('hoster', fonte.get('provider'))))
        li.setProperty('languages', s(fonte.get('languages')))
        li.setProperty('url_para_tocar', s(fonte.get('url')))
        li.setProperty('video_info', s(fonte.get('video_info')))
        li.setProperty('source', s(fonte.get('source', '')))
        li.setProperty('codec', s(fonte.get('codec', '')))
        li.setProperty('hdr', s(fonte.get('hdr', '')))
        li.setProperty('audio', s(fonte.get('audio', '')))
    
        # ===== CREATE OPTIMIZED LABEL =====
        title = fonte.get('display_title', 'Untitled')
    
        # Creates compact technical string
        tech_parts = []
    
        # Quality
        if qualidade_limpa and qualidade_limpa != "Others":
            tech_parts.append(f"[B][COLOR FF3399FF]{qualidade_limpa}[/COLOR][/B]")
    
        # Codec
        codec = fonte.get('codec', '')
        if codec:
            tech_parts.append(f"[COLOR FFFFCC00]{codec}[/COLOR]")
    
        # HDR (only if it is HDR)
        hdr = fonte.get('hdr', '')
        if hdr and hdr.upper() != 'SDR':
            tech_parts.append(f"[COLOR FF00FF00]{hdr}[/COLOR]")
    
        # Audio (abbreviated)
        audio = fonte.get('audio', '')
        if audio:
            audio_short = self._abreviar_audio(audio)
            tech_parts.append(f"[COLOR FF66CCFF]{audio_short}[/COLOR]")
    
        # Source
        source = fonte.get('source', '')
        if source:
            tech_parts.append(f"[COLOR FFCC66FF]{source}[/COLOR]")
    
        # Putting technical parts together
        tech_str = ""
        if tech_parts:
            tech_str = " | ".join(tech_parts) + "\n"
    
        # Seed and size info
        stats_parts = []
        seeders = fonte.get('seeders_label', '')
        if seeders:
            stats_parts.append(f"Seeds: [B]{seeders}[/B]")
    
        size = fonte.get('size', '')
        # Filter invalid size values
        if size and size not in ['N/A', 'n/a', '', '0 B', '0.0 B', '0 KB', '0.0 KB']:
            stats_parts.append(f"Tamanho: [B]{size}[/B]")
    
        stats_str = " | ".join(stats_parts)
    
        # Provider, Hoster and language
        provider = fonte.get('provider', '')
        hoster = fonte.get('hoster', provider)
        languages = fonte.get('languages', '')
        
        meta_str = ""
        if provider or languages:
            meta_parts = []
        if provider:
            if hoster != provider:
                meta_parts.append(f"Hoster: [B][COLOR FF00FFFF]{hoster}[/COLOR][/B] (via {provider})")
            else:
                meta_parts.append(f"Site: [B][COLOR FF00FFFF]{provider}[/COLOR][/B]")
        if languages:
            meta_parts.append(f"Idioma: [B]{languages}[/B]")
        meta_str = " | ".join(meta_parts)
    
        # Final label (3 lines maximum)
        label_lines = []
    
        # Line 1: Technical information
        if tech_str.strip():
            label_lines.append(tech_str.strip())
    
        # Line 2: Main title
        label_lines.append(f"[B]{title}[/B]")
    
        # Line 3: Stats + metadata
        line3_parts = []
        if stats_str:
            line3_parts.append(stats_str)
        if meta_str:
            line3_parts.append(meta_str)
    
        if line3_parts:
            label_lines.append(" | ".join(line3_parts))
    
        # Put it all together
        final_label = "\n".join(label_lines)
        li.setLabel(final_label)
    
        # Saves to cache
        self._listitem_cache[cache_key] = li
    
        return li

    def _abreviar_audio(self, audio_string):
        """Abbreviates common audio strings to save space"""
        audio_lower = audio_string.lower()
    
        # Abbreviation mapping
        abbrev_map = {
           'dolby digital': 'DD',
           'dd 5.1': 'DD5.1',
           'ac3': 'DD',
           'dolby atmos': 'Atmos',
           'dts-hd master audio': 'DTS-HD',
           'dts-hd': 'DTS-HD',
           'dts': 'DTS',
           'aac': 'AAC',
           'truehd': 'TrueHD',
           'flac': 'FLAC',
           'mp3': 'MP3',
           'opus': 'Opus'
       }
    
       # Search for matches
        for key, abbrev in abbrev_map.items():
            if key in audio_lower:
                return abbrev
    
        # If not found, returns first 6 characters
        return audio_string[:6]
    
    def _atualizar_labels_filtros(self):
        """Update filter button labels"""
        try:
            q = self.filtro_atual if self.filtro_atual != "All" else "Quality"
            i = self.filtro_idioma_atual if self.filtro_idioma_atual != "All" else "Language"
            p = self.filtro_provedor_atual if self.filtro_provedor_atual != "All" else "Provider"
            
            self.getControl(1300).setLabel(q)
            self.getControl(1400).setLabel(i)
            self.getControl(1500).setLabel(p)
        except Exception as e:
            xbmc.log(f"[Dialogs] Error updating labels: {e}", xbmc.LOGERROR)
    
    def onInit(self):
        """Dialog initialization"""
        try:
            # Background art
            if self.item_data:
                self.setProperty('info.fanart', self.item_data.get('backdrop', ''))
                self.setProperty('info.poster', self.item_data.get('poster', ''))
            
            # Update labels
            self._atualizar_labels_filtros()
            
            # Popula list (first time)
            self.popular_lista_fontes()
            
            # Focus on the first filter
            self.setFocusId(1300)
            
        except Exception as e:
            xbmc.log(f"[Dialogs] Error in onInit: {e}", xbmc.LOGERROR)
    
    def popular_lista_fontes(self):
        """Populates font list (OPTIMIZED).
        Uses ListItems cache + quick filter."""
        try:
            lista_control = self.getControl(1000)
            lista_control.reset()
            
            # === OPTIMIZED FILTER (one pass) ===
            fontes_filtradas = []
            
            for fonte in self.todas_as_fontes:
                # Quality filter
                if self.filtro_atual != "All":
                    if self._normalizar_qualidade(fonte.get('quality_label', '')) != self.filtro_atual:
                        continue
                
                # Language filter - Direct comparison with what has been added to the set
                if self.filtro_idioma_atual != "All":
                    lang_data = fonte.get('languages', '')
                    # If the filter is "PT-BR", it must match if the data has "PT-BR" or "[BR]"
                    match_map = {
                        'EN-US': ['EN-US', '[EN]'],
                        'PT-BR': ['PT-BR', '[BR]'],
                        'DUAL': ['DUAL', '[DUAL]'],
                        'LEG': ['LEG', '[EN]'],
                        'ITA': ['ITA', '[IT]'],
                        'SPA': ['SPA', '[ES]'],
                        'FRE': ['FRE', '[FR]'],
                        'GER': ['GER', '[DE]'],
                        'JAP': ['JAP', '[JP]']
                    }
                    
                    allowed_terms = match_map.get(self.filtro_idioma_atual, [self.filtro_idioma_atual])
                    if not any(term in lang_data for term in allowed_terms):
                        continue
                
                # Provider filter
                if self.filtro_provedor_atual != "All":
                    if fonte.get('provider', '') != self.filtro_provedor_atual:
                        continue
                
                fontes_filtradas.append(fonte)
            
            # === ADD ITEMS (using cache) ===
            for fonte in fontes_filtradas:
                li = self._criar_listitem(fonte)
                lista_control.addItem(li)
            
        except Exception as e:
            xbmc.log(f"[Dialogs] Error when popular list: {e}", xbmc.LOGERROR)
    
    def onClick(self, controlId):
        """Click handler"""
        dialog = xbmcgui.Dialog()
        
        if controlId == 1000:
            # Font selection
            item = self.getControl(1000).getSelectedItem()
            if item:
                self.escolha = item.getProperty('url_para_tocar')
                self.close()
        
        elif controlId == 1300:
            # Quality filter
            escolha_idx = dialog.select('Filtrar por Qualidade', self.qualidades_disponiveis)
            if escolha_idx > -1:
                self.filtro_atual = self.qualidades_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()
        
        elif controlId == 1400:
            # Language filter
            escolha_idx = dialog.select('Filtrar por Idioma', self.idiomas_disponiveis)
            if escolha_idx > -1:
                self.filtro_idioma_atual = self.idiomas_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()
        
        elif controlId == 1500:
            # Provider filter
            escolha_idx = dialog.select('Filter by Provider', self.provedores_disponiveis)
            if escolha_idx > -1:
                self.filtro_provedor_atual = self.provedores_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()
    
    def onAction(self, action):
        """Action handler (back, esc, etc)"""
        if action.getId() in [ACTION_PREVIOUS_MENU, ACTION_NAV_BACK]:
            # NEW: Mark as canceled before closing
            self.cancelled = True
            xbmc.log("[Dialogs] Usuario cancelou a selecao de fontes", xbmc.LOGINFO)
            self.close()

# ==========================================================
# NEW: EXTERNAL SCRAPERS CONFIGURATION
# ==========================================================

def configure_external_scrapers():
    """Opens a menu to choose which external scraper to use.
    Automatically detects scrapers installed on Kodi.
    Saves the choice in JSON AND in Kodi settings."""
    import xbmcaddon
    import xbmcvfs
    import os
    try:
        from .config_manager import set_enabled_scraper
    except ImportError:
        from resources.lib.config_manager import set_enabled_scraper
    
    ADDON = xbmcaddon.Addon()
    
    # Detect installed scrapers
    try:
        addons_path = xbmcvfs.translatePath('special://home/addons/')
    except AttributeError:
        addons_path = xbmc.translatePath('special://home/addons/')
    
    scrapers = []
    
    if os.path.exists(addons_path):
        for item in os.listdir(addons_path):
            # Search for script.module.* which are scrapers
            if item.startswith('script.module.'):
                full_path = os.path.join(addons_path, item)
                addon_xml = os.path.join(full_path, 'addon.xml')
                
                # Try to get the friendly name
                display_name = item
                if os.path.exists(addon_xml):
                    try:
                        with open(addon_xml, 'r', encoding='utf-8') as f:
                            content = f.read()
                            import re
                            name_match = re.search(r'name="([^"]+)"', content)
                            if name_match:
                                display_name = name_match.group(1)
                    except:
                        pass
                
                scrapers.append({
                    'id': item,
                    'name': display_name
                })
    
    if not scrapers:
        xbmcgui.Dialog().notification("CINEBOX TrainAgain", "No scrapers found!")
        xbmc.log("[Cinebox] No scraper found", xbmc.LOGERROR)
        return
    
    # Sort by name
    scrapers.sort(key=lambda x: x['name'].lower())
    
    # Get current scraper
    current_scraper = ADDON.getSetting('enabled_external_scrapers')
    # Remove colors if they exist
    if '[COLOR' in current_scraper:
        current_scraper = current_scraper.replace('[COLOR lime]', '').replace('[/COLOR]', '')
    
    current_index = -1
    
    scraper_names = [s['name'] for s in scrapers]
    scraper_ids = [s['id'] for s in scrapers]
    
    if current_scraper:
        try:
            current_index = scraper_ids.index(current_scraper)
        except ValueError:
            current_index = -1
    
    xbmc.log(f"[Cinebox] Scrapers found: {scraper_ids}", xbmc.LOGINFO)
    xbmc.log(f"[Cinebox] Current scraper: {current_scraper}", xbmc.LOGINFO)
    
    # Open selection dialog
    dialog = xbmcgui.Dialog()
    selected = dialog.select(
        "Choose External Scraper:",
        scraper_names,
        preselect=current_index
    )
    
    xbmc.log(f"[Cinebox] User selection: {selected}", xbmc.LOGINFO)
    
    if selected >= 0:
        selected_id = scraper_ids[selected]
        selected_name = scraper_names[selected]
        
        # Save to JSON (config_manager)
        set_enabled_scraper(selected_id)
        
        # Also save in Kodi's settings.xml with green color
        colored_value = f"[COLOR lime]{selected_id}[/COLOR]"
        ADDON.setSetting('enabled_external_scrapers', colored_value)
        
        # Check if it was saved
        saved_value = ADDON.getSetting('enabled_external_scrapers')
        xbmc.log(f"[Cinebox] Attempt to save: {selected_id}", xbmc.LOGINFO)
        xbmc.log(f"[Cinebox] Value saved in Kodi: {saved_value}", xbmc.LOGINFO)
        
        msg = f"Scraper selecionado: {selected_name}"
        xbmcgui.Dialog().notification("CINEBOX [COLOR red]TrainAgain[/COLOR]", msg)
        xbmc.log(f"[Cinebox] Scraper configured: {selected_id}", xbmc.LOGINFO)
