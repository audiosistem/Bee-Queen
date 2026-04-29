from ..plugin import Plugin
import xbmc, xbmcgui, xbmcaddon
import json
import resolveurl
# NEW: Import for M3U handling
try:
    from resources.lib.plugins.m3u_parser import m3u  # Adjust path to your m3u_parser.py
except ImportError:
    m3u = None  # Fallback: Skip M3U queuing if unavailable
    xbmc.log("M3U parser import failed—falling back to direct playback", level=xbmc.LOGWARNING)

addon_id = xbmcaddon.Addon().getAddonInfo('id')
default_icon = xbmcaddon.Addon(addon_id).getAddonInfo('icon')

class default_play_video(Plugin):
    name = "default video playback"
    priority = 0
    
    def play_video(self, item):
        item = json.loads(item)
        link = item.get("link", "")
        if link == "":
            return False
        title = item["title"]
        thumbnail = item.get("thumbnail", default_icon)
        summary = item.get("summary", "")
        
        # NEW: Handle M3U playlists explicitly for seamless queuing
        # Inside play_video, replace the M3U try block:
        if link.endswith(('.m3u', '.m3u8')) and m3u is not None:
            try:
                parser = m3u()
                response = parser.get_list(link)
                
                if not isinstance(response, str) or not response.strip():
                    raise ValueError("Invalid or empty M3U response")
                
                xbmc.log(f"{self.name}: Fetched M3U content ({len(response)} chars) for '{title}'", level=xbmc.LOGINFO)
                
                chunks = parser.EpgRegex(response)  # e.g., 4 chunks
                
                if not chunks:
                    raise ValueError("No valid chunks parsed from M3U")
                
                # Detect loopable structure (short list of sequential chunks)
                num_base_chunks = len(chunks)
                if num_base_chunks > 0 and num_base_chunks < 10:  # Assume <10 means "loopable cycle"
                    xbmc.log(f"{self.name}: Detected {num_base_chunks} base chunks for looping", level=xbmc.LOGINFO)
                    
                    # Generate repeated queue: e.g., 20 cycles for ~80 total (adjust REPEAT_CYCLES as needed)
                    REPEAT_CYCLES = 20  # Tune: 25 for ~100 chunks
                    total_chunks = []
                    for cycle in range(REPEAT_CYCLES):
                        for chunk in chunks:
                            # Clone with cycle info for title (optional)
                            looped_chunk = chunk.copy()
                            looped_chunk['tvg_name'] = f"{chunk.get('tvg_name', 'Chunk')} (Loop {cycle+1})"
                            total_chunks.append(looped_chunk)
                    
                    chunks = total_chunks  # Use expanded list
                    xbmc.log(f"{self.name}: Expanded to {len(chunks)} looped chunks for '{title}'", level=xbmc.LOGINFO)
                
                # Create ListItem for the overall playlist (unchanged)
                liz = xbmcgui.ListItem(title)
                video_info = liz.getVideoInfoTag()
                video_info.setTitle(title)
                video_info.setPlot(summary)
                liz.setArt({"thumb": thumbnail, "icon": thumbnail, "poster": thumbnail})
                
                # Queue all chunks into video playlist (unchanged)
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                playlist.clear()
                
                for chunk in chunks:
                    stream_url = chunk.get('stream_url', '').strip()
                    if not stream_url:
                        continue
                    chunk_title = chunk.get('tvg_name', 'Unknown Chunk')
                    chunk_thumb = chunk.get('tvg_logo', thumbnail)
                    
                    chunk_liz = xbmcgui.ListItem(label=chunk_title)
                    chunk_liz.setPath(stream_url)
                    chunk_liz.setProperty('IsPlayable', 'true')
                    chunk_liz.setMimeType('video/MP2T')
                    chunk_video_info = chunk_liz.getVideoInfoTag()
                    chunk_video_info.setTitle(chunk_title)
                    chunk_liz.setArt({'thumb': chunk_thumb})
                    
                    playlist.add(stream_url, chunk_liz)
                
                # Play the queued playlist + enable infinite repeat
                xbmc.Player().play(playlist, liz)
                xbmc.executebuiltin('PlayerControl(RepeatAll)')  # NEW: Loops the full playlist endlessly
                xbmc.log(f"{self.name}: Started looped playback of {len(chunks)}-chunk playlist for '{title}'", level=xbmc.LOGINFO)
                return True
                
            except Exception as e:
                xbmc.log(f"{self.name}: M3U playback error for '{link}': {str(e)}", level=xbmc.LOGERROR)
        # Fallback to direct play...
        # Fallback...
                # Fallback to direct play if parsing fails
                link = link  # Keep original for fallback
        
        # ORIGINAL/ Fallback: Direct/single link playback (with deprecation fix)
        liz = xbmcgui.ListItem(title)
        video_info = liz.getVideoInfoTag()
        if item.get("infolabels"):
            # Handle infolabels dict (set key-value via setters)
            infolabels = item["infolabels"]
            video_info.setTitle(infolabels.get("title", title))
            video_info.setPlot(infolabels.get("plot", summary))
            # Add more setters as needed, e.g., video_info.setGenre(infolabels.get("genre", ""))
        else:
            video_info.setTitle(title)
            video_info.setPlot(summary)
        liz.setArt({"thumb": thumbnail, "icon": thumbnail, "poster": thumbnail})

        # If link looks like an internal route (e.g. "file_iptv/search/..." or
        # "tele_iptv/search/...."), run it as a plugin path instead of trying
        # to play it as media.
        if not link.startswith("plugin://"):
            internal_prefixes = ("file_iptv/", "/file_iptv/", "tele_iptv/", "/tele_iptv/")
            if link.startswith(internal_prefixes):
                plugin_path = link.lstrip("/")
                plugin_url = f"plugin://{addon_id}/{plugin_path}"
                xbmc.log(
                    f"{self.name}: Redirecting internal route to RunPlugin '{plugin_url}'",
                    level=xbmc.LOGINFO,
                )
                xbmc.executebuiltin(f'RunPlugin("{plugin_url}")')
                return True
        
        if resolveurl.HostedMediaFile(link).valid_url():
            url = resolveurl.HostedMediaFile(link).resolve()
            xbmc.log(f"{self.name}: Resolved URL via resolveurl for '{title}'", level=xbmc.LOGINFO)
            return xbmc.Player().play(url, liz)
        xbmc.log(f"{self.name}: Direct playback of '{link}' for '{title}'", level=xbmc.LOGINFO)
        return xbmc.Player().play(link, liz)