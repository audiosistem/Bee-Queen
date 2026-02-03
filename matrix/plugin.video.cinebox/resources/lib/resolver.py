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
        # ✅ NEW: Flag to track whether setResolvedUrl was called
        self.url_resolved = False

        # Clears old properties on startup
        xbmc.executebuiltin('ClearProperty(elementum_progress,home)')
        xbmc.executebuiltin('ClearProperty(elementum_status,home)')
        xbmc.executebuiltin('ClearProperty(resolve_status,home)')
        xbmc.executebuiltin('ClearProperty(CineboxStatus,home)')
        xbmc.executebuiltin('ClearProperty(CineboxProgress,home)')

        if self.item_data:
            fanart = self.item_data.get('backdrop') or self.item_data.get('episode_fanart') or ''
            clearlogo = self.item_data.get('clearlogo') or self.item_data.get('tvshow.clearlogo') or ''
            
            # ✅ DEFINITIVE FIX: If you don't have a logo yet, try searching via ListItem if available
            if not clearlogo:
                try:
                    # Try to get from the current ListItem (the one that triggered the playback)
                    clearlogo = xbmc.getInfoLabel('ListItem.Art(clearlogo)') or xbmc.getInfoLabel('ListItem.Art(tvshow.clearlogo)')
                except:
                    pass

            xbmc.log(f"[Cinebox] Resolver - Fanart: {fanart}", xbmc.LOGINFO)
            xbmc.log(f"[Cinebox] Resolver - Clearlogo: {clearlogo}", xbmc.LOGINFO)
            
            self.setProperty("info.title", self.item_data.get('title', 'Resolvendo Fonte...'))
            self.setProperty("info.fanart", fanart)
            self.setProperty("info.poster", self.item_data.get('poster', ''))
            self.setProperty("info.clearlogo", clearlogo)
            
            # Also defines them as global properties to ensure that the skin sees them if there is a refresh
            xbmc.executebuiltin(f'SetProperty(info.fanart,"{fanart}",home)')
            xbmc.executebuiltin(f'SetProperty(info.clearlogo,"{clearlogo}",home)')

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
                raise Exception("Failed to resolve the final URL.")

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
        """✅ FIXED V5: Force stop Elementum using HTTP /stop and PlayerControl"""
        xbmc.log("[Cinebox] Starting forced shutdown procedure of Elementum", xbmc.LOGINFO)
        
        # 1. Try to stop via HTTP (Elementum listens on port 65220)
        # This prevents Kodi's "NOT FOUND" error when trying to RunPlugin
        try:
            import requests
            # Elementum has a /stop endpoint that stops the download engine
            requests.get("http://127.0.0.1:65220/stop", params={'doresume': 'false'}, timeout=0.5)
            xbmc.log("[Cinebox] Comando /stop enviado via HTTP para o Elementum", xbmc.LOGINFO)
        except:
            # If HTTP fails, try RunPlugin as a fallback (even if it gives NOT FOUND in some versions)
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.elementum/stop)')

        # 2. Stop Kodi player and clean playlist
        try:
            xbmc.executebuiltin('PlayerControl(stop)')
            xbmc.executebuiltin('Playlist.Clear')
            xbmc.log("[Cinebox] PlayerControl(stop) e Playlist.Clear executed", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Cinebox] Error stopping player: {e}", xbmc.LOGDEBUG)
        
        # 3. Closes Elementum dialogs that may be blocking the process
        try:
            xbmc.executebuiltin('Dialog.Close(all, true)')
            xbmc.log("[Cinebox] Closed dialogues", xbmc.LOGINFO)
        except:
            pass
        
        # 4. Cleans Elementum properties
        try:
            window = xbmcgui.Window(10000)
            window.clearProperty('ElementumStatus')
            window.clearProperty('ElementumProgress')
            xbmc.executebuiltin('ClearProperty(elementum_progress,home)')
            xbmc.executebuiltin('ClearProperty(elementum_status,home)')
            xbmc.log("[Cinebox] Clean Elementum properties", xbmc.LOGINFO)
        except:
            pass

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
            # ✅ OPTIMIZATION: Reduced from 180s to 120s
            while not xbmc.Player().isPlaying() and (time.time() - start_kill < 120) and not self.cancelled:
                if xbmc.Monitor().abortRequested(): break
                
                # Closes by ID
                for d_id in dialog_ids:
                    if xbmcgui.getCurrentWindowDialogId() == d_id:
                        xbmc.executebuiltin(f'Dialog.Close({d_id}, true)')
                
                # Close by name
                for d_name in dialog_names:
                    xbmc.executebuiltin(f'Dialog.Close({d_name}, true)')
                
                xbmc.sleep(150) # ✅ OPTIMIZATION: Reduced frequency (100ms -> 150ms)

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
            
            # Known paths for Android (Kodi and Forks like WBMC)
            android_paths = [
                '/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/temp/kodi.log',
                '/storage/emulated/0/Android/data/tv.wonderbox.www/files/.kodi/temp/kodi.log',
                '/data/data/org.xbmc.kodi/files/.kodi/temp/kodi.log',
                '/data/data/tv.wonderbox.www/files/.kodi/temp/kodi.log',
                '/sdcard/Android/data/org.xbmc.kodi/files/.kodi/temp/kodi.log',
                '/sdcard/Android/data/tv.wonderbox.www/files/.kodi/temp/kodi.log',
                '/storage/emulated/0/.kodi/temp/kodi.log',
            ]
            log_paths.extend(android_paths)
            
            # Test each path
            for path in log_paths:
                try:
                    if os.path.exists(path) and os.path.isfile(path):
                        xbmc.log(f"[Cinebox] Log found in: {path}", xbmc.LOGINFO)
                        return path
                except:
                    pass
            
            xbmc.log(f"[Cinebox] No log file found. Paths tested: {log_paths}", xbmc.LOGWARNING)
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
                    
                    # ✅ OPTIMIZATION: Reduced from 100KB to 50KB (faster)
                    buffer_size = min(50000, file_size)
                    f.seek(file_size - buffer_size)
                    content = f.read()
                
                # Search for the last line with bufferTickerEvent
                lines = content.split('\n')
                for line in reversed(lines):
                    if 'bufferTickerEvent' in line and 'Buffer. Pr:' in line:
                        xbmc.log(f"[Cinebox] Buffer line found: {line[:100]}", xbmc.LOGDEBUG)
                        return line
                
                xbmc.log(f"[Cinebox] No buffer line found in the log", xbmc.LOGDEBUG)
                return None
            except Exception as e:
                xbmc.log(f"[Cinebox] Error reading log: {str(e)[:100]}", xbmc.LOGDEBUG)
                return None

        def monitor():
            xbmc.log("[Cinebox] Monitor thread started", xbmc.LOGINFO)
            if is_elementum:
                xbmc.log("[Cinebox] Elementum detected, starting progress monitoring", xbmc.LOGINFO)
                # Try to force Elementum not to show dialogs via property
                xbmc.executebuiltin('SetProperty(ElementumBackground,true,home)')
                xbmc.executebuiltin('SetProperty(resolve_status,Starting Elementum,home)')
                xbmc.executebuiltin('SetProperty(CineboxStatus,Starting Elementum,home)')
                
                # Start dialog killer in parallel
                threading.Thread(target=dialog_killer, daemon=True).start()

            player = xbmc.Player()
            start_time = time.time()
            last_status_info = {}
            log_path = get_kodi_log_path()
            
            xbmc.log(f"[Cinebox] Log path: {log_path}", xbmc.LOGINFO)
            xbmc.log(f"[Cinebox] Starting monitoring loop", xbmc.LOGINFO)

            loop_count = 0
            # Monitor WHILE downloading (before starting playback)
            while not player.isPlaying() and not self.cancelled:
                loop_count += 1
                if loop_count % 10 == 0:
                    xbmc.log(f"[Cinebox] Loop iteration {loop_count}", xbmc.LOGDEBUG)
                
                if xbmc.Monitor().abortRequested():
                    xbmc.log("[Cinebox] Abort requested", xbmc.LOGINFO)
                    self.cancelled = True
                    break
                
                if time.time() - start_time > 180:
                    xbmc.log("[Cinebox] Timeout de 180s", xbmc.LOGINFO)
                    break

                if is_elementum:
                    xbmc.log("[Cinebox] Inside the block is_elementum", xbmc.LOGDEBUG)
                    # If we still don't have data, let us know that it is being resolved.
                    if time.time() - start_time < 5:
                        xbmc.executebuiltin('SetProperty(CineboxStatus,Solving Magnetic Link...,home)')

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
                                
                                xbmc.log(f"[Cinebox] Progress detected: {progress}% - {download_speed}", xbmc.LOGINFO)
                                
                                # Format status with complete information
                                status_label = f"[COLOR red]Buffering[/COLOR] ({progress}%)\nD:{download_speed} U:{upload_speed} S:{seeds}/{peers}"
                                resolve_status = f"[COLOR red]Buffering[/COLOR] ({progress}%)"
                                
                                # Store in cache
                                last_status_info = {
                                    'progress': progress,
                                    'status_label': status_label,
                                    'resolve_status': resolve_status
                                }

                                # Clear local properties before setting new ones to avoid "ghosting"
                                self.clearProperty('CineboxStatus')
                                self.clearProperty('resolve_status')
                                
                                # Sets GLOBAL properties
                                xbmc.executebuiltin(f"SetProperty(elementum_progress,{progress},home)")
                                xbmc.executebuiltin(f"SetProperty(has_elementum_data,true,home)")
                                status_escaped = status_label.replace('"', '\\"').replace("'", "\\'")
                                resolve_escaped = resolve_status.replace('"', '\\"').replace("'", "\\'")
                                xbmc.executebuiltin(f"SetProperty(CineboxStatus,\"{status_escaped}\",home)")
                                xbmc.executebuiltin(f"SetProperty(resolve_status,\"{resolve_escaped}\",home)")
                                
                                # Defines in the dialog window also with refresh
                                try:
                                    self.setProperty('elementum_progress', str(progress))
                                    self.setProperty('CineboxStatus', status_label)
                                    self.setProperty('resolve_status', resolve_status)
                                    # Force window refresh
                                    xbmc.executebuiltin('UpdateWindow()')
                                except Exception as e:
                                    xbmc.log(f"[Cinebox] Error setting property: {e}", xbmc.LOGWARNING)
                                
                                # DIRECT UPDATE OF CONTROLS BY ID
                                try:
                                    # ✅ FIX: Check if the control exists before trying to use
                                    # ID 1001 is the default for status, 1003 may not exist on all skins
                                    for cid in [1001, 1003]:
                                        try:
                                            control = self.getControl(cid)
                                            if control:
                                                control.setText(status_label)
                                        except:
                                            pass
                                except Exception as e:
                                    xbmc.log(f"[Cinebox] Error updating status controls: {e}", xbmc.LOGDEBUG)
                                
                                # Progress is updated via the 'elementum_progress' property on the skin
                                pass
                                
                                found_status = True
                    
                    if not found_status:
                        elapsed = int(time.time() - start_time)
                        xbmc.log(f"[Cinebox] Waiting for Elementum... (tentativa {elapsed}s)", xbmc.LOGDEBUG)
                        # If we have cached information, show it
                        if last_status_info:
                            xbmc.executebuiltin(f"SetProperty(elementum_progress,{last_status_info.get('progress', 0)},home)")
                            xbmc.executebuiltin(f"SetProperty(resolve_status,{last_status_info.get('resolve_status', 'Waiting for Elementum...')},home)")
                            xbmc.executebuiltin(f"SetProperty(CineboxStatus,{last_status_info.get('status_label', 'Waiting for Elementum...')},home)")
                        else:
                            xbmc.executebuiltin('SetProperty(resolve_status,Waiting for Elementum...,home)')
                            xbmc.executebuiltin('SetProperty(CineboxStatus,Waiting for Elementum...,home)')
                    else:
                        xbmc.log("[Cinebox] Status encontrado!", xbmc.LOGDEBUG)

                xbmc.sleep(1000)
            
            # ✅ FIX V6: If canceled, ensures signal reaches main thread
            if self.cancelled:
                xbmc.log("[Cinebox] Cancellation detected on the monitor, aborting playback", xbmc.LOGINFO)
                self.kill_elementum_process()
                self.url_resolved = False
            else:
                # Only marks as resolved if the player actually started or timed out
                if xbmc.Player().isPlaying():
                    xbmc.log("[Cinebox] Player started, ending monitoring", xbmc.LOGINFO)
                    self.url_resolved = True
                else:
                    self.url_resolved = False
            
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
        
        # CRITICAL FIX: Wait for thread monitor to check cancellation
        # Wait up to 5 seconds for the thread monitor to initialize
        start_wait = time.time()
        while not self.url_resolved and not self.cancelled and (time.time() - start_wait < 5):
            time.sleep(0.1)
        
        # ✅ FIX V6: Complete playback blocking after cancellation
        if not self.cancelled:
            xbmc.log("[Cinebox] Chamando setResolvedUrl", xbmc.LOGINFO)
            xbmcplugin.setResolvedUrl(handle=self.handle, succeeded=True, listitem=play_item)
        else:
            xbmc.log("[Cinebox] Cancellation detected, sending failure to Kodi to stop the player", xbmc.LOGINFO)
            # Returning succeeded=False with an empty ListItem is the signal for Kodi to abort the player
            xbmcplugin.setResolvedUrl(handle=self.handle, succeeded=False, listitem=xbmcgui.ListItem())
            
            # Force an additional stop on the player if Kodi has already started the process
            xbmc.sleep(500)
            xbmc.executebuiltin('PlayerControl(stop)')
            xbmc.executebuiltin('Playlist.Clear')

    def onClick(self, controlId):
        """✅ NEW: Detects clicks on dialog buttons"""
        xbmc.log(f"[Cinebox] Click detected on the controller: {controlId}", xbmc.LOGINFO)
        # If there is a close button (commonly ID 10 or custom)
        if controlId in (10, 100, 101): # Common IDs for close/cancel buttons
            self.cancelled = True
            if self.is_torrent_source:
                self.kill_elementum_process()
            self.close()

    def onAction(self, action):
        """✅ IMPROVED V4: Detects Elementum IMMEDIATE cancellation and force stop"""
        # Cancellation action IDs (Back, Menu, Stop, etc.)
        # Added ACTION_SELECT_ITEM (7) if it is on a close button
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PARENT_DIR, xbmcgui.ACTION_STOP, xbmcgui.ACTION_PREVIOUS_MENU):
            xbmc.log(f"[Cinebox] Cancellation action detected (ID: {action.getId()})", xbmc.LOGINFO)
            self.cancelled = True
            
            if self.is_torrent_source:
                xbmc.log("[Cinebox] Cancelling Elementum download...", xbmc.LOGINFO)
                self.kill_elementum_process()
            
            self.close()
    
    def onDeinit(self):
        """✅ NEW: Captures window deinit event (WindowXMLDialog) and for Elementum"""
        xbmc.log("[Cinebox] onDeinit called - Closing resolution window", xbmc.LOGINFO)
        
        # Mark as canceled
        self.cancelled = True
        
        # If it's a torrent source, kill Elementum
        if self.is_torrent_source:
            xbmc.log("[Cinebox] Stopping Elementum in onDestroy", xbmc.LOGINFO)
            try:
                self.kill_elementum_process()
                time.sleep(0.3)
                player = xbmc.Player()
                if player.isPlaying():
                    player.stop()
                xbmc.executebuiltin('PlayerControl(stop)')
                xbmc.log("[Cinebox] Element stuck on onDestroy", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"[Cinebox] Error stopping Elementum in onDestroy: {e}", xbmc.LOGWARNING)
        
        # Clean properties
        xbmc.executebuiltin('ClearProperty(elementum_progress,home)')
        xbmc.executebuiltin('ClearProperty(elementum_status,home)')
        xbmc.executebuiltin('ClearProperty(resolve_status,home)')
        xbmc.executebuiltin('ClearProperty(CineboxStatus,home)')
        xbmc.executebuiltin('ClearProperty(CineboxProgress,home)')
        xbmc.log("[Cinebox] onDeinit completed", xbmc.LOGINFO)
