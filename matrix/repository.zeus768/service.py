"""
Zeus768 Repository - GitHub Commit Watcher Service
Checks for new commits on the repo and forces Kodi to check for addon updates.
"""
import xbmc
import xbmcgui
import xbmcaddon
import json
import os
import time

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_ICON = os.path.join(ADDON_PATH, 'icon.png')

GITHUB_API = 'https://api.github.com/repos/Zeus768/zeus768/commits'
GITHUB_BRANCH = 'main'
CHECK_INTERVAL = 1800  # 30 minutes
LAST_COMMIT_FILE = os.path.join(ADDON_PATH, 'last_commit.txt')


def get_last_saved_commit():
    try:
        with open(LAST_COMMIT_FILE, 'r') as f:
            return f.read().strip()
    except:
        return ''


def save_last_commit(sha):
    try:
        with open(LAST_COMMIT_FILE, 'w') as f:
            f.write(sha)
    except:
        pass


def check_github_commits():
    """Check GitHub for new commits and trigger update if found"""
    try:
        from urllib.request import urlopen, Request
        
        url = f'{GITHUB_API}?sha={GITHUB_BRANCH}&per_page=1'
        req = Request(url, headers={
            'User-Agent': 'Zeus768-Kodi-Repo/1.0',
            'Accept': 'application/vnd.github.v3+json'
        })
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))

        if not data or not isinstance(data, list):
            return

        latest_sha = data[0].get('sha', '')
        commit_msg = data[0].get('commit', {}).get('message', '').split('\n')[0][:80]
        saved_sha = get_last_saved_commit()

        if not saved_sha:
            # First run - save current and don't notify
            save_last_commit(latest_sha)
            xbmc.log(f'[Zeus768 Repo] Initial commit saved: {latest_sha[:8]}', xbmc.LOGINFO)
            return

        if latest_sha != saved_sha:
            xbmc.log(f'[Zeus768 Repo] New commit detected: {latest_sha[:8]} - {commit_msg}', xbmc.LOGINFO)
            save_last_commit(latest_sha)

            # Force Kodi to check for addon updates
            xbmc.executebuiltin('UpdateAddonRepos()')
            xbmc.sleep(2000)

            # Notify user
            xbmcgui.Dialog().notification(
                'Zeus768 Repo Updated',
                f'New update available: {commit_msg}',
                ADDON_ICON, 6000
            )

    except Exception as e:
        xbmc.log(f'[Zeus768 Repo] GitHub check error: {e}', xbmc.LOGDEBUG)


if __name__ == '__main__':
    monitor = xbmc.Monitor()
    xbmc.log('[Zeus768 Repo] Commit watcher service started', xbmc.LOGINFO)

    # Wait for Kodi to settle
    xbmc.sleep(30000)

    # Initial check
    if not monitor.abortRequested():
        check_github_commits()

    # Check every 30 minutes
    while not monitor.abortRequested():
        if monitor.waitForAbort(CHECK_INTERVAL):
            break
        check_github_commits()

    xbmc.log('[Zeus768 Repo] Commit watcher service stopped', xbmc.LOGINFO)
