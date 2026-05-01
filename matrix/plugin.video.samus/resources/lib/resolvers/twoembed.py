# twoembed.py
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://www.2embed.cc'
}
DOMAIN = "https://www.2embed.cc"
PLAYER_URL = "https://uqloads.xyz"

def get_twoembed_sources(content_id, season=None, episode=None):
    content_id = str(content_id)  # 🔧 Conversie la string

    def get_embed_url():
        is_imdb = content_id.startswith("tt")
        if season and episode:
            if is_imdb:
                return f"{DOMAIN}/embedtv/imdb/{content_id}&s={season}&e={episode}"
            else:
                return f"{DOMAIN}/embedtv/{content_id}&s={season}&e={episode}"
        else:
            if is_imdb:
                return f"{DOMAIN}/embed/imdb/{content_id}"
            else:
                return f"{DOMAIN}/embed/{content_id}"

    def get_player4u_url(embed_url):
        try:
            res = requests.post(embed_url, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                                data="pls=pls", timeout=30)
            res.raise_for_status()
            html = res.text
            match = re.search(r"'(https://[^']*player4u[^']*)'", html)
            return match.group(1) if match else None
        except Exception as e:
            return None

    def extract_id(url):
        match = re.search(r'id=([\w\d]+)', url)
        return match.group(1) if match else url.split('/')[-1]

    def get_sources_from_player4u(player4u_url):
        try:
            res = requests.get(player4u_url, headers=HEADERS, timeout=30)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            links = []

            for a_tag in soup.select("li.slide-toggle a.playbtnx"):
                onclick = a_tag.get("onclick", "")
                text = a_tag.get_text(strip=True)
                quality_match = re.search(r"(\d+p|4K)", text, re.IGNORECASE)
                url_match = re.search(r"go\('([^']+)'\)", onclick)

                if quality_match and url_match:
                    quality = quality_match.group(1).upper()
                    partial_url = url_match.group(1)
                    video_id = extract_id(partial_url)
                    full_url = f"{PLAYER_URL}/e/{video_id}"
                    headers_str = "User-Agent=Mozilla/5.0&Referer=https://uqloads.xyz/"
                    links.append({
                        "url": f"{full_url}",
                        "label": f"{quality}",
                        "quality": quality,
                        "direct": False,
                        "provider": "2Embed"
                    })
            return links
        except Exception:
            return []

    embed_url = get_embed_url()
    player4u_url = get_player4u_url(embed_url)

    if not player4u_url:
        return []

    return get_sources_from_player4u(player4u_url)
