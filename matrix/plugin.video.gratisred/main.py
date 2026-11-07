# -*- coding: utf-8 -*-

from resources.lib.modules.ipv6_fallback import install as ipv6_fallback
ipv6_fallback()

from sys import argv

from resources.lib import system

system.router(argv[2])


