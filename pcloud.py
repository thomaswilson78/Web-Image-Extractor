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


def set_artist_dir(directory) -> dict[str:str]:
    """Get folders within directories and map them to account names."""
    # Artist can have more than one account they go by, the folder structure uses "," to split the names,
    # they need to be decoupled in order to search them quicker via dictionary.
    dir_return = {}
    for d in os.listdir(directory):
        account_split = d.split(",")
        for account in account_split:
            dir_return[account] = d
            
    return dir_return


artist_directories:dict[str:str] = set_artist_dir(__artist_path)
ai_art_directories:set[str] = os.listdir(__ai_art_path) #These are named 1:1, don't need specific logic


def save_pcloud(img_id, artist, url, filename):
    path = __default_path
    if artist in artist_directories:
        path = __artist_path + artist_directories[artist] + "/"
    if artist in ai_art_directories:
        path = __ai_art_path + artist + "/"

    filepath = path + artist + " - " + str(img_id) + " - " + filename
    if not os.path.exists(filepath):
        urllib.request.urlretrieve(url, filepath)
        print(str(img_id) + " saved to " + filepath)
    else:
        print(f"{Fore.YELLOW}{filepath} already exists.{Style.RESET_ALL}")
