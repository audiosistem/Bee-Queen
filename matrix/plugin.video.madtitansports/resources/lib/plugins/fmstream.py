from resources.lib.plugin import Plugin, run_hook
import xbmcgui
from bs4 import BeautifulSoup
import urllib
import requests, re
import sys
import xbmcplugin

def recursive_replace(string: str, repl: str, new: str):
    while repl in string:
        string = string.replace(repl, new)
    return string

def clean_stream_url(url):
    if 'myradiostream.com' in url:
        url = url.replace('https://', 'http://').replace(':/', ':').rstrip(';/')
        if not url.endswith('/listen.mp3'):
            url += '/listen.mp3'
    return url

def parse_station(station):
    profiles=['', 'LC', 'HE', 'HE2', 'AAC Main']
    protocols=['http', 'https', 'mms', 'mmsh', 'rtsp', 'rtmp']

    res = {}
    if not station:
        return {"code": -1}
    res["link"] = station[0]
    res["bitrate"] = station[2]
    res["code"] = station[6]
    if len(station) > 7:
        res["protocol"] = protocols[station[7]]
    else:
        res["protocol"] = "http"
    if type(station[1]) == str:
        if station[1].isnumeric():
            res["codec"] = profiles[int(station[1])]
        else:
            res["codec"] = station[1]
    else:
        res["codec"] = res["protocol"]
    return res

class Fmstream(Plugin):
    name = "fmstream"
    plugin_id = "plugin.video.madtitansports"

    def process_item(self, item):
        if self.name in item:
            link = item.get(self.name, "")
            thumbnail = item.get("thumbnail", "")
            fanart = item.get("fanart", "")
            icon = item.get("icon", "")
            if link.startswith("search"):
                item["is_dir"] = True
                item["link"] = f"{self.name}/{link}"
                list_item = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
                list_item.setArt({"thumb": thumbnail, "fanart": fanart})
                item["list_item"] = list_item
                return item

    def routes(self, plugin):
        @plugin.route(f"/{self.name}/search/<query>")
        def search(query):
            query = urllib.parse.unquote_plus(query)
            if query == "*":
                query = xbmcgui.Dialog().input("Enter query")
                if query == "": return
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                r = requests.get("http://fmstream.org/index.php?s=" + query, headers=headers).text.replace("\r", "").replace("\\/", "/")
            except Exception as e:
                xbmcgui.Dialog().ok("Error", f"Failed to fetch search results: {str(e)}")
                return

            soup = BeautifulSoup(r, "html.parser")
            blocks = soup.find_all('div', class_='stnblock')
            jen_list = []
            full_plugin = f"plugin://{self.plugin_id}"
            for block in blocks:
                try:
                    h3 = block.find('h3', class_='stn')
                    if not h3:
                        continue
                    title = h3.text.strip()

                    # Summary
                    summary_parts = []
                    loc = block.find('span', class_='loc')
                    if loc:
                        summary_parts.append(loc.text)
                    stys = block.find_all('span', class_='sty')
                    for sty in stys:
                        summary_parts.append(sty.text)
                    desc = block.find('span', class_='desc')
                    if desc:
                        summary_parts.append(desc.text[:200] + "..." if len(desc.text) > 200 else desc.text)
                    player_a = block.find('a', class_='hp')
                    player_href = player_a['href'] if player_a else ""
                    if player_href:
                        summary_parts.append(f"Player: {player_href}")
                    summary = ' | '.join(summary_parts).strip()

                    # Streams from sq titles
                    sq_divs = block.find_all('div', attrs={'class': lambda x: x and 'sq' in x})
                    streams = []
                    for sq in sq_divs:
                        title_attr = sq.get('title', '')
                        if title_attr:
                            br = sq.find('div', class_='br')
                            bitrate = br.text.strip() if br else "Unknown"
                            codec_span = sq.find('span', class_='aac1')
                            codec = codec_span.text.strip() if codec_span else "Unknown"
                            clean_url = clean_stream_url(title_attr)
                            streams.append(f"{clean_url} ({bitrate}kbps {codec})")

                    # Link: first clean stream or fallback build
                    link = streams[0].split(' (')[0] if streams else player_href
                    if not link:
                        link = f"tunein.com/search?query={urllib.parse.quote(title)}"

                    # Fallback build if no streams
                    if not streams:
                        if 'flashplayer.php' in player_href:
                            s_match = re.search(r's=(\w+)', player_href)
                            p_match = re.search(r'p=(\d+)', player_href)
                            if s_match and p_match:
                                link = f'http://{s_match.group(1)}.myradiostream.com:{p_match.group(1)}/listen.mp3'
                        elif 'klaq.com' in player_href:
                            link = 'https://live.amperwave.net/direct/townsquare-klaqfmaac-ibc3'
                        elif 'espn.com/milwaukee' in player_href:
                            link = 'https://prclive1.listenon.in/iheart/30418.m3u8'
                        elif 'z100.iheart.com' in player_href or 'hot z100' in title.lower():
                            link = 'https://c5icy.prod.playlists.ihrhls.com/1469_icy'  # iHeart Shoutcast MP3 stream for Z100
                        # Add more as needed

                    # BBC direct
                    if 'bbc' in title.lower():
                        slug_match = re.search(r'live/([a-z_]+)', player_href or link)
                        if slug_match:
                            slug = slug_match.group(1)
                            link = f'https://lsn.lv/bbcradio.m3u8?station={slug}&bitrate=96000'

                    # Direct if media file, else route to play
                    if link.endswith(('.m3u8', '.mp3', '.aac', '.pls')):
                        stream_link = link
                    else:
                        stream_link = f"{full_plugin}/{self.name}/play/{urllib.parse.quote(link)}"

                    jen_data = {
                        "title": title,
                        "link": stream_link,
                        "type": "item",
                        "summary": summary if summary else "No description available."
                    }
                    jen_list.append(jen_data)
                except Exception:
                    continue

            if not jen_list:
                xbmcgui.Dialog().ok("No Results", "No stations found for this query. Try a different term (e.g., 'bbc' or 'pop').")
                return

            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item, return_item_on_failure=True) for item in jen_list]
            run_hook("display_list", jen_list)

        @plugin.route(f"/{self.name}/play/<path:encoded_url>")
        def play(encoded_url):
            player_url = urllib.parse.unquote(encoded_url)
            handle = int(sys.argv[1])
            stream_url = None
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                resp = requests.get(player_url, headers=headers)
                if resp.status_code == 404:
                    # Fallback mapping
                    pass
                else:
                    resp.raise_for_status()
                    page_text = resp.text

                    # Extract
                    patterns = [
                        r'"(streamUrl|url|stream)"\s*:\s*"([^"]+\.(m3u8|aac|mp3|pls)[^"]*)"',
                        r'src["\']?\s*:\s*["\']([^"\']+\.(m3u8|aac|mp3|pls)[^"\']*)["\']'
                    ]
                    for pat in patterns:
                        match = re.search(pat, page_text, re.I)
                        if match:
                            stream_url = clean_stream_url(match.group(2))
                            break
                    if not stream_url:
                        match = re.search(r'(https?://[^"\']+\.(m3u8|aac|mp3|pls)[^"\']*)', page_text)
                        if match:
                            stream_url = clean_stream_url(match.group(1))
                    if not stream_url:
                        soup = BeautifulSoup(page_text, "html.parser")
                        for tag in ['audio', 'source']:
                            elem = soup.find(tag, src=re.compile(r'\.(m3u8|aac|mp3|pls)'))
                            if elem and elem.get('src'):
                                stream_url = clean_stream_url(elem['src'])
                                if not stream_url.startswith('http'):
                                    stream_url = player_url.rsplit('/', 1)[0] + '/' + stream_url.lstrip('/')
                                break

                # Fallback build if no extraction
                if not stream_url:
                    if 'flashplayer.php' in player_url:
                        s_match = re.search(r's=(\w+)', player_url)
                        p_match = re.search(r'p=(\d+)', player_url)
                        if s_match and p_match:
                            stream_url = f'http://{s_match.group(1)}.myradiostream.com:{p_match.group(1)}/listen.mp3'
                    elif 'klaq.com' in player_url:
                        stream_url = 'https://live.amperwave.net/direct/townsquare-klaqfmaac-ibc3'
                    elif 'espn.com/milwaukee' in player_url:
                        stream_url = 'https://prclive1.listenon.in/iheart/30418.m3u8'
                    elif 'z100.iheart.com' in player_url or 'hot z100' in player_url.lower():
                        stream_url = 'https://c5icy.prod.playlists.ihrhls.com/1469_icy'  # iHeart Shoutcast MP3 stream for Z100
                    elif 'audacy.com' in player_url:
                        slug = player_url.split('/')[-1].lower().replace('stations/', '')
                        slug = slug.replace('850weei', 'weei-am').replace('thebeachmiami', 'wedr')
                        if 'weei' in slug:
                            stream_url = 'https://live.amperwave.net/direct/audacy-weei-am-aac-imc'
                        elif 'wedr' in slug:
                            stream_url = 'https://live.amperwave.net/direct/audacy-wedraac-imc'
                        else:
                            stream_url = f'https://live.amperwave.net/direct/audacy-{slug}aac-imc'
                    # Other mappings...

                if stream_url and stream_url != player_url:
                    listitem = xbmcgui.ListItem(path=stream_url)
                    if '.m3u8' in stream_url:
                        mime = "application/vnd.apple.mpegurl"  # HLS
                    elif '.aac' in stream_url or '_icy' in stream_url:
                        mime = "audio/aac" if '.aac' in stream_url else "audio/mpeg"  # AAC or MP3 for ICY
                    else:
                        mime = "audio/mpeg"  # Default for MP3
                    listitem.setMimeType(mime)
                    listitem.setProperty("IsPlayable", "true")
                    xbmcplugin.setResolvedUrl(handle, True, listitem)
                else:
                    xbmcgui.Dialog().notification("Stream Not Found", f"Opening player for {player_url.split('/')[-1]}. Try Kodi's 'Radio' addon.")
                    listitem = xbmcgui.ListItem(path=player_url)
                    listitem.setMimeType("text/html")
                    listitem.setProperty("IsPlayable", "false")
                    xbmcplugin.setResolvedUrl(handle, True, listitem)
            except Exception as e:
                xbmcgui.Dialog().ok("Play Error", f"Failed: {str(e)}")
                listitem = xbmcgui.ListItem(path=player_url)
                listitem.setProperty("IsPlayable", "false")
                xbmcplugin.setResolvedUrl(handle, True, listitem)