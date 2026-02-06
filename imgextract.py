#!/usr/bin/env python -u

import os
import sys
import re
import random
import urllib.parse as urlparse
import time
from playsound import playsound
from selenium import webdriver
from selenium.webdriver.common.by import By
import twscrape
from twscrape.models import Tweet
import pixivpy3
import pixiv_auth
import pcloud
from colorama import Fore, Style
from operator import attrgetter

if sys.platform == "linux":
    sys.path.append(os.path.expanduser("~/pCloudDrive/repos/DanbooruAPI/"))
elif sys.platform == "win32":
    sys.path.append("P:\\repos\\DanbooruAPI")

import danbooru

IS_DEBUG = hasattr(sys, 'gettrace') and sys.gettrace() is not None 

pixiv_api = pixivpy3.AppPixivAPI()
twt_api = twscrape.API()
dan_api = danbooru.API()

# Some file names by default are awful. This will be used to cut out everything but the ID.
custom_filenames = {"files.yande.re":1, "konachan.com":2}


# Pixiv has two tokens, refresh and access, the latter needs to be periodically updated to access Pixiv and download images.
def set_pixiv_refresh_token():
    """Update Pixiv access token."""
    refresh_token = os.getenv("PIXIV_REFRESH_TOKEN")
    new_token = pixiv_auth.refresh(refresh_token)
    pixiv_api.auth(refresh_token=new_token)

    return new_token


def is_ai_generated_twitter(tw_response:Tweet) -> bool:
    # This obviously won't catch everything, but should at least be enough to catch a decent quantity.
    # Anyone not caught can by the criteria below can be added to "ai_artist.txt" to filter them out.
    
    # Check list of known AI artist first
    if os.path.exists("./ai_artist.txt"):
        users = [ x.replace("\n","") for x in open("./ai_artist.txt").readlines() ]
        if tw_response.user.username in users:
            return True

    # Some users will have "@AIArt" or similar in their username    
    if "aiart" in tw_response.user.displayname.lower():
        return True
    
    # Checks if using the "#AIArt" hashtag
    if "#aiart" in tw_response.rawContent.lower():
        return True
    
    # Checks user bio to see if they have any AI keywords. Don't recommend using just "ai art" 
    # as some legit artist might have "use in ai art is prohibited" or similar in their bio.
    desc_keywords = [ "ComfyUI", "Stable Diffusion", "StableDiffusion", "AIイラスト", "AIillst", "Nijijourney", "NorvelAI" ]
    desc = tw_response.user.rawDescription.lower()
    for keyword in desc_keywords:
        if keyword.lower() in desc:
            return True

    return False


async def initialize_api_services(img_data):
    site_set = {site for site, _, _, _ in img_data}
    if "pixiv.net" in site_set:
        set_pixiv_refresh_token()
    if "twitter.com" or "x.com" in site_set:
        if not any(await twt_api.pool.get_all()):
            print(f"{Fore.RED}No Twitter(X) accounts provided. Add them by using the \"add-twitter-account\" command.{Style.RESET_ALL}")
            exit()
        await twt_api.pool.login_all()


def __get_urls_from_file(file):
    extension = os.path.splitext(file)[1]
    if not extension == ".txt":
        raise Exception("Incorrect file format.")

    urls = open(file).readlines()

    if not any(urls):
        raise Exception("Empty file.")

    return urls


def __get_url_data(lines:list[str]):
    """Pulls urls and url related meta-data needed to extract files."""

    def invalid_url(keyword:str):
        """Ensures that URL is valid for image extraction by matching a keyword in the URL (i.e. Twitter -> "status", Danbooru -> "posts", etc.)"""
        if parsed_url.path.find(keyword) < 0:
            print(f"{Fore.YELLOW}URL is not valid: {url}{Style.RESET_ALL}")
            return True
        
        return False
            
    # Ensure urls are properly useable by removing list indexes, new lines and the "www." prefix
    lines = [re.sub(r"^\d+\. ", "", li).replace("\n","").replace("www.", "") for li in lines]

    img_data = []
    file_formats = [".jpg", ".jpeg", ".png", ".webp", ".jfif", ".gif", ".mp4", ".webm"]

    for url in lines:
        parsed_url = urlparse.urlparse(url)
        # NOTE: path starts with "/" so you'll need to account for an extra item at the start of the list
        split_path = parsed_url.path.split("/")

        match parsed_url.hostname:
            case "twitter.com" | "x.com":
                if invalid_url("/status/"):
                    continue
                # account @ 1, id @ 3: /{account}/status/{tweet_id}
                img_data.append((parsed_url.hostname, split_path[1], split_path[3], url))
            case "pixiv.net":
                if invalid_url("/artworks/"):
                    continue
                # id @ 3: /{lang}/artworks/{illustration_id}
                img_data.append((parsed_url.hostname, "", split_path[3], url)) 
            case "danbooru.donmai.us" | "shima.donmai.us":
                if invalid_url("/posts/"):
                    continue
                # id @ 2: /post/{post_id}
                # Only pull ID, remove url queries (anything after ?) if exists.
                post_id = split_path[2][:split_path[2].find("?")+1] if split_path[2].find("?") > 0 else split_path[2]
                img_data.append((parsed_url.hostname, "", post_id, url)) 
            case _:
                # Check if URL is a media element, if not, ignore URL.
                if not any([url.endswith(format) for format in file_formats]):
                    print(f"{Fore.YELLOW}Url does not contain an image/video: {parsed_url.geturl()}{Style.RESET_ALL}")
                    continue
                img_data.append((parsed_url.hostname, "", None, url))

    return img_data


async def extract_urls(location, is_ai_art):
    """Extracts images/videos from url or file containing list of urls provided."""
    is_file = os.path.isfile(location)
    # If file is local, pull urls from file. Otherwise treat "location" as a url.
    data = __get_url_data(__get_urls_from_file(location) if is_file else [location])

    if not await extract_images(data, is_ai_art):
        print("Extraction completed with errors. See output.")
    else:
        if is_file and not IS_DEBUG:
            print("No issues encountered. Removing file...")
            os.remove(location)
        elif IS_DEBUG:
            print("DEBUG: File not deleted for debugging purposes.")
        print("Extraction complete.")


def get_custom_id(url, idx):
    return url.split("%20")[idx]


async def extract_images(img_data, is_all_ai):
    await initialize_api_services(img_data)

    # If "is_all_ai" is true, then all extracted files will download and save with a "[AI]" tag at the end of the filename.
    pcloud.set_tags(is_all_ai)

    no_errors = True
    pix_response = None
    for site, artist, img_id, url in img_data:
        try:
            # Danbooru only needs to add to favorites using the DanbooruAPI tool, all others will extract the image to save locally
            if site not in {"danbooru.donmai.us", "shima.donmai.us"}:
                if site == "pixiv.net":
                    pix_response = pixiv_api.illust_detail(img_id)
                    if any(pix_response) and any(pix_response.illust):
                        artist = pix_response.illust.user.account
                    else:
                        print(f"{Fore.YELLOW}Invalid pixiv repsonse.{Style.RESET_ALL}")
                        continue

                # First clause handles Twitter(X) and Pixiv, second handles all other cases
                if not img_id is None:
                    fieldA, fieldB = (artist, img_id) 
                elif site in custom_filenames:
                    id_index = custom_filenames[site]
                    fieldA, fieldB = (site, get_custom_id(url, id_index))
                else:
                    fieldA, fieldB = (site, url[str.rfind(url, "/") + 1:])
                check_file = f"{fieldA} - {fieldB}"
                if pcloud.file_exists(check_file):
                    print(f"{Fore.YELLOW}{check_file} already exists: {pcloud.get_file_location(check_file)}{Style.RESET_ALL}")
                    continue
                    
            match site:
                case "danbooru.donmai.us" | "shima.donmai.us":
                    dan_api.add_favorite(img_id)
                    print(f"Favorited {img_id}.")
                case "twitter.com" | "x.com":
                    tw_response = await twt_api.tweet_details(int(img_id))
                    # all_ai_art will superseed this in importance
                    is_ai_art:bool = True if is_all_ai else is_ai_generated_twitter(tw_response)

                    for image in tw_response.media.photos:
                        # make sure image is at max possible resolution
                        url = image.url + "?name=4096x4096"
                        filename = image.url[image.url.rfind('/') + 1:]
                        pcloud.save_pcloud(url, is_ai_art, artist=tw_response.user.username, img_id=str(img_id), filename=filename)
                    for video in tw_response.media.videos:
                        vid:twscrape.MediaVideoVariant = max(video.variants, key=attrgetter("bitrate"))
                        filename = vid.url[vid.url.rfind('/') + 1:vid.url.rfind('?')]
                        pcloud.save_pcloud(vid.url, is_ai_art, artist=tw_response.user.username, img_id=str(img_id), filename=filename)
                    for animation in tw_response.media.animated:
                        url = animation.videoUrl
                        filename = url[url.rfind('/') + 1:]
                        pcloud.save_pcloud(url, is_ai_art, artist=tw_response.user.username, img_id=str(img_id), filename=filename)
                case "pixiv.net" | "www.pixiv.net":
                    pcloud.save_pcloud_pixiv(pixiv_api, pix_response.illust)
                case _:
                    filename:str = url[str.rfind(url, "/") + 1:]
                    if site in custom_filenames:
                        img_id = get_custom_id(url, custom_filenames[site])
                        filename = f"{img_id}{os.path.splitext(url)[1]}"
                    pcloud.save_pcloud(url, is_ai_art=False, site=site, filename=filename)

        except Exception as e:
            print(f"{Fore.RED}{img_id}:{e}{Style.RESET_ALL}")
            no_errors = False

    return no_errors


def allow_lookup_tabs(urls:list) -> bool:
    """If there are still tabs that have iqdb.org/google.com, ask user if they wish to continue or double check them."""
    match_found:bool = False
    lookup_methods = { ".*iqdb.org.*", ".*google.com.*" }

    for url in urls:
        if re.match(rf"({"|".join(lookup_methods)})", url):
            match_found = True
            break

    # If there were, stop process to allow for double check.
    if match_found:
        while True:
            iqdb_val = input(f"There are still lookup tabs open. Halt image extraction and check remaining lookup image match(es)?[Y/n]: ").lower()
            match iqdb_val:
                case "y" | "":
                    return False
                case "n":
                    return True
                case _:
                    print("Invalid input.")
            
    return True

def set_driver(browser):
    current_directory = os.getcwd()
    match browser.lower():
        case "chrome":
            driver_file = "chromedriver" + (".exe" if sys.platform == "win32" else "")
            service = webdriver.ChromeService(executable_path=rf"{current_directory}/{driver_file}")

            options = webdriver.ChromeOptions()
            # Formly used before tab collection/extraction was automated, now no longer needed since the browser will stay opened 
            # until extraction finishes. Only keeping this here for reference. Will likley never use this again.
            # options.add_experimental_option("detach", True) # Need this to keep the window open after task finishes

            ext_path = f"{current_directory}/Extensions/Chrome/"
            for ext in os.listdir(ext_path):
                options.add_extension(extension=rf"{ext_path}/{ext}")

            driver = webdriver.Chrome(options=options,service=service)
        case "firefox":
            driver = webdriver.Firefox(service=webdriver.FirefoxService())
            ext_path = f"{current_directory}/Extensions/Firefox/"

            for ext in os.listdir(ext_path):
                 driver.install_addon(path=rf"{ext_path}/{ext}")
        case _:
            raise Exception("Invalid browser defined.")

    return driver


async def lookup(file, browser:str, method:str):
    """"Reads urls from file and searches via iqdb.org for a match. Utilizes selenium to pull file."""
    # Extract data from URLs
    img_data = __get_url_data(__get_urls_from_file(file))
    await initialize_api_services(img_data)
    
    # If set to true then alternate to iqdb for Pixiv URLs as Google Lens cannot handle them.
    allow_iqdb_pixiv:bool = False
    if method == "lens" and any("pixiv" in site for site, _, _, _ in img_data):
            while True:
                input_val = input(f"It is unadvised to use Google Lens with Pixiv urls. Allow iqdb to search for Pixiv links?[Y/n]: ").lower() 
                match input_val:
                    case "y" | "":
                        allow_iqdb_pixiv = True
                        break
                    case "n":
                        break
                    case _:
                        print("Invalid entry.")
                        continue

    # Setup selenium to work with selected browser and install any extensions/add-ons
    driver = set_driver(browser)
    driver.implicitly_wait(180)

    def iqdb_lookup(url):
        driver.switch_to.new_window('tab')
        driver.get("https://iqdb.org/")
        
        #To not overwhelm servers as well as make traffic look less suspect to avoid being banned.
        time.sleep(round(random.uniform(2.500, 4.300), 2))

        url_text_box = driver.find_element(by=By.ID, value="url")
        submit_button = driver.find_element(by=By.CSS_SELECTOR, value="input[type='submit']")

        url_text_box.send_keys(url)
        submit_button.click()

    def google_lens_lookup(url):
        if allow_iqdb_pixiv and "i.pximg.net" in url:
            iqdb_lookup(url)
        else:
            driver.switch_to.new_window('tab')
            driver.get(rf"https://lens.google.com/uploadbyurl?url={url}")

            # Check if there is a captcha, if so it needs to be solved before continuing.
            if re.match(r".*google.com\/sorry\/.*", driver.current_url):
                while True:
                    input_val = input(f"Capcha solved?[Y/n]: ").lower() 
                    match input_val:
                        case "y" | "":
                            break
                        case _:
                            continue

            #To not overwhelm servers as well as make traffic look less suspect to avoid being banned.
            time.sleep(round(random.uniform(2.500, 3.300), 2))

    match method:
        case "iqdb":
            lookup_method = iqdb_lookup
        case "lens":
            lookup_method = google_lens_lookup

    for site, _, img_id, url in img_data:
        try:
            if url != img_data[0][3]:
                driver.switch_to.new_window('tab')

            driver.get(url)
            match site:
                case "danbooru.donmai.us" | "shima.donmai.us":
                    continue
                case "twitter.com" | "x.com":
                    tw_response = await twt_api.tweet_details(int(img_id))
                    if is_ai_generated_twitter(tw_response):
                        continue
                    
                    for image in tw_response.media.photos:
                        image_url = image.url + "?name=small" # Small should suffice and use less bandwidth
                        lookup_method(image_url)
                case "pixiv.net" | "www.pixiv.net":
                    pix_response = pixiv_api.illust_detail(img_id)
                    if any(pix_response) and any(pix_response.illust):
                        pixiv_img = pix_response.illust
                        # Skip AI images
                        if pixiv_img.illust_ai_type == 2:
                            continue

                        if any(pixiv_img.meta_pages): # Multi Image
                            for img in pixiv_img.meta_pages:
                                lookup_method(img.image_urls.medium)
                        else: # Single Image
                            # Try Danbooru first to save time. If we get a hit, open a tab for them instead.
                            dan_response = dan_api.get_posts({"tags":f"pixiv:{img_id}"})
                            if any(dan_response):
                                driver.switch_to.new_window('tab')
                                driver.get(f"https://danbooru.donmai.us/posts/{dan_response[0]['id']}")
                            else:
                                lookup_method(pixiv_img.image_urls.medium)
                case _:
                    lookup_method(url)
        except Exception as e:
            print(f"{site} - {img_id}: {e}")

    playsound("./assets/ping.wav")
    print("Done.")

    while True:
        # This is more a formality. Let's me go through everything first before I let it auto-extract.
        input_val = input(f"Auto-extract tabs?[Y/n]: ").lower()
        match input_val:
            case "y" | "":
                try:
                    urls:list = []
                    # Pull urls from open browser tabs
                    for handle in driver.window_handles:
                        driver.switch_to.window(handle)
                        urls.append(driver.current_url)

                    # If lookup tabs are still open, halt extraction.
                    if allow_lookup_tabs(urls) == False:
                        continue
                        
                    # Create a temporary local file to save the tab URLs to.
                    extract_file = f"{os.getcwd()}/temp.txt"
                    if os.path.exists(extract_file):
                        os.remove(extract_file)
                    with open(extract_file, "+w") as fi:
                        fi.write("\n".join(urls))

                    # Extract the data like we would by calling the "extract" command via CLI using the file that was just created.
                    await extract_urls(extract_file, False)
                    if not IS_DEBUG:
                        os.remove(file)
                        print("File deleted.")
                    else:
                        print("DEBUG: File not deleted for debugging purposes.")
                except Exception as e:
                    print(f"Error Occurred: {e}")
                break
            case "n":
                break
            case _:
                print("Invalid input.")

    driver.quit()