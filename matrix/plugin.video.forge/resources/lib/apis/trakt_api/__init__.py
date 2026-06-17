# -*- coding: utf-8 -*-
"""Trakt API client package.

Split from the original `apis/trakt_api.py` (D3 refactor). Submodules are
imported eagerly so `from apis import trakt_api; trakt_api.add_to_watchlist(...)`
and `router.py`'s `exec("trakt_api.%s(params)" % mode)` dispatch keep working.

`import time` is kept at the package level so legacy test code that patches
`trakt_api.time.time` still reaches the global time module.
"""

import time

from .auth import *  # noqa: F403
from .core import *  # noqa: F403
from .discovery import *  # noqa: F403
from .lists import *  # noqa: F403
from .sync import *  # noqa: F403
