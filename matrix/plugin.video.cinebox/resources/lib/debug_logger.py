# -*- coding: utf-8 -*-
"""
Módulo de Debug Logger para Cinebox
Registra logs detalhados para diagnóstico de problemas
"""

import xbmc
import xbmcaddon
import xbmcvfs
import os
import time
from datetime import datetime
import traceback
import json

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

class DebugLogger:
    """
    Logger personalizado para debug detalhado
    """
    
    def __init__(self):
        self.addon = ADDON
        self._refresh_settings()
        
        # Definir caminho do arquivo de log
        try:
            profile_dir = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        except AttributeError:
            profile_dir = xbmc.translatePath(self.addon.getAddonInfo('profile'))
        
        if not os.path.exists(profile_dir):
            try:
                os.makedirs(profile_dir)
            except:
                pass
        
        self.log_file = os.path.join(profile_dir, 'cinebox_debug.log')
        
        # Níveis de log
        self.levels = {
            'Básico': 1,
            'Médio': 2,
            'Completo': 3
        }

    def _refresh_settings(self):
        """Recarrega as configurações do addon"""
        # Forçar recarregamento das configurações do addon
        try:
            self.enabled = self.addon.getSettingBool('debug.enabled')
            self.level = self.addon.getSettingString('debug.level')
            self.scrapers_debug = self.addon.getSettingBool('debug.scrapers')
            self.network_debug = self.addon.getSettingBool('debug.network')
            self.save_to_file = self.addon.getSettingBool('debug.save_to_file')
        except:
            # Fallback caso o addon não esteja totalmente carregado
            self.enabled = True
            self.level = 'Médio'
            self.scrapers_debug = True
            self.network_debug = True
            self.save_to_file = True
        
        levels = {'Básico': 1, 'Médio': 2, 'Completo': 3}
        self.current_level = levels.get(self.level, 2)
    
    def _should_log(self, min_level=1):
        """Verifica se deve registrar o log baseado no nível"""
        # Sempre logar erros e avisos no log do Kodi para facilitar diagnóstico
        if min_level <= 1:
            return True
        self._refresh_settings()
        return self.enabled and self.current_level >= min_level
    
    def _format_message(self, category, message, level='INFO'):
        """Formata a mensagem de log"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        return f"[{timestamp}] [{ADDON_NAME}] [{category}] [{level}] {message}"
    
    def _write_to_file(self, formatted_message):
        """Escreve no arquivo de log"""
        if not self.save_to_file:
            return
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(formatted_message + '\n')
        except Exception as e:
            xbmc.log(f"[{ADDON_NAME}] Erro ao escrever no arquivo de log: {e}", xbmc.LOGERROR)
    
    def _log(self, category, message, kodi_level, min_level=1):
        """Método interno de log"""
        # Forçar log no Kodi para categorias importantes
        force_kodi = category.startswith('SCRAPER') or category == 'NETWORK' or kodi_level >= xbmc.LOGWARNING
        
        should_log = self._should_log(min_level)
        
        if not should_log and not force_kodi:
            return
        
        level_name = {
            xbmc.LOGDEBUG: 'DEBUG',
            xbmc.LOGINFO: 'INFO',
            xbmc.LOGWARNING: 'WARNING',
            xbmc.LOGERROR: 'ERROR',
            xbmc.LOGFATAL: 'FATAL'
        }.get(kodi_level, 'INFO')
        
        formatted = self._format_message(category, message, level_name)
        
        # Log no Kodi (sempre se for forçado ou se o nível permitir)
        if force_kodi or should_log:
            xbmc.log(formatted, kodi_level)
        
        # Log em arquivo (apenas se habilitado nas configurações)
        if should_log:
            self._write_to_file(formatted)
    
    def debug(self, category, message, min_level=3):
        """Log de debug (apenas nível Completo)"""
        self._log(category, message, xbmc.LOGDEBUG, min_level)
    
    def info(self, category, message, min_level=1):
        """Log de informação (todos os níveis)"""
        self._log(category, message, xbmc.LOGINFO, min_level)
    
    def warning(self, category, message, min_level=1):
        """Log de aviso (todos os níveis)"""
        self._log(category, message, xbmc.LOGWARNING, min_level)
    
    def error(self, category, message, min_level=1):
        """Log de erro (todos os níveis)"""
        self._log(category, message, xbmc.LOGERROR, min_level)
    
    def exception(self, category, message):
        """Log de exceção com traceback completo"""
        if not self.enabled:
            return
        
        tb = traceback.format_exc()
        full_message = f"{message}\n{tb}"
        self._log(category, full_message, xbmc.LOGERROR, 1)
    
    def scraper(self, scraper_name, message, min_level=2):
        """Log específico para scrapers"""
        if not self.scrapers_debug:
            return
        self._log(f"SCRAPER:{scraper_name}", message, xbmc.LOGINFO, min_level)
    
    def network(self, url, method='GET', status=None, headers=None, response=None):
        """Log específico para requisições de rede"""
        if not self.network_debug:
            return
        
        message = f"{method} {url}"
        if status:
            message += f" - Status: {status}"
        if headers and self.current_level >= 3:
            message += f"\nHeaders: {json.dumps(headers, indent=2)}"
        if response and self.current_level >= 3:
            # Limitar tamanho da resposta
            resp_str = str(response)[:500]
            message += f"\nResponse: {resp_str}..."
        
        self._log("NETWORK", message, xbmc.LOGDEBUG, 2)
    
    def scraper_sources(self, scraper_name, sources_count, sources_sample=None):
        """Log de fontes encontradas por scraper"""
        if not self.scrapers_debug:
            return
        
        message = f"Encontradas {sources_count} fontes"
        
        if sources_sample and self.current_level >= 2:
            message += f"\nAmostra: {json.dumps(sources_sample[:3], indent=2, ensure_ascii=False)}"
        
        self._log(f"SCRAPER:{scraper_name}", message, xbmc.LOGINFO, 2)
    
    def scraper_error(self, scraper_name, error, url=None):
        """Log de erro de scraper"""
        if not self.scrapers_debug:
            return
        
        message = f"Erro: {str(error)}"
        if url:
            message += f"\nURL: {url}"
        if self.current_level >= 3:
            message += f"\n{traceback.format_exc()}"
        
        self._log(f"SCRAPER:{scraper_name}", message, xbmc.LOGERROR, 1)
    
    def clear_log(self):
        """Limpa o arquivo de log"""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
            self.info("DEBUG", "Arquivo de log limpo com sucesso")
            return True
        except Exception as e:
            self.error("DEBUG", f"Erro ao limpar log: {e}")
            return False
    
    def get_log_content(self, lines=100):
        """Retorna as últimas N linhas do log"""
        try:
            if not os.path.exists(self.log_file):
                return "Nenhum log disponível"
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"Erro ao ler log: {e}"
    
    def get_log_size(self):
        """Retorna o tamanho do arquivo de log"""
        try:
            if os.path.exists(self.log_file):
                size = os.path.getsize(self.log_file)
                # Converter para KB ou MB
                if size < 1024:
                    return f"{size} bytes"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.2f} KB"
                else:
                    return f"{size / (1024 * 1024):.2f} MB"
            return "0 bytes"
        except:
            return "Desconhecido"

# Instância global
logger = DebugLogger()
