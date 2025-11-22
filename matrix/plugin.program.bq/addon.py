# -*- coding: UTF-8 -*-

import os
import time
import webbrowser
from kodi_six import xbmc, xbmcgui


def menuoptions():
    dialog = xbmcgui.Dialog()
    funcs = (
        function1,
        function2,
        function3,
        function4,
        function5,
        function6,
        function7,
        function8,
        function9,
        function10,
        function11,
    )
    call = dialog.select('[B]BQ[/B]', [
            '[B]ClickSud[/B]',
            '[B]FlixTor[/B]',
            '[B]AZMovies[/B]',
            '[B]Stream4U[/B]',
            '[B]YESMovies[/B]',
            '[B]VexMovies[/B]',
            '[B]MoviesJoy[/B]',
            '[B]MyFlixer[/B]',
            '[B]Sflix[/B]',
            '[B]1HD[/B]',
            '[B]Cancel & Close[/B]',
        ]
    )
    # dialog.selectreturns
    #   0 -> escape pressed
    #   1 -> first item
    #   2 -> second item
    if call:
        # esc is not pressed
        if call < 0:
            return
        func = funcs[call-11] # Number of functions (function10)
        return func()
    else:
        func = funcs[call]
        return func()
    return


def platform():
    if xbmc.getCondVisibility('system.platform.android'):
        return 'android'
    elif xbmc.getCondVisibility('system.platform.linux'):
        return 'linux'
    elif xbmc.getCondVisibility('system.platform.windows'):
        return 'windows'
    elif xbmc.getCondVisibility('system.platform.osx'):
        return 'osx'
    elif xbmc.getCondVisibility('system.platform.atv2'):
        return 'atv2'
    elif xbmc.getCondVisibility('system.platform.ios'):
        return 'ios'
myplatform = platform()
mycommand = 'StartAndroidActivity(,android.intent.action.VIEW,,%s)'


def function1(): # Web.app
    link = 'https://clicksud.com.in'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function2(): # FlixTor
    link = 'https://flixtor.guru'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function3(): # AZMovie
    link = 'https://azmovies.ag'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function4(): # Stream4U
    link = 'https://streamm4u.com.co/home'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function5(): # YESMovies
    link = 'https://ww.yesmovies.vc/yesmovies'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function6(): # VexMovies
    link = 'https://www.vexmovies.biz.id'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function7(): # MoviesJoy
    link = 'https://moviesjoy.pw'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function8(): # MyFlixer
    link = 'https://myflixer.is/home'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function9(): # Sflix
    link = 'https://sflix.to/home'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function10(): # 1HD
    link = 'https://1hd.to/home'
    if myplatform == 'android':
        return xbmc.executebuiltin(mycommand % link)
    else:
        return webbrowser.open(link)


def function11(): 0 # Cancel & Close


menuoptions()


