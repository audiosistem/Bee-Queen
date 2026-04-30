# -*- coding: utf-8 -*-
# Python 3

from resources.lib.handler.ParameterHandler import ParameterHandler


class cContextElement:
    def __init__(self):
        self.__sTitle = ''
        self.__oOutputParameterHandler = ParameterHandler()

    def setFunction(self, sFunctionName):
        self.__sFunctionName = sFunctionName

    def getFunction(self):
        return self.__sFunctionName

    def setFile(self, sFile):
        self.__sFile = sFile

    def getFile(self):
        return self.__sFile

    def setTitle(self, sTitle):
        self.__sTitle = sTitle

    def getTitle(self):
        return self.__sTitle

    def setSiteName(self, sSiteName):
        self.__sSiteName = sSiteName

    def getSiteName(self):
        return self.__sSiteName

    def setOutputParameterHandler(self, oOutputParameterHandler):
        self.__oOutputParameterHandler = oOutputParameterHandler

    def getOutputParameterHandler(self):
        return self.__oOutputParameterHandler
