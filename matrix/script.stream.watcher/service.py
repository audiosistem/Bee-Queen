# -*- coding: utf-8 -*-
"""
Stream Auto-Reconnect Service for Kodi
Monitorizează starea redării și reconectează automat fluxurile live întrerupte.
Compatibil cu Kodi 19 (Matrix), Kodi 20 (Nexus), Kodi 21 (Omega) și Kodi 22 (Piers).
"""
import time
import xbmc
import xbmcgui
import xbmcaddon

ADDON_ID = "script.stream.watcher"


class SettingsHelper(object):
    """Asigură citirea setărilor compatibilă atât cu Kodi 19/20 cât și cu Kodi 21+."""

    def __init__(self, addon):
        self.addon = addon

    def get_bool(self, setting_id, default=True):
        try:
            if hasattr(self.addon, "getSettings"):
                return self.addon.getSettings().getBool(setting_id)
            if hasattr(self.addon, "getSettingBool"):
                return self.addon.getSettingBool(setting_id)
        except Exception:
            pass
        try:
            val = self.addon.getSetting(setting_id)
            if val != "":
                return val.lower() == "true"
        except Exception:
            pass
        return default

    def get_int(self, setting_id, default=3):
        try:
            if hasattr(self.addon, "getSettings"):
                return self.addon.getSettings().getInt(setting_id)
            if hasattr(self.addon, "getSettingInt"):
                return self.addon.getSettingInt(setting_id)
        except Exception:
            pass
        try:
            val = self.addon.getSetting(setting_id)
            if val != "":
                return int(val)
        except Exception:
            pass
        return default


class SystemMonitor(xbmc.Monitor):
    """Monitorizează evenimentele de sistem (setări, oprire Kodi) prin API-ul xbmc.Monitor."""

    def __init__(self, watcher=None):
        super(SystemMonitor, self).__init__()
        self.watcher = watcher

    def onSettingsChanged(self):
        if self.watcher:
            self.watcher.load_settings()

    def onNotification(self, sender, method, data):
        if self.watcher:
            self.watcher.on_system_notification(sender, method, data)


class StreamWatcher(xbmc.Player):
    """Monitorizează starea player-ului și gestionează reconectarea automată a stream-urilor."""

    def __init__(self, monitor):
        super(StreamWatcher, self).__init__()
        self.monitor = monitor

        try:
            self.addon = xbmcaddon.Addon(ADDON_ID)
        except Exception:
            self.addon = xbmcaddon.Addon()

        self.settings = SettingsHelper(self.addon)

        self.last_url = ""
        self.plugin_url = ""
        self.last_name = "Live Stream"
        self.is_live = False
        self.is_active = True
        self.manual_stop = False
        self.retry_count = 0
        self.playback_start_time = 0
        self.is_reconnecting = False
        self.cancel_reconnect = False
        self.last_drop_time = 0

        self.load_settings()
        xbmc.log("[StreamWatcher] Serviciul de fundal a pornit cu succes.", xbmc.LOGINFO)

    def load_settings(self):
        self.enabled = self.settings.get_bool("enabled", True)
        self.reconnect_delay = self.settings.get_int("reconnect_delay", 3)
        self.max_retries = self.settings.get_int("max_retries", 3)
        self.notifications = self.settings.get_bool("notifications", True)
        self.live_only = self.settings.get_bool("live_only", True)
        self.smart_idle_check = self.settings.get_bool("smart_idle_check", True)
        self.force_inputstream = self.settings.get_bool("force_inputstream", False)
        xbmc.log(
            "[StreamWatcher] Setări încărcate: enabled={0}, delay={1}s, retries={2}, live_only={3}, notifications={4}, smart_idle={5}".format(
                self.enabled,
                self.reconnect_delay,
                self.max_retries,
                self.live_only,
                self.notifications,
                self.smart_idle_check,
            ),
            xbmc.LOGDEBUG,
        )

    def on_system_notification(self, sender, method, data):
        # Dacă utilizatorul sau sistemul solicită oprirea Kodi / intrarea în sleep
        if method in ("System.OnQuit", "System.OnSleep"):
            self.cancel_reconnect = True
            self.is_active = False
            self.is_reconnecting = False
            xbmc.log("[StreamWatcher] Oprire Kodi detectată. Anulare monitorizare.", xbmc.LOGINFO)
            return

        # Monitorizare notificare Player.OnStop din sistem (JSON-RPC)
        if method == "Player.OnStop":
            try:
                import json
                data_obj = json.loads(data) if isinstance(data, str) else (data or {})
                was_end = data_obj.get("end", False)
                xbmc.log("[StreamWatcher] Player.OnStop notificare: end={0}".format(was_end), xbmc.LOGDEBUG)
                if not was_end:
                    # Utilizatorul a oprit manual redarea (tasta Stop/Back/meniu)
                    self.manual_stop = True
                    self.cancel_reconnect = True
                    self.is_reconnecting = False
                    self.retry_count = 0
                    xbmc.log("[StreamWatcher] Oprire manuală confirmată (Player.OnStop end=False).", xbmc.LOGINFO)
                else:
                    # Server deconectat / EOF atins
                    self.manual_stop = False
            except Exception:
                pass

    def onPlayBackStarted(self):
        try:
            current_file = self.getPlayingFile()
            infolabel_file = xbmc.getInfoLabel("Player.Filenameandpath")

            active_url = current_file or infolabel_file
            if not active_url or active_url.startswith("announcement://"):
                return

            # Dacă utilizatorul a comutat manual pe alt canal, resetăm numărul de reîncercări
            if active_url != self.last_url and (not self.is_reconnecting or (time.time() - self.last_drop_time > 15)):
                self.retry_count = 0

            # Salvare cale plugin (ex: Playlist Bee plugin://...)
            if infolabel_file and infolabel_file.startswith("plugin://"):
                self.plugin_url = infolabel_file
            elif current_file and current_file.startswith("plugin://"):
                self.plugin_url = current_file
            elif not self.is_reconnecting:
                self.plugin_url = ""

            self.last_url = active_url
            self.cancel_reconnect = True
            self.manual_stop = False
            self.playback_start_time = time.time()

            # Extragem titlul
            title = ""
            try:
                tag = self.getVideoInfoTag()
                if tag:
                    title = tag.getTitle()
            except Exception:
                pass

            if not title:
                title = xbmc.getInfoLabel("Player.Title")
            if not title or title.strip() == "":
                title = "Live Stream"

            self.last_name = title
            self.is_live = self.detect_if_live()

            # Redarea a pornit cu succes -> deblocăm flag-ul de reconectare
            self.is_reconnecting = False

            xbmc.log(
                "[StreamWatcher] Stream pornit: '{0}' (Live={1}, Plugin={2}) -> {3}".format(
                    self.last_name, self.is_live, bool(self.plugin_url), self.last_url
                ),
                xbmc.LOGINFO,
            )
        except Exception as e:
            xbmc.log("[StreamWatcher] Eroare la onPlayBackStarted: {0}".format(str(e)), xbmc.LOGERROR)
            self.is_reconnecting = False

    def onAVStarted(self):
        try:
            self.is_live = self.detect_if_live()
        except Exception:
            pass

    def detect_if_live(self):
        """Detectează dacă media redată este un stream continuu (fără sfârșit natural)."""
        try:
            if xbmc.getInfoLabel("Player.Live").lower() == "true":
                return True
            if not xbmc.getCondVisibility("Player.HasDuration"):
                return True
            total_time = self.getTotalTime()
            if total_time <= 0:
                return True
            # Verificare specifică fluxurilor TV/IPTV
            check_url = (self.last_url or "").lower()
            if any(ext in check_url for ext in (".m3u8", ".ts", ".mpd", ".ism", "/live/")) or (self.plugin_url or "").startswith("plugin://"):
                return True
        except Exception:
            pass
        return False

    def onPlayBackEnded(self):
        """
        Apelat când redarea atinge sfârșitul fluxului (EOF).
        Pentru stream-urile LIVE, EOF înseamnă căderi de rețea sau deconectare de server.
        """
        if not self.enabled or not self.is_active or self.manual_stop:
            return

        xbmc.log("[StreamWatcher] onPlayBackEnded declanșat.", xbmc.LOGDEBUG)

        if self.is_live:
            # Un stream LIVE nu se termină de la sine -> este 100% o cădere / deconectare de server
            self.manual_stop = False
            self.handle_drop(reason="Live stream deconectat de la server (EOF)")
        elif not self.live_only:
            try:
                cur = self.getTime()
                total = self.getTotalTime()
                if total > 0 and (total - cur) > 20:
                    self.handle_drop(reason="Conținut VOD întrerupt prematur")
            except Exception:
                pass

    def onPlayBackStopped(self):
        """
        Apelat când redarea este oprită (manual sau forțat de erori de rețea/buffer).
        """
        if not self.enabled or not self.is_active:
            return

        xbmc.log("[StreamWatcher] onPlayBackStopped declanșat.", xbmc.LOGDEBUG)

        # 1. Verificare oprire manuală explicită: utilizatorul a apăsat Stop/Back/tastatură în ultima secundă
        if self.smart_idle_check:
            user_interacted_recently = not xbmc.getCondVisibility("System.IdleTime(1)")
            if user_interacted_recently:
                xbmc.log(
                    "[StreamWatcher] Activitate recentă a utilizatorului detectată (Stop/Back). Nu se reconectează.",
                    xbmc.LOGINFO,
                )
                self.manual_stop = True
                self.cancel_reconnect = True
                self.is_reconnecting = False
                self.retry_count = 0
                return

        # 2. Verificare oprire rapidă (< 8 secunde de la pornirea manuală): se consideră oprire intenționată
        playback_duration = time.time() - self.playback_start_time if self.playback_start_time > 0 else 0
        if self.playback_start_time > 0 and playback_duration < 8 and not self.is_reconnecting:
            xbmc.log(
                "[StreamWatcher] Oprire rapidă detectată ({0:.1f}s). Se presupune oprire manuală de utilizator.".format(
                    playback_duration
                ),
                xbmc.LOGINFO,
            )
            self.manual_stop = True
            self.cancel_reconnect = True
            self.is_reconnecting = False
            self.retry_count = 0
            return

        # Dacă utilizatorul a dat Stop manual confirmat, nu reconectăm
        if self.manual_stop:
            return

        # Dacă o reconectare este deja în curs (ex. din onPlayBackEnded), nu duplicăm
        if self.is_reconnecting:
            return

        if self.is_live or not self.live_only:
            self.handle_drop(reason="Stream oprit neașteptat (timeout rețea / conexiune picată)")

    def handle_drop(self, reason="Cădere neașteptată stream"):
        if not self.last_url and not self.plugin_url:
            return
        if self.manual_stop:
            xbmc.log("[StreamWatcher] Oprire manuală activă. Reconectare omisă.", xbmc.LOGDEBUG)
            return
        if self.is_reconnecting:
            xbmc.log("[StreamWatcher] Proces de reconectare deja activ.", xbmc.LOGDEBUG)
            return

        # Verificare număr maxim reîncercări
        if self.max_retries > 0 and self.retry_count >= self.max_retries:
            xbmc.log(
                "[StreamWatcher] S-a atins numărul maxim de reîncercări ({0}/{1}) pentru: {2}".format(
                    self.retry_count, self.max_retries, self.last_name
                ),
                xbmc.LOGWARNING,
            )
            if self.notifications:
                xbmcgui.Dialog().notification(
                    "Stream Watcher",
                    "Eșec reconectare: server indisponibil.",
                    xbmcgui.NOTIFICATION_ERROR,
                    4000,
                )
            self.retry_count = 0
            self.last_url = ""
            self.plugin_url = ""
            self.is_reconnecting = False
            return

        self.retry_count += 1
        self.is_reconnecting = True
        self.cancel_reconnect = False
        self.last_drop_time = time.time()

        max_str = str(self.max_retries) if self.max_retries > 0 else "∞"
        xbmc.log(
            "[StreamWatcher] {0}. Încercare de reconectare {1}/{2} pentru: '{3}' (Plugin={4})".format(
                reason, self.retry_count, max_str, self.last_name, bool(self.plugin_url)
            ),
            xbmc.LOGINFO,
        )

        if self.notifications:
            xbmcgui.Dialog().notification(
                "Stream Watcher",
                "Reconectare ({0}/{1}) în {2}s...".format(
                    self.retry_count, max_str, self.reconnect_delay
                ),
                xbmcgui.NOTIFICATION_INFO,
                self.reconnect_delay * 1000,
            )

        # Pauză de stabilizare non-blocantă
        for i in range(self.reconnect_delay * 10):
            if self.monitor.abortRequested() or not self.is_active or self.cancel_reconnect or self.manual_stop:
                xbmc.log("[StreamWatcher] Reconectarea a fost anulată.", xbmc.LOGINFO)
                self.is_reconnecting = False
                return

            # Dacă utilizatorul apasă o tastă pe telecomandă/tastatură în timpul numărătorii (anulare imediată)
            if i > 2 and self.smart_idle_check and not xbmc.getCondVisibility("System.IdleTime(1)"):
                xbmc.log("[StreamWatcher] Interacțiune utilizator în timpul numărătorii inverse. Anulare reconectare.", xbmc.LOGINFO)
                self.manual_stop = True
                self.cancel_reconnect = True
                self.is_reconnecting = False
                self.retry_count = 0
                return

            xbmc.sleep(100)

        # Executare comandă de redare
        if not self.isPlaying() and not self.manual_stop and not self.cancel_reconnect:
            try:
                success = self.trigger_playback()
                if success:
                    xbmc.log("[StreamWatcher] Comanda de redare a fost transmisă cu succes.", xbmc.LOGINFO)
                else:
                    xbmc.log("[StreamWatcher] Nu s-a putut trimite comanda de redare.", xbmc.LOGWARNING)
            except Exception as e:
                xbmc.log("[StreamWatcher] Eșec la transmiterea comenzii de redare: {0}".format(str(e)), xbmc.LOGERROR)

        # Așteptăm confirmarea pornirii player-ului pentru a nu lăsa flag-ul blocat
        for _ in range(30):
            if self.isPlaying() or self.cancel_reconnect or self.manual_stop or self.monitor.abortRequested():
                break
            xbmc.sleep(100)

        self.is_reconnecting = False

    def trigger_playback(self):
        """
        Determină metoda corectă de redare:
        - Fluxuri din Addon-uri (plugin://, ex. Playlist Bee): PlayMedia("plugin://...") pentru re-rezolvare completă.
        - Fluxuri PVR (pvr://): PlayMedia("pvr://...").
        - Fluxuri directe (http, https): xbmc.Player().play cu ListItem fără forțare eronată de inputstream.adaptive.
        """
        target_plugin = self.plugin_url if (self.plugin_url and self.plugin_url.startswith("plugin://")) else ""
        if not target_plugin and self.last_url and self.last_url.startswith("plugin://"):
            target_plugin = self.last_url

        # 1. Fluxuri din Addon / Plugin (Playlist Bee, etc.)
        if target_plugin:
            safe_plugin_url = target_plugin.replace('"', '\\"')
            xbmc.log("[StreamWatcher] Re-executare prin PlayMedia (plugin): {0}".format(safe_plugin_url), xbmc.LOGINFO)
            xbmc.executebuiltin('PlayMedia("{0}")'.format(safe_plugin_url))
            return True

        # 2. Fluxuri PVR
        if self.last_url and self.last_url.startswith("pvr://"):
            safe_pvr = self.last_url.replace('"', '\\"')
            xbmc.log("[StreamWatcher] Re-executare prin PlayMedia (PVR): {0}".format(safe_pvr), xbmc.LOGINFO)
            xbmc.executebuiltin('PlayMedia("{0}")'.format(safe_pvr))
            return True

        # 3. Fluxuri directe (HTTP/HTTPS/RTMP etc.)
        if self.last_url:
            xbmc.log(
                "[StreamWatcher] Re-redare flux direct: '{0}' -> {1}".format(
                    self.last_name, self.last_url
                ),
                xbmc.LOGINFO,
            )
            try:
                liz = self.create_listitem(self.last_url, self.last_name)
                self.play(self.last_url, liz)
                return True
            except Exception as e:
                xbmc.log(
                    "[StreamWatcher] Player.play a eșuat ({0}), se încearcă fallback prin PlayMedia...".format(str(e)),
                    xbmc.LOGWARNING,
                )
                safe_url = self.last_url.replace('"', '\\"')
                xbmc.executebuiltin('PlayMedia("{0}")'.format(safe_url))
                return True

        return False

    def create_listitem(self, url, name):
        """Creează un ListItem conform standardelor moderne Kodi 20 Nexus și Kodi 21 Omega."""
        liz = xbmcgui.ListItem(name, path=url)
        liz.setProperty("IsPlayable", "true")

        # Setare metadate video conform Kodi 20/21 (InfoTagVideo)
        try:
            info_tag = liz.getVideoInfoTag()
            info_tag.setTitle(name)
            info_tag.setMediaType("video")
        except AttributeError:
            liz.setInfo(type="Video", infoLabels={"Title": name, "mediatype": "video"})

        url_lower = url.lower()

        # Suport pentru fluxuri adaptive doar unde este necesar (DASH, SmoothStreaming)
        if ".mpd" in url_lower:
            liz.setProperty("inputstream", "inputstream.adaptive")
            liz.setProperty("inputstream.adaptive.manifest_type", "mpd")
            liz.setMimeType("application/dash+xml")
        elif ".ism" in url_lower:
            liz.setProperty("inputstream", "inputstream.adaptive")
            liz.setProperty("inputstream.adaptive.manifest_type", "ism")
        elif ".m3u8" in url_lower and self.force_inputstream:
            liz.setProperty("inputstream", "inputstream.adaptive")
            liz.setProperty("inputstream.adaptive.manifest_type", "hls")
            liz.setMimeType("application/vnd.apple.mpegurl")

        return liz


def main():
    monitor = SystemMonitor()
    watcher = StreamWatcher(monitor)
    monitor.watcher = watcher

    xbmc.log("[StreamWatcher] Bucla principală a serviciului este activă.", xbmc.LOGINFO)

    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break

        # Dacă redarea a funcționat stabil cel puțin 10 secunde, resetăm contorul de reîncercări
        if watcher.retry_count > 0 and watcher.isPlaying():
            if watcher.playback_start_time > 0 and (time.time() - watcher.playback_start_time > 10):
                xbmc.log(
                    "[StreamWatcher] Redare stabilă confirmată (>10s). Contor reîncercări resetat la 0.",
                    xbmc.LOGDEBUG,
                )
                watcher.retry_count = 0

    watcher.is_active = False
    watcher.cancel_reconnect = True
    xbmc.log("[StreamWatcher] Serviciul de fundal a fost oprit.", xbmc.LOGINFO)


if __name__ == "__main__":
    main()