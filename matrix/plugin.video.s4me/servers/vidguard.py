# Conector vidguard
#
# some pieces of code taken from https://github.com/Gujal00/ResolveURL/
# --------------------------------------------------------
import base64
import json
import binascii

from core import httptools
from core import scrapertools
from platformcode import config
from platformcode import logger


def test_video_exists(page_url):
    logger.debug("(page_url='%s')" % page_url)
    data = httptools.downloadpage(page_url)
    if data.code == 404:
        return False,  config.get_localized_string(70449) % "VidGuard"
    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    logger.debug("url=" + page_url)
    video_urls = []
    data = httptools.downloadpage(page_url).data
    enc_data = scrapertools.find_single_match(data, r'eval\("window\.ADBLOCKER\s*=\s*false;\\n(.+?);"\);</script')
    if enc_data:
        import aadecode
        enc_data = enc_data.replace('\\u002b', '+')
        enc_data = enc_data.replace('\\u0027', "'")
        enc_data = enc_data.replace('\\u0022', '"')
        enc_data = enc_data.replace('\\/', '/')
        enc_data = enc_data.replace('\\\\', '\\')
        enc_data = enc_data.replace('\\"', '"')
        enc_data = aadecode.decode(enc_data, alt = True)
        stream_url = json.loads(enc_data[11:]).get('stream')
        video_urls.append(['hls', sig_decode(stream_url)])

    return video_urls

def sig_decode(url):
        sig = url.split('sig=')[1].split('&')[0]
        t = ''
        for v in binascii.unhexlify(sig):
            t += chr((v if isinstance(v, int) else ord(v)) ^ 2)
        t = list(base64.b64decode(t + '==')[:-5][::-1])

        for i in range(0, len(t) - 1, 2):
            t[i + 1], t[i] = t[i], t[i + 1]

        url = url.replace(sig, ''.join(chr(x) for x in t)[:-5])
        return url
