# -*- coding: utf-8 -*-
import xbmcgui
import xbmc
import xbmcplugin
import sys
import threading
import time
import json
import requests
import re
import os
import subprocess
from urllib.parse import quote_plus
from typing import Callable, Optional

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

class CineboxPlayer(xbmc.Player):
    def __init__(self, callback: Callable[[], None]):
        xbmc.Player.__init__(self)
        self.callback = callback

    def onPlayBackStarted(self):
        xbmc.log("[CineboxPlayer] Playback started. Closing resolver...", xbmc.LOGINFO)
        self.callback()

class CineboxResolverWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_url = kwargs.get('source_url')
        self.item_data = kwargs.get('item_data')
        self.resolved_url = None
        self.handle = kwargs.get('handle', int(sys.argv[1]))
        self.is_torrent_source = False
        self.player: Optional[CineboxPlayer] = None
        
        # ✅ NEW: Flag to track if it has been canceled
        self.cancelled = False
        self.elementum_process_id = None

        # Clears old properties on startup
        xbmc.executebuiltin('ClearProperty(elementum_progress,home)')
        xbmc.executebuiltin('ClearProperty(elementum_status,home)')
        xbmc.executebuiltin('ClearProperty(resolve_status,home)')
        xbmc.executebuiltin('ClearProperty(CineboxStatus,home)')
        xbmc.executebuiltin('ClearProperty(CineboxProgress,home)')

        if self.item_data:
            fanart = self.item_data.get('backdrop') or self.item_data.get('episode_fanart') or ''
            clearlogo = self.item_data.get('clearlogo') or self.item_data.get('tvshow.clearlogo') or ''

            self.setProperty("info.title", self.item_data.get('title', 'Resolvendo Fonte...'))
            self.setProperty("info.fanart", fanart)
            self.setProperty("info.poster", self.item_data.get('poster', ''))
            self.setProperty("info.clearlogo", clearlogo)
            
            # Also defines them as global properties to ensure that the skin sees them if there is a refresh
            xbmc.executebuiltin(f'SetProperty(info.fanart,{fanart},home)')
            xbmc.executebuiltin(f'SetProperty(info.clearlogo,{clearlogo},home)')

    def onInit(self):
        threading.Thread(target=self.start_resolution_process, daemon=True).start()

    def start_resolution_process(self):
        xbmc.log("[Cinebox] start_resolution_process started", xbmc.LOGINFO)
        time.sleep(0.5)
        try:
            xbmc.log("[Cinebox] Starting URL resolution", xbmc.LOGINFO)
            xbmc.executebuiltin('SetProperty(resolve_status,Searching for information...,home)')
            final_url, item_info = self.resolve_url_logic(self.source_url, self.item_data)

            if not final_url:
                raise Exception("Falha ao resolver a URL final.")

            self.resolved_url = final_url
            xbmc.executebuiltin('SetProperty(resolve_status,Carregando player...,home)')
            xbmc.log(f"[Cinebox] URL final: {final_url}", xbmc.LOGINFO)
            self.play_resolved_source(final_url, item_info)

        except Exception as e:
            xbmc.executebuiltin('SetProperty(resolve_status,Error resolving,home)')
            xbmc.log(f"[CineboxResolver] ERROR: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Cinebox", "Error resolving source.", xbmcgui.NOTIFICATION_ERROR, 5000)
            self.close()

    def resolve_url_logic(self, url, item_info):
        final_url = url
        if url.startswith('magnet:') or (len(url) == 40 and not url.startswith('http')):
            self.is_torrent_source = True
            magnet_uri = url if url.startswith('magnet:') else f"magnet:?xt=urn:btih:{url}"
            encoded_uri = quote_plus(magnet_uri)
            tmdb_id = item_info.get('tmdb_id')
            media_type = item_info.get('media_type')
            final_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
            if tmdb_id:
                final_url += f"&tmdb={tmdb_id}"
            if media_type == 'tvshow':
                season = item_info.get('season')
                episode = item_info.get('episode')
                if season is not None and episode is not None:
                    final_url += f"&season={season}&episode={episode}"
        return final_url, item_info

    def _create_listitem(self, final_url, item_info):
        play_item = xbmcgui.ListItem(path=final_url)
        info_labels = {
            'title': item_info.get('episode_title', item_info.get('title', 'Playback')),
            'mediatype': item_info.get('media_type', 'video'),
        }
        play_item.setInfo('video', info_labels)
        play_item.setArt({
            'thumb': item_info.get('episode_poster') or item_info.get('poster') or '',
            'poster': item_info.get('poster') or '',
            'fanart': item_info.get('backdrop') or '',
            'clearlogo': item_info.get('clearlogo') or '',
        })
        play_item.setProperty('IsPlayable', 'true')
        return play_item

    def kill_elementum_process(self):
        """✅ NEW V2: Kills Elementum process aggressively"""
        xbmc.log("[Cinebox] Tentando matar processo do Elementum", xbmc.LOGINFO)
        try:
            # Try to kill via pkill (more reliable)
            subprocess.run(['pkill', '-f', 'elementum'], timeout=2)
            xbmc.log("[Cinebox] pkill elementum executado", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Cinebox] pkill falhou: {e}", xbmc.LOGDEBUG)
        
        try:
            # Try to kill via killall
            subprocess.run(['killall', 'elementum'], timeout=2)
            xbmc.log("[Cinebox] killall elementum executado", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Cinebox] killall falhou: {e}", xbmc.LOGDEBUG)

    def play_resolved_source(self, final_url, item_info):
        play_item = self._create_listitem(final_url, item_info)
        
        # Start monitoring BEFORE calling setResolvedUrl to suppress dialogs
        is_elementum = "plugin.video.elementum" in final_url

        def dialog_killer():
            """Dedicated thread to close unwanted dialogs as quickly as possible."""
            if not is_elementum: return
            
            # Common dialog IDs we want to suppress
            dialog_ids = [10101, 10151, 10100, 10150]
            dialog_names = ['extendedprogressdialog', 'progressdialog', 'busydialog']
            
            start_kill = time.time()
            while not xbmc.Player().isPlaying() and (time.time() - start_kill < 180) and not self.cancelled:
                if xbmc.Monitor().abortRequested(): break
                
                # Closes by ID
                for d_id in dialog_ids:
                    if xbmcgui.getCurrentWindowDialogId() == d_id:
                        xbmc.executebuiltin(f'Dialog.Close({d_id}, true)')
                
                # Close by name
                for d_name in dialog_names:
                    xbmc.executebuiltin(f'Dialog.Close({d_name}, true)')
                
                xbmc.sleep(100) # Checks every 100ms

        def get_kodi_log_path():
            """Gets the path of the Kodi log file with multiple retries"""
            log_paths = []
            
            try:
                # Try to get it via xbmc.translatePath
                log_path = xbmc.translatePath('special://logpath/')
                if log_path and os.path.isdir(log_path):
                    log_paths.append(os.path.join(log_path, 'kodi.log'))
            except:
                pass
            
            # Known paths for Android
            android_paths = [
                '/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/temp/kodi.log',
                '/data/data/org.xbmc.kodi/files/.kodi/temp/kodi.log',
                '/sdcard/Android/data/org.xbmc.kodi/files/.kodi/temp/kodi.log',
                '/storage/emulated/0/.kodi/temp/kodi.log',
            ]
            log_paths.extend(android_paths)
            
            # Test each path
            for path in log_paths:
                try:
                    if os.path.exists(path) and os.path.isfile(path):
                        xbmc.log(f"[Cinebox] Log encontrado em: {path}", xbmc.LOGINFO)
                        return path
                except:
                    pass
            
            xbmc.log(f"[Cinebox] Nenhum arquivo de log encontrado. Caminhos testados: {log_paths}", xbmc.LOGWARNING)
            return None

        def parse_elementum_buffer_info(log_line):
            """Extracts Elementum buffer information from the log"""
            try:
                # Extracts progress: Pr: 43%
                pr_match = re.search(r'Pr:\s*(\d+)%', log_line)
                progress = int(pr_match.group(1)) if pr_match else 0
                
                # Extracts Speed: Sp: 71 kB / 0 B
                sp_match = re.search(r'Sp:\s*([\d.]+\s*[KMG]?B)\s*/\s*([\d.]+\s*[KMG]?B)', log_line)
                download_speed = sp_match.group(1).strip() if sp_match else "0 B"
                upload_speed = sp_match.group(2).strip() if sp_match else "0 B"
                
                # Extracts connections: Con: 4/7 + 1/35
                con_match = re.search(r'Con:\s*(\d+)/(\d+)\s*\+\s*(\d+)/(\d+)', log_line)
                if con_match:
                    seeds = int(con_match.group(1))
                    peers = int(con_match.group(3))
                else:
                    seeds = peers = 0
                
                return {
                    'progress': progress,
                    'download_speed': download_speed,
                    'upload_speed': upload_speed,
                    'seeds': seeds,
                    'peers': peers,
                    'valid': True
                }
            except Exception as e:
                xbmc.log(f"[Cinebox] Error parsing buffer info: {e}", xbmc.LOGDEBUG)
                return None

        def read_last_elementum_buffer_line(log_path):
            """Read the last Elementum buffer event from the log file"""
            try:
                if not log_path or not os.path.exists(log_path):
                    xbmc.log(f"[Cinebox] Log file does not exist: {log_path}", xbmc.LOGDEBUG)
                    return None
                
                # Open the file and read the last lines
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Go to the end of the file
                    f.seek(0, 2)
                    file_size = f.tell()
                    
                    # Reads the last 100KB (enlarged for more history)
                    buffer_size = min(100000, file_size)
                    f.seek(file_size - buffer_size)
                    content = f.read()
                
                # Search for the last line with bufferTickerEvent
                lines = content.split('\n')
                for line in reversed(lines):
                    if 'bufferTickerEvent' in line and 'Buffer. Pr:' in line:
                        xbmc.log(f"[Cinebox] Buffer line encontrada: {line[:100]}", xbmc.LOGDEBUG)
                        return line
                
                xbmc.log(f"[Cinebox] Nenhuma linha de buffer encontrada no log", xbmc.LOGDEBUG)
                return None
            except Exception as e:
                xbmc.log(f"[Cinebox] Error reading log: {str(e)[:100]}", xbmc.LOGDEBUG)
                return None

        def monitor():
            xbmc.log("[Cinebox] Monitor thread started", xbmc.LOGINFO)
            if is_elementum:
                xbmc.log("[Cinebox] Detectado Elementum, iniciando monitoramento de progresso", xbmc.LOGINFO)
                # Try to force Elementum not to show dialogs via property
                xbmc.executebuiltin('SetProperty(ElementumBackground,true,home)')
                xbmc.executebuiltin('SetProperty(resolve_status,Iniciando Elementum...,home)')
                xbmc.executebuiltin('SetProperty(CineboxStatus,Iniciando Elementum...,home)')
                
                # Start dialog killer in parallel
                threading.Thread(target=dialog_killer, daemon=True).start()

            player = xbmc.Player()
            start_time = time.time()
            last_status_info = {}
            log_path = get_kodi_log_path()
            
            xbmc.log(f"[Cinebox] Caminho do log: {log_path}", xbmc.LOGINFO)
            xbmc.log(f"[Cinebox] Iniciando loop de monitoramento", xbmc.LOGINFO)

            loop_count = 0
            # Monitor WHILE downloading (before starting playback)
            while not player.isPlaying() and not self.cancelled:
                loop_count += 1
                if loop_count % 10 == 0:
                    xbmc.log(f"[Cinebox] Loop iteration {loop_count}", xbmc.LOGDEBUG)
                
                if xbmc.Monitor().abortRequested():
                    xbmc.log("[Cinebox] Abort solicitado", xbmc.LOGINFO)
                    self.cancelled = True
                    break
                
                if time.time() - start_time > 180:
                    xbmc.log("[Cinebox] Timeout de 180s", xbmc.LOGINFO)
                    break

                if is_elementum:
                    xbmc.log("[Cinebox] Dentro do bloco is_elementum", xbmc.LOGDEBUG)
                    # If we still don't have data, let us know that it is being resolved.
                    if time.time() - start_time < 5:
                        xbmc.executebuiltin('SetProperty(CineboxStatus,Resolving Magnetic Link...,home)')

                    found_status = False
                    
                    # Try reading log information
                    if log_path:
                        buffer_line = read_last_elementum_buffer_line(log_path)
                        if buffer_line:
                            buffer_info = parse_elementum_buffer_info(buffer_line)
                            if buffer_info and buffer_info.get('valid'):
                                progress = buffer_info.get('progress', 0)
                                download_speed = buffer_info.get('download_speed', '0 B')
                                upload_speed = buffer_info.get('upload_speed', '0 B')
                                seeds = buffer_info.get('seeds', 0)
                                peers = buffer_info.get('peers', 0)
                                
                                xbmc.log(f"[Cinebox] Progresso detectado: {progress}% - {download_speed}", xbmc.LOGINFO)
                                
                                # Format status with complete information
                                status_label = f"Buffering ({progress}%)\nD:{download_speed} U:{upload_speed} S:{seeds}/{peers}"
                                resolve_status = f"Buffering ({progress}%)"
                                
                                # Store in cache
                                last_status_info = {
                                    'progress': progress,
                                    'status_label': status_label,
                                    'resolve_status': resolve_status
                                }

                                # Sets GLOBAL properties
                                xbmc.executebuiltin(f"SetProperty(elementum_progress,{progress},home)")
                                status_escaped = status_label.replace('"', '\\"').replace("'", "\\'")
                                resolve_escaped = resolve_status.replace('"', '\\"').replace("'", "\\'")
                                xbmc.executebuiltin(f"SetProperty(CineboxStatus,\"{status_escaped}\",home)")
                                xbmc.executebuiltin(f"SetProperty(resolve_status,\"{resolve_escaped}\",home)")
                                
                                # Defines in the dialog window as well
                                try:
                                    self.setProperty('elementum_progress', str(progress))
                                    self.setProperty('CineboxStatus', status_label)
                                    self.setProperty('resolve_status', resolve_status)
                                except Exception as e:
                                    xbmc.log(f"[Cinebox] Error when setProperty: {e}", xbmc.LOGWARNING)
                                
                                # DIRECT UPDATE OF CONTROLS BY ID
                                try:
                                    self.getControl(1001).setText(status_label)
                                    self.getControl(1003).setPercent(progress)
                                except Exception as e:
                                    xbmc.log(f"[Cinebox] Error updating controls: {e}", xbmc.LOGWARNING)
                                
                                found_status = True
                    
                    if not found_status:
                        elapsed = int(time.time() - start_time)
                        xbmc.log(f"[Cinebox] Aguardando Elementum... (tentativa {elapsed}s)", xbmc.LOGDEBUG)
                        # If we have cached information, show it
                        if last_status_info:
                            xbmc.executebuiltin(f"SetProperty(elementum_progress,{last_status_info.get('progress', 0)},home)")
                            xbmc.executebuiltin(f"SetProperty(resolve_status,{last_status_info.get('resolve_status', 'Aguardando Elementum...')},home)")
                            xbmc.executebuiltin(f"SetProperty(CineboxStatus,{last_status_info.get('status_label', 'Aguardando Elementum...')},home)")
                        else:
                            xbmc.executebuiltin('SetProperty(resolve_status,Aguardando Elementum...,home)')
                            xbmc.executebuiltin('SetProperty(CineboxStatus,Aguardando Elementum...,home)')
                    else:
                        xbmc.log("[Cinebox] Status encontrado!", xbmc.LOGDEBUG)

                xbmc.sleep(1000)
            
            # ✅ NEW V3: If canceled, kills the Elementum process and stops the player
            if self.cancelled:
                xbmc.log("[Cinebox] Cancellation detected on monitor, forcing stop", xbmc.LOGINFO)
                try:
                    self.kill_elementum_process()
                    time.sleep(0.3)
                    player = xbmc.Player()
                    if player.isPlaying():
                        player.stop()
                    xbmc.executebuiltin('PlayerControl(stop)')
                    xbmc.log("[Cinebox] Forced stop executed", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[Cinebox] Forced stop error: {e}", xbmc.LOGWARNING)
            
            # Clears properties when finished
            xbmc.executebuiltin('ClearProperty(elementum_progress,home)')
            xbmc.executebuiltin('ClearProperty(elementum_status,home)')
            xbmc.executebuiltin('ClearProperty(resolve_status,home)')
            xbmc.executebuiltin('ClearProperty(CineboxStatus,home)')
            xbmc.executebuiltin('ClearProperty(CineboxProgress,home)')
            
            if player.isPlaying() or time.time() - start_time > 180:
                self.close()

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        
        time.sleep(0.2)
        xbmcplugin.setResolvedUrl(handle=self.handle, succeeded=True, listitem=play_item)

    def onAction(self, action):
        """✅ IMPROVED V3: Detects cancellation and force stopping of Elementum"""
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PARENT_DIR, xbmcgui.ACTION_STOP):
            xbmc.log("[Cinebox] Cancel action detected", xbmc.LOGINFO)
            self.cancelled = True
            
            # To Elementum immediately
            if self.is_torrent_source:
                xbmc.log("[Cinebox] Forcing Elementum to stop on cancellation", xbmc.LOGINFO)
                try:
                    # Kills the Elementum process FIRST
                    self.kill_elementum_process()
                    xbmc.log("[Cinebox] Processo Elementum morto", xbmc.LOGINFO)
                    
                    # Wait a bit to make sure it's dead
                    time.sleep(0.5)
                    
                    # For the player
                    player = xbmc.Player()
                    if player.isPlaying():
                        player.stop()
                        xbmc.log("[Cinebox] Player parado", xbmc.LOGINFO)
                    
                    # Execute command to close any active playback
                    xbmc.executebuiltin('PlayerControl(stop)')
                    xbmc.log("[Cinebox] PlayerControl(stop) executado", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[Cinebox] Error stopping Elementum: {e}", xbmc.LOGWARNING)
            
            self.close()
