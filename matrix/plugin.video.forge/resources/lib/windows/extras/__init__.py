# -*- coding: utf-8 -*-
"""``windows.extras`` — the big Extras panel, split by section.

Each section lives in its own sibling module as a mixin; ``Extras`` composes
them in :mod:`windows.extras.core`. Callers (``indexers.dialogs``,
``windows.people``) continue to import the public names from
``windows.extras`` unchanged::

    open_window(("windows.extras", "Extras"), "extras.xml", ...)
    open_window(("windows.extras", "ShowTextMedia"), "textviewer_media.xml", ...)
"""

from windows.extras.core import Extras
from windows.extras.text_media import ShowTextMedia

__all__ = ["Extras", "ShowTextMedia"]
