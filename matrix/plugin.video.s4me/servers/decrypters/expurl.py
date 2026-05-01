# -*- coding: utf-8 -*-

from lib import unshortenit

def expand_url(url):
    e = unshortenit.UnshortenIt()
    estado = 200

    while estado != 0:
        long_url, estado = e.unshorten(url)
        url = long_url

    return long_url

