# -*- coding: utf-8 -*-
import re
import json
import requests
from typing import List, Dict

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Referer": "https://vidify.top/",
    "Accept": "*/*",
    "Accept-Language": "ro-RO,ro;q=0.5",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def get_tv_episode_streams_from_hyper(tmdb_id: str, season_number: int, episode_number: int) -> List[Dict]:
    url = f"https://vidify.top/hyper.php?id={tmdb_id}&season={season_number}&episode={episode_number}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"[HYPER] Eroare la request: {e}")
        return []

    match = re.search(r"const\s+mediaData\s*=\s*(\{.*?\});", response.text, re.DOTALL)
    if not match:
        print("[HYPER] Nu s-a găsit mediaData în răspuns")
        return []

    try:
        media_data = json.loads(match.group(1))
    except Exception as e:
        print(f"[HYPER] Eroare la parsare mediaData: {e}")
        return []

    results = []
    for item in media_data.get("qualityOptions", []):
        if item.get("url"):
            results.append({
                "server": "hyper",
                "season": season_number,
                "episode": episode_number,
                "label": item.get("html"),
                "url": item.get("url"),
                "direct": True
            })

    return results

def get_tv_episode_streams_from_multi(imdb_id: str, season_number: int, episode_number: int, quality: str = "high") -> List[Dict]:
    base_url = "https://8streamapi-production-1993.up.railway.app"
    headers = HEADERS.copy()
    headers["Origin"] = "https://vidify.top"
    headers["Content-Type"] = "application/json"

    try:
        response = requests.get(f"{base_url}/api/v1/mediaInfo?id={imdb_id}", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[Vidify-MULTI] Eroare mediaInfo: {e}")
        return []

    if not data.get("success") or "data" not in data:
        return []

    playlist = data["data"].get("playlist", [])
    decryption_key = data["data"].get("key")
    results = []

    for season in playlist:
        if str(season.get("id")) != str(season_number):
            continue
        for episode in season.get("folder", []):
            if str(episode.get("episode")) != str(episode_number):
                continue
            for source in episode.get("folder", []):
                if not isinstance(source, dict) or not source.get("file"):
                    continue

                payload = {
                    "file": source["file"],
                    "key": decryption_key,
                    "quality": quality
                }

                try:
                    stream_response = requests.post(f"{base_url}/api/v1/getStream", headers=headers, data=json.dumps(payload), timeout=10)
                    stream_response.raise_for_status()
                    stream_data = stream_response.json()
                except Exception as e:
                    print(f"[Vidify-MULTI] Eroare getStream: {e}")
                    continue

                if not stream_data.get("success"):
                    continue

                stream_url = stream_data.get("data", {}).get("link")
                if stream_url:
                    results.append({
                        "label": f"MULTI - {source.get('title')}",
                        "url": stream_url,
                        "headers": HEADERS,
                        "direct": True
                    })

    return results

def resolve(tmdb_id: str, imdb_id: str, season: int, episode: int, quality: str = "high") -> List[Dict]:
    print(f"🔎 Caut surse pentru TMDb: {tmdb_id}, IMDb: {imdb_id}, S{season}E{episode}")
    hyper_sources = get_tv_episode_streams_from_hyper(tmdb_id, season, episode)
    multi_sources = get_tv_episode_streams_from_multi(imdb_id, season, episode, quality)
    combined = hyper_sources + multi_sources
    unique = list({item['url']: item for item in combined}.values())
    return unique

def get_vidify_tv_episode_sources(tmdb_id: str, imdb_id: str, season: int, episode: int, quality: str = "high") -> List[Dict]:
    return resolve(tmdb_id, imdb_id, season, episode, quality)

def get_vidify_movie_sources(tmdb_id: str, imdb_id: str, quality: str = "high") -> List[Dict]:
    def extract_from_hyper(tmdb_id: str) -> List[Dict]:
        url = f"https://vidify.top/hyper.php?id={tmdb_id}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"[Vidify-HYPER] Eroare la request: {e}")
            return []

        match = re.search(r"const\s+mediaData\s*=\s*(\{.*?\});", response.text, re.DOTALL)
        if not match:
            print("[Vidify-HYPER] Nu s-a găsit mediaData")
            return []

        try:
            media_data = json.loads(match.group(1))
        except Exception as e:
            print(f"[Vidify-HYPER] Eroare parsare mediaData: {e}")
            return []

        return [
            {
                "server": "hyper",
                "label": src.get("html") or "Hyper",
                "url": src.get("url"),
                "direct": True
            }
            for src in media_data.get("qualityOptions", [])
            if src.get("url")
        ]

    def extract_from_multi(imdb_id: str, quality: str = "high") -> List[Dict]:
        base_url = "https://8streamapi-production-1993.up.railway.app"
        headers = HEADERS.copy()
        headers["Origin"] = "https://vidify.top"
        headers["Content-Type"] = "application/json"

        try:
            response = requests.get(f"{base_url}/api/v1/mediaInfo?id={imdb_id}", headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"[Vidify-MULTI] Eroare mediaInfo: {e}")
            return []

        if not data.get("success") or "data" not in data:
            return []

        playlist = data["data"].get("playlist", [])
        decryption_key = data["data"].get("key")
        results = []

        for item in playlist:
            if not isinstance(item, dict) or not item.get("file"):
                continue

            payload = {
                "file": item["file"],
                "key": decryption_key,
                "quality": quality
            }

            try:
                stream_response = requests.post(f"{base_url}/api/v1/getStream", headers=headers, data=json.dumps(payload), timeout=10)
                stream_response.raise_for_status()
                stream_data = stream_response.json()
            except Exception as e:
                print(f"[Vidify-MULTI] Eroare getStream: {e}")
                continue

            if not stream_data.get("success"):
                continue

            stream_url = stream_data.get("data", {}).get("link")
            if stream_url:
                results.append({
                    "server": "multi",
                    "label": item.get("title") or "Multi",
                    "url": stream_url,
                    "headers": HEADERS,
                    "direct": True
                })

        return results

    print(f"[Vidify] Caut surse pentru FILM TMDb: {tmdb_id}, IMDb: {imdb_id}")
    hyper = extract_from_hyper(tmdb_id)
    multi = extract_from_multi(imdb_id, quality)
    combined = hyper + multi
    unique = list({item["url"]: item for item in combined}.values())
    return unique
