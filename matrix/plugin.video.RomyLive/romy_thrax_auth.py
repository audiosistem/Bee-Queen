# -*- coding: utf-8 -*-
"""Anonymous Thrax device protocol adapted from ThraxTV thrax_auth.py.

Reference addon declares GPL-2.0-only. No embedded credentials, no device
name sent. Share the documented Kodi token store with other Thrax addons.
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE = 'https://api.derzis.xyz'


class DeviceAuth:
    def __init__(self, path, client='plugin.video.RomyLive', log=lambda msg: None):
        self.path, self.client, self.log = path, client, log
        self.cached = None

    def read(self):
        try:
            with open(self.path, encoding='utf-8') as source:
                return json.load(source)
        except (OSError, ValueError):
            return {}

    def write(self, data):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            temp = self.path + '.tmp'
            with open(temp, 'w', encoding='utf-8') as out:
                json.dump(data, out)
            os.replace(temp, self.path)
        except OSError:
            self.log('Tokenul anonim Thrax nu a putut fi salvat.')

    def request(self, method, route, body=None, token=None):
        payload = json.dumps(body).encode('utf-8') if body is not None else None
        request = urllib.request.Request(BASE + route, data=payload, method=method,
            headers={'User-Agent': 'Kodi thrax_auth/1', 'Accept': 'application/json'})
        if payload is not None:
            request.add_header('Content-Type', 'application/json')
        if token:
            request.add_header('X-Thrax-Token', token)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read(262144)
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.read(262144)
            finally:
                exc.close()

    def register(self, data):
        if time.time() - data.get('esec', 0) < 300:
            return None
        try:
            status, raw = self.request('POST', '/auth/register',
                {'platform': 'kodi', 'model': '', 'version': 'kodi'})
            token = json.loads(raw).get('token') if status == 200 else None
            self.log('Inregistrare anonima Thrax: HTTP %s.' % status)
        except Exception as exc:
            self.log('Inregistrare Thrax: %s.' % type(exc).__name__)
            token = None
        if token:
            self.write({'token': token, 'verificat': time.time()})
        else:
            self.write(dict(data, esec=time.time()))
        return token

    def token(self):
        if self.cached:
            return self.cached
        data = self.read()
        token = data.get('token')
        if not token:
            token = self.register(data)
        elif time.time() - data.get('verificat', 0) > 86400:
            try:
                status, _ = self.request('GET', '/auth/account', token=token)
            except Exception:
                status = 0
            if status == 401:
                token = self.register({})
            elif status in (200, 409):
                self.write(dict(data, verificat=time.time()))
        self.cached = token
        return token

    def headers(self):
        token = self.token()
        if not token:
            return None
        return {'X-Thrax-Client': self.client, 'X-Thrax-Token': token}

    def forget(self):
        self.cached = None
        self.write({})