# -*- coding: utf-8 -*-
"""Compatibility bridge.

JackSparrow expects TextViewerXML under resources.lib.jacksparrow.textviewer.
luc_kodi already provides it under resources.lib.windows.textviewer.
"""

from resources.lib.windows.textviewer import TextViewerXML  # re-export
