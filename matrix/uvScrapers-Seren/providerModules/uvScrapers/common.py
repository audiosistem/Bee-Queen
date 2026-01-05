import os
import html

import requests
import xbmc
import xbmcvfs

from resources.lib.common import provider_tools
from resources.lib.modules.globals import g

PACKAGE_NAME = "uvScrapers"


def log(msg, level="debug"):
    g.log("   >>>   {}".format(msg), level)


def debug(msg, format=None):
    if format:
        msg.format(format)
    g.log(msg, "debug")


def get_all_relative_py_files(file):
    files = os.listdir(os.path.dirname(file))
    return [
        filename[:-3]
        for filename in files
        if not filename.startswith("__") and filename.endswith(".py")
    ]


def get_setting(id):
    return provider_tools.get_setting(PACKAGE_NAME, id)


def set_setting(id, value):
    return provider_tools.set_setting(PACKAGE_NAME, id, value)


def execute_jsonrpc(method, params):
    import json

    call_params = {"id": 1, "jsonrpc": "2.0", "method": method, "params": params}
    call = json.dumps(call_params)
    response = xbmc.executeJSONRPC(call)
    return json.loads(response)


def cleantext(text):
    try:
        text = text.encode('utf-8', 'ignore').decode("utf-8")
    except:
        pass
    text = html.unescape(text)
    return text.strip()


def get_subs(tracks, existing_subs):
    for track in tracks:
        if ('hun' in track["label"].lower() or 'rom' in track["label"].lower() or 'eng' in track["label"].lower()) and 'benga' not in track["label"].lower():
            if {track['label']: track['file']} not in existing_subs:
                existing_subs.append({track['label']: track['file']})
    return existing_subs


def fix_subtitles(subs):
    fixed_subs = []
    for sub in subs:
        for language, file in sub.items():
            language = language.lower()
            language_nr = language.split(' ')[-1].split('-')[-1]
            language_nr = '' if language_nr == language else '-' + language_nr
            if 'hun' in language:
                language_code = 'hun'
            elif 'rom' in language:
                language_code = 'rum'
            elif 'eng' in language:
                language_code = 'eng'
            else:
                language_code = ''
            if language_code in file.split('/')[-1]:
                fixed_subs.append(file)
            else:
                try:
                    subtitle = requests.get(file).text
                    subtitle_filename = file.split('/')[-1]
                    subtitle_extension = subtitle_filename.split('.')[-1]
                    subtitle_filename = subtitle_filename.replace('.' + subtitle_extension, f'.{language_code}{language_nr}.{subtitle_extension}')
                    subtitle_path = os.path.join(xbmcvfs.translatePath("special://temp/"), subtitle_filename)
                    if not xbmcvfs.exists(subtitle_path):
                        with xbmcvfs.File(subtitle_path, 'w') as f:
                            f.write(subtitle)
                    fixed_subs.append(subtitle_path)
                except Exception as e:
                    fixed_subs.append(file)
                    log(f"Error processing subtitle {file}: {e}")
    return fixed_subs
