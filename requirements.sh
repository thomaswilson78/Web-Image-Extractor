#!/bin/sh
# Run this to install needed external libraries

source .venv/bin/activate
pip install colorama
pip install playsound3
# twscrape is outdated and will need fixed
pip install twscrape
pip install asyncclick
pip install selenium
# To use, need to run the "pixiv_auth" file to pull the refresh token
pip install pixivpy3
pip install cloudscraper
