import os
import sys
import urllib
from colorama import Fore, Style

__pcloud_path = ""

if sys.platform == "linux":
    __pcloud_path = os.path.expanduser("~/pCloudDrive/")
elif sys.platform == "win32":
    __pcloud_path = "P:/"

__default_path = __pcloud_path + "Images/_Need Sorted/"
__artist_path = __pcloud_path + "Images/Other/Artist Collections/"
__ai_art_path = __pcloud_path + "Images/Other/AI Art/_Collections/"

artist_directories = {
    "___OTINTIN": "___OTINTIN aka _lili_i",
    "_lili_i": "___OTINTIN aka _lili_i",
    "to0699" : "to0699",
    "baalbuddy" : "baalbuddy",
    "CuteSexyRobutts" : "CuteSexyRobutts",
    "gishiki_unc" : "gishiki_unc",
    "greenopi1" : "greenopi1",
    "Grimgrim" : "Grimgrim",
    "hime_takamura" : "hime_takamura",
    "vanishlily" : "Ironlily",
    "Ixy" : "Ixy",
    "kaynimatic" : "kaynimatic",
    "khyleri" : "khyleri",
    "logan0241" : "logan0241",
    "meiwowowo" : "meiwowowo",
    "Merryweather" : "Merryweather",
    "meru" : "meru",
    "Nekojira" : "Nekojira",
    "neneneqo" : "neneneqo",
    "Oxcoxa" : "oxcoxa",
    "personalami" : "personalami",
    "Rakeemgc" : "Rakeemgc",
    "simomo404" : "simomo404",
    "some1else45" : "some1else45",
    "TRENTE30m" : "TRENTE30m"
}

ai_art_directories = {
    "8co28": "8co28",
    "AiartYasshy": "AiartYasshy",
    "AiRSTR7": "AiRSTR7",
    "chun_paretto": "chun_paretto",
    "DreadnaughtDark": "DreadnaughtDark",
    "eatsleep1111": "eatsleep1111",
    "haru_tonatsu": "haru_tonatsu",
    "hasukimm": "hasukimm",
    "hidari0906": "hidari0906",
    "HoDaRaKe": "HoDaRaKe",
    "iolite_aoto": "iolite_aoto",
    "kanae_isshiki": "kanae_isshiki",
    "kataitumutumu": "kataitumutumu",
    "killergangAI": "killergangAI",
    "KuronekoAI_84": "KuronekoAI_84",
    "Miuu_Airi": "Miuu_Airi",
    "Murata_san_": "Murata_san_",
    "NeneneAI": "NeneneAI",
    "redraw_0": "redraw_0",
    "sagawa_gawa": "sagawa_gawa",
    "sayaka_aiart": "sayaka_aiart",
    "Sinozick": "Sinozick",
    "suigintoxic": "suigintoxic",
    "ton_ton_ai": "ton_ton_ai",
    "yurari_banri": "yurari_banri",
    "yuyake_mashiro": "yuyake_mashiro",
    "zuuuka2": "zuuuka2",
    "Alcott777": "Alcott777",
    "aoi_itsukushima": "aoi_itsukushima"
}

def save_pcloud(img_id, artist, url, filename):
    path = __default_path
    if artist in artist_directories:
        path = __artist_path + artist_directories[artist] + "/"
    if artist in ai_art_directories:
        path = __ai_art_path + ai_art_directories[artist] + "/"

    filepath = path + artist + " - " + str(img_id) + " - " + filename
    if not os.path.exists(filepath):
        urllib.request.urlretrieve(url, filepath)
        print(str(img_id) + " saved to " + filepath)
    else:
        print(f"{Fore.YELLOW}{filepath} already exists.{Style.RESET_ALL}")
