# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Simone Bianchelli
# OptiKlean - Kodi Cleaning and Optimization Addon

import os
import sys

import xbmc
import xbmcaddon 
import xbmcvfs

try:
    from resources.lib.update_state import get_restart_pending_state
except ImportError as e:
    xbmc.log(f"OptiKlean: Fallita importazione update_state: {str(e)}", xbmc.LOGERROR)

    def get_restart_pending_state():
        return {}

try:
    from autoupdater import AutoUpdater
except ImportError as e:
    xbmc.log(f"OptiKlean: Fallita importazione autoupdater: {str(e)}", xbmc.LOGERROR)
    AutoUpdater = None

try:
    from default import run_automatic_maintenance, monitor_settings_changes
except ImportError as e:
    xbmc.log(f"OptiKlean: Errore nell'importare da default.py: {str(e)}", xbmc.LOGERROR)
    run_automatic_maintenance = None
    monitor_settings_changes = None

# Ottieni il percorso dell'addon e aggiungilo ai percorsi di sistema
addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo('id')
addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
sys.path.append(addon_path)
CLEANING_TYPES = (
    "clear_cache_and_temp",
    "clear_unused_thumbnails",
    "clear_addon_leftovers",
    "clear_kodi_packages",
    "optimize_databases",
)

# Path to addon_data for storing logs
addon_data_folder = xbmcvfs.translatePath(f"special://profile/addon_data/{addon.getAddonInfo('id')}/")


def is_restart_pending():
    return bool(get_restart_pending_state())


def run_scheduled_maintenance(monitor):
    """Run automatic maintenance once, applying the startup delay only once."""
    if run_automatic_maintenance is None:
        addon_id = addon.getAddonInfo('id')
        xbmc.executebuiltin(f'RunScript({addon_id}, autorun)')
        return not monitor.abortRequested()

    delay_seconds = monitor.addon.getSettingInt("autostart_delay") * 60
    if delay_seconds > 0:
        xbmc.log(f"OptiKlean: Applying startup delay once before automatic maintenance ({delay_seconds} seconds)", xbmc.LOGINFO)
        elapsed = 0
        while elapsed < delay_seconds and not monitor.abortRequested():
            step = min(5, delay_seconds - elapsed)
            if monitor.waitForAbort(step):
                return False
            elapsed += step

    if monitor.abortRequested():
        return False

    run_automatic_maintenance(skip_auto_delay=True)
    return True


class OptiKleanMonitor(xbmc.Monitor):
    def __init__(self):
        super(OptiKleanMonitor, self).__init__()
        self.addon = xbmcaddon.Addon()
        self.startup_complete = False
        self.maintenance_executed = False
        self.updater = AutoUpdater() if AutoUpdater else None
        self.check_first_run()

    def check_first_run(self):
        """Controlla se qualsiasi opzione attiva non ha file JSON e attiva la manutenzione automatica se necessaria"""
        try:
            if is_restart_pending():
                xbmc.log("OptiKlean: Restart pending attivo, salto la prima manutenzione automatica", xbmc.LOGWARNING)
                return

            if run_automatic_maintenance is None:
                return

            if not self._needs_first_run():
                return

            xbmc.log("OptiKlean: rilevato primo avvio per le opzioni abilitate", xbmc.LOGINFO)
            if self._wait_for_startup_complete():
                xbmc.log("OptiKlean: avvio prima manutenzione automatica", xbmc.LOGINFO)
                if run_scheduled_maintenance(self):
                    self.maintenance_executed = True
                    check_and_run_update(self, settle_before_check=True)

        except Exception as e:
            xbmc.log(f"OptiKlean: Errore in check_first_run: {str(e)}", xbmc.LOGERROR)

    def _needs_first_run(self):
        profile_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        for cleaning in CLEANING_TYPES:
            if not self.addon.getSettingBool(f"{cleaning}_enable"):
                continue

            last_run_file = os.path.join(profile_path, f"last_{cleaning}.json")
            if not xbmcvfs.exists(last_run_file):
                xbmc.log(f"OptiKlean: Primo avvio rilevato per '{cleaning}' abilitato ma senza file JSON", xbmc.LOGINFO)
                return True
        return False

    def _wait_for_startup_complete(self):
        while not self.abortRequested() and not self.startup_complete:
            if self.waitForAbort(5):
                return False
        return not self.abortRequested()

    def onSettingsChanged(self):
        """Gestisci cambio impostazioni"""
        try:
            if is_restart_pending():
                xbmc.log("OptiKlean: Restart pending attivo, ignoro il refresh impostazioni", xbmc.LOGWARNING)
                return

            xbmc.log("OptiKlean: impostazioni cambiate", xbmc.LOGINFO)
            
            # Assicurati che la cartella del profilo esista
            if not xbmcvfs.exists(addon_data_folder):
                xbmcvfs.mkdirs(addon_data_folder)

            # Aggiorna subito lo stato delle impostazioni automatiche
            if monitor_settings_changes:
                monitor_settings_changes()
            else:
                xbmc.log("OptiKlean: monitor_settings_changes non disponibile", xbmc.LOGWARNING)

            # Check if first run needed for newly enabled cleanings
            self.check_first_run()
            
        except Exception as e:
            xbmc.log(f"OptiKlean: Errore gestione impostazioni cambiate: {str(e)}", xbmc.LOGERROR)
    
    def onNotification(self, sender, method, data):
        xbmc.log(f"OptiKlean: Notifica ricevuta - {method}", xbmc.LOGDEBUG)
        
        if method == "GUI.OnScreensaverDeactivated" or method == "Player.OnPlay":
            self.startup_complete = True
            xbmc.log("OptiKlean: Avvio di Kodi completato", xbmc.LOGINFO)
        
        if method in ["VideoLibrary.OnScanFinished", "AudioLibrary.OnScanFinished"]:
            self.startup_complete = True
            xbmc.log("OptiKlean: Scansione libreria completata, Kodi è pronto", xbmc.LOGINFO)
            
        if method.startswith("VideoLibrary") or method.startswith("AudioLibrary"):
            self.startup_complete = True
            xbmc.log("OptiKlean: Attività database rilevata, Kodi è attivo", xbmc.LOGINFO)
            
        if method.startswith("Input") or method.startswith("GUI"):
            self.startup_complete = True
            xbmc.log("OptiKlean: Interazione utente rilevata", xbmc.LOGDEBUG)

def check_and_run_update(monitor, settle_before_check=False):
    if is_restart_pending():
        return

    if (
        monitor.maintenance_executed
        and monitor.updater
        and monitor.updater._is_auto_update_enabled()
    ):
        if settle_before_check and monitor.waitForAbort(3):
            return
        if monitor.updater.check_and_update():
            xbmc.log("OptiKlean: Aggiornamento completato", xbmc.LOGINFO)

# Funzione principale del servizio
if __name__ == '__main__':
    xbmc.log("OptiKlean: Servizio avviato", xbmc.LOGINFO)
    
    # Pulizia di sicurezza per la cartella temp_restore all'avvio di Kodi
    try:
        from resources.lib.backup_restore import _cleanup_temp_restore
        
        xbmc.log("OptiKlean: Performing safety cleanup check for temp_restore folder on startup.", xbmc.LOGINFO)
        _cleanup_temp_restore(addon_data_folder)
    except Exception as e:
        xbmc.log(f"OptiKlean: Error during startup safety cleanup: {str(e)}", xbmc.LOGWARNING)

    monitor = OptiKleanMonitor()
    if is_restart_pending():
        xbmc.log("OptiKlean: Restart pending attivo, il servizio sospende le operazioni normali fino al riavvio", xbmc.LOGWARNING)
    xbmc.sleep(5000)  # 5 secondi di attesa iniziale

    wait_time = 3
    idle_counter = 0
    settings_check_counter = 0  # Contatore per monitoraggio impostazioni (ogni 10 minuti)
    update_check_counter = 0  # Contatore per controlli update periodici
    
    while not monitor.abortRequested():
        restart_pending = is_restart_pending()
        xbmc.log(
            f"OptiKlean: Avvio completo: {monitor.startup_complete}, "
            f"Manutenzione automatica eseguita: {monitor.maintenance_executed}, "
            f"Restart pending: {restart_pending}",
            xbmc.LOGDEBUG,
        )
        if monitor.waitForAbort(wait_time):
            break

        if restart_pending:
            wait_time = 60
            continue
        
        # Monitoraggio impostazioni in background ogni 10 minuti (600 secondi)
        settings_check_counter += wait_time
        if settings_check_counter >= 600:
            try:
                if monitor_settings_changes:
                    monitor_settings_changes()
                    xbmc.log("OptiKlean: Controllo periodico impostazioni completato", xbmc.LOGDEBUG)
            except Exception as e:
                xbmc.log(f"OptiKlean: Errore controllo periodico impostazioni: {str(e)}", xbmc.LOGERROR)
            settings_check_counter = 0

        update_check_counter += wait_time
        if update_check_counter >= 600:
            try:
                check_and_run_update(monitor)
            except Exception as e:
                xbmc.log(f"OptiKlean: Errore controllo periodico aggiornamenti: {str(e)}", xbmc.LOGERROR)
            update_check_counter = 0
        
        if not monitor.maintenance_executed:
            try:
                xbmc.sleep(2000)
                if not xbmc.Player().isPlaying():
                    xbmc.log("OptiKlean: Kodi è pronto, controllo intervalli giorni per manutenzione automatica", xbmc.LOGINFO)
                    if run_scheduled_maintenance(monitor):
                        monitor.maintenance_executed = True
                        wait_time = 60
                        check_and_run_update(monitor, settle_before_check=True)
                else:
                    xbmc.log("OptiKlean: Riproduzione in corso, riprogrammo la pulizia", xbmc.LOGINFO)
                    idle_counter += 1
                    if idle_counter > 10:
                        xbmc.log("OptiKlean: Timeout attesa inattività, controllo intervalli", xbmc.LOGINFO)
                        if run_scheduled_maintenance(monitor):
                            monitor.maintenance_executed = True
                            wait_time = 60
                            check_and_run_update(monitor, settle_before_check=True)
            except Exception as e:
                xbmc.log(f"OptiKlean: Errore durante la manutenzione automatica: {str(e)}", xbmc.LOGERROR)
                monitor.maintenance_executed = True
                wait_time = 60

    xbmc.log("OptiKlean: Servizio terminato", xbmc.LOGINFO)
