# -*- coding: utf-8 -*-
import xbmcvfs, requests, os, xbmc

def fix_subtitles(subs):
    fixed_subs = []
    temp_path = xbmcvfs.translatePath("special://temp/")
    for sub in subs:
        for lang_label, file_url in sub.items():
            try:
                lang = lang_label.lower()
                code = 'hun' if 'hun' in lang else 'rum' if any(x in lang for x in ['rom', 'rum']) else 'eng'
                dest = os.path.join(temp_path, f"cc_{abs(hash(file_url))}.{code}.srt")
                
                if not xbmcvfs.exists(dest):
                    r = requests.get(file_url, timeout=10)
                    if r.status_code == 200:
                        with xbmcvfs.File(dest, 'wb') as f: f.write(r.content)
                fixed_subs.append(dest)
            except: 
                fixed_subs.append(file_url)
    return fixed_subs
