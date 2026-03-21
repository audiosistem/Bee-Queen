import requests
import xbmc
import xbmcaddon
import xbmcgui
import time

ADDON = xbmcaddon.Addon()
BASE_URL = 'https://api.trakt.tv'

# --- CHEI INTERNE ADDON (Ascunse de utilizator) ---
# Pune aici cheile tale de pe https://trakt.tv/oauth/apps
TRAKT_CLIENT_ID = '6b3a26573b14c3e4ef5ed00f3c3889e4719554ffa858065a504892435ce019fd'
TRAKT_CLIENT_SECRET = 'bcfeb7d92b05d13eb6986a12ed22e1e7273e709e7f42d577330f6794b0e8ef72'
# --------------------------------------------------

class TraktAPI:
    def __init__(self):
        # Safety: Ensure keys are strings and strip whitespace
        self.client_id = str(TRAKT_CLIENT_ID).strip()
        self.client_secret = str(TRAKT_CLIENT_SECRET).strip()
        
        self.access_token = ADDON.getSetting('trakt_token')
        self.refresh_token = ADDON.getSetting('trakt_refresh')
        self.expires_at = ADDON.getSetting('trakt_expiry')
        
    def _get_headers(self):
        headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.client_id
        }
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers

    def _save_tokens(self, token_data):
        created_at = token_data.get('created_at', time.time())
        expires_in = token_data.get('expires_in', 7776000)
        
        ADDON.setSetting('trakt_token', token_data['access_token'])
        ADDON.setSetting('trakt_refresh', token_data['refresh_token'])
        ADDON.setSetting('trakt_expiry', str(int(created_at + expires_in)))
        ADDON.setSetting('trakt_info', 'Conectat')
        
        self.access_token = token_data['access_token']

    def authorize(self):
        if not self.client_id or 'YOUR_' in self.client_id:
            xbmcgui.Dialog().ok("Eroare", "Cheile API Trakt nu sunt configurate in cod.")
            return

        # 1. Get Device Code
        try:
            headers = {
                'Content-Type': 'application/json',
                'trakt-api-version': '2',
                'trakt-api-key': self.client_id
            }
            resp = requests.post(f'{BASE_URL}/oauth/device/code', json={'client_id': self.client_id}, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            xbmcgui.Dialog().notification("Trakt Error", f"Request failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR)
            xbmc.log(f"[VeziAici-Trakt] Auth Error: {e}", xbmc.LOGERROR)
            return

        user_code = data['user_code']
        verification_url = data['verification_url']
        device_code = data['device_code']
        interval = data['interval']
        expires_in = data['expires_in']

        # 2. Show Dialog
        pd = xbmcgui.DialogProgress()
        line1 = f'1. Mergi la: {verification_url}'
        line2 = f'2. Introdu codul: {user_code}'
        pd.create('Activare Trakt', f'{line1}\n{line2}')
        
        # 3. Poll for token
        start_time = time.time()
        while time.time() - start_time < expires_in:
            if pd.iscanceled():
                pd.close()
                return
            time.sleep(interval)
            try:
                headers = {
                    'Content-Type': 'application/json',
                    'trakt-api-version': '2',
                    'trakt-api-key': self.client_id
                }
                poll_resp = requests.post(f'{BASE_URL}/oauth/device/token', json={
                    'code': device_code,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret
                }, headers=headers)
                
                if poll_resp.status_code == 200:
                    token_data = poll_resp.json()
                    self._save_tokens(token_data)
                    pd.close()
                    xbmcgui.Dialog().notification("Trakt", "Autorizare reusita!", xbmcgui.NOTIFICATION_INFO)
                    return
            except: pass
        pd.close()

    def revoke_auth(self):
        if not self.access_token: return
        try:
            requests.post(f'{BASE_URL}/oauth/revoke', json={
                'token': self.access_token, 'client_id': self.client_id, 'client_secret': self.client_secret
            }, headers={'Content-Type': 'application/json'})
        except: pass
        ADDON.setSetting('trakt_token', ''); ADDON.setSetting('trakt_refresh', ''); ADDON.setSetting('trakt_expiry', '')
        ADDON.setSetting('trakt_info', 'Neconectat')
        self.access_token = ''
        xbmcgui.Dialog().notification("Trakt", "Cont deconectat.", xbmcgui.NOTIFICATION_INFO)

    def search_movie(self, title, year=None):
        url = f'{BASE_URL}/search/movie'
        params = {'query': title}
        if year: params['years'] = year
        try:
            r = requests.get(url, params=params, headers=self._get_headers())
            if r.status_code == 200: return r.json()
        except: pass
        return []

    def search_show(self, title):
        url = f'{BASE_URL}/search/show'
        params = {'query': title}
        try:
            r = requests.get(url, params=params, headers=self._get_headers())
            if r.status_code == 200: return r.json()
        except: pass
        return []

    def get_episode_summary(self, show_slug, season, episode):
        url = f'{BASE_URL}/shows/{show_slug}/seasons/{season}/episodes/{episode}'
        try:
            r = requests.get(url, headers=self._get_headers())
            if r.status_code == 200: return r.json()
        except: pass
        return None

    def scrobble(self, action, item_type, ids, progress=0):
        if not self.access_token: return
        url = f'{BASE_URL}/scrobble/{action}'
        payload = {item_type: {'ids': ids}, 'progress': progress}
        try:
            requests.post(url, json=payload, headers=self._get_headers())
        except: pass