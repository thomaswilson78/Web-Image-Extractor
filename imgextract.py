#!/usr/bin/env python -u

import os
import sys
import re
import random
import urllib.parse as urlparse
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
import twscrape
import pixivpy3
import pixiv_auth
import pcloud
from colorama import Fore, Style
from operator import attrgetter

if sys.platform == "linux":
    sys.path.append(os.path.expanduser("~/pCloudDrive/repos/DanbooruAPI/"))
elif sys.platform == "win32":
    sys.path.append("P:/repos/DanbooruAPI")

import danbooru


pixiv_api = pixivpy3.AppPixivAPI()
twt_api = twscrape.API()
dan_api = danbooru.API()


file_formats = [".jpg", ".jpeg", ".png", ".webm", ".jfif", ".gif", ".mp4", ".webm"]


# Pixiv refresh tokens expire, needs to be periodically updated
def set_pixiv_refresh_token():
    old_token = os.getenv("PIXIV_REFRESH_TOKEN")
    new_token = pixiv_auth.refresh(old_token)
    os.environ["PIXIV_REFRESH_TOKEN"] = new_token
    pixiv_api.auth(refresh_token=new_token)

    return new_token


# Pull the website and associated ID with post
def __extract_data_from_file(file):
    extension = os.path.splitext(file)[1]
    if not extension == ".txt":
        raise Exception("Incorrect file format.")

    lines = open(file).readlines()

    if not any(lines):
        raise Exception("Empty file.")

    return __extract_urls(lines)

def __extract_urls(lines:list[str]):
    # Ensure urls are properly useable by removing list indexes, new lines and the "www." prefix
    lines = [re.sub("^\d+\. ", "", li).replace("\n","").replace("www.", "") for li in lines]

    img_data = []
    pixiv_auth_set = False
    for url in lines:
        parsed_url = urlparse.urlparse(url)
        # NOTE: path starts with "/" so you'll need to account for an extra item in the list
        split_path = parsed_url.path.split("/")

        match parsed_url.hostname:
            case "twitter.com":
                # Make sure the URL is to a status, not to home, search, etc.
                if parsed_url.path.find("/status/") < 0:
                    print(f"{Fore.YELLOW}URL is not valid: {url}{Style.RESET_ALL}")
                    continue
                # account @ 1, id @ 3: /{account}/status/{tweet_id}
                img_data.append((parsed_url.hostname, split_path[1], split_path[3], url))
            case "pixiv.net":
                if not pixiv_auth_set:
                    set_pixiv_refresh_token()
                    pixiv_auth_set = True
                # Make sure the URL is to the image
                if parsed_url.path.find("/artworks/") < 0:
                    print(f"{Fore.YELLOW}URL is not valid: {url}{Style.RESET_ALL}")
                    continue
                # id @ 3: /{lang}/artworks/{illustration_id}
                img_data.append((parsed_url.hostname, "", split_path[3], url)) 
            case "danbooru.donmai.us":
                # Make sure the URL is to the image
                if parsed_url.path.find("/posts/") < 0:
                    print(f"{Fore.YELLOW}URL is not valid: {url}{Style.RESET_ALL}")
                    continue
                # id @ 2: /post/{post_id}
                post_id = split_path[2]
                # Ensure that if any parameters were in the url that they're removed.
                index = post_id.find("?")
                if index > 0:
                    post_id = post_id[:index]
                img_data.append((parsed_url.hostname, "", post_id, url)) 
            case _:
                if not any([url.endswith(format) for format in file_formats]):
                    print(f"{Fore.YELLOW}Url does not contain an image/video: {parsed_url.geturl()}{Style.RESET_ALL}")
                    continue
                img_data.append((parsed_url.hostname, "", None, url))


    return img_data


def __fav_danbooru(site, img_id):
    dan_found = False

    if site == "danbooru.donmai.us":
        dan_api.add_favorite(img_id)
        print(f"Favorited {img_id}.")
        dan_found = True
    else:
        params = {}
        if site == "pixiv.net": # Pixiv for some reason has it's own tag
            params = {"tags": f"pixiv:{img_id}"}
        else:
            params = {"tags": f"source:*{site}*{img_id}"}
        json_data = dan_api.get_posts(params)

        dan_found = any(json_data)
        
        if dan_found:
            for item in json_data:
                # If art is attached to a banned artist, then ignore it because it's locked and cannot be viewed.
                if item['is_banned']:
                    print(f"{Fore.YELLOW}Danbooru lists {item['id']} as made by a banned artist. Have to save manually.{Style.RESET_ALL}")
                    return False
                dan_api.add_favorite(item["id"])
                print(f"Favorited {img_id} to post {item['id']}.")

    return dan_found


async def __extract_images(site, img_id, url):
    match site:
        case "twitter.com":
            tw_response = await twt_api.tweet_details(int(img_id))
            for image in tw_response.media.photos:
                # make sure image is at max resolution
                url = image.url + "?name=4096x4096"
                filename = image.url[image.url.rfind('/') + 1:]
                pcloud.save_pcloud_twitter(img_id, tw_response.user.username, url, filename)
            for video in tw_response.media.videos:
                vid:twscrape.MediaVideoVariant = max(video.variants, key=attrgetter("bitrate"))
                filename = vid.url[vid.url.rfind('/') + 1:vid.url.rfind('?')]
                pcloud.save_pcloud_twitter(img_id, tw_response.user.username, vid.url, filename)
            for animation in tw_response.media.animated:
                url = animation.videoUrl
                filename = url[url.rfind('/') + 1:]
                pcloud.save_pcloud_twitter(img_id, tw_response.user.username, url, filename)
        case "pixiv.net" | "www.pixiv.net":
            pix_response = pixiv_api.illust_detail(img_id)
            if any(pix_response) and any(pix_response.illust):
                pcloud.save_pcloud_pixiv(pixiv_api, pix_response.illust)
        case _:
            pcloud.save_pcloud_other(site, url)


async def extract_from_file(file, collection, is_ai_art):
    img_data = __extract_data_from_file(file)

    # Keep the file if errors were encountered, but if everything went smoothly then delete the file since it's no longer needed.
    if not await extract(img_data, collection, is_ai_art):
        print("Extraction complete. See output for errors.")
    else:
        print("Extraction complete. No issues encountered, removing file.")
        os.remove(file)


async def extract_from_url(url, is_ai_art):
    img_data = __extract_urls([url])

    if not await extract(img_data, True, is_ai_art):
        print("Extraction failed. See output for errors.")
    else:
        print("Extraction complete.")


async def extract(img_data, collection, is_ai_art):
    if not any(await twt_api.pool.get_all()):
        print(f"{Fore.RED}No Twitter accounts provided. Add them by using the \"add-twitter-account\" command.")
        exit()

    await twt_api.pool.login_all()

    if is_ai_art:
        pcloud.set_ai_art_path()

    no_errors = True
    for site, artist, img_id, url in img_data:
        try:
            dan_found = False 
            if not img_id is None:
                if pcloud.file_exists(artist, img_id):
                    continue

                dan_found = __fav_danbooru(site, img_id)
                # Force saving if artist part of a collection
                if collection and artist in pcloud.artist_directories:
                    dan_found = False 
            else:
                filename = url[str.rfind(url, "/")+1:]
                if pcloud.file_exists(site, filename):
                    continue
                    
            if not dan_found:
                await __extract_images(site, img_id, url)
        except Exception as e:
            print(f"{Fore.RED}{img_id}:{e}{Style.RESET_ALL}")
            no_errors = False

    return no_errors


async def iqdb(file):
    img_data = __extract_data_from_file(file)

    current_directory = os.getcwd()
    service = webdriver.ChromeService(executable_path=rf"{current_directory}/chromedriver")

    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)

    ext_path = f"{current_directory}/Extensions/"
    for ext in os.listdir(ext_path):
        options.add_extension(extension=rf"{ext_path}/{ext}")

    driver = webdriver.Chrome(options=options,service=service)

    def execute_web_driver(url):
        driver.switch_to.new_window('tab')
        driver.get("https://iqdb.org/")
        
        driver.implicitly_wait(5)
        time.sleep(random.uniform(.4, .7))

        url_text_box = driver.find_element(by=By.ID, value="url")
        submit_button = driver.find_element(by=By.CSS_SELECTOR, value="input[type='submit']")

        url_text_box.send_keys(url)
        submit_button.click()

        #To make traffic looks less suspect and to not overwhelm servers and potentially get banned.
        time.sleep(round(random.uniform(4.000, 6.999), 2))

    for site, _, img_id, url in img_data:
        try:
            driver.switch_to.new_window('tab')
            driver.get(url)

            match site:
                case "twitter.com":
                    tw_response = await twt_api.tweet_details(int(img_id))
                    for image in tw_response.media.photos:
                        image_url = image.url + "?name=small" # Small should suffice and uses less bandwidth
                        execute_web_driver(image_url)
                case "pixiv.net" | "www.pixiv.net":
                    pix_response = pixiv_api.illust_detail(img_id)
                    if any(pix_response) and any(pix_response.illust):
                        pixiv_img = pix_response.illust
                        if any(pixiv_img.meta_pages): # Multi Image
                            for img in pixiv_img.meta_pages:
                                execute_web_driver(img.image_urls.medium)
                        else: # Single Image
                            execute_web_driver(pixiv_img.image_urls.medium)
                case _:
                    execute_web_driver(url)
        except Exception as e:
            print(e)

    print("Done.")