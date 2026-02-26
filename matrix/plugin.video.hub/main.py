import sys
import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import parse_qsl, urlencode
import importlib.util
import os
import xbmcaddon
import importlib # Import importlib

# Get the plugin handle
_handle = int(sys.argv[1])
_base_url = sys.argv[0]

_addon = xbmcaddon.Addon('plugin.video.hub')

def get_params():
    """Get the plugin parameters"""
    paramstring = sys.argv[2][1:]
    return dict(parse_qsl(paramstring))

def main_menu():
    """Main plugin function"""
    
    # Add menu items conditionally
    if _addon.getSettingBool('show_xtreme_iptv'):
        add_menu_item('Xtream IPTV', 'xtremeiptvplayer')
    if _addon.getSettingBool('show_stalker_iptv'):
        add_menu_item('Stalker IPTV', 'stalker')
    if _addon.getSettingBool('show_edem_iptv'):
        add_menu_item('Edem IPTV', 'edemplayer')
    if _addon.getSettingBool('show_m3u_player'):
        add_menu_item('Liste M3U', 'm3uplayer')
    if _addon.getSettingBool('show_radio_romania'):
        add_menu_item('Radio Romania', 'radio_ro')
    if _addon.getSettingBool('show_alte_liste'):
        add_menu_item('Alte liste', 'alteliste')
    
    add_menu_item('Setari', 'settings') # Always show settings

    # End of directory
    xbmcplugin.endOfDirectory(_handle)

def add_menu_item(name, action):
    """Function to add a menu item"""
    li = xbmcgui.ListItem(label=name)
    if action == 'settings':
        url = f'{_base_url}?action={action}'
        li.setProperty('IsPlayable', 'false') # Settings is not a playable item
    else:
        url = f'{_base_url}?action={action}'
    xbmcplugin.addDirectoryItem(handle=_handle, url=url, listitem=li, isFolder=True)

def router(params):
    """Router function"""
    action = params.get('action')

    if action is None:
        main_menu()
    elif action == 'settings': # Handle settings action
        _addon.openSettings()
    else:
        module_name = action
        if action == 'stalker':
            # Stalker uses addon.py as its entry point
            full_module_name = f"sources.{module_name}.addon"
        else:
            # Other modules use main.py as their entry point
            full_module_name = f"sources.{module_name}.main"

        try:
            # Temporarily add the project root to sys.path to allow absolute imports from 'sources'
            project_root = os.path.dirname(__file__)
            sys.path.insert(0, project_root)
            xbmc.log(f"main.py: sys.path before import: {sys.path}", level=xbmc.LOGINFO)

            module = importlib.import_module(full_module_name)
            
            # Restore sys.path
            sys.path.remove(project_root)

            # Temporarily change the current working directory to the module's directory
            # This is important for modules that rely on relative paths for resources
            original_cwd = os.getcwd()
            module_dir = os.path.join(project_root, 'sources', module_name)
            os.chdir(module_dir)
            
            # Pass the original sys.argv to the sub-plugin's router
            # The sub-plugin's router expects sys.argv[0] to be its own plugin URL
            # and sys.argv[2] to be the query string.
            original_argv = sys.argv
            sys.argv = [f'plugin://plugin.video.hub/sources/{action}/', str(_handle), sys.argv[2]]
            
            module.router(get_params()) # Call the sub-plugin's router
            
            sys.argv = original_argv # Restore original sys.argv
            os.chdir(original_cwd) # Restore original current working directory

        except ImportError as e:
            xbmc.log(f"Error loading module {full_module_name}: {e}", level=xbmc.LOGERROR)
            xbmcgui.Dialog().notification('Error', f'Failed to load module: {action}', xbmcgui.NOTIFICATION_ERROR)
        except Exception as e:
            xbmc.log(f"Error in module {full_module_name}: {e}", level=xbmc.LOGERROR)
            xbmcgui.Dialog().notification('Error', f'Error in module {action}', xbmcgui.NOTIFICATION_ERROR)

if __name__ == '__main__':
    router(get_params())
