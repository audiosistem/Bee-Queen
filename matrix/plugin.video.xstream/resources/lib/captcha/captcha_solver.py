# -*- coding: utf-8 -*-
# Python 3
#
#05.07.2025 Heptamer
#
# Captcha Bibliothek


import json
import time
import xbmc
import xbmcgui
from resources.lib.handler.requestHandler import cRequestHandler
from resources.lib.tools import logger
from resources.lib.config import cConfig


class CaptchaSolver:
    """
    Eine wiederverwendbare Klasse zum Lösen verschiedener Captcha-Typen.
    Unterstützt aktuell 2Captcha für reCAPTCHA v2.
    """

    def __init__(self, api_key=None, provider=None, timeout=120):
        """
        Initialisiert den Captcha-Solver.

        Args:
            api_key (str): API-Schlüssel für den Captcha-Dienst
            provider (str): Captcha-Dienst ('2captcha', '9kw', etc.)
            timeout (int): Maximale Wartezeit in Sekunden
        """
        self.api_key = api_key
        self.provider = provider
        self.timeout = timeout
        self.is_alive = True  # Für 9kw-Abbruch

    def set_api_key(self, api_key):
        """Setzt den API-Schlüssel"""
        self.api_key = api_key

    def set_provider(self, provider):
        """Setzt den Provider"""
        self.provider = provider

    def set_kill(self):
        """Abbruch-Signal für 9kw"""
        self.is_alive = False

    def solve_recaptcha_v2(self, site_key, page_url):
        """
        Löst ein reCAPTCHA v2.

        Args:
            site_key (str): Der Google reCAPTCHA Site-Key
            page_url (str): Die URL der Seite mit dem Captcha

        Returns:
            str: Der Captcha-Lösungstoken
        """
        if self.provider == '2captcha':
            return self._solve_with_2captcha(site_key, page_url)
        # Hier können später weitere Provider hinzugefügt werden
        elif self.provider == '9kw':
            return self._solve_with_9kw(site_key, page_url)
        else:
            raise ValueError(f"Captcha-Provider '{self.provider}' wird nicht unterstützt")

    def _solve_with_2captcha(self, site_key, page_url):
        """2Captcha-Implementation für reCAPTCHA v2"""
        if not self.api_key:
            xbmcgui.Dialog().ok(cConfig().getLocalizedString(30241), cConfig().getLocalizedString(30291))
            return None

        params = {
            'key': self.api_key,
            'method': 'userrecaptcha',
            'googlekey': site_key,
            'pageurl': page_url,
            'json': 1,
        }

        # Captcha-Anfrage senden
        captcha_request = cRequestHandler('https://2captcha.com/in.php', caching=False, method='POST',
                                          data=json.dumps(params))
        captcha_request.addHeaderEntry('Content-Type', 'application/json')
        response_text = captcha_request.request()

        try:
            json_response = json.loads(response_text)
        except json.JSONDecodeError:
            raise Exception(f"Ungültige Antwort vom Captcha-Dienst: {response_text}")

        if 'request' not in json_response:
            raise Exception(f"Ungültige Antwort vom Captcha-Dienst: {json_response}")

        captcha_id = json_response['request']
        logger.info(f'Captcha-Anfrage gesendet mit ID: {captcha_id}')

        # Auf die Lösung warten
        return self._get_2captcha_result(captcha_id)

    def _get_2captcha_result(self, captcha_id):
        """Wartet auf und holt das Ergebnis von 2Captcha"""
        start_time = time.time()

        while True:
            request = cRequestHandler(
                f"https://2captcha.com/res.php?key={self.api_key}&json=1&action=get&id={captcha_id}",
                caching=False
            )
            request.addHeaderEntry('Content-Type', 'application/json')
            response_text = request.request()

            try:
                json_res = json.loads(response_text)
            except json.JSONDecodeError:
                logger.error(f"Fehler beim Parsen der 2Captcha-Antwort: {response_text}")
                raise Exception(f"Ungültige JSON-Antwort: {response_text}")

            if json_res.get('status') == 1:
                return json_res.get('request')
            elif json_res.get('request') != 'CAPCHA_NOT_READY':
                error_msg = f"Fehler beim Lösen des Captchas: {json.dumps(json_res, indent=2)} \nID: {captcha_id}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # Timeout-Überprüfung
            if time.time() - start_time >= self.timeout:
                error_msg = f"Timeout beim Warten auf Captcha-Lösung (ID: {captcha_id})"
                logger.error(error_msg)
                raise Exception(error_msg)

            # Kurze Pause zwischen den Anfragen
            time.sleep(2)

    def _solve_with_9kw(self, site_key, page_url):
        """9kw.eu-Implementation für reCAPTCHA v2"""
        if not self.api_key:
            xbmcgui.Dialog().ok(cConfig().getLocalizedString(30241), cConfig().getLocalizedString(30291))
            return None

        # Prüfen, ob Selfsolve aktiviert ist (über Addon-Einstellungen)
        selfsolve = '1' if cConfig().getSetting('9kw.SelfSolve', 'false') == 'true' else '0'

        post = {
            'apikey': self.api_key,
            'action': 'usercaptchaupload',
            'interactive': '1',
            'json': '1',
            'file-upload-01': site_key,
            'oldsource': 'recaptchav2',
            'pageurl': page_url,
            'maxtimeout': str(self.timeout)
        }

        if selfsolve == '1':
            post['selfsolve'] = '1'

        token = ''

        try:
            URL = 'https://www.9kw.eu/index.cgi'
            request = cRequestHandler(URL, caching=False, method='POST', data=post)
            response_text = request.request()

            if response_text:
                data = json.loads(response_text)
                if 'captchaid' in data:
                    captcha_id = data['captchaid']
                    tries = 0

                # Warte auf Captcha-Lösung
                while tries < self.timeout and self.is_alive:
                    tries += 1
                    xbmc.sleep(1000)  # 1 Sekunde warten

                    check_url = f"https://www.9kw.eu/index.cgi?action=usercaptchacorrectdata&id={captcha_id}&apikey={self.api_key}&json=1"
                    result_request = cRequestHandler(check_url, caching=False)
                    result_text = result_request.request()

                    if result_text:
                        try:
                            result_data = json.loads(result_text)
                            token = result_data.get('answer', '')
                            if token:
                                break
                        except Exception as e:
                            logger.error(f"Fehler beim Parsen der 9kw-Antwort: {str(e)}")

        except Exception as e:
            logger.error(f"9kw Error: {str(e)}")

        return token
