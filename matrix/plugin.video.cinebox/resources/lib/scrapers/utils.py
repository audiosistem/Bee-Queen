# In: resources/lib/scrapers/utils.py
import re
import xbmc
import unicodedata

# --- ✅ normalize_for_compare function (VERSION WITH UNICODEDATA) ✅ ---
def normalize_for_compare(text):
    """Normalizes text for comparison:
    - Convert to string
    - Remove accents (ex: "Mission" -> "Mission")
    - Converts to lowercase
    - Removes all non-alphanumeric characters"""
    if not text:
        return ""
    try:
        text = str(text)
        # Remove accents (NFKD Normalization)
        nfkd_form = unicodedata.normalize('NFKD', text)
        # Using 'ascii' with 'ignore' to remove non-ASCII characters after normalization
        text_ascii = nfkd_form.encode('ascii', 'ignore').decode('ascii')
        text = text_ascii # Use the version without accents if the conversion worked
    except Exception as e:
        # In case of error (rare), log in and use the original normalized text
        xbmc.log(f"Error removing accents: {e}. Using original text: {text}", xbmc.LOGWARNING)
        pass # Keeps the original text in case of error

    text = text.lower()
    # Remove everything that is not a letter or number
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

# --- ✅ guess_quality_from_name function (FULL VERSION) ✅ ---
# Note: Removed the leading '_' to be a public function of the module
def guess_quality_from_name(name):
    """Try to guess the quality from a name/text."""
    if not name: return None
    n = name.lower()
    # Check from largest to smallest
    if '2160p' in n or '4k' in n or 'uhd' in n: return '4K'
    if '1080p' in n or 'fullhd' in n or 'full hd' in n: return '1080p' # Add fullHD
    if '720p' in n: return '720p'
    # Generic HD Terms
    if 'hdtv' in n or 'webdl' in n or 'web-dl' in n or 'webrip' in n or 'hdrip' in n or 'bluray' in n or 'bdrip' in n: return 'HD'
    # SD Terms
    if 'dvdrip' in n or 'sd' in n or '480p' in n or 'tvrip' in n: return 'SD'
    # Default to HD if you don't find anything specific
    return 'HD'

# --- ✅ get_anime_search_patterns and get_anime_search_codes functions ✅ ---
# (Required for episode filter)

def get_anime_search_patterns(season, episode):
    """(HELPER v2 - S2->S1 'split-cour' logic removed) 
    Generates SXXEXX patterns (tuples). Maintains the S1->S2 logic for some animes."""
    patterns = set()
    # Always adds the exact S/E pattern requested
    patterns.add( (season, episode) ) 
    
    # Maintains logic for cases where S01E13+ can be treated as S02E01+
    # (May be refined/removed if it causes problems in anime)
    if season == 1 and episode > 11:
        for offset in [12, 13]: # Try common split-cour offsets
            if episode > offset: 
                patterns.add( (2, episode - offset) )
                
    # --- BLOCK REMOVED ---
    # The 'elif season > 1:' block was removed as it was generating
    # S01Exx incorrectly when ordering S02Exx for normal series.
    # --- END OF REMOVAL ---
            
    return list(patterns)

# Note: Removed the leading '_'
def get_anime_search_codes(season, episode):
    """(HELPER) Generates search codes (strings) S01E21, 21, 021, S02E09 etc."""
    patterns = get_anime_search_patterns(season, episode)
    codes = set()
    for s, e in patterns:
        codes.add(f"S{s:02d}E{e:02d}")
        codes.add(f"{s:02d}x{e:02d}")
        codes.add(f"{s}.{e:02d}")
        if s == 1 and e != 1:
            codes.add(f"{e:02d}")
            codes.add(f"{e:03d}")
            codes.add(f"ep{e:02d}")
            codes.add(f"e{e:02d}")
    return list(codes)

def format_size(size_bytes):
    """(HELPER) Formats bytes in KB, MB, GB. Returns None if invalid."""
    try:
        size_bytes = int(size_bytes)
        # Do not return sizes that are too small or invalid
        if size_bytes <= 0:
            return None
        if size_bytes < 1024:
            # Files smaller than 1KB are suspicious, probably metadata
            return None
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.2f} MB"
        else:
            return f"{size_bytes / (1024**3):.2f} GB"
    except Exception:
        return None