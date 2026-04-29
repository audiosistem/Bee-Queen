# -*- coding: utf-8 -*-
"""
    air_table OTB2 Tv Shows Template
    Copyright (C) 2021,
    Version 1.0.1
    Team MicroJen

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

    -------------------------------------------------------------

    Usage Examples:


    Returns the OTB2 TV Shows list-

    <dir>
    <title>OTB2 TV Shows</title>
    <airtable>all</airtable>
    </dir>
   
    --------------------------------------------------------------

"""

import xbmc, xbmcaddon, xbmcgui
from ..plugin import Plugin

"""
----------------------------------------------------------
"""
table_id = "appAOlZIM6vIq6Tr6" # your table_id
table_name = "my_movies"   # your table name
workspace_api_key = "keyriB3N9JnGEYorn" # your airtable api key
"""
----------------------------------------------------------
"""

CACHE_TIME = 0  # change to wanted cache time in seconds

addon_fanart = xbmcaddon.Addon().getAddonInfo('fanart')
addon_icon = xbmcaddon.Addon().getAddonInfo('icon')
AddonName = xbmc.getInfoLabel('Container.PluginName')
AddonName = xbmcaddon.Addon(AddonName).getAddonInfo('id')


class airtable_parser(Plugin):
    name = "airtable parser" 
    priority = 100

    def process_item(self, item):
        if "airtable" in item:
            table_info = item["airtable"]
            thumbnail = item.get("thumbnail", "")
            fanart = item.get("fanart", "")
            list_item = xbmcgui.ListItem(
                item.get("title", item.get("name", "")), offscreen=True
            )
            list_item.setArt({"thumb": thumbnail, "fanart": fanart})
            item["list_item"] = list_item
            item["is_dir"] = True
            if table_info.startswith("season") or table_info.startswith("show"): item["link"] = "airtable/jen/%s***%s" % (table_info, workspace_api_key)
            else: item["link"] = "airtable/jen/all|%s|%s|all***%s" % (table_name, table_id, workspace_api_key)
            return item





            