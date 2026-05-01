# -*- coding: utf-8 -*-
# -*- Server Voe -*-
# -*- Created for Alfa-addon -*-
# -*- By the Alfa Develop Group -*-
# some pieces of code taken from https://github.com/Gujal00/ResolveURL/

from core import httptools, support
from core import scrapertools
from platformcode import logger
from platformcode import config
from six.moves import urllib_parse
import sys
import base64
import re

PY3 = False
if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int


def test_video_exists(page_url):
    global data
    logger.info("(page_url='%s')" % page_url)
    data = httptools.downloadpage(page_url).data
    redirect_url = support.match(data, patron=r"}\s}\selse\s{\swindow.location.href\s=\s'(http[^']+)'").match

    if redirect_url:
        data = httptools.downloadpage(redirect_url).data

    if "File not found" in data or "File is no longer available" in data:
        return False, config.get_localized_string(70449) % "VOE"
    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    video_urls = []
    video_srcs = support.match(data, patron=r'json">\["([^"]+)"]</script>\s*<script\s*src="([^"]+)', debug=False).match
    if video_srcs:
        d = support.match(urllib_parse.urljoin(page_url, video_srcs[1]), patron=r"(\[(?:'\W{2}'[,\]]){1,9})", debug=False).match
        if d:
            s = voe_decode(video_srcs[0], d[1])
            video_srcs = [(s.get(x).split("?")[0].split(".")[-1], s.get(x)) for x in ['file', 'source', 'direct_access_url'] if x in s.keys()]
            if len(video_srcs) > 1:
                video_srcs.sort(key=lambda x: int(re.sub(r"\D", "", x[0])))
            for x in video_srcs:
                video_urls.append([" [Voe] " + ('hls' if x[0] == 'm3u8' else x[0]), x[1]])
    
    return video_urls


def get_filename(page_url):
    title = httptools.downloadpage(page_url).data.split('<title>')[1].split('</title>')[0]
    prefix = 'Watch '
    if title.startswith(prefix):
        return title[len(prefix):]
    return ""
    
def voe_decode(ct, luts):
    import json
    lut = [''.join([('\\' + x) if x in '.*+?^${}()|[]\\' else x for x in i]) for i in luts[2:-2].split("','")]
    txt = ''
    for i in ct:
        x = ord(i)
        if 64 < x < 91:
            x = (x - 52) % 26 + 65
        elif 96 < x < 123:
            x = (x - 84) % 26 + 97
        txt += chr(x)
    for i in lut:
        txt = re.sub(i, '', txt)

    ct = base64.b64decode(txt).decode()
    txt = ''.join([chr(ord(i) - 3) for i in ct])
    txt = base64.b64decode(txt[::-1]).decode()
    return json.loads(txt)
