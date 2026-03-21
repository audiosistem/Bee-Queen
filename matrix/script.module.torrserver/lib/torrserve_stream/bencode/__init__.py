from __future__ import absolute_import

import sys

if sys.version_info >=  (3, 0):
    from .py3 import *
else:
    from .py2.bencode import *