#!/usr/bin/env python -u

import asyncclick as click
import twscrape
import imgextract

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
    await imgextract.extract(file, nosaving, nodanbooru, force, collection)


commands.add_command(extract)
commands.add_command(add_twitter_account)
commands.add_command(remove_twitter_account)

if __name__ == "__main__":
    commands()
