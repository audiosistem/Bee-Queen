# -*- coding: utf-8 -*-
# Python 3
#
#05.07.2025 Heptamer
#
# Captcha Helper

from resources.lib.tools import logger
from resources.lib.config import cConfig
from resources.lib.captcha.captcha_solver import CaptchaSolver


def solve_recaptcha(site_key, page_url, provider=None):
    """
    Hilfsfunktion zum Lösen von reCAPTCHAs

    Args:
        site_key (str): Der Google reCAPTCHA Site-Key
        page_url (str): Die URL der Seite mit dem Captcha
        provider (str): Optional, überschreibt den konfigurierten Provider


    Returns:
        str: Der Captcha-Lösungstoken
    """
    # Bestimme den Provider aus den Einstellungen oder dem Parameter
    if provider is None:
        provider = cConfig().getSetting('captcha.provider', '2captcha')

    # API-Key abhängig vom Provider holen
    if provider == '2captcha':
        api_key = cConfig().getSetting('2captcha.pass')
        if not api_key:
            logger.error("2Captcha API-Schlüssel ist nicht gesetzt")
            return None
    elif provider == '9kw':
        api_key = cConfig().getSetting('9kw.pass')
        if not api_key:
            logger.error("9kw.eu API-Schlüssel ist nicht gesetzt")
            return None
    ###############################################################
    else:
        logger.error(f"Unbekannter Captcha-Provider '{provider}'")
        return None

    # Timeout aus Einstellungen holen
    timeout = int(cConfig().getSetting('captcha.timeout', '120'))

    # Solver erstellen und Captcha lösen
    solver = CaptchaSolver(api_key=api_key, provider=provider, timeout=timeout)
    try:
        return solver.solve_recaptcha_v2(site_key, page_url)
    except Exception as e:
        logger.error(f"Fehler beim Lösen des reCAPTCHAs: {str(e)}")
        return None


def extract_recaptcha_sitekey(html_content):
    """
    Extrahiert den reCAPTCHA Site-Key aus dem HTML-Inhalt.

    Args:
        html_content (str): Der HTML-Inhalt der Webseite

    Returns:
        str: Der extrahierte Site-Key oder None
    """
    from resources.lib.tools import cParser

    patterns = [
        r"series\.init\s*\(\s*\d+\s*,\s*\d+\s*,\s*'([^']+)'\s*\)\s*;",  # BurningSeries-Muster
        r'data-sitekey="([^"]+)"',  # Standard reCAPTCHA-Muster
        r"grecaptcha.execute\s*\(\s*'([^']+)'"  # Unsichtbares reCAPTCHA
    ]

    for pattern in patterns:
        isMatch, site_key = cParser.parseSingleResult(html_content, pattern)
        if isMatch:
            return site_key

    return None