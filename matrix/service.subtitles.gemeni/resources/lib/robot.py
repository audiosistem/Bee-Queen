# -*- coding: utf-8 -*-
import xbmc, xbmcgui, xbmcvfs
import os, sys, re, json, urllib.parse, urllib.request
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURARE COPIATĂ ---
MODEL_PREFERAT = [
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash-lite-preview",
    ]
CPS_MAX = 21 
PAUZA_DUPA_EROARE = 0.5 
MAX_WORKERS = 4 

# --- LOGICA DE IMPORT CHEI DIN EXTERIOR ---
try:
    from .key import api_keys as backup_keys
except ImportError:
    try: 
        import key
        backup_keys = key.api_keys 
    except: 
        backup_keys = []

def get_duration(timing_str):
    try:
        start, end = timing_str.split(' --> ')
        t1 = datetime.strptime(start.replace(',', '.'), '%H:%M:%S.%f')
        t2 = datetime.strptime(end.replace(',', '.'), '%H:%M:%S.%f')
        return max((t2 - t1).total_seconds(), 0.5)
    except: return 2.0

def translate_gemini(texts_dict, target_lang, api_key, model_name, style_instruction=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    prompt = (f"Translate to {target_lang}.\n{style_instruction}\n"
              "Return ONLY a JSON object: {{'ID': 'translation'}}. No talk.")
    
    payload = {
        "contents": [{"parts": [{"text": f"{prompt}\n\n{json.dumps(texts_dict)}"}]}],
        "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}
    }
    try:
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=15) as r:
            res_data = json.loads(r.read().decode('utf-8'))
            text_raspuns = res_data['candidates'][0]['content']['parts'][0]['text']
            match = re.search(r'\{.*\}', text_raspuns, re.DOTALL)
            return json.loads(match.group()) if match else json.loads(text_raspuns)
    except: return None

def process_batch_worker(batch, target_lang, all_keys, style_instruction):
    # b[0] e ID-ul, b[2] e textul original
    to_translate = {b[0]: re.sub(r'<[^>]*>', '', b[2]).strip() for b in batch}
    for k_idx, current_key in enumerate(all_keys):
        for current_model in MODEL_PREFERAT:
            rezultat = translate_gemini(to_translate, target_lang, current_key, current_model, style_instruction)
            if rezultat:
                chunk_srt = ""
                for b_id, timing, orig_text in batch:
                    traducere = rezultat.get(str(b_id), rezultat.get(b_id, orig_text))
                    chunk_srt += f"{b_id}\n{timing}\n{traducere}\n\n"
                return chunk_srt, k_idx + 1, current_model
        time.sleep(PAUZA_DUPA_EROARE)
    return None, 0, ""

def run_translation(sub_addon_id):
    import xbmcaddon
    _addon = xbmcaddon.Addon(sub_addon_id)
    if _addon.getSetting('robot_activat') != 'true': return

    # --- COLECTARE CHEI (Addon + Backup) ---
    keys_din_setari = [_addon.getSetting('api_key_google')] + [_addon.getSetting(f'api_key_{i}') for i in range(2, 6)]
    all_keys = list(dict.fromkeys([k for k in keys_din_setari if k] + backup_keys))

    if not all_keys:
        xbmcgui.Dialog().ok("Eroare", "Nu s-a găsit nicio cheie API (nici în setări, nici în key.py)!"); return

    langs = ["ro", "en", "es", "fr", "de", "it", "hu", "pt", "ru", "tr", "bg", "el", "pl", "cs", "nl"]
    try: target_lang = langs[_addon.getSettingInt('subs_languages')]
    except: target_lang = "ro"

    # Încercăm să luăm stilul dacă funcția build_style_instruction există
    try:
        from translator import build_style_instruction
        style_instruction = build_style_instruction(target_lang)
    except:
        style_instruction = "Professional localization."

    profile_path = xbmcvfs.translatePath(f'special://profile/addon_data/{sub_addon_id}/')
    _, files = xbmcvfs.listdir(profile_path)
    srt_files = [f for f in files if f.lower().endswith('.srt') and not f.startswith('robot_tradus')]
    if not srt_files: return
    
    sub_path = os.path.join(profile_path, srt_files[0])
    try:
        f = xbmcvfs.File(sub_path); content = f.read(); f.close()
        pattern = re.compile(r'(\d+)\r?\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\r?\n([\s\S]*?)(?=\r?\n\r?\n|$)')
        blocks = pattern.findall(content)
        
        batch_size = 80
        batches = [blocks[i:i + batch_size] for i in range(0, len(blocks), batch_size)]
        
        dp = xbmcgui.DialogProgress()
        dp.create("Robot Gemini", "Pornire...")

        final_results = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_batch_worker, b, target_lang, all_keys, style_instruction): i for i, b in enumerate(batches)}
            
            completed = 0
            for future in futures:
                if dp.iscanceled(): break
                batch_idx = futures[future]
                res_text, k_num, model_name = future.result()
                
                # --- LOGICA RETRY ---
                retry_attempt = 0
                while not res_text and retry_attempt < 3:
                    retry_attempt += 1
                    dp.update(int((completed / len(batches)) * 100), f"Eroare pachet {batch_idx+1}. Reîncercare {retry_attempt}/3...")
                    time.sleep(2)
                    res_text, k_num, model_name = process_batch_worker(batches[batch_idx], target_lang, all_keys, style_instruction)

                if res_text:
                    final_results[batch_idx] = res_text
                    completed += 1
                    progres = int((completed / len(batches)) * 100)
                    dp.update(progres, f"Progres: {completed}/{len(batches)}\nModel: {model_name}\nCheie: {k_num}")
                else:
                    xbmcgui.Dialog().ok("Eroare", f"Pachetul {batch_idx+1} a eșuat definitiv."); break
        dp.close()

        if len(final_results) == len(batches):
            translated_srt = "".join([final_results[i] for i in sorted(final_results.keys())])
            output_path = os.path.join(profile_path, f"robot_tradus.{target_lang}.srt")
            f = xbmcvfs.File(output_path, 'w'); f.write(translated_srt); f.close()
            xbmc.Player().setSubtitles(output_path)
    except Exception as e:
        xbmc.log(f"ROBOT_FATAL: {str(e)}", xbmc.LOGERROR)
