"""
	Fenomscrapers Module
"""

import os
import importlib
from pkgutil import iter_modules, walk_packages
from pov.modules.control import setting as getSetting

#sourcePath = os.path.dirname(__file__)
#files = os.listdir(sourcePath)
#__all__ = [filename[:-3] for filename in files if not filename.startswith('__') and filename.endswith('.py')]


def sources(specified_folders=None, ret_all=False):
	sourcePath = os.path.dirname(__file__)
	try:
		sourceDict = []
		append = sourceDict.append
		for loader, module_name, is_pkg in iter_modules([sourcePath]):
			if is_pkg: continue
			if not ret_all and not enabledCheck(module_name): continue
			try:
				module_source = importlib.import_module('.' + module_name, package=__name__).source
				if hasattr(module_source, 'clear_all'): module_source.clear_all()
				append((module_name, module_source))
			except Exception as e:
				from pov.modules import log_utils
				log_utils.error()
		return sourceDict
	except:
		from pov.modules import log_utils
		log_utils.error()
		return []

def enabledCheck(module_name):
	try: return getSetting('provider.' + module_name) == 'true'
	except:
		from pov.modules import log_utils
		log_utils.error()
		return True

def __legacy_sources(specified_folders=None, ret_all=False):
	debug = getSetting('debug.enabled') == 'true'
	sourceFolder = 'providers'
	try:
		sourceDict = []
		append = sourceDict.append
		sourceFolderLocation = os.path.join(os.path.dirname(__file__), sourceFolder)
		sourceSubFolders = [x[1] for x in os.walk(sourceFolderLocation)][0]
		if specified_folders: sourceSubFolders = specified_folders
		for i in sourceSubFolders:
			for loader, module_name, is_pkg in walk_packages([os.path.join(sourceFolderLocation, i)]):
				if is_pkg: continue
				if ret_all or enabledCheck(module_name):
					try:
#						module = loader.find_module(module_name).load_module(module_name)
						module = loader.find_spec(module_name).loader.load_module(module_name)
						append((module_name, module.source))
					except Exception as e:
						if not debug: continue
						from pov.modules import log_utils
						log_utils.log('Error: Loading module: "%s": %s' % (module_name, e), level=log_utils.LOGWARNING)
		return sourceDict
	except:
		from pov.modules import log_utils
		log_utils.error()
		return []

