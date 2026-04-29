import xbmcgui
import xbmcaddon
import requests
from ..plugin import Plugin
import logging
import xbmcvfs
import os

addon_id = xbmcaddon.Addon().getAddonInfo('id')

logger = logging.getLogger(__name__)
LOGPATH = xbmcvfs.translatePath('special://logpath/')
FILENAME = 'new.log'
LOG_FILE = os.path.join(LOGPATH, FILENAME)

def log_debug(msg):
    """Write to both file and Kodi log"""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{msg}\n")
        logger.debug(msg)
    except Exception as e:
        logger.error(f"Logging failed: {str(e)}")

class NewPlugin(Plugin):
    name = "new"
    priority = 100

    def make_request(self, url):
        """Handle request submissions"""
        dialog = xbmcgui.Dialog()
        user_input = dialog.input("Enter your request", type=xbmcgui.INPUT_ALPHANUM)
        if user_input:
            try:
                response = requests.post(
                    "http://62.210.85.247:5001/api/requests",
                    json={"request": user_input},
                    timeout=10
                )
                if response.status_code == 200:
                    dialog.ok(addon_id, "Request sent successfully!")
                else:
                    dialog.ok(addon_id, f"Error: Server responded with status {response.status_code}")
                    log_debug(f"Request failed with status code: {response.status_code}")
            except requests.RequestException as e:
                dialog.ok(addon_id, f"Error: Could not connect to server ({str(e)})")
                log_debug(f"Request failed: {str(e)}")

    def process_item(self, item):
        if self.name in item:
            link = item.get(self.name, "")
            item["link"] = f"{self.name}/{link}"
            item["is_dir"] = False
            list_item = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
            item["list_item"] = list_item
            return item

    def routes(self, plugin):
        # Register the route handler
        plugin.route(f"/{self.name}/<path:url>")(self.make_request)

def register():
    return NewPlugin()