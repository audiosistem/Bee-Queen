from entry import logger, POVMonitor

if __name__ == '__main__':
	logger('POV', 'Main Monitor Service Starting (%s)' % POVMonitor.ver())
	logger('POV', 'Settings Monitor Service Starting')

	with POVMonitor() as pov:
		pov.startUpServices()
		pov.waitForAbort()

	logger('POV', 'Settings Monitor Service Finished')
	logger('POV', 'Main Monitor Service Finished')

