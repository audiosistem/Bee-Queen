# -*- coding: utf-8 -*-

import os
import six
import traceback

from datetime import datetime
from io import open
from kodi_six import xbmc
from resources.lib.modules import control

LOGDEBUG = xbmc.LOGDEBUG
LOGINFO = xbmc.LOGINFO
LOGNOTICE = xbmc.LOGNOTICE if control.getKodiVersion() < 19 else xbmc.LOGINFO
LOGWARNING = xbmc.LOGWARNING
LOGERROR = xbmc.LOGERROR
LOGFATAL = xbmc.LOGFATAL
LOGNONE = xbmc.LOGNONE

version = control.addonInfo('version')
#ChangeLog_head = '--[Scrubs v2 - %s - Changelog]--' % version
WhatisNew_head = '--[Scrubs v2 - %s - What Is New]--' % version
PreviousLog_head = '--[Scrubs v2 current version - %s]--' % version
DebugLog_head = '--[Scrubs v2 - %s - DebugLog]--' % version
DEBUGPREFIX = '[Scrubs v2 - %s - DEBUG]' % version

LOGPATH = control.transPath('special://logpath/')
log_file = os.path.join(LOGPATH, 'scrubsv2.log')
changelogfile = os.path.join(control.addonPath, 'resources', 'whatisnew.txt')

debug_enabled = control.setting('addon.debug')
debugtime_enabled = control.setting('addon.debugtime')
debugspacer_enabled = control.setting('addon.debugspacer')


def log(msg, trace=0, level=LOGDEBUG):
    if not debug_enabled == 'true':
        return
    try:
        if trace == 1:
            failure = six.ensure_str(traceback.format_exc())
            _msg = '%s: %s' % (six.ensure_text(msg), failure)
        else:
            _msg = '%s' % six.ensure_text(msg)
        if not os.path.exists(log_file):
            f = open(log_file, 'w')
            f.close()
        with open(log_file, 'a', encoding='utf-8') as f:
            if not debugtime_enabled == 'true':
                line = '%s: %s' % (DEBUGPREFIX, _msg)
            else:
                line = '[%s %s] %s: %s' % (datetime.now().date(), str(datetime.now().time())[:8], DEBUGPREFIX, _msg)
            if not debugspacer_enabled == 'true':
                f.write(line.rstrip('\r\n') + '\n')
            else:
                f.write('' + '\n')
                f.write(line.rstrip('\r\n') + '\n')
                f.write('' + '\n')
    except Exception as e:
        xbmc.log('%s Logging Failure: %s' % (DEBUGPREFIX, e), level)
        pass


def changelog():
    try:
        control.textViewer(changelogfile, WhatisNew_head)
    except:
        log('changelog', 1)
        control.infoDialog('Error opening changelog')
        pass


def previous_redwizard_changelogs():
    try:
        import requests
        previous_redwizard_changelogs_link = 'https://repo.redwizard.xyz/plugin-changelogs/scrubsv2-changelogs/previous_redwizard_changelogs.txt'
        previous_redwizard_changelogs_html = requests.get(previous_redwizard_changelogs_link).text
        control.textViewer2(previous_redwizard_changelogs_html, PreviousLog_head)
    except:
        log('previous_changelogs', 1)
        control.infoDialog('Error Opening Previous Red Wizard Changelogs')
        pass


def previous_jewbmx_changelogs():
    try:
        import requests
        previous_jewbmx_changelogs_link = 'https://repo.redwizard.xyz/plugin-changelogs/scrubsv2-changelogs/previous_jewbmx_changelogs.txt'
        previous_jewbmx_changelogs_html = requests.get(previous_jewbmx_changelogs_link).text
        control.textViewer2(previous_jewbmx_changelogs_html, PreviousLog_head)
    except:
        log('previous_changelogs', 1)
        control.infoDialog('Error Opening Previous JewBMX Changelogs')
        pass


def view_log():
    try:
        control.textViewer(log_file, DebugLog_head)
    except:
        log('view_log', 1)
        control.infoDialog('Error opening log file')
        pass


def empty_log():
    try:
        open(log_file, 'w').close()
    except:
        log('empty_log', 1)
        control.infoDialog('Error emptying log file')
        pass


