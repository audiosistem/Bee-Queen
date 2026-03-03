import xbmc
import xbmcaddon
import xbmcgui
import re
import time
from resources.lib.trakt_api import TraktAPI


class TraktMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.trakt = TraktAPI()

    def onSettingsChanged(self):
        # Re-initialize API if settings change (e.g. token revocation)
        self.trakt = TraktAPI()


class TraktPlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.trakt = TraktAPI()
        self.playing_item = None
        self.scrobble_data = {}
        self.last_pos = 0

    def onAVStarted(self):
        # Use onAVStarted as it's more reliable for getting tag info than onPlayBackStarted
        self._start_scrobble()

    def onPlayBackStopped(self):
        self._stop_scrobble()

    def onPlayBackEnded(self):
        self._stop_scrobble()

    def _clean_title(self, title):
        # Remove common Romanian streaming suffixes/prefixes
        # e.g. "Serialul ...", "Online", "Subtitrat", dates in paranthesis if they confuse search
        # Keep it simple first: remove "Serialul" prefix if present
        clean = re.sub(r"(?i)^serialul\s+", "", title)
        # Remove "Online" or "Subtitrat"
        clean = re.sub(r"(?i)\s+(online|subtitrat|in romana).*?$", "", clean)
        # Remove trailing dash variants
        clean = re.sub(r"\s+[-–—]\s*$", "", clean)
        return clean.strip()

    def _start_scrobble(self):
        if not self.trakt.access_token:
            xbmc.log(
                "[VeziAici-Trakt] No access token, skipping scrobble.", xbmc.LOGINFO
            )
            return

        try:
            # 1. Try to get title from Window Property (set by addon.py)
            # This is the most reliable method as it bypasses player tag issues
            title = xbmcgui.Window(10000).getProperty("VeziAici_Title")

            # 2. Fallback to Player Tag
            if not title:
                item = self.getPlayingItem()
                title = item.getVideoInfoTag().getTitle()

                # Wait loop
                retries = 3
                while not title and retries > 0:
                    xbmc.sleep(1000)
                    title = item.getVideoInfoTag().getTitle()
                    retries -= 1

            if not title:
                xbmc.log(
                    "[VeziAici-Trakt] No title found (Property or Player), skipping.",
                    xbmc.LOGWARNING,
                )
                return

            # Clear property to avoid stale data for next play
            xbmcgui.Window(10000).clearProperty("VeziAici_Title")

            xbmc.log(f"[VeziAici-Trakt] Raw Title Detected: '{title}'", xbmc.LOGINFO)

            season = None
            episode = None
            is_episode = False

            # 1. Regex Extraction
            # Try specific pattern: "Show Name - Sezonul X - Episodul Y"
            match = re.search(
                r"(.*?)\s*[-–—]\s*Sezonul\s*(\d+)\s*[-–—]\s*Episodul\s*(\d+)",
                title,
                re.IGNORECASE,
            )

            if match:
                raw_show_name = match.group(1)
                season = int(match.group(2))
                episode = int(match.group(3))
                is_episode = True

                clean_show_name = self._clean_title(raw_show_name)
                xbmc.log(
                    f"[VeziAici-Trakt] Parsed as Episode: Show='{clean_show_name}', S={season}, E={episode}",
                    xbmc.LOGINFO,
                )
            else:
                # Try simpler pattern: "Show Name Ep. X" (often used in Asian dramas)
                # Or just treat as movie first
                clean_show_name = self._clean_title(title)
                xbmc.log(
                    f"[VeziAici-Trakt] Parsed as Movie/Unknown: '{clean_show_name}'",
                    xbmc.LOGINFO,
                )

            self.scrobble_data = {
                "title": clean_show_name,
                "season": season,
                "episode": episode,
                "is_episode": is_episode,
                "ids": None,
            }

            # 2. Search Trakt
            if is_episode:
                # Search for the Show
                results = self.trakt.search_show(clean_show_name)
                xbmc.log(
                    f"[VeziAici-Trakt] Show Search Results for '{clean_show_name}': {len(results)} found",
                    xbmc.LOGINFO,
                )

                if results:
                    show_data = results[0]["show"]
                    show_slug = show_data["ids"]["slug"]
                    show_title = show_data["title"]
                    xbmc.log(
                        f"[VeziAici-Trakt] Matched Show: '{show_title}' ({show_slug})",
                        xbmc.LOGINFO,
                    )

                    # Get precise Episode ID
                    episode_data = self.trakt.get_episode_summary(
                        show_slug, season, episode
                    )

                    if episode_data:
                        self.scrobble_data["ids"] = episode_data["ids"]
                        self.trakt.scrobble(
                            "start", "episode", episode_data["ids"], progress=0
                        )
                        xbmc.log(
                            f"[VeziAici-Trakt] Scrobble START SUCCESS: {show_title} S{season}E{episode}",
                            xbmc.LOGINFO,
                        )
                        xbmcgui.Dialog().notification(
                            "Trakt",
                            f"Vizionezi: {show_title} {season}x{episode}",
                            xbmcgui.NOTIFICATION_INFO,
                        )
                    else:
                        xbmc.log(
                            f"[VeziAici-Trakt] Episode not found on Trakt API for S{season}E{episode}",
                            xbmc.LOGWARNING,
                        )
                else:
                    xbmc.log(
                        f"[VeziAici-Trakt] Show not found on Trakt.", xbmc.LOGWARNING
                    )

            else:
                # Movie Search
                results = self.trakt.search_movie(clean_show_name)
                xbmc.log(
                    f"[VeziAici-Trakt] Movie Search Results for '{clean_show_name}': {len(results)} found",
                    xbmc.LOGINFO,
                )

                if results:
                    movie_data = results[0]["movie"]
                    self.scrobble_data["ids"] = movie_data["ids"]
                    self.scrobble_data["is_episode"] = False

                    self.trakt.scrobble("start", "movie", movie_data["ids"], progress=0)
                    xbmc.log(
                        f"[VeziAici-Trakt] Scrobble START SUCCESS: Movie '{movie_data['title']}'",
                        xbmc.LOGINFO,
                    )
                    xbmcgui.Dialog().notification(
                        "Trakt",
                        f"Vizionezi: {movie_data['title']}",
                        xbmcgui.NOTIFICATION_INFO,
                    )
                else:
                    xbmc.log(
                        f"[VeziAici-Trakt] Movie not found on Trakt.", xbmc.LOGWARNING
                    )

        except Exception as e:
            xbmc.log(
                f"[VeziAici-Trakt] CRITICAL ERROR in onAVStarted: {e}", xbmc.LOGERROR
            )

    def _stop_scrobble(self):
        if not self.trakt.access_token or not self.scrobble_data.get("ids"):
            return

        try:
            progress = self.getProgress()
            if progress > 80:  # Consider watched
                action = "stop"
            else:
                action = "pause"

            item_type = "episode" if self.scrobble_data["is_episode"] else "movie"
            self.trakt.scrobble(
                action, item_type, self.scrobble_data["ids"], progress=progress
            )
            xbmc.log(
                f"[VeziAici-Trakt] Scrobble {action.upper()} {item_type}", xbmc.LOGINFO
            )

            # Reset
            self.scrobble_data = {}

        except Exception as e:
            xbmc.log(f"[VeziAici-Trakt] Error in _stop_scrobble: {e}", xbmc.LOGERROR)

    def getProgress(self):
        try:
            total = self.getTotalTime()
            current = self.getTime()
            if total > 0:
                return (current / total) * 100
        except:
            pass
        return 0


if __name__ == "__main__":
    monitor = TraktMonitor()
    player = TraktPlayer()

    xbmc.log("[VeziAici-Trakt] Service Started", xbmc.LOGINFO)

    # Keep the service alive
    while not monitor.abortRequested():
        if monitor.waitForAbort(10):
            break

    xbmc.log("[VeziAici-Trakt] Service Stopped", xbmc.LOGINFO)
