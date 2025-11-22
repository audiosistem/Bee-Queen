# -*- coding: utf-8 -*-
import os
import xbmc
import xbmcaddon
import xbmcvfs
from resources.lib.windows.base import BaseDialog
from resources.lib.functions import dataPath, log


class ChannelsXML(BaseDialog):
    def __init__(self, *args, **kwargs):
        super(ChannelsXML, self).__init__(self, args)
        self.window_id = 2003
        self.channels = kwargs.get('channels')
        self.total_results = str(len(self.channels))
        self.info = kwargs.get('info')
        self.addon_path = args[1]
        self.activated = None
        self.lines = []
        self.make_items()
        self.set_properties()
        self.selected = (None, '')

    def onInit(self):
        super(ChannelsXML, self).onInit()
        win = self.getControl(self.window_id)
        win.addItems(self.item_list)
        self.setFocusId(self.window_id)

    def run(self):
        self.doModal()
        try: del self.info
        except: pass
        return self.selected

    def onAction(self, action):
        try:
            action_id = action.getId()
            if action_id in self.selection_actions:
                focus_id = self.getFocusId()
                position = self.get_position(self.window_id)
                chosen = self.item_list[position]
                if focus_id == 2003:
                    name = chosen.getProperty('cinemagia.name')
                    activated = chosen.getProperty('cinemagia.activated') == 'true'
                    url = chosen.getProperty('cinemagia.url')
                    if activated:
                        with open(dataPath, 'w') as f:
                            for line in self.lines:
                                lineurl = line.split(',')[0]
                                if lineurl.rstrip() != url:
                                    f.write('%s\n' % line)
                    else:
                        if os.path.exists(dataPath):
                            with open(dataPath, 'a') as f:
                                f.write('%s,%s\n' % (url, name))
                        else:
                            with open(dataPath, 'w+') as f:
                                f.write('%s,%s\n' % (url, name))
                    self.make_items()
                    self.set_properties()
                    win = self.getControl(self.window_id)
                    win.reset()
                    win.addItems(self.item_list)
                    win.selectItem(position)
            if action in self.closing_actions:
                self.selected = (None, '')
                self.close()
        except BaseException as e:
            log(e)

    def make_items(self):
        def builder():
            selectedicon = os.path.join(self.addon_path, 'resources', 'skins', 'Default', 'media', 'common', 'check.png')
            unselectedicon = os.path.join(self.addon_path, 'resources', 'skins', 'Default', 'media', 'common', 'black.png')
            j = 1
            self.active_count = 0
            lines = []
            liner = []
            if os.path.exists(dataPath):
                with open(dataPath) as f:
                    lines = f.readlines()
                self.lines = [line.rstrip() for line in lines]
            if self.lines:
                lines = [liner.split(',')[0].rstrip() for liner in self.lines]
            for count, item in enumerate(self.channels, 1):
                try:
                    url, name = item
                    listitem = self.make_listitem()
                    listitem.setProperty('cinemagia.name', name)
                    if url in lines:
                        self.active_count += 1
                        listitem.setProperty('cinemagia.activated', 'true')
                        listitem.setProperty('cinemagia.type', selectedicon)
                    else:
                        listitem.setProperty('cinemagia.activated', 'false')
                        listitem.setProperty('cinemagia.type', unselectedicon)
                    listitem.setProperty('cinemagia.url', url)
                    listitem.setProperty('cinemagia.number', str(j))
                    j += 1
                    yield listitem
                except BaseException as e:
                    log(e)
        try:
            self.item_list = list(builder())
            self.total_results = str(len(self.item_list) - 1)
        except BaseException as e:
            log(e)

    def set_properties(self):
        self.setProperty('cinemagia.activated_items', str(self.active_count))
        self.setProperty('cinemagia.total_items', self.total_results)
