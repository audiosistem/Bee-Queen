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


def _cache_basename(imdb, season, episode, lang, ext='.srt'):
    imdb = str(imdb or '0').strip()
    lang = (lang or 'en').replace(' ', '_')
    if season not in (None, '', 'None', '0') and episode not in (None, '', 'None'):
        return 'GratisRedSubs_%s_%s_%s_%s%s' % (imdb, season, episode, lang, ext)
    return 'GratisRedSubs_%s_%s%s' % (imdb, lang, ext)


def _cache_path(imdb, season, episode, lang, ext='.srt'):
    return os.path.join(
        control.transPath('special://temp/'),
        _cache_basename(imdb, season, episode, lang, ext),
    )


def _load_cached_subtitle(imdb, season, episode, langs):
    """Return (path, display_name) when a usable per-title cache file exists."""
    for lang in langs:
        for ext in ('.srt', '.ass', '.ssa', '.sub', '.vtt'):
            path = _cache_path(imdb, season, episode, lang, ext)
            if not path or not os.path.isfile(path):
                continue
            try:
                with open(path, 'rb') as handle:
                    raw = handle.read()
            except Exception:
                continue
            if not opensubs_api.usable_subtitle_text(raw):
                continue
            return path, os.path.basename(path)
    return None, None


def _write_subtitle_file(path, content):
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
    except Exception:
        pass
    with control.openFile(path, 'w') as handle:
        handle.write(content)


def _notify_subtitles(lang_tag, file_name, cached=False):
    if control.setting('subtitles.notify') != 'true':
        return
    try:
        if not (xbmc.Player().isPlaying() and xbmc.Player().isPlayingVideo()):
            return
    except Exception:
        return
    label = re.sub(r'[_\.]+', ' ', os.path.basename(file_name or 'subtitle')).strip()
    heading = '%s subtitles cached' % lang_tag.upper() if cached else '%s subtitles downloaded' % lang_tag.upper()
    control.infoDialog(label, heading=heading, time=6000)


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
            lang_tag = langs[0]

            cached_path, cached_name = _load_cached_subtitle(imdb, season, episode, langs)
            if cached_path:
                control.sleep(1000)
                xbmc.Player().setSubtitles(cached_path)
                _notify_subtitles(lang_tag, cached_name, cached=True)
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
            subtitle_path = _cache_path(imdb, season, episode, lang_tag, ext)
            _write_subtitle_file(subtitle_path, content)
            control.sleep(1000)
            xbmc.Player().setSubtitles(subtitle_path)
            _notify_subtitles(lang_tag, file_name or os.path.basename(subtitle_path), cached=False)
        except Exception:
            pass
