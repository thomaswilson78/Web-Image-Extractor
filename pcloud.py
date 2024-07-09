import os
import sys
import re
import requests
from pixivpy3 import AppPixivAPI

__pcloud_path = ""

if sys.platform == "linux":
    __pcloud_path = os.path.expanduser("~/pCloudDrive/")
elif sys.platform == "win32":
    __pcloud_path = "P:\\"

__default_path = __pcloud_path + "Images/_Need Sorted/"
__artist_path = __pcloud_path + "Images/Other/Artist Collections/"
__ai_art_path = __pcloud_path + "Images/Other/AI Art/_Collections/"
__meta_tags = ""


def set_tags(is_ai, is_noscan):
    global __meta_tags, __default_path
    if is_ai:
        __meta_tags += " - [AI]"
    if is_noscan:
        __meta_tags += " - [NoScan]"
    

def __add_filename_tags(filename:str, temp_tags:str = "") -> str:
    name, ext = os.path.splitext(filename)
    return name + __meta_tags + temp_tags + ext


def get_file_list() -> dict[str:str]:
    """Pulls all files that use the extraction naming convention i.e. artist - status_id - filename, site - filename, etc."""
    all_files = [f"{os.path.join(dir,f)}" for dir, _, files in os.walk(__pcloud_path+"Images/_Need Sorted") for f in files]
    filtered_files:list[str] = list(filter(lambda f: re.match(r".+ - .+\..+", f), all_files))
    return {f"{os.path.basename(f.split(' - ')[0])} - {f.split(' - ')[1]}":f for f in filtered_files}


def get_file_location(file:str) -> str:
    return __file_list[file]


def file_exists(file):
    """Checks to ensure no repeat files in the entire image folder."""
    # This method is way more accurate and faster. This way we check ALL directories, not just the one being saved to.
    return file in __file_list 

__file_list = get_file_list()


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
ai_art_directories:set[str] = os.listdir(__ai_art_path) # These are named 1:1, don't need specific logic


def set_path(artist):
    is_ai_art = False
    path = __default_path
    if artist != "":
        if artist in artist_directories:
            path = __artist_path + artist_directories[artist] + "/"
        elif artist in ai_art_directories:
            is_ai_art = True
            path = __ai_art_path + artist + "/"
    
    return (path, is_ai_art)


def save_pcloud(url, **kwargs):
    artist = ""
    if "artist" in kwargs:
        artist = kwargs["artist"]

    path, is_ai_art = set_path(artist)
    temp_tags = " [AI]" if is_ai_art and not ' [AI]' in __meta_tags else ""
    filename = __add_filename_tags(" - ".join(kwargs.values()), temp_tags)
    filepath = os.path.join(path, filename)

    r = requests.get(url)
    with open(filepath, 'wb') as outfile:
        outfile.write(r.content)
    values = [ value for _, value in kwargs.items()][0:2]
    __file_list[f"{' - '.join(values)}"] = filepath

    print(str(filename) + " saved to " + filepath)


def save_pcloud_pixiv(pixiv_api:AppPixivAPI, pixiv_img):
    # Pixiv is unfortunately bitchy and doesn't like images being pulled off their website, so the API has to do it.
    img_id = pixiv_img.id
    artist = pixiv_img.user.account
    path, is_ai_art = set_path(artist)
    
    # If art is tagged as AI but the -ai command wasn't used, add [AI] tag to file.
    def set_temp_tag_ai() -> str:
        if ' [AI]' in __meta_tags:
            return ""
        if is_ai_art or 'AI-generated Illustration' in [tag.translated_name for tag in pixiv_img.tags]:
            return " [AI]"

        return ""

    def extract_image(url):
        img_num = url[url.rfind("/") + 1:]
        temp_tags = set_temp_tag_ai()
        filename = __add_filename_tags(artist + " - " + str(img_id) + " - " + img_num, temp_tags)
        pixiv_api.download(url, path=path, name=filename)
        print(filename + " saved to " + path + filename)
        __file_list[f"{artist} - {img_id}"] = path + filename

    if any(pixiv_img.meta_pages):
        for img in pixiv_img.meta_pages:
            extract_image(img.image_urls.original)
    elif not pixiv_img.meta_single_page is None:
        extract_image(pixiv_img.meta_single_page.original_image_url)