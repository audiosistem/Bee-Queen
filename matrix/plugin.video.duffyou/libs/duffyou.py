# -*- coding: utf-8 -*-
import plugin

def play(id, title="", plot="", thumb=""):
    plugin.play(plugin.Item(
            action='play',
            url=id,
            label=title,
            plot=plot,
            thumb=thumb
            ))

def resolver(id, title="", plot="", thumb=""):
    ret = plugin.play(plugin.Item(
            action='resolver',
            url=id,
            label=title,
            plot=plot,
            thumb=thumb
            ))

    url, title, plot, thumb = ret
    return url, title, plot, thumb