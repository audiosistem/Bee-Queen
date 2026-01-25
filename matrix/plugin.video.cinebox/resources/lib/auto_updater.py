# -*- coding: utf-8 -*-
import os
import time
import threading
from datetime import datetime, timedelta
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

"""
Sistema de Atualização Automática - Cinebox
Versão: 3.1.0 (Enhanced)
Melhoria: Limpeza profunda de cache e atualização forçada no startup
Inspirado na arquitetura do IMDB TrainAgain
"""

def get_addon():
    return xbmcaddon.Addon()

def show_notification(title, message, icon=xbmcgui.NOTIFICATION_INFO, duration=5000):
    """Exibe uma notificação de forma garantida"""
    try:
        # Remove tags de cores para o título da notificação se necessário
        clean_title = title.replace('[COLOR red]', '').replace('[/COLOR]', '').replace('[COLOR yellow]', '')
        xbmcgui.Dialog().notification(clean_title, message, icon, duration, False)
    except:
        pass

class AutoUpdater:
    def __init__(self, monitor):
        self.monitor = monitor
        self.update_lock = threading.Lock()
        
        addon = get_addon()
        self.addon_id = addon.getAddonInfo('id')
        self.addon_name = addon.getAddonInfo('name')
        
        self.refresh_settings()
        self.last_update = self.get_last_update_time()
        self.is_running = False
        
        self.log_info(f"Inicializado - Enabled: {self.enabled}, Startup: {self.update_on_startup}, Interval: {self.interval_hours}h")

    def refresh_settings(self):
        try:
            addon = get_addon()
            self.enabled = addon.getSettingBool('auto_update_enabled')
            self.interval_hours = int(addon.getSetting('update_interval') or 5)
            self.update_on_startup = addon.getSettingBool('update_on_startup')
            self.show_notifications = addon.getSettingBool('show_update_notifications')
        except:
            self.enabled = True
            self.interval_hours = 5
            self.update_on_startup = True
            self.show_notifications = True

    def log_info(self, message):
        xbmc.log(f"[{self.addon_name} AutoUpdater] {message}", xbmc.LOGINFO)
    
    def log_error(self, message):
        xbmc.log(f"[{self.addon_name} AutoUpdater] ERROR - {message}", xbmc.LOGERROR)

    def get_last_update_time(self):
        try:
            addon_data_path = xbmcvfs.translatePath(f'special://profile/addon_data/{self.addon_id}/')
            update_file = os.path.join(addon_data_path, '.last_update')
            if os.path.exists(update_file):
                with open(update_file, 'r') as f:
                    return datetime.fromisoformat(f.read().strip())
            
            addon = get_addon()
            val = addon.getSetting('last_update_check')
            return datetime.fromisoformat(val) if val else None
        except:
            return None

    def set_last_update_time(self):
        try:
            now = datetime.now()
            addon_data_path = xbmcvfs.translatePath(f'special://profile/addon_data/{self.addon_id}/')
            os.makedirs(addon_data_path, exist_ok=True)
            with open(os.path.join(addon_data_path, '.last_update'), 'w') as f:
                f.write(now.isoformat())
            get_addon().setSetting('last_update_check', now.isoformat())
            self.last_update = now
        except Exception as e:
            self.log_error(f"Erro ao salvar timestamp: {e}")

    def is_update_needed(self):
        self.refresh_settings()
        if not self.enabled: return False
        if self.last_update is None: return True
        return (datetime.now() - self.last_update) >= timedelta(hours=self.interval_hours)

    def clear_deep_cache(self):
        """Limpa todos os caches possíveis para garantir novos conteúdos"""
        try:
            self.log_info("Iniciando limpeza profunda de cache...")
            
            # 1. Limpa cache de memória (Window Properties)
            window = xbmcgui.Window(10000)
            keys_to_clear = [
                'cinebox.movies.cache', 'cinebox.tvshows.cache', 'cinebox.trending.cache',
                'cinebox.movies.popular', 'cinebox.tvshows.popular'
            ]
            for key in keys_to_clear:
                window.clearProperty(key)
            
            # 2. Limpa cache do Banco de Dados (api_cache)
            try:
                from resources.lib.db.db import db_instance
                conn = db_instance._get_conn()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM api_cache")
                conn.commit()
                db_instance._release_conn(conn)
                # Limpa o SmartCache em memória também
                db_instance._cache.clear()
                self.log_info("✓ Cache do banco de dados limpo")
            except Exception as e:
                self.log_error(f"Erro ao limpar cache do DB: {e}")

            # 3. Limpa cache de módulos (main.py)
            try:
                import sys
                if 'main' in sys.modules:
                    main_mod = sys.modules['main']
                    if hasattr(main_mod, '_MODULE_CACHE'):
                        main_mod._MODULE_CACHE.clear()
                    if hasattr(main_mod, '_JSON_CACHE'):
                        main_mod._JSON_CACHE.clear()
                self.log_info("✓ Cache de módulos limpo")
            except:
                pass

            self.log_info("Limpeza profunda concluída.")
        except Exception as e:
            self.log_error(f"Erro geral na limpeza de cache: {e}")

    def update_content(self, reason="Periódica"):
        if not self.update_lock.acquire(blocking=False):
            self.log_info("Atualização já em curso.")
            return False
        
        try:
            self.refresh_settings()
            if not self.enabled: return False
            
            # Se estiver assistindo algo, espera o player parar (máximo 10 min de espera)
            wait_count = 0
            while xbmc.Player().isPlaying() and wait_count < 60:
                if self.monitor.waitForAbort(10): return False
                wait_count += 1
            
            self.log_info(f"Iniciando atualização ({reason})")
            
            if self.show_notifications:
                show_notification(self.addon_name, "Atualizando catálogo...", xbmcgui.NOTIFICATION_INFO)
            
            # Limpeza profunda antes de buscar novos dados
            self.clear_deep_cache()
            
            success = False
            try:
                from resources.lib.indexer import check_for_updates_silently
                check_for_updates_silently(get_addon())
                success = True
            except Exception as e:
                self.log_error(f"Falha no indexer: {e}")
            
            if success:
                self.set_last_update_time()
                if self.show_notifications:
                    show_notification(self.addon_name, "Catálogo atualizado!", xbmcgui.NOTIFICATION_INFO)
                
                # Força o Kodi a atualizar a listagem atual
                xbmc.executebuiltin('Container.Refresh')
                return True
            else:
                if self.show_notifications:
                    show_notification(self.addon_name, "Erro na atualização", xbmcgui.NOTIFICATION_ERROR)
                return False
        finally:
            self.update_lock.release()

    def worker(self):
        self.log_info("Worker iniciado.")
        
        # --- ATUALIZAÇÃO DE STARTUP ---
        # Aguarda 15 segundos para o Kodi estabilizar a rede e serviços
        if not self.monitor.waitForAbort(15):
            self.refresh_settings()
            if self.update_on_startup and self.enabled:
                self.log_info("Disparando atualização de startup...")
                self.update_content(reason="Startup")
        
        # --- LOOP PERIÓDICO ---
        while not self.monitor.waitForAbort(300): # A cada 5 minutos verifica se precisa
            if self.is_update_needed():
                self.update_content(reason="Agendada")
        
        self.log_info("Worker finalizado.")

    def start(self):
        if not self.is_running:
            self.is_running = True
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()

    def stop(self):
        self.is_running = False
