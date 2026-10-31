import sys
import xbmcvfs

files_path = 'special://home/addons/plugin.video.pov/lib/pov/'
pov_path = xbmcvfs.translatePath('special://home/addons/plugin.video.pov/lib/')
if pov_path not in sys.path: sys.path.insert(0, pov_path)

from pov import sources
from pov.modules.client import randomagent
from pov.modules.health import health
from pov.modules.undesirables import Undesirables, add_new_default_keywords, undesirablesInput, undesirablesSelect, undesirablesUserRemove

