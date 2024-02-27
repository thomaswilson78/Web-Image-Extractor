#!/usr/bin/env python -u

import os
import sys
import urllib.parse as urlparse
import pcloud
import twscrape
import pixivpy3
from colorama import Fore, Style

if sys.platform == "linux":
    sys.path.append(os.path.expanduser("~/pCloudDrive/repos/DanbooruAPI/"))
elif sys.platform == "win32":
    sys.path.append("P:/repos/DanbooruAPI")

import danbooru

pixiv_api = pixivpy3.AppPixivAPI()
twt_api = twscrape.API()
dan_api = danbooru.API()

# Pull the website and associated ID with post
def __extract_ids(file):
    extension = os.path.splitext(file)[1]
    if not extension == ".txt":
        raise Exception("Incorrect file format.")

    lines = open(file).readlines()

    if not any(lines):
        raise Exception("Empty file.")

    lines = [li.replace("\n", "") for li in lines]

    id_list = []
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
                id_list.append((url.hostname, split_path[1], split_path[3]))
            case "pixiv.net":
                # Make sure the URL is to the image
                if url.path.find("/artworks/") < 0:
                    print(f"{Fore.YELLOW}URL is not valid: {line}{Style.RESET_ALL}")
                # id @ 3: /{lang}/artworks/{illustration_id}
                id_list.append((url.hostname, "", split_path[3])) 
            case "danbooru.donmai.us":
                # id @ 2: /post/{post_id}
                post_id = split_path[2]
                # Ensure that if any parameters were in the url that they're removed.
                index = post_id.find("?")
                if index > 0:
                    post_id = post_id[:index]
                id_list.append((url.hostname, "", post_id)) 
            case _:
                print(f"{Fore.YELLOW}Unable to pull ID, {url.hostname} is not supported.{Style.RESET_ALL}")
                continue

    return id_list


def __fav_danbooru(site, img_id):
    dan_found = False

    if site == "danbooru.donmai.us":
        dan_api.add_favorite(img_id)
        print(f"Favorited {img_id}.")
        dan_found = True
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
                pcloud.save_pcloud(img_id, tw_response.user.username, url, filename)
            # Would like a way to extract videos as well, but need to sit on this
            # for video in tw_response.media.videos:
            #     for variant in video.variants
            #         variant.url
        case "pixiv.net":
            return
            # I'll try to figure this out later, not sure how to handle
            # pages w/ multiple images.
            # pix_response = pixiv_api.illust_detail(img_id)
            # filename = pixiv_api.download("")
            # pcloud.save_pcloud(img_id, pix_response["user"]["name"], url)
            # continue
        case _:
            raise Exception(f"{img_id}:{site} not handled.")


async def extract(file, nosaving, nodanbooru, force, collection):
    if not any(await twt_api.pool.get_all()):
        print(f"{Fore.RED}No Twitter accounts provided. Add them by using the \"add-twitter-account\" command.")
        exit()

    await twt_api.pool.login_all()
    # I'm not sure how good this token is, I think it has to be refreshed every
    # hour. I may just scrap this if it becomes a major hurdle, especially
    # since it's a bit of a pain to extract a valid token.
    pixiv_api.set_auth(os.getenv("PIXIV_TOKEN"))

    errors_encountered = False
    for site, artist, img_id in __extract_ids(file):
        try:
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
            errors_encountered

    # Keep the file if errors were encountered, but if everything went smoothly then delete the file since it's no longer needed.
    if errors_encountered:
        print("Extraction complete. See output for errors.")
    else:
        print("Extraction complete. No issues encountered, removing file.")
        os.remove(file)