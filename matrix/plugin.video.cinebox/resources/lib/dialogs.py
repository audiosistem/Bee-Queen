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
        
        # === CACHE DE LISTITEMS (OTIMIZACAO) ===
        self._listitem_cache = {}
        
        # NOVO: Flag para rastrear cancelamento
        self.cancelled = False
        
        # === PRE-PROCESSA QUALIDADES/IDIOMAS/PROVEDORES ===
        self._pre_processar_filtros()
        
        # Filtros atuais
        self.filtro_atual = "Todos"
        self.filtro_idioma_atual = "Todos"
        self.filtro_provedor_atual = "Todos"
    
    def _pre_processar_filtros(self):
        """
        Pré-processa TODAS as fontes UMA VEZ no init.
        Extrai qualidades, idiomas e provedores.
        """
        qualidades_set = set()
        idiomas_set = set()
        provedores_set = set()
        
        for fonte in self.todas_as_fontes:
            # Qualidade normalizada
            q = self._normalizar_qualidade(fonte.get('quality_label', ''))
            qualidades_set.add(q)
            
            # Idiomas - Lógica simplificada e robusta para o menu
            langs = fonte.get('languages', 'LEG')
            # Mapeamento manual para garantir nomes limpos no menu
            if 'PT-BR' in langs or '[BR]' in langs: idiomas_set.add('PT-BR')
            if 'DUAL' in langs or '[DUAL]' in langs: idiomas_set.add('DUAL')
            if 'LEG' in langs or '[EN]' in langs: idiomas_set.add('LEG')
            if 'ITA' in langs or '[IT]' in langs: idiomas_set.add('ITA')
            if 'SPA' in langs or '[ES]' in langs: idiomas_set.add('SPA')
            if 'FRE' in langs or '[FR]' in langs: idiomas_set.add('FRE')
            if 'GER' in langs or '[DE]' in langs: idiomas_set.add('GER')
            if 'JAP' in langs or '[JP]' in langs: idiomas_set.add('JAP')
            
            # Provedor
            provider = fonte.get('provider', '').strip()
            if provider:
                provedores_set.add(provider)
        
        # Ordena qualidades
        ordem_qualidade = ["4K", "1080p", "720p", "SD", "CAM", "scr", "sd", "Outros"]
        self.qualidades_disponiveis = ["Todos"] + sorted(
            qualidades_set,
            key=lambda q: ordem_qualidade.index(q) if q in ordem_qualidade else 99
        )
        
        self.idiomas_disponiveis = ["Todos"] + sorted(idiomas_set)
        if len(self.idiomas_disponiveis) == 1:
            self.idiomas_disponiveis.append("Original")
        
        self.provedores_disponiveis = ["Todos"] + sorted(provedores_set)
    
    @staticmethod
    def limpar_tags_kodi(texto):
        """Remove tags Kodi ([COLOR], [B], etc) de forma robusta"""
        if not texto:
            return ""
        # Remove tags [COLOR hex], [COLOR name], [/COLOR], [B], [/B], [I], [/I]
        texto = re.sub(r'\[COLOR.*?\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[/COLOR\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[/?B\]', '', texto, flags=re.IGNORECASE)
        texto = re.sub(r'\[/?I\]', '', texto, flags=re.IGNORECASE)
        return texto.strip()
    
    def _normalizar_qualidade(self, q_string):
        """Normaliza string de qualidade (com cache)"""
        q_clean = self.limpar_tags_kodi(q_string).upper()
        
        # Ordem de verificação (mais específico primeiro)
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
        
        # Se não identificou nenhuma das qualidades acima, retorna "Outros"
        # Isso fará com que o Kodi procure por resolution/Outros.png
        return "Outros"
    
    def _criar_listitem(self, fonte):
        """
        Cria ListItem com cache e label otimizado.
        """
       # Chave única para cache
        cache_key = str(fonte.get('url', '')) or str(id(fonte))
    
        if cache_key in self._listitem_cache:
            return self._listitem_cache[cache_key]
    
        # Cria novo ListItem
        li = xbmcgui.ListItem(label="")  # Label vazio, vamos setar depois
    
        # Properties (mantenha para filtros/outros usos)
        qualidade_limpa = self._normalizar_qualidade(fonte.get('quality_label', ''))
        
        # Helper para garantir string
        def s(v): return str(v) if v is not None else ""

        li.setProperty('quality', s(qualidade_limpa))
        li.setProperty('release_title', s(fonte.get('display_title')))
        # Garante que 'seeders' tenha apenas o número para o XML, enquanto 'seeders_label' tem a cor
        seeds_raw = str(fonte.get('seeders', '0'))
        # ✅ FORÇA O VALOR NO PROPERTY PARA O XML
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
    
        # ===== CRIA LABEL OTIMIZADO =====
        title = fonte.get('display_title', 'Sem título')
    
        # Cria string técnica compacta
        tech_parts = []
    
        # Qualidade
        if qualidade_limpa and qualidade_limpa != "Outros":
            tech_parts.append(f"[B][COLOR FF3399FF]{qualidade_limpa}[/COLOR][/B]")
    
        # Codec
        codec = fonte.get('codec', '')
        if codec:
            tech_parts.append(f"[COLOR FFFFCC00]{codec}[/COLOR]")
    
        # HDR (só se for HDR)
        hdr = fonte.get('hdr', '')
        if hdr and hdr.upper() != 'SDR':
            tech_parts.append(f"[COLOR FF00FF00]{hdr}[/COLOR]")
    
        # Áudio (abreviado)
        audio = fonte.get('audio', '')
        if audio:
            audio_short = self._abreviar_audio(audio)
            tech_parts.append(f"[COLOR FF66CCFF]{audio_short}[/COLOR]")
    
        # Source
        source = fonte.get('source', '')
        if source:
            tech_parts.append(f"[COLOR FFCC66FF]{source}[/COLOR]")
    
        # Juntar partes técnicas
        tech_str = ""
        if tech_parts:
            tech_str = " | ".join(tech_parts) + "\n"
    
        # Info de seeds e tamanho
        stats_parts = []
        seeders = fonte.get('seeders_label', '')
        if seeders:
            stats_parts.append(f"Seeds: [B]{seeders}[/B]")
    
        size = fonte.get('size', '')
        # Filtrar valores inválidos de tamanho
        if size and size not in ['N/A', 'n/a', '', '0 B', '0.0 B', '0 KB', '0.0 KB']:
            stats_parts.append(f"Tamanho: [B]{size}[/B]")
    
        stats_str = " | ".join(stats_parts)
    
        # Provider, Hoster e idioma
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
    
        # Label final (3 linhas máximo)
        label_lines = []
    
        # Linha 1: Info técnica
        if tech_str.strip():
            label_lines.append(tech_str.strip())
    
        # Linha 2: Título principal
        label_lines.append(f"[B]{title}[/B]")
    
        # Linha 3: Stats + metadata
        line3_parts = []
        if stats_str:
            line3_parts.append(stats_str)
        if meta_str:
            line3_parts.append(meta_str)
    
        if line3_parts:
            label_lines.append(" | ".join(line3_parts))
    
        # Junta tudo
        final_label = "\n".join(label_lines)
        li.setLabel(final_label)
    
        # Salva no cache
        self._listitem_cache[cache_key] = li
    
        return li

    def _abreviar_audio(self, audio_string):
        """Abrevia strings de áudio comuns para economizar espaço"""
        audio_lower = audio_string.lower()
    
        # Mapeamento de abreviações
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
    
       # Procura por correspondências
        for key, abbrev in abbrev_map.items():
            if key in audio_lower:
                return abbrev
    
        # Se não encontrar, retorna primeiros 6 caracteres
        return audio_string[:6]
    
    def _atualizar_labels_filtros(self):
        """Atualiza labels dos botões de filtro"""
        try:
            q = self.filtro_atual if self.filtro_atual != "Todos" else "Qualidade"
            i = self.filtro_idioma_atual if self.filtro_idioma_atual != "Todos" else "Idioma"
            p = self.filtro_provedor_atual if self.filtro_provedor_atual != "Todos" else "Provedor"
            
            self.getControl(1300).setLabel(q)
            self.getControl(1400).setLabel(i)
            self.getControl(1500).setLabel(p)
        except Exception as e:
            xbmc.log(f"[Dialogs] Erro ao atualizar labels: {e}", xbmc.LOGERROR)
    
    def onInit(self):
        """Inicialização do dialog"""
        try:
            # Arte de fundo
            if self.item_data:
                self.setProperty('info.fanart', self.item_data.get('backdrop', ''))
                self.setProperty('info.poster', self.item_data.get('poster', ''))
            
            # Atualiza labels
            self._atualizar_labels_filtros()
            
            # Popula lista (primeira vez)
            self.popular_lista_fontes()
            
            # Foco no primeiro filtro
            self.setFocusId(1300)
            
        except Exception as e:
            xbmc.log(f"[Dialogs] Erro no onInit: {e}", xbmc.LOGERROR)
    
    def popular_lista_fontes(self):
        """
        Popula lista de fontes (OTIMIZADO).
        Usa cache de ListItems + filtro rápido.
        """
        try:
            lista_control = self.getControl(1000)
            lista_control.reset()
            
            # === FILTRO OTIMIZADO (uma passagem) ===
            fontes_filtradas = []
            
            for fonte in self.todas_as_fontes:
                # Filtro de qualidade
                if self.filtro_atual != "Todos":
                    if self._normalizar_qualidade(fonte.get('quality_label', '')) != self.filtro_atual:
                        continue
                
                # Filtro de idioma - Comparação direta com o que foi adicionado ao set
                if self.filtro_idioma_atual != "Todos":
                    lang_data = fonte.get('languages', '')
                    # Se o filtro é "PT-BR", ele deve bater se o dado tiver "PT-BR" ou "[BR]"
                    match_map = {
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
                
                # Filtro de provedor
                if self.filtro_provedor_atual != "Todos":
                    if fonte.get('provider', '') != self.filtro_provedor_atual:
                        continue
                
                fontes_filtradas.append(fonte)
            
            # === ADICIONA ITENS (usando cache) ===
            for fonte in fontes_filtradas:
                li = self._criar_listitem(fonte)
                lista_control.addItem(li)
            
        except Exception as e:
            xbmc.log(f"[Dialogs] Erro ao popular lista: {e}", xbmc.LOGERROR)
    
    def onClick(self, controlId):
        """Handler de cliques"""
        dialog = xbmcgui.Dialog()
        
        if controlId == 1000:
            # Seleção de fonte
            item = self.getControl(1000).getSelectedItem()
            if item:
                self.escolha = item.getProperty('url_para_tocar')
                self.close()
        
        elif controlId == 1300:
            # Filtro de qualidade
            escolha_idx = dialog.select('Filtrar por Qualidade', self.qualidades_disponiveis)
            if escolha_idx > -1:
                self.filtro_atual = self.qualidades_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()
        
        elif controlId == 1400:
            # Filtro de idioma
            escolha_idx = dialog.select('Filtrar por Idioma', self.idiomas_disponiveis)
            if escolha_idx > -1:
                self.filtro_idioma_atual = self.idiomas_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()
        
        elif controlId == 1500:
            # Filtro de provedor
            escolha_idx = dialog.select('Filtrar por Provedor', self.provedores_disponiveis)
            if escolha_idx > -1:
                self.filtro_provedor_atual = self.provedores_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()
    
    def onAction(self, action):
        """Handler de ações (back, esc, etc)"""
        if action.getId() in [ACTION_PREVIOUS_MENU, ACTION_NAV_BACK]:
            # NOVO: Marca como cancelado antes de fechar
            self.cancelled = True
            xbmc.log("[Dialogs] Usuario cancelou a selecao de fontes", xbmc.LOGINFO)
            self.close()

# ============================================
# NOVO: CONFIGURAÇÃO DE SCRAPERS EXTERNOS
# ============================================

def configure_external_scrapers():
    """
    Abre um menu para escolher qual scraper externo usar.
    Detecta automaticamente os scrapers instalados no Kodi.
    Salva a escolha em JSON E nas configurações do Kodi.
    """
    import xbmcaddon
    import xbmcvfs
    import os
    try:
        from .config_manager import set_enabled_scraper
    except ImportError:
        from resources.lib.config_manager import set_enabled_scraper
    
    ADDON = xbmcaddon.Addon()
    
    # Detectar scrapers instalados
    try:
        addons_path = xbmcvfs.translatePath('special://home/addons/')
    except AttributeError:
        addons_path = xbmc.translatePath('special://home/addons/')
    
    scrapers = []
    
    if os.path.exists(addons_path):
        for item in os.listdir(addons_path):
            # Procura por script.module.* que são scrapers
            if item.startswith('script.module.'):
                full_path = os.path.join(addons_path, item)
                addon_xml = os.path.join(full_path, 'addon.xml')
                
                # Tenta pegar o nome amigável
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
        xbmcgui.Dialog().notification("CINEBOX [COLOR red]TrainAgain[/COLOR]", "Nenhum scraper encontrado!")
        xbmc.log("[Cinebox] Nenhum scraper encontrado", xbmc.LOGERROR)
        return
    
    # Ordenar por nome
    scrapers.sort(key=lambda x: x['name'].lower())
    
    # Obter scraper atual
    current_scraper = ADDON.getSetting('enabled_external_scrapers')
    # Remove cores se existirem
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
    
    xbmc.log(f"[Cinebox] Scrapers encontrados: {scraper_ids}", xbmc.LOGINFO)
    xbmc.log(f"[Cinebox] Scraper atual: {current_scraper}", xbmc.LOGINFO)
    
    # Abrir diálogo de seleção
    dialog = xbmcgui.Dialog()
    selected = dialog.select(
        "Escolha o Scraper Externo:",
        scraper_names,
        preselect=current_index
    )
    
    xbmc.log(f"[Cinebox] Seleção do usuário: {selected}", xbmc.LOGINFO)
    
    if selected >= 0:
        selected_id = scraper_ids[selected]
        selected_name = scraper_names[selected]
        
        # Salvar em JSON (config_manager)
        set_enabled_scraper(selected_id)
        
        # Salvar também no settings.xml do Kodi com cor verde
        colored_value = f"[COLOR lime]{selected_id}[/COLOR]"
        ADDON.setSetting('enabled_external_scrapers', colored_value)
        
        # Verificar se foi salvo
        saved_value = ADDON.getSetting('enabled_external_scrapers')
        xbmc.log(f"[Cinebox] Tentativa de salvar: {selected_id}", xbmc.LOGINFO)
        xbmc.log(f"[Cinebox] Valor salvo no Kodi: {saved_value}", xbmc.LOGINFO)
        
        msg = f"Scraper selecionado: {selected_name}"
        xbmcgui.Dialog().notification("CINEBOX [COLOR red]TrainAgain[/COLOR]", msg)
        xbmc.log(f"[Cinebox] Scraper configurado: {selected_id}", xbmc.LOGINFO)
