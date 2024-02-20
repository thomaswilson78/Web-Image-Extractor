#!/usr/bin/env python -u

import os
import sys
import re
import asyncclick as click
import pcloud
import twscrape
import pixivpy3
from colorama import Fore, Style

if sys.platform == "linux":
    sys.path.append(os.path.expanduser("~/pCloudDrive/repos/DanbooruAPI/"))
elif sys.platform == "win32":
    sys.path.append("P:/repos/DanbooruAPI")

import danbooruapi

pixiv_api = pixivpy3.AppPixivAPI()
twt_api = twscrape.API()


@click.group()
def commands():
    pass


@click.command()
@click.option("--username", required=True, prompt="Twitter Username",
              help="Username for the Twitter account. Will be prompted if not provided.")
@click.option("--password", required=True, prompt="Twitter Password", hide_input=True,
              help="Password for the Twitter account. Will be prompted if not provided.")
@click.option("--email", required=True, prompt="Twitter Email",
              help="Email associated with the Twitter account. Will be prompted if not provided.")
@click.option("--emailpassword", required=True, prompt="Email Password", hide_input=True,
              help="Password associated with the email account. Will be prompted if not provided.")
async def add_twitter_account(username, password, email, emailpassword):
    """Add a Twitter account to the list of accounts used in scraping data off the website."""
    await twt_api.pool.add_account(username, password, email, emailpassword)


@click.command()
@click.option("--username", required=True, prompt="Twitter Username")
async def remove_twitter_account(username):
    """Removes Twitter account from list of available accounts."""
    await twt_api.pool.delete_accounts(username)


# Pull the website and associated ID with post
def extract_ids(file):
    extension = os.path.splitext(file)[1]
    if not extension == ".txt":
        raise Exception("Incorrect file format.")

    id_list = []
    f = open(file)
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
                # id is always in 3rd slot: twitter.com/{account}/status/{tweet_id}
                id_list.append((split_url[0], split_url[1], split_url[3]))
            case "pixiv.net":
                id_list.append((split_url[0], "", split_url[3])) # id is always in 3rd slot: pixiv.net/{lang}/artworks/{illustration_id}
            case "danbooru.donmai.us":
                post_id = split_url[2] # id is always in 2nd slot: danbooru.donmai.us/post/{post_id}
                # Ensure that if any parameters were in the url that they're removed.
                index = post_id.find("?")
                if index > 0:
                    post_id = post_id[:index]
                id_list.append((split_url[0], post_id)) 
            case _:
                print(f"{Fore.YELLOW}Unable to pull ID, {split_url[0]} is not a valid website.{Style.RESET_ALL}")
                continue

    return id_list


def fav_danbooru(site, img_id):
    dan_found = False

    if site == "danbooru.donmai.us":
        danbooruapi.API.add_favorite(img_id)
        print(f"Favorited {img_id}.")
        dan_found = True
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


@click.command()
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("-ns", "--nosaving", is_flag=True, default=False, 
              help="Disables saving, only adds to favorites.")
@click.option("-nd", "--nodanbooru", is_flag=True, default=False, 
              help="Disables favoriting image to Danbooru, only saves.")
@click.option("-f", "--force", is_flag=True, default=False, 
              help="Forces all images to save regardless if found on Danbooru.")
@click.option("-c", "--collection", is_flag=True, default=False, 
              help="If artist is part of a collection, save image.")
async def extract(file, nosaving, nodanbooru, force, collection):
    """Pull image(s) from the Twitter/Danbooru and either adds them to favorites (if available) or downloads the image."""
    if not any(await twt_api.pool.get_all()):
        print(f"{Fore.RED}No Twitter accounts provided. Add them by using the \"add-twitter-account\" command.")
        exit()

    await twt_api.pool.login_all()
    # I'm not sure how good this token is, I think it has to be refreshed every
    # hour. I may just scrap this if it becomes a major hurdle, especially
    # since it's a bit of a pain to extract a valid token.
    pixiv_api.set_auth(os.getenv("PIXIV_TOKEN"))

    for site, artist, img_id in extract_ids(file):
        try:
            dan_found = 0
            if not nodanbooru:
                dan_found = fav_danbooru(site, img_id)
                # Force saving if artist part of a collection
                if dan_found and collection:
                    if artist in pcloud.artist_directories:
                        dan_found = False 
                    
            if not dan_found or force:
                if not nosaving:
                    await extract_images(site, img_id)
                else:
                    print(f"{Fore.YELLOW}Saving disabled, {img_id} skipped.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}{img_id}:{e}{Style.RESET_ALL}")

    print("Extraction complete. See output for any errors.")


commands.add_command(extract)
commands.add_command(add_twitter_account)
commands.add_command(remove_twitter_account)

if __name__ == "__main__":
    commands()
