"""
	luc_kodi Add-on
"""

from resources.lib.modules.control import setting as getSetting

def debrid_resolvers(order_matters=True):
	try:
		ad_enabled = getSetting('alldebrid.token') != '' and getSetting('alldebrid.enable') == 'true'
		ed_enabled = getSetting('easydebrid.token') != '' and getSetting('easydebrid.enable') == 'true'
		oc_enabled = getSetting('offcloud.token') != '' and getSetting('offcloud.enable') == 'true'
		pm_enabled = getSetting('premiumize.token') != '' and getSetting('premiumize.enable') == 'true'
		rd_enabled = getSetting('realdebrid.token') != '' and getSetting('realdebrid.enable') == 'true'
		tb_enabled = getSetting('torbox.token') != '' and getSetting('torbox.enable') == 'true'
		premium_resolvers = []
		if ad_enabled:
			from resources.lib.debrid import alldebrid
			premium_resolvers.append(alldebrid.AllDebrid())
		if ed_enabled:
			from resources.lib.debrid import easydebrid
			premium_resolvers.append(easydebrid.EasyDebrid())
		if oc_enabled:
			from resources.lib.debrid import offcloud
			premium_resolvers.append(offcloud.Offcloud())
		if pm_enabled:
			from resources.lib.debrid import premiumize
			premium_resolvers.append(premiumize.Premiumize())
		if rd_enabled:
			from resources.lib.debrid import realdebrid
			premium_resolvers.append(realdebrid.RealDebrid())
		if tb_enabled:
			from resources.lib.debrid import torbox
			premium_resolvers.append(torbox.TorBox())
		if order_matters:
			premium_resolvers.sort(key=lambda x: get_priority(x))
		return premium_resolvers
	except:
		from resources.lib.modules import log_utils
		log_utils.error()

def status():
	return debrid_resolvers() != []

def get_priority(cls):
	try:
		return int(getSetting((cls.__class__.__name__ + '.priority').lower()))
	except:
		from resources.lib.modules import log_utils
		log_utils.error()
		return 10
