#!/bin/bash
rm tests/home/userdata/addon_data/plugin.video.s4me/settings_channels/*.json
rm tests/home/userdata/addon_data/plugin.video.s4me/settings_servers/*.json
rm tests/home/userdata/addon_data/plugin.video.s4me/cookies.dat
rm tests/home/userdata/addon_data/plugin.video.s4me/kod_db.sqlite
python -m pip install --upgrade pip
pip install -U sakee
pip install -e git+https://github.com/mac12m99/HtmlTestRunner.git@master#egg=html-testRunner
pip install -U parameterized
export PYTHONPATH=$PWD
export KODI_INTERACTIVE=0
export KODI_HOME=$PWD/tests/home
if (( $# >= 1 ))
then
  export S4ME_TST_CH=$1
fi
python tests/test_generic.py