#!/usr/bin/env python -u

import os
import sys
import re
import urllib.parse as urlparse
import pcloud
import twscrape
import pixivpy3
import pixiv_auth
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
    
    lines = [re.sub("^\d+\. ", "", li).replace("\n","").replace("www.", "") for li in lines]

    return __extract_urls(lines)

def __extract_urls(lines:list[str]):
    img_data = []
    pixiv_auth_set = False
    for line in lines:
        url = urlparse.urlparse(line)
        # NOTE: path starts with "/" so you'll need to account for an extra item in the list
        split_path = url.path.split("/")

        match url.hostname:
            case "twitter.com":
                # Make sure the URL is to a status, not to home, search, etc.
                if url.path.find("/status/") < 0:
                    print(f"{Fore.YELLOW}URL is not valid: {line}{Style.RESET_ALL}")
                    continue
                # account @ 1, id @ 3: /{account}/status/{tweet_id}
                img_data.append((url.hostname, split_path[1], split_path[3]))
            case "pixiv.net" | "www.pixiv.net":
                if not pixiv_auth_set:
                    set_pixiv_refresh_token()
                    pixiv_auth_set = True
                # Make sure the URL is to the image
                if url.path.find("/artworks/") < 0:
                    print(f"{Fore.YELLOW}URL is not valid: {line}{Style.RESET_ALL}")
                    continue
                # id @ 3: /{lang}/artworks/{illustration_id}
                img_data.append((url.hostname, "", split_path[3])) 
            case "danbooru.donmai.us":
                # Make sure the URL is to the image
                if url.path.find("/posts/") < 0:
                    print(f"{Fore.YELLOW}URL is not valid: {line}{Style.RESET_ALL}")
                    continue
                # id @ 2: /post/{post_id}
                post_id = split_path[2]
                # Ensure that if any parameters were in the url that they're removed.
                index = post_id.find("?")
                if index > 0:
                    post_id = post_id[:index]
                img_data.append((url.hostname, "", post_id)) 
            case _:
                print(f"{Fore.YELLOW}Unable to pull ID, {url.hostname} is not supported.{Style.RESET_ALL}")
                continue

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
                dan_api.add_favorite(item["id"])
                print(f"Favorited {img_id} to post {item['id']}.")

    return dan_found


async def __extract_images(site, img_id):
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
            raise Exception(f"{img_id}:{site} not handled.")


async def extract_from_file(file, nosaving, nodanbooru, force, collection):
    img_data = __extract_data_from_file(file)

    # Keep the file if errors were encountered, but if everything went smoothly then delete the file since it's no longer needed.
    if not await extract(img_data, nosaving, nodanbooru, force, collection):
        print("Extraction complete. See output for errors.")
    else:
        print("Extraction complete. No issues encountered, removing file.")
        os.remove(file)


async def extract_from_url(url):
    img_data = __extract_urls([url])

    if not await extract(img_data, False, False, False, True):
        print("Extraction failed. See output for errors.")
    else:
        print("Extraction complete.")


async def extract(img_data, nosaving, nodanbooru, force, collection):
    if not any(await twt_api.pool.get_all()):
        print(f"{Fore.RED}No Twitter accounts provided. Add them by using the \"add-twitter-account\" command.")
        exit()

    await twt_api.pool.login_all()

    for site, artist, img_id in img_data:
        try:
            if pcloud.file_exists(artist, img_id):
                continue

            dan_found = 0
            if not nodanbooru:
                dan_found = __fav_danbooru(site, img_id)
                # Force saving if artist part of a collection
                if dan_found and collection:
                    if artist in pcloud.artist_directories:
                        dan_found = False 
                    
            if not dan_found or force:
                if not nosaving:
                    await __extract_images(site, img_id)
                else:
                    print(f"{Fore.YELLOW}Saving disabled, {img_id} skipped.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}{img_id}:{e}{Style.RESET_ALL}")
            return False

    return True