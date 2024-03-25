import os
import sys
import urllib
import re
from colorama import Fore, Style
from pixivpy3 import AppPixivAPI

__pcloud_path = ""

if sys.platform == "linux":
    __pcloud_path = os.path.expanduser("~/pCloudDrive/")
elif sys.platform == "win32":
    __pcloud_path = "P:/"

__default_path = __pcloud_path + "Images/_Need Sorted/"
__artist_path = __pcloud_path + "Images/Other/Artist Collections/"
__ai_art_path = __pcloud_path + "Images/Other/AI Art/_Collections/"


def get_file_list() -> dict[str:str]:
    """Pulls all files that use the extraction naming convention -> {uploader/artist} - {location/status} - {image_id}"""
    all_files = [f"{dir}/{f}" for dir, _, files in os.walk(__pcloud_path+"Images") for f in files]
    filtered_files:list[str] = list(filter(lambda f: re.match("/.+ - \d+ - ", f), all_files))
    return {f"{os.path.basename(f.split(' - ')[0])} - {f.split(' - ')[1]}":f for f in filtered_files}

__file_list = get_file_list()


def file_exists(artist,id):
    """Checks to ensure no repeat files in the entire image folder."""
    # This method is way more accurate and faster. This way we check ALL directories, not just the one being saved to.
    file = f"{artist} - {id}"
    exists =  file in __file_list 
    if exists:
        print(f"{Fore.YELLOW}{__file_list[file]} already exists.{Style.RESET_ALL}")
    return exists


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


def save_pcloud_twitter(img_id, artist, url, filename):
    path = __default_path
    if artist in artist_directories:
        path = __artist_path + artist_directories[artist] + "/"
    if artist in ai_art_directories:
        path = __ai_art_path + artist + "/"

    filepath = path + artist + " - " + str(img_id) + " - " + filename
    urllib.request.urlretrieve(url, filepath)
    __file_list[f"{artist} - {img_id}"] = filepath
    print(str(img_id) + " saved to " + filepath)


def save_pcloud_pixiv(pixiv_api:AppPixivAPI, pixiv_img):
    path = __default_path
    img_id = pixiv_img.id
    artist = pixiv_img.user.account
    if artist in artist_directories:
        path = __artist_path + artist_directories[artist] + "/"
    if artist in ai_art_directories:
        path = __ai_art_path + artist + "/"

    for img in pixiv_img.meta_pages:
        url:str = img.image_urls.original
        img_name = url[url.rfind("/") + 1:]
        file_name = artist + " - " + str(img_id) + " - " + img_name
        pixiv_api.download(url, path=path, name = file_name)
        print(str(img_name) + " saved to " + path + file_name)

    __file_list[f"{artist} - {img_id}"] = path + file_name
