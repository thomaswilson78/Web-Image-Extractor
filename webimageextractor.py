import os
import sys
import re
import asyncio
from colorama import Fore, Style

import pcloud
import accounts

import twscrape
import pixivpy3

if sys.platform == "linux":
    sys.path.append(os.path.expanduser("~/pCloudDrive/repos/DanbooruAPI/"))
elif sys.platform == "win32":
    sys.path.append("P:/repos/DanbooruAPI")

import danbooruapi

pixiv_api = pixivpy3.AppPixivAPI()
twt_api = twscrape.API()


def display_man():
    #  one day my lazy butt will make this, but that day is not today
    return


def get_input_file():
    file = ""
    try:
        file = sys.argv[1]
    except:
        raise Exception("File not provided.")

    if not os.path.isfile(file):
        raise Exception("File does not exist.")

    extension = os.path.splitext(file)[1]
    if not extension == ".txt":
        raise Exception("Incorrect file format.")

    return file


# Pull the website and associated ID with post
def extract_ids():
    id_list = []
    f = open(get_input_file())
    lines = f.readlines()

    if not any(lines):
        raise Exception("Empty file.")

    lines = [li.replace("\n", "") for li in lines]

    for line in lines:
        new_line = re.sub(".*http.*://", "", line)
        new_line = re.sub("www.", "", new_line)
        split_url = new_line.split("/")

        match split_url[0]:
            case "twitter.com":
                # tweet_id is always in 3rd slot: twitter.com/{account}/status/{tweet_id}
                id_list.append((split_url[0], split_url[1], split_url[3]))

            case "pixiv.net":
                id_list.append((split_url[0], "", split_url[3])) # tweet_id is in 3rd slot: pixiv.net/{lang}/artworks/{illustration_id}
            case "danbooru.donmai.us":
                post_id = split_url[2]
                index = post_id.find("?")
                if index > 0:
                    post_id = post_id[:index]
                id_list.append((split_url[0], post_id)) # tweet_id is in 3rd slot: pixiv.net/{lang}/artworks/{illustration_id}
            case _:
                print(f"{Fore.YELLOW}Unable to pull ID, {split_url[0]} is not a valid website.{Style.RESET_ALL}")
                continue

    return id_list


def fav_danbooru(site, img_id):
    dan_found = 0

    if site == "danbooru.donmai.us":
        danbooruapi.API.add_favorite(img_id)
        print(f"Favorited {img_id}.")
        dan_found = 1
    else:
        params = {"tags": f"source:*{site}*{img_id}"}
        json_data = danbooruapi.API.get_posts(params)

        dan_found = any(json_data)
        
        if dan_found:
            for item in json_data:
                danbooruapi.API.add_favorite(item["id"])
                print(f"Favorited {img_id} to post {item['id']}.")

    return dan_found


async def extract_images(site, img_id):
    match site:
        case "twitter.com":
            tw_response = await twt_api.tweet_details(int(img_id))
            for image in tw_response.media.photos:
                # make sure image is at max resolution
                url = image.url + "?name=4096x4096"
                filename = image.url[image.url.rfind('/') + 1:]
                pcloud.save_pcloud(img_id, tw_response.user.username, url, filename)
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


async def main():
    # Disable saving favorites to Danbooru, only save to pCloud
    disable_dan = 1 if "-dd" in sys.argv else 0
    # Disable saving favorites to Danbooru, only save to pCloud
    disable_saving = 1 if "-ds" in sys.argv else 0
    # Save even if found on Danbooru
    force_save = 1 if "-f" in sys.argv else 0
    # If artist is part of a collection, save as well
    save_collection = 1 if "-c" in sys.argv else 0

    await accounts.add_twitter_accounts()
    await twt_api.pool.login_all()
    # I'm not sure how good this token is, I think it has to be refreshed every
    # hour. I may just scrap this if it becomes a major hurdle, especially
    # since it's a bit of a pain to extract a valid token.
    pixiv_api.set_auth(os.getenv("PIXIV_TOKEN"))

    for site, artist, img_id in extract_ids():
        try:
            dan_found = 0
            if not disable_dan:
                dan_found = fav_danbooru(site, img_id)
                # Force saving if artist part of a collection
                if dan_found and save_collection:
                    if artist in pcloud.artist_directories:
                        dan_found = 0 
                    
            # might try to incorporate the saucenao API but that's a bit iffy,
            # especially when even they admit their API sucks

            if not dan_found or force_save:
                if not disable_saving:
                    await extract_images(site, img_id)
                else:
                    print(f"{Fore.YELLOW}Saving disabled, {img_id} skipped.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}{img_id}:{e}{Style.RESET_ALL}")

    print("Extraction complete. See output for any errors.")


if __name__ == "__main__":
    asyncio.run(main())
