import base64, codecs
magic = 'aW1wb3J0IHhibWNhZGRvbiwgeGJtY2d1aQp0cnk6CiAgICBmcm9tIHJlc291cmNlcy5saWIuREkgaW1wb3J0IERJCiAgICBmcm9tIHJlc291cmNlcy5saWIucGx1Z2luIGltcG9ydCBydW5faG9vaywgcmVnaXN0ZXJfcm91dGVzCmV4Y2VwdCBJbXBvcnRFcnJvcjoKICAgIGZyb20gLnJlc291cmNlcy5saWIuREkgaW1wb3J0IERJCiAgICBmcm9tIC5yZXNvdXJjZXMubGliLnBsdWdpbiBpbXBvcnQgcnVuX2hvb2ssIHJlZ2lzdGVyX3JvdXRlcwoKdHJ5OgogICAgZnJvbSByZXNvdXJjZXMubGliLnV0aWwuY29tbW9uIGltcG9ydCAqCmV4Y2VwdCBJbXBvcnRFcnJvcjoKICAgIGZyb20gLnJlc291cmNlcy5saWIudXRpbC5jb21tb24gaW1wb3J0ICoKICAgIAojcm9vdF94bWxfdXJsID0gb3duQWRkb24uZ2V0U2V0dGluZygncm9vdF94bWwnKSBvciAiZmlsZTovL21haW4ueG1sIgpyb290X3htbF91cmwgPSAiaHR0cDovL2RvY3VtZW50YXJ5cy5kby5hbS95b3V0dWJlL1JvbXlZT1UxOS5qc29uIgojcm9vdF94bWxfdXJsID0gICJmaWxlOi8vc2NyYXBlcl9saXN0Lmpzb24iCgpwbHVnaW4gPSBESS5wbHVnaW4Kc2hvcnRfY2hlY2tlciA9IChbCiAgICAnQWRmLmx5JywgCiAgICAnQml0Lmx5JywgCiAgICAnQ2hpbHAuaXQnLCAKICAgICdDbGNrLnJ1JywgCiAgICAnQ3V0dC5seScsIAogICAgJ0RhLmdkJywgCiAgICAnR2l0LmlvJywgCiAgICAnZ29vLmdsJywgCiAgICAnSXMuZ2QnLCAKICAgICdOdWxsUG9pbnRlcicsIAogICAgJ09zLmRiJywgCiAgICAnT3cubHknLCAKICAgICdQby5zdCcsIAogICAgJ1Fwcy5ydScsIAogICAgJ1Nob3J0LmNtJywgCiAgICAnVGlueS5jYycsIAogICAgJ1RpbnlVUkwuY29tJywgCiAgICAnR2l0LmlvJywgCiAgICAnVGlueS5jYycsIAogICAgIF0pCgpAcGx1Z2luLnJvdXRlKCIvIikKZGVmIHJvb3QoKSAtPiBOb25lOgogICAgZ2V0X2xpc3Qocm9vdF94bWxfdXJsKQoKQHBsdWdpbi5yb3V0ZSgiL2dldF9saXN0LzxwYXRoOnVybD'
love = '4vXDcxMJLtM2I0K2kcp3DbqKWfBvOmqUVcVP0+VR5iozH6PvNtVPNwMT9soT9aXTLvVSWyLJEcozptqKWfVTS0VUWiqKEyVQ4tVUg1pzk9VvNcPvNtVPOsM2I0K2kcp3DbqKWfXDbXMTIzVS9aMKEsoTymqPu1pzjcBtbtVPNtV2EiK2kiMluzVvOFMJSxnJ5aVUIloPN+VPO7qKWfsFVtXDbtVPNtnJLtVvMfnKA0K3OuM2H9VvOcovO1pzj6PvNtVPNtVPNtoTymqS9jLJqyVQ0tnJ50XUIloP5mpTkcqPtvWzkcp3EspTSaMG0vXIfkKFxXVPNtVPNtVPO1pzjtCFO1pzjhp3OfnKDbVvMfnKA0K3OuM2H9VvyoZS0XVPNtVTIfp2H6PvNtVPNtVPNtoTymqS9jLJqyVQ0tZDbtVPNtnJLtLJ55XTAbMJAeYzkiq2IlXPxtnJ4tqKWfYzkiq2IlXPxtMz9lVTAbMJAeVTyhVUAbo3W0K2AbMJAeMKVcBtbtVPNtVPNtVUIloPN9VREWYaAyp3Aco24hM2I0XUIloPxhqKWfPvNtVPOlMKAjo25mMFN9VUW1oy9bo29eXPWaMKEsoTymqPVfVUIloPxXVPNtVTyzVUWyp3OioaAyBvNtVPNtVPNtVPNtPvNtVPNtVPNtV2EiK2kiMluzW2EyMzS1oUDtYFOlMKAjo25mMFN9VSkhVUgmqUVbpzImpT9hp2HcsFNaVPxXVPNtVPNtVPOcMvOiq25OMTEiov5aMKEGMKE0nJ5aDz9ioPtvqKAyK2AuL2uyVvxtLJ5xVT5iqPNvqT1xLv9mMJSlL2tvVTyhVUIloQbXVPNtVPNtVPNtVPNtERxhMTVhp2I0XUIloPjtpzImpT9hp2HcPvNtVPNtVPNtnzIhK2kcp3DtCFOlqJ5snT9inltvpTSlp2IsoTymqPVfVUIloPjtpzImpT9hp2HcPvNtVPNtVPNtpTSaMKZtCFNkPvNtVPNtVPNtoJI0LI9cqTIgVQ0tZNbtVPNtVPNtVTyzVUuvoJAuMTEiov5OMTEiovtcYzqyqSAyqUEcozqPo29fXPWcqTIgK21yqTRvXFOuozDtoz90VPW0oJEvYlVtnJ4tqKWfBtbtVPNtVPNtVPNtVPOzo3VtnKEyoFOcovOdMJ5soTymqQbXVPNtVPNtVPNtVPNtVPNtVTyzVT1yqTSsnKEyoFN9CFNlZQbXVPNtVPNtVPNtVPNtVPNtVPNtVPOgMKEuK2y0MJ0tCFNjPvNtVPNtVPNtVPNtVPNtVPNtVPNtpTSaMKZtCFOjLJqyplNeVQRXVPNtVPNt'
god = 'ICAgICAgICAgIGlmIGFueSAoeCBpbiBpdGVtIGZvciB4IGluIFsidG1kYiIsICJ0bWRiX2lkIiwgImltZGIiLCAiaW1kYl9pZCJdKToKICAgICAgICAgICAgICAgICAgICBtZXRhX2l0ZW0gKz0gMQogICAgICAgICAgICAgICAgaXRlbS51cGRhdGUoeyJsaXN0X3BhZ2UiOnBhZ2VzfSkKICAgICAgICAgICAgICAgIAogICAgICAgICAgICBqZW5fbGlzdCA9IFtydW5faG9vaygicHJvY2Vzc19pdGVtIiwgaXRlbSkgZm9yIGl0ZW0gaW4gamVuX2xpc3QgaWYgaXRlbS5nZXQoImxpc3RfcGFnZSIpID09IGxpc3RfcGFnZV0KICAgICAgICAgICAgZm9yIHBhZ2UgaW4gcmFuZ2UoMSxwYWdlcysxKToKICAgICAgICAgICAgICAgIGlmIHBhZ2UgPT0gbGlzdF9wYWdlOgogICAgICAgICAgICAgICAgICAgIGNvbnRpbnVlCiAgICAgICAgICAgICAgICBwYWdlX2l0ZW0gPSB4Ym1jZ3VpLkxpc3RJdGVtKGYiUGFnZXtzdHIocGFnZSl9IikKICAgICAgICAgICAgICAgIHBhZ2VfaWNvbiA9IHhibWNhZGRvbi5BZGRvbigpLmdldEFkZG9uSW5mbygiaWNvbiIpCiAgICAgICAgICAgICAgICBwYWdlX2ZhbmFydCA9IHhibWNhZGRvbi5BZGRvbigpLmdldEFkZG9uSW5mbygiZmFuYXJ0IikKICAgICAgICAgICAgICAgIHBhZ2VfaXRlbS5zZXRBcnQoeyJpY29uIjogcGFnZV9pY29uLCAidGh1bWIiOiBwYWdlX2ljb24sICJwb3N0ZXIiOiBwYWdlX2ljb24sICJmYW5hcnQiOiBwYWdlX2ZhbmFydH0pCiAgICAgICAgICAgICAgICBqZW5fbGlzdC5hcHBlbmQoeyJ0eXBlIjogImRpciIsICJsaW5rIjogZiIvZ2V0X2xpc3Qve3VybH0mbGlzdF9wYWdlPXtzdHIocGFnZSl9IiwgImxpc3RfaXRlbSI6IHBhZ2VfaXRlbSwgImlzX2RpciI6IFRydWV9KQogICAgICAgIGVsc2U6CiAgICAgICAgICAgICNkb19sb2coZidkZWZhdWx0IC0gamVuIGxpc3QgPSBcbiB7c3RyKGplbl9saXN0KX0gJykKICAgICAgICAgICAgamVuX2xpc3QgPSBbcnVuX2hvb2soInByb2Nlc3NfaXRlbSIsIGl0ZW0pIG'
destiny = 'MipvOcqTIgVTyhVTcyoy9fnKA0KDbtVPNtVPNtVTcyoy9fnKA0VQ0tJjbtVPNtVPNtVUW1oy9bo29eXPWaMKEsoJI0LJEuqTRvYPOcqTIgYPOlMKE1pz5snKEyoI9ioy9zLJyfqKWyCIElqJHcVTMipvOcqTIgVTyhVTcyoy9fnKA0PvNtVPNtVPNtKDbtVPNtVPNtVUW1oy9bo29eXPWxnKAjoTS5K2kcp3DvYPOdMJ5soTymqPxXVPNtVTIfp2H6PvNtVPNtVPNtpaIhK2uio2fbVzEcp3OfLKysoTymqPVfVSgqXDbXDUOfqJqcov5lo3I0MFtvY3OfLKysqzyxMJ8iCUOuqTt6qzyxMJ8+VvxXMTIzVUOfLKysqzyxMJ8bqzyxMJ86VUA0pvx6PvNtVPOspTkurI92nJEyolu2nJEyolxXPzEyMvOspTkurI92nJEyolu2nJEyolx6PvNtVPOcoKOipaDtLzSmMGL0PvNtVPO2nJEyo19fnJ5eVQ0tWlptPvNtVPO2nJEyolN9VTWup2H2AP51pzkmLJMyK2V2ATEyL29xMFu2nJEyolxtVPNtVPNXVPNtVTyzVPpvoTyhnlV6WlOcovOmqUVbqzyxMJ8cVQbXVPNtVPNtVPO2nJEyo19fnJ5eVQ0tpaIhK2uio2fbVaOlMI9joTS5VvjtqzyxMJ8cPvNtVPNtVPNtnJLtqzyxMJ9soTyhnlN6VNbtVPNtVPNtVPNtVPOlqJ5snT9inltvpTkurI92nJEyolVfVUMcMTIiK2kcozfcVPNtVPNtVPNXVPNtVTIfp2HtBtbtVPNtVPNtVUW1oy9bo29eXPWjoTS5K3McMTIiVvjtqzyxMJ8cPtcNpTk1M2yhYaWiqKEyXPVip2I0qTyhM3ZvXDcxMJLtp2I0qTyhM3ZbXGbXVPNtVUuvoJAuMTEiov5OMTEiovtcYz9jMJ5GMKE0nJ5apltcPtcNpTk1M2yhYaWiqKEyXPViL2kyLKWsL2SwnTHvXDcxMJLtL2kyLKWsL2SwnTHbXGbXVPNtVREWYzEvYzAfMJSlK2AuL2uyXPxXVPNtVTygpT9lqPO4Lz1wPvNtVPNwrTWgLl5moTIypPtkZQNjXDbtVPNtrTWgLl5yrTIwqKEyLaIcoUEcovtvD29hqTScozIlYyWyMaWyp2tvXDbXpzIanKA0MKWspz91qTImXUOfqJqcovxXPzEyMvOgLJyhXPx6PvNtVPOjoUIanJ4hpaIhXPxXVPNtVUWyqUIlovNjPtccMvOsK25uoJIsKlN9CFNvK19gLJyhK18vBtbtVPNtoJScovtcPt=='
joy = '\x72\x6f\x74\x31\x33'
trust = eval('\x6d\x61\x67\x69\x63') + eval('\x63\x6f\x64\x65\x63\x73\x2e\x64\x65\x63\x6f\x64\x65\x28\x6c\x6f\x76\x65\x2c\x20\x6a\x6f\x79\x29') + eval('\x67\x6f\x64') + eval('\x63\x6f\x64\x65\x63\x73\x2e\x64\x65\x63\x6f\x64\x65\x28\x64\x65\x73\x74\x69\x6e\x79\x2c\x20\x6a\x6f\x79\x29')
eval(compile(base64.b64decode(eval('\x74\x72\x75\x73\x74')),'<string>','exec'))