# -*- coding: utf-8 -*-
import xbmc, xbmcgui, xbmcvfs, xbmcaddon
import os, sys, re, json, urllib.parse, urllib.request, html
import time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
try:
    from . import uploader
except:
    try: import uploader
    except: uploader = None

API_TIMEOUT = 300
THINKING_LEVEL = "low"
FIRST_BATCH_SIZE = 100
NEXT_BATCH_SIZE = 300

MODEL_PREFERAT = [
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",   
    "gemini-3.5-flash",     
    "gemini-flash-latest",     
]
FIRST_BATCH_TIMEOUT = 300

STOP_WORDS = {
    "ok", "okay", "yeah", "yes", "no", "nah", "yep", "yup", "oh", "ah", "wow", 
    "hey", "ha", "haha", "huh", "uh", "um", "mmm", "hmm", "oops", "phew", 
    "shh", "brrr", "sigh", "pant", "gasp", "laugh", "sob", "...", "..", "-", "--"
}

AD_PATTERNS = [
    r"www\.[a-z0-9]+\.[a-z]{2,}", r"https?://[^\s]+", r"subtitles by|translated by",
    r"OpenSubtitles|Subscene", r"support us|donate", r"@[a-z0-9_]+"
]

PAUZA_DUPA_EROARE = 10.0 
keys_lock = Lock()
write_lock = Lock()
keys_in_use = set()

def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO, duration=3000):
    xbmc.executebuiltin('Notification("{}", "{}", "{}", {})'.format(title, message, duration, icon))
def split_smart_long_line(text, max_chars=44):
    if not text or len(text) <= max_chars or "\n" in text:
        return text
    
    match_dialog = re.search(r'\s+-\s*([A-ZĂÎȘȚÂ])', text)
    if match_dialog:
        p1, p2 = text[:match_dialog.start()].strip(), text[match_dialog.start():].strip()
        if len(p1) <= max_chars and len(p2) <= max_chars:
            return p1 + "\n" + (p2 if p2.startswith('-') else "- " + p2)

    match_punct = re.search(r'([.!?])\s+', text)
    if match_punct:
        p1, p2 = text[:match_punct.start(1)+1].strip(), text[match_punct.start(1)+1:].strip()
        if len(p1) <= max_chars and len(p2) <= max_chars:
            return p1 + "\n" + p2
    
    if ',' in text:
        mid = len(text) // 2
        commas = [i for i, c in enumerate(text) if c == ',']
        if commas:
            best_comma = min(commas, key=lambda x: abs(x - mid))
            p1, p2 = text[:best_comma+1].strip(), text[best_comma+1:].strip()
            if len(p1) <= max_chars and len(p2) <= max_chars:
                return p1 + "\n" + p2
                
    mid = len(text) // 2
    for i in range(0, 25):
        for pos in [mid + i, mid - i]:
            if 0 < pos < len(text) and text[pos] == ' ':
                return text[:pos].strip() + "\n" + text[pos:].strip()
    return text

try:
    from .key import api_keys as backup_keys
except ImportError:
    try: 
        import key
        backup_keys = key.api_keys 
    except: 
        backup_keys = []
def _build_prompt(target_lang, num_texts):
    LANG_SPECIFIC = {
        'ro': {
            'name': 'Romanian',
            'diacritics': 'Use all Romanian diacritics correctly: ă, â, î, ș, ț.',
            'style': (
                '- Adapt profanity to strong but non-vulgar Romanian expressions.\n'
                '- "marry me" → "căsătorește-te cu mine"\n'
                '- "babe/honey" → "iubire", "dragoste", "iubi"\n'
                '- "baby" → "puiule"\n'
                '- "Oh my God" → "Doamne Dumnezeule"\n'
                '- "my treat" → "fac eu cinste"\n'
                '- Adapt threats stylistically: "Kill them" → "Elimină-i" (not "Ucide-i")\n'
                '- "lakh" = sută de mii, "crore" = zece milioane\n'
            ),
        },
        'es': {
            'name': 'Spanish',
            'diacritics': 'Use all Spanish accents and punctuation correctly: á, é, í, ó, ú, ñ, ü, ¿, ¡.',
            'style': ('- Use natural Latin American/Castilian Spanish.\n- Adapt profanity.\n- "Oh my God" → "Dios mío"\n'),
        },
        'fr': {
            'name': 'French',
            'diacritics': 'Use all French accents correctly.',
            'style': ('- Use natural spoken French.\n- "Oh my God" → "Mon Dieu"\n'),
        },
        'de': {'name': 'German', 'diacritics': 'Use all German special characters correctly.', 'style': '- Use natural spoken German.\n'},
        'it': {'name': 'Italian', 'diacritics': 'Use all Italian accents correctly.', 'style': '- Use natural spoken Italian.\n'},
        'pt': {'name': 'Portuguese', 'diacritics': 'Use all Portuguese accents correctly.', 'style': '- Use natural Portuguese.\n'},
        'hu': {'name': 'Hungarian', 'diacritics': 'Use all Hungarian accents correctly.', 'style': '- Use natural spoken Hungarian.\n'},
        'ru': {'name': 'Russian', 'diacritics': 'Use correct Russian Cyrillic characters.', 'style': '- Use natural spoken Russian.\n'},
        'tr': {'name': 'Turkish', 'diacritics': 'Use all Turkish special characters correctly.', 'style': '- Use natural spoken Turkish.\n'},
        'bg': {'name': 'Bulgarian', 'diacritics': 'Use correct Bulgarian Cyrillic characters.', 'style': '- Use natural spoken Bulgarian.\n'},
        'el': {'name': 'Greek', 'diacritics': 'Use correct Greek characters with proper accents.', 'style': '- Use natural spoken Greek.\n'},
        'pl': {'name': 'Polish', 'diacritics': 'Use all Polish diacritics correctly.', 'style': '- Use natural spoken Polish.\n'},
        'cs': {'name': 'Czech', 'diacritics': 'Use all Czech diacritics correctly.', 'style': '- Use natural spoken Czech.\n'},
        'nl': {'name': 'Dutch', 'diacritics': 'Use correct Dutch spelling.', 'style': '- Use natural spoken Dutch.\n'},
        'en': {'name': 'English', 'diacritics': '', 'style': '- Use natural spoken American/British English.\n'}
    }

    lang_info = LANG_SPECIFIC.get(target_lang, {
        'name': target_lang.upper(),
        'diacritics': f'Use correct {target_lang.upper()} characters and diacritics.',
        'style': f'- Use natural, modern spoken {target_lang.upper()}.\n',
    })

    lang_name = lang_info['name']
    diacritics_rule = lang_info.get('diacritics', '')
    style_rules = lang_info.get('style', '')

    return f"""**MISSION:**
You are a world-class expert in video subtitle localization and cultural adaptation.
Translate ALL subtitle texts below into natural, modern, impactful {lang_name}.

**OUTPUT FORMAT (CRITICAL):**
- Return ONLY a valid JSON array of objects. No markdown, no code fences.
- Format strictly as: [{{"index": "ID", "text": "translated text"}}]
- You MUST return exactly {num_texts} items in the array.

**MULTILINGUAL SOURCE HANDLING:**
- The source text may be in ANY language. Identify and translate accurately into {lang_name}.
- Preserve the original meaning 100%.

**STYLE AND TONE ({lang_name.upper()}):**
- Sound natural, as if spoken by a talented actor in a contemporary {lang_name} film.
- Use modern, spoken {lang_name} — avoid rigid, literal translations.
- Adapt idioms and expressions to culturally equivalent {lang_name} ones.
- Adapt profanity to strong but appropriate {lang_name} expressions (not literal).
{style_rules}
**FORMATTING RULES (STRICT):**
- Each line must NOT exceed 43 characters.
- If translation exceeds 43 chars, split logically across two lines with \\n.
- If still too long, rephrase for brevity.
- Dialogue lines starting with "-" must be followed by space + capital letter.
- NEVER output more than 2 text lines per subtitle block.
{f'- {diacritics_rule}' if diacritics_rule else ''}
- Final output must be grammatically flawless.

**INTERJECTION CLEANUP (REMOVE COMPLETELY):**
Remove these filler sounds/interjections entirely: Aaah, Aah, Ah, Ahem, Ahh, Argh, Aw, Aww, Eh, Ehm, Er, Erm, Err, Gah, Ha, Heh, Hm, Hmm, Hmmm, Hmph, Huh, Mm, Mmm, Mhm, Oh, Ohh, Ooh, Oops, Ouch, Ow, Pff, Pfft, Phew, Psst, Sh, Shh, Shhh, Ugh, Uh, Uhh, Uhm, Um, Umm, Whew, Whoa, Wow, Yikes.

**CRITICAL ANTI-SHIFTING RULES:**
- Text from input index X MUST remain in output index X.
- If a single sentence is broken across two indices, translate the broken parts EXACTLY where they are. Do NOT combine them."""
def translate_gemini(texts_dict, target_lang, api_key, model_name, timeout=API_TIMEOUT, thinking_level=THINKING_LEVEL):
    url = "https://generativelanguage.googleapis.com/v1alpha/models/{}:generateContent?key={}".format(model_name, api_key)
    prompt = _build_prompt(target_lang, len(texts_dict))
    json_input = [{"index": str(k), "text": v} for k, v in texts_dict.items()]

    generation_config = {
        "temperature": 0.3,  
        "response_mime_type": "application/json",
        "responseSchema": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "index": {"type": "STRING"},
                    "text": {"type": "STRING"}
                },
                "required": ["index", "text"]
            }
        }
    }

    if thinking_level and thinking_level.lower() != "off":
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level.upper()}

    payload = {
        "contents": [{"parts": [{"text": prompt + "\n\n" + json.dumps(json_input, ensure_ascii=False)}]}],
        "generationConfig": generation_config,
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
        ],
    }

    xbmc.log("API call: model={} (v1alpha), cheie=...{}, {} texte, limba={}".format(
        model_name, api_key[-4:], len(texts_dict), target_lang), xbmc.LOGDEBUG)

    result_container = {'response': None, 'error': None, 'code': 0}

    def _do_request():
        try:
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json; charset=utf-8'}, method='POST')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result_container['response'] = resp.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            result_container['code'] = e.code
            try: result_container['error'] = e.read().decode('utf-8', errors='replace')[:300]
            except Exception: result_container['error'] = str(e)
        except Exception as e: 
            result_container['error'] = "{}: {}".format(type(e).__name__, e)

    req_thread = threading.Thread(target=_do_request)
    req_thread.daemon = True
    req_thread.start()

    while req_thread.is_alive():
        req_thread.join(timeout=1.0)
        if not xbmc.Player().isPlaying(): return None, -1

    if result_container['code'] > 0: 
        xbmc.log("Eroare HTTP {} de la API: {}".format(result_container['code'], result_container['error']), xbmc.LOGERROR)
        return None, result_container['code']
    
    if not result_container['response']: 
        if result_container['error']: xbmc.log("Eroare Conexiune/Timeout: {}".format(result_container['error']), xbmc.LOGERROR)
        else: xbmc.log("Timpul de așteptare a expirat sau răspunsul a fost gol.", xbmc.LOGERROR)
        return None, 0

    try: res_data = json.loads(result_container['response'])
    except: return None, 0

    if 'error' in res_data: return None, res_data['error'].get('code', 0)
    
    candidates = res_data.get('candidates', [])
    if not candidates or not isinstance(candidates, list) or len(candidates) == 0: return None, 0
    
    first_candidate = candidates[0]
    if first_candidate.get('finishReason', '') == 'SAFETY': return None, 0

    try: text_r = first_candidate['content']['parts'][0]['text']
    except: return None, 0
    if not text_r: return None, 0

    text_r = text_r.strip()
    if text_r.startswith("```"): text_r = re.sub(r"^```(?:json)?\n|\n```$", "", text_r).strip()

    try:
        parsed_array = json.loads(text_r)
        result_dict = {str(item['index']): str(item['text']) for item in parsed_array if 'index' in item and 'text' in item}
        return result_dict, 0
    except Exception as e:
        xbmc.log("JSON Parse Error: {}".format(e), xbmc.LOGERROR)
        return None, 0

def process_batch_worker(batch, target_lang, all_keys, timeout_current):
    if not xbmc.Player().isPlaying(): return None, 0, ""
    to_translate, skipped_lines = {}, {}

    for b_id, timing, text in batch:
        clean_text = re.sub(r'<[^>]*>', '', text).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)
        
        if any(re.search(p, clean_text, re.IGNORECASE) for p in AD_PATTERNS):
            skipped_lines[str(b_id)] = ""
            continue
            
        word_only = re.sub(r'[^\w\s]', '', clean_text).lower().strip()
        if word_only in STOP_WORDS:
            skipped_lines[str(b_id)] = clean_text
            continue

        to_translate[str(b_id)] = clean_text

    if not to_translate:
        chunk_srt = ""
        for b_id, timing, orig_text in batch:
            val = skipped_lines.get(str(b_id), "")
            chunk_srt += "{}\n{}\n{}\n\n".format(b_id, timing, val)
        return chunk_srt, 1, "Skipped"

    tried_keys_indices = set()
    while len(tried_keys_indices) < len(all_keys):
        if not xbmc.Player().isPlaying(): break
        current_key = None
        k_idx_real = 0
        with keys_lock:
            for i, k in enumerate(all_keys):
                if k not in keys_in_use and i not in tried_keys_indices:
                    current_key = k; keys_in_use.add(k)
                    k_idx_real = i + 1; break
        if not current_key: time.sleep(2); continue

        try:
            for model in MODEL_PREFERAT:
                if not xbmc.Player().isPlaying(): return None, 0, ""
                rezultat, err_code = translate_gemini(to_translate, target_lang, current_key, model, timeout=timeout_current)
                
                if resultado := rezultat:
                    chunk_srt = ""
                    for b_id, timing, orig_text in batch:
                        trad = resultado.get(str(b_id), skipped_lines.get(str(b_id), orig_text))
                        trad = str(trad).replace('- ', '').strip()
                        trad = split_smart_long_line(trad, max_chars=44)
                        linii = [l.strip().lstrip('- ').strip() for l in trad.splitlines()]
                        final_text = "\n".join(linii)
                        chunk_srt += "{}\n{}\n{}\n\n".format(b_id, timing, final_text)
                    return chunk_srt, k_idx_real, model
                
                if err_code == -1: return None, 0, ""
                xbmc.log("Modelul {} a esuat (Cod {}). Incercam urmatorul...".format(model, err_code), xbmc.LOGWARNING)
                
            tried_keys_indices.add(k_idx_real - 1)
        finally:
            with keys_lock:
                if current_key in keys_in_use: keys_in_use.remove(current_key)
    return None, 0, ""
def run_translation(sub_addon_id, mode="fast"):
    global MODEL_PREFERAT, FIRST_BATCH_TIMEOUT
    global FIRST_BATCH_SIZE, NEXT_BATCH_SIZE, THINKING_LEVEL

    try: _addon = xbmcaddon.Addon(sub_addon_id)
    except Exception as e:
        xbmc.log("Nu pot accesa addon {}: {}".format(sub_addon_id, e), xbmc.LOGERROR)
        return

    if _addon.getSetting('robot_activat') != 'true': return

    xbmc.log("Mod Fix: Pachetul 1 la {} linii, restul la {} | Gandire: {} | Modele: {}".format(
        FIRST_BATCH_SIZE, NEXT_BATCH_SIZE, THINKING_LEVEL, MODEL_PREFERAT), xbmc.LOGINFO)

    try: max_workers_setat = _addon.getSettingInt('max_workers_count') + 1
    except: max_workers_setat = 1
    
    keys_din_setari = [_addon.getSetting('api_key_r3_{}'.format(i)) for i in range(1, 6)]
    all_keys = list(dict.fromkeys([k for k in keys_din_setari if k] + backup_keys))
    
    if not all_keys:
        if xbmcgui.Dialog().yesno("Eroare Gemini", "Lipsă Chei API! Mergi la setări?"): _addon.openSettings()
        return

    langs = ["ro", "en", "es", "fr", "de", "it", "hu", "pt", "ru", "tr", "bg", "el", "pl", "cs", "nl"]
    try: target_lang = langs[_addon.getSettingInt('subs_languages')]
    except: target_lang = "ro"

    profile_path = xbmcvfs.translatePath('special://profile/addon_data/{}/'.format(sub_addon_id))
    _, files = xbmcvfs.listdir(profile_path)
    srt_files = [f for f in files if f.lower().endswith('.srt') and not (f.startswith('Google-') or f.startswith('Gemini-') or f.startswith('Lingva-'))]
    if not srt_files: return

    orig_full_name = srt_files[0]
    sub_path = os.path.join(profile_path, orig_full_name)
    base_name = orig_full_name.rsplit('.', 1)[0]
    final_name = "Gemini-{}.{}.srt".format(base_name, target_lang)
    output_path = os.path.join(profile_path, final_name)

    if uploader:
        cale_cloud = uploader.get_folder_grup() 
        auth = uploader.koofr_get_auth()
        remote_url = "https://app.koofr.net/dav/Koofr/Subtitrari/{}/{}".format(cale_cloud, urllib.parse.quote(final_name))
        try:
            req_c = urllib.request.Request(remote_url, method='GET', headers={"Authorization": auth})
            with urllib.request.urlopen(req_c, timeout=10) as r:
                if r.getcode() == 200:
                    notify("Cloud", "Subtitrare găsită! Descărcăm...", duration=2000)
                    with xbmcvfs.File(output_path, 'wb') as f_o: f_o.write(r.read())
                    xbmc.Player().setSubtitles(output_path)
                    return 
        except: pass

    try:
        with xbmcvfs.File(sub_path, 'rb') as f: raw_content = f.read()
            
        if isinstance(raw_content, bytes):
            try: content = raw_content.decode('utf-8')
            except: content = raw_content.decode('latin-1', errors='ignore')
        else: content = str(raw_content)
            
        pattern = re.compile(r'(\d+)\r?\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\r?\n([\s\S]*?)(?=\r?\n\r?\n|$)')
        blocks = pattern.findall(content)
        total_lines = len(blocks)
        
        batches = []
        if total_lines > 0:
            batches.append(blocks[:FIRST_BATCH_SIZE])
            restul_blocurilor = blocks[FIRST_BATCH_SIZE:]
            for i in range(0, len(restul_blocurilor), NEXT_BATCH_SIZE):
                batches.append(restul_blocurilor[i:i + NEXT_BATCH_SIZE])
        
        completed_lines, final_results = 0, {}
        chei_folosite, modele_folosite = set(), set()
        last_notify_time = time.time()
        
        notify("Gemini Robot", "Start: {} linii | Pachete: {}".format(total_lines, len(batches)))

        with ThreadPoolExecutor(max_workers=max_workers_setat) as executor:
            futures = {}
            for idx, b in enumerate(batches):
                t_out = FIRST_BATCH_TIMEOUT if idx == 0 else API_TIMEOUT
                futures[executor.submit(process_batch_worker, b, target_lang, all_keys, t_out)] = idx
            
            for future in as_completed(futures):
                if not xbmc.Player().isPlaying(): break
                idx = futures[future]
                res_srt, k_num, model_name = future.result()
                
                if res_srt:
                    with write_lock:
                        final_results[idx] = res_srt
                        completed_lines += len(batches[idx])
                        if k_num > 0: chei_folosite.add(str(k_num))
                        if model_name: modele_folosite.add(model_name)
                        
                        current_srt = "".join([final_results[i] for i in sorted(final_results.keys())])
                        with xbmcvfs.File(output_path, 'wb') as f_out: f_out.write(current_srt.encode('utf-8'))
                        if xbmc.Player().isPlaying(): xbmc.Player().setSubtitles(output_path)
                            
                    t_acum = time.time()
                    if (t_acum - last_notify_time > 15 or completed_lines == total_lines) and xbmc.Player().isPlaying():
                        msg = '{}/{} linii | M:{}'.format(completed_lines, total_lines, model_name)
                        notify('Gemini Progres', msg, duration=2000)
                        last_notify_time = t_acum
                else: 
                    xbmc.log("Un batch a esuat complet la traducere.", xbmc.LOGERROR)
                    break

        if not xbmc.Player().isPlaying(): return
        
        if len(final_results) == len(batches):
            statistici = "Modele: {} | Chei: {}".format(", ".join(modele_folosite), ", ".join(chei_folosite))
            notify("Succes Complet", statistici, duration=5000)
            if uploader: threading.Thread(target=uploader.upload_now, args=(output_path, final_name)).start()
        elif completed_lines > 0:
            if not xbmcgui.Dialog().yesno("Incomplet", "Unele linii au eșuat. Păstrezi ce s-a tradus?"):
                xbmcvfs.delete(output_path)

    except Exception as e:
        xbmc.log("Eroare Critica Robot Gemini: " + str(e), xbmc.LOGERROR)