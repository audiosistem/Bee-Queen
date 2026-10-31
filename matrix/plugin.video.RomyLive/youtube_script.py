# -*- coding: utf-8 -*-
"""Entry point for bundled YouTube context-menu/settings actions."""
import sys
from romy_youtube import _engine_path

if __name__ == '__main__':
    _engine_path()
    from romy_youtube_engine.kodion import script_actions
    script_actions.run(sys.argv)