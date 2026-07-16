# -*- coding: utf-8 -*-

import os
import re

from kodi_six import xbmc

from resources.lib.modules import control
from resources.lib.apis import opensubs_api

_LANG_OVERRIDES = {
    'Portuguese(Brazil)': 'pb',
    'Chinese': 'zh-cn',
}


def _language_code(label):
    if not label:
        return ''
    if label in _LANG_OVERRIDES:
        return _LANG_OVERRIDES[label]
    try:
        code = xbmc.convertLanguage(label, xbmc.ISO_639_1)
        if code and code != 'und':
            return code
    except Exception:
        pass
    return ''


def _language_preferences():
    langs = []
    for setting_id in ('subtitles.lang.1', 'subtitles.lang.2'):
        code = _language_code(control.setting(setting_id))
        if code and code not in langs:
            langs.append(code)
    return langs or ['en']


def _subtitle_extension(file_name):
    if not file_name:
        return '.srt'
    ext = os.path.splitext(str(file_name).split('?')[0])[1].lower()
    if ext in ('.srt', '.ass', '.ssa', '.sub', '.vtt'):
        return ext
    return '.srt'


class subtitles:
    def get(self, imdb, season, episode, year=None, title=None):
        try:
            if control.setting('subtitles') != 'true':
                return
            if not imdb or imdb == '0':
                return
            if not opensubs_api.configured():
                return
            langs = _language_preferences()
            try:
                active = xbmc.Player().getSubtitles()
            except Exception:
                active = ''
            if active and active in langs:
                return
            languages = ','.join(langs)
            content, file_name = opensubs_api.fetch_playback_subtitle(
                imdb,
                season=season,
                episode=episode,
                year=year,
                languages=languages,
                title=title,
            )
            if not content:
                return
            ext = _subtitle_extension(file_name)
            lang_tag = langs[0]
            subtitle_path = os.path.join(
                control.transPath('special://temp/'),
                'GratisRedSubs.%s%s' % (lang_tag, ext),
            )
            with control.openFile(subtitle_path, 'w') as handle:
                handle.write(content)
            control.sleep(1000)
            xbmc.Player().setSubtitles(subtitle_path)
            if control.setting('subtitles.notify') == 'true':
                if xbmc.Player().isPlaying() and xbmc.Player().isPlayingVideo():
                    label = re.sub(r'[_\.]+', ' ', os.path.basename(file_name or 'subtitle')).strip()
                    control.infoDialog(
                        label,
                        heading='%s subtitles downloaded' % lang_tag.upper(),
                        time=6000,
                    )
        except Exception:
            pass
