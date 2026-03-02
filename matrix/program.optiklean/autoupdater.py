# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Simone Bianchelli
# OptiKlean - Kodi Cleaning and Optimization Addon

import os
import json
import urllib.request
import urllib.parse
import re
import shutil
import zipfile
import hashlib
import glob
from datetime import datetime, timedelta
from distutils.version import LooseVersion

import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui

class AutoUpdater:
    # 1. Configurazione GitLab
    GITLAB_PROJECT_PATH = "personal4143605/optiklean"  # Formato: "user_or_group/repo"
    GITLAB_BRANCH = "main"                            # Branch di default
    GITLAB_ACCESS_TOKEN = ""  # nosec B105 - Empty string for public repos, not a hardcoded password
    ADDON_ZIP_NAME = "program.optiklean.zip"          # nome dello zip dell'addon
    
    # 2. Costanti derivate (NON MODIFICARE MANUALMENTE)
    GITLAB_API_BASE = "https://gitlab.com/api/v4"
    GITLAB_PROJECT_URL = f"{GITLAB_API_BASE}/projects/{urllib.parse.quote(GITLAB_PROJECT_PATH, safe='')}"
    
    # 3. Configurazione aggiornamenti
    MAX_DOWNLOAD_RETRY = 3      # Numero massimo di tentativi di download
    @property
    def update_check_interval(self):
        """Restituisce l'intervallo di controllo aggiornamenti (in ore) scelto dall'utente"""
        try:
            interval = int(self.addon.getSetting("update_check_interval"))
            if interval < 1:
                return 24  # fallback di sicurezza
            return interval
        except Exception as e:
            xbmc.log(f"OptiKlean: Errore lettura update_check_interval: {str(e)}", xbmc.LOGWARNING)
            return 24  # fallback di sicurezza

    def __init__(self):
        # Configurazione addon
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')
        self.current_version = self.addon.getAddonInfo('version')
        
        # Percorsi file system
        self.addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.profile_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.commit_file = os.path.join(self.profile_path, 'last_commit.json')
        self.temp_dir = os.path.join(self.profile_path, 'temp')

        # Configurazione logo
        media_path = os.path.join(self.addon_path, 'resources', 'media')
        self.logo_path = os.path.join(media_path, 'logo.png')

        # Crea cartelle se non esistono
        self._ensure_directories()
            
        # Log di verifica configurazione
        xbmc.log(f"OptiKlean: GitLab project: {self.GITLAB_PROJECT_PATH}", xbmc.LOGDEBUG)
        xbmc.log(f"OptiKlean: Addon path: {self.addon_path}", xbmc.LOGDEBUG)
        xbmc.log(f"OptiKlean: Current version: {self.current_version}", xbmc.LOGDEBUG)

    def _ensure_directories(self):
        """Assicura che tutte le directory necessarie esistano"""
        for path in [self.profile_path, self.temp_dir]:
            if not xbmcvfs.exists(path):
                xbmcvfs.mkdirs(path)
                xbmc.log(f"OptiKlean: Created directory {path}", xbmc.LOGDEBUG)

    def _is_auto_update_enabled(self):
        """Safe getter for update setting with fallback"""
        try:
            return self.addon.getSettingBool("enable_auto_updates")
        except Exception as e:
            xbmc.log(f"OptiKlean: Settings error, using default (True): {str(e)}", xbmc.LOGERROR)
            return True  # Default safe value

    def _extract_version(self, message):
        """Estrae la versione dal commit message"""
        patterns = [
            r'\[?v\.?(\d+\.\d+\.\d+)\]?',  # [v1.2.3], v1.2.3, v.1.2.3
            r'\b(\d+\.\d+\.\d+)\b'         # 1.2.3 isolato
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match
        return None

    def _load_commit_data(self):
        """Carica i dati del commit dal file JSON"""
        try:
            if os.path.exists(self.commit_file):
                with open(self.commit_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            xbmc.log(f"OptiKlean: Error loading commit data: {str(e)}", xbmc.LOGERROR)
            return {}

    def _save_commit_data(self, commit_id, gitlab_version):
        """Salva i nuovi dati del commit"""
        data = {
            "commit_id": commit_id,
            "local_version": self.current_version,
            "gitlab_version": gitlab_version,
            "last_check": datetime.now().isoformat(),
            "kodi_version": xbmc.getInfoLabel('System.BuildVersion')
        }
        
        try:
            with open(self.commit_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            xbmc.log(f"OptiKlean: Error saving commit data: {str(e)}", xbmc.LOGERROR)

    def _get_latest_commit(self):
        """Recupera l'ultimo commit che ha modificato program.optiklean.zip da GitLab"""
        try:
            url = (
                f"{self.GITLAB_PROJECT_URL}/repository/commits"
                f"?ref_name={self.GITLAB_BRANCH}&per_page=1&path={self.ADDON_ZIP_NAME}"
            )
            
            # Validate URL scheme for security
            if not url.startswith('https://'):
                xbmc.log("OptiKlean: Invalid URL scheme, only HTTPS allowed", xbmc.LOGERROR)
                return None

            headers = {}
            if self.GITLAB_ACCESS_TOKEN:
                headers["Private-Token"] = self.GITLAB_ACCESS_TOKEN

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310
                commits = json.loads(response.read().decode('utf-8'))

                if not commits:
                    xbmc.log(f"OptiKlean: No commits found for {self.ADDON_ZIP_NAME}", xbmc.LOGWARNING)
                    return None

                commit = commits[0]
                return {
                    'id': commit['id'],
                    'message': commit.get('message', ''),
                    'date': commit['committed_date']
                }
        except Exception as e:
            xbmc.log(f"OptiKlean: GitLab API error: {str(e)}", xbmc.LOGERROR)
            return None

    def _should_update(self, gitlab_commit, local_data):
        xbmc.log("OptiKlean: _should_update() chiamata", xbmc.LOGDEBUG)
        """Determina se è necessario aggiornare"""
        
        # Estrazione versione dal commit remoto
        version_match = self._extract_version(gitlab_commit['message'])
        gitlab_version = version_match.group(1) if version_match else None
        local_version = local_data.get('local_version', self.current_version)

        # Log di debug: messaggio commit e versione estratta
        xbmc.log(f"OptiKlean: Commit message: {gitlab_commit['message']}", xbmc.LOGDEBUG)
        xbmc.log(f"OptiKlean: Remote version extracted: {gitlab_version}", xbmc.LOGDEBUG)

        # Primo avvio: se la versione coincide, NON aggiornare
        if not local_data.get('commit_id'):
            if gitlab_version and gitlab_version == local_version:
                xbmc.log("OptiKlean: Prima esecuzione, versione già aggiornata", xbmc.LOGINFO)
                return False
            xbmc.log("OptiKlean: No previous commit data, considering update", xbmc.LOGINFO)
            return True

        # Commit ID immutato - solo in questo caso controlliamo il limite temporale
        if local_data['commit_id'] == gitlab_commit['id']:
            xbmc.log("OptiKlean: Commit ID unchanged, checking time limits", xbmc.LOGDEBUG)
            if self._should_skip_check(local_data):
                return False
            return False

        if not gitlab_version:
            xbmc.log("OptiKlean: No version in commit message, updating for safety", xbmc.LOGWARNING)
            return True

        xbmc.log(f"OptiKlean: Version comparison - Remote: {gitlab_version}, Local: {local_version}", xbmc.LOGINFO)

        try:
            is_newer = LooseVersion(gitlab_version) > LooseVersion(local_version)
            if is_newer:
                xbmc.log("OptiKlean: New version found, ignoring time limits for update", xbmc.LOGINFO)
            return is_newer
        except Exception as e:
            xbmc.log(f"OptiKlean: Version comparison error: {str(e)}, updating for safety", xbmc.LOGWARNING)
            return True

    def _should_skip_check(self, local_data):
        """Determina se saltare il controllo per limiti di frequenza"""
        if not local_data.get('last_check'):
            xbmc.log("OptiKlean: No previous check time, not skipping", xbmc.LOGDEBUG)
            return False

        try:
            last_check = datetime.fromisoformat(local_data['last_check'])
            time_diff = datetime.now() - last_check

            # Usa il valore parametrico invece della costante
            if time_diff < timedelta(hours=self.update_check_interval):
                xbmc.log(f"OptiKlean: Skipping check, last one was {time_diff.total_seconds()/3600:.1f} hours ago (interval: {self.update_check_interval}h)", xbmc.LOGDEBUG)
                return True
            else:
                xbmc.log(f"OptiKlean: Time limit passed ({time_diff.total_seconds()/3600:.1f}h > {self.update_check_interval}h), check allowed", xbmc.LOGDEBUG)

        except Exception as e:
            xbmc.log(f"OptiKlean: Error calculating check interval: {str(e)}", xbmc.LOGWARNING)

        return False

    def _calculate_file_hash(self, file_path):
        """Calcola l'hash SHA256 di un file"""
        if not os.path.exists(file_path):
            return None
            
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            xbmc.log(f"OptiKlean: Hash calculation error: {str(e)}", xbmc.LOGWARNING)
            return None

    def _install_update(self, zip_path):
        """Installa l'aggiornamento preservando i dati utente"""
        temp_extract = os.path.join(self.temp_dir, 'extracted')

        # Pulisci la cartella di estrazione solo se esiste
        if os.path.exists(temp_extract):
            try:
                shutil.rmtree(temp_extract)
            except Exception as e:
                xbmc.log(f"OptiKlean: Failed to clean temp directory: {str(e)}", xbmc.LOGWARNING)
                return False

        try:
            os.makedirs(temp_extract, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)

            # Cerca ricorsivamente addon.xml
            addon_xml_files = glob.glob(os.path.join(temp_extract, '**', 'addon.xml'), recursive=True)
            if not addon_xml_files:
                xbmc.log("OptiKlean: Invalid update package - missing addon.xml", xbmc.LOGERROR)
                return False

            # Usa la directory che contiene addon.xml come root estratta
            extracted_root = os.path.dirname(addon_xml_files[0])

            # Backup dei file di configurazione se esistono
            self._backup_user_data()

            # Copia i file sovrascrivendo solo la cartella dell'addon
            for item in os.listdir(extracted_root):
                src = os.path.join(extracted_root, item)
                dst = os.path.join(self.addon_path, item)

                # Salta la cartella 'userdata' se esiste
                if item.lower() == 'userdata':
                    continue

                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            xbmc.log("OptiKlean: Update files installed successfully", xbmc.LOGINFO)
            return True

        except Exception as e:
            xbmc.log(f"OptiKlean: Update installation failed: {str(e)}", xbmc.LOGERROR)
            return False
        # NIENTE pulizia qui: la pulizia va fatta SOLO dopo il successo e la notifica!

    def _backup_user_data(self):
        """Backup dei file di configurazione dell'utente"""
        try:
            # Salva settings.xml se esiste
            settings_file = os.path.join('special://profile', 'userdata', 'addon_data', self.addon_id, 'settings.xml')
            settings_path = xbmcvfs.translatePath(settings_file)
            
            if xbmcvfs.exists(settings_path):
                backup_path = os.path.join(self.profile_path, 'settings_backup.xml')
                xbmcvfs.copy(settings_path, backup_path)
                xbmc.log(f"OptiKlean: Settings backup created at {backup_path}", xbmc.LOGINFO)
                
        except Exception as e:
            xbmc.log(f"OptiKlean: Settings backup error: {str(e)}", xbmc.LOGWARNING)

    def _show_update_notification(self, commit_info):
        """Mostra notifica e dialog all'utente"""
        short_id = commit_info['id'][:8]
        commit_message = commit_info['message'].replace('\n', '[CR]')
        
        # 30219: "Updated to commit"
        xbmcgui.Dialog().notification(
            self.addon.getLocalizedString(31236),  # "OptiKlean update"
            f"{self.addon.getLocalizedString(30219)} {short_id}",
            self.logo_path, 
            4000
        )
        
        # 2. Finestra di dialogo dettagliata
        try:
            dialog = xbmcgui.Dialog()
            dialog.ok(
                f"{self.addon.getLocalizedString(31236)} {short_id}",  # "OptiKlean update"
                f"{commit_message}\n\n{self.addon.getLocalizedString(30401)}"  # "To apply the update, it is recommended to restart Kodi."
            )
        except Exception as e:
            xbmc.log(f"OptiKlean: Dialog error: {str(e)}", xbmc.LOGERROR)

    def _download_with_retry(self, url, destination, max_retries=MAX_DOWNLOAD_RETRY):
        """Scarica un file con gestione dei tentativi"""
        # Validate URL scheme for security
        if not url.startswith('https://'):
            xbmc.log("OptiKlean: Invalid URL scheme, only HTTPS allowed", xbmc.LOGERROR)
            return False
            
        headers = {}
        if self.GITLAB_ACCESS_TOKEN:
            headers["Private-Token"] = self.GITLAB_ACCESS_TOKEN
            
        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response, open(destination, 'wb') as out_file:  # nosec B310
                    file_size = int(response.info().get('Content-Length', 0))
                    downloaded = 0
                    block_size = 8192
                    
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                            
                        downloaded += len(buffer)
                        out_file.write(buffer)
                        
                        if file_size > 0:
                            percent = downloaded * 100 / file_size
                            if percent % 10 == 0:  # Log ogni 10%
                                xbmc.log(f"OptiKlean: Download {percent:.1f}% complete", xbmc.LOGDEBUG)
                
                xbmc.log(f"OptiKlean: Download complete: {downloaded} bytes", xbmc.LOGINFO)
                return True
                
            except Exception as e:
                xbmc.log(f"OptiKlean: Download attempt {attempt} failed: {str(e)}", xbmc.LOGWARNING)
                
                if attempt < max_retries:
                    xbmc.sleep(2000)  # Attendi prima di riprovare
                else:
                    xbmc.log("OptiKlean: Download failed after maximum retries", xbmc.LOGERROR)
                    return False
        
        return False

    def _perform_update(self, commit_info):
        """Esegue l'aggiornamento completo con notifiche"""
        try:
            # Download
            zip_url = (
                f"{self.GITLAB_PROJECT_URL}/repository/files/"
                f"{urllib.parse.quote(self.ADDON_ZIP_NAME, safe='')}/raw"
                f"?ref={commit_info['id']}"
            )
            zip_path = os.path.join(self.temp_dir, 'update.zip')

            # Verifica se il file esiste già e rimuovilo
            if os.path.exists(zip_path):
                os.remove(zip_path)

            # Download con retry
            if not self._download_with_retry(zip_url, zip_path):
                # 30220: "Download failed"
                xbmcgui.Dialog().notification(
                    self.addon.getLocalizedString(30998),  # "Error"
                    self.addon.getLocalizedString(30220),
                    xbmcgui.NOTIFICATION_ERROR, 
                    3000
                )
                return False

            # Installazione
            if self._install_update(zip_path):
                version_match = self._extract_version(commit_info['message'])
                gitlab_version = version_match.group(1) if version_match else "unknown"
                self._save_commit_data(commit_info['id'], gitlab_version)

                if self._is_auto_update_enabled():
                    self._show_update_notification(commit_info)

                    # Pulizia SOLO dopo successo e notifica
                    temp_extract = os.path.join(self.temp_dir, 'extracted')
                    try:
                        if os.path.exists(temp_extract):
                            shutil.rmtree(temp_extract, ignore_errors=True)
                        if os.path.exists(zip_path):
                            os.remove(zip_path)
                    except Exception as e:
                        xbmc.log(f"OptiKlean: Cleanup error: {str(e)}", xbmc.LOGWARNING)
                else:
                    xbmc.log("OptiKlean: Update installed but auto-update disabled", xbmc.LOGINFO)

                return True

        except Exception as e:
            xbmc.log(f"OptiKlean: Update failed: {str(e)}", xbmc.LOGERROR)
            # 30221: "Update failed"
            xbmcgui.Dialog().notification(
                self.addon.getLocalizedString(30998),  # "Error"
                f"{self.addon.getLocalizedString(30221)}: {str(e)}", 
                xbmcgui.NOTIFICATION_ERROR, 
                5000
            )
        return False

    def check_and_update(self):
        """Controlla gli aggiornamenti e li installa se necessario"""
        update_status = "ENABLED" if self._is_auto_update_enabled() else "DISABLED"
        xbmc.log(f"OptiKlean: Auto-update status - Setting: {self.addon.getSetting('enable_auto_updates')}, Effective: {update_status}", xbmc.LOGDEBUG)
        xbmc.log(f"OptiKlean: Auto-updates are currently {update_status}", xbmc.LOGINFO)
        
        if not self._is_auto_update_enabled():
            xbmc.log("OptiKlean: Auto-updates disabled in settings", xbmc.LOGDEBUG)
            return False

        try:
            local_data = self._load_commit_data()
            gitlab_commit = self._get_latest_commit()
            
            xbmc.log(f"OptiKlean: gitlab_commit = {gitlab_commit}", xbmc.LOGDEBUG)

            if not gitlab_commit:
                xbmc.log("OptiKlean: Failed to retrieve commit information", xbmc.LOGWARNING)
                return False
                
            if self._should_update(gitlab_commit, local_data):
                xbmc.log(f"OptiKlean: Update available, performing update to {gitlab_commit['id'][:8]}", xbmc.LOGINFO)
                return self._perform_update(gitlab_commit)
            else:
                xbmc.log("OptiKlean: No update needed", xbmc.LOGDEBUG)
                return False
                
        except Exception as e:
            xbmc.log(f"OptiKlean: Critical update error: {str(e)}", xbmc.LOGERROR)
            # 30221: "Update failed"
            xbmcgui.Dialog().notification(
                self.addon.getLocalizedString(30998),  # "Error"
                self.addon.getLocalizedString(30221), 
                xbmcgui.NOTIFICATION_ERROR, 
                5000
            )
        return False