import requests
from bs4 import BeautifulSoup
import base64
from Crypto.Cipher import Blowfish
import re

PRIMEWIRE_API_KEY = "lzQPsXSKcG"
BASE_URL = "https://www.primewire.tf"

def search_primewire(imdb_id):
    url = f"{BASE_URL}/api/v1/show?key={PRIMEWIRE_API_KEY}&imdb_id={imdb_id}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data["id"], data["type"]

def fetch_html(primewire_id, content_type):
    url = f"{BASE_URL}/{'movie' if content_type == 'movie' else 'tv'}/{primewire_id}"
    r = requests.get(url)
    if r.status_code == 404:
        raise ValueError(f"❌ Pagina nu există: {url}")
    r.raise_for_status()
    return r.text

def blowfish_decrypt_b64(data_b64, key):
    data = base64.b64decode(data_b64)
    cipher = Blowfish.new(key.encode("utf-8"), Blowfish.MODE_ECB)
    decrypted = cipher.decrypt(data)
    return decrypted.rstrip(b"\x00").decode("utf-8", errors="ignore")

def extract_links_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    user_data = soup.select_one("#user-data")
    if not user_data or not user_data.has_attr("v"):
        raise ValueError("❌ Encrypted data not found in #user-data")

    encrypted = user_data["v"]
    key = encrypted[-10:]
    payload = encrypted[:-10]
    decrypted = blowfish_decrypt_b64(payload, key)
    ids = re.findall(r".{1,5}", decrypted)

    results = []
    all_links = soup.select(".propper-link")
    for i, link in enumerate(all_links):
        if i >= len(ids):
            break
        id_ = ids[i]
        version_block = link.find_parent("div", class_="movie_version_link")
        if not version_block:
            continue
        container = version_block.find_parent("div", class_="movie_version")
        if not container:
            continue
        host = container.select_one(".version-host")
        quality = container.select_one(".quality-mark")
        results.append({
            "id": id_,
            "host": host.text.strip() if host else "?",
            "quality": quality.text.strip() if quality else "?"
        })
    return results

def resolve_source_url(source_id):
    url = f"{BASE_URL}/links/gos/{source_id}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data.get("url")

# === Testare ===
if __name__ == "__main__":
    #imdb_id = "tt10676052"  # Schimbă cu ce vrei
    imdb_id = "tt2661044"
    try:
        prime_id, content_type = search_primewire(imdb_id)
        html = fetch_html(prime_id, content_type)
        links = extract_links_from_html(html)

        print(f"[✅] Surse video găsite ({len(links)}):")
        for l in links:
            try:
                final_url = resolve_source_url(l["id"])
                print(f"{l['host']} | {l['quality']} | {final_url}")
            except Exception as e:
                print(f"{l['host']} | {l['quality']} | ❌ Eroare: {e}")

    except Exception as e:
        print(f"[❌] Eroare: {e}")
