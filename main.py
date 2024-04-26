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
@click.option("-ai", "--ai_art", is_flag=True, default=False, 
              help="Indicated if arts is AI generated.")
async def extract(file, ai_art):
    """Pull image(s) from the Twitter/Danbooru and either adds them to favorites (if available) or downloads the image."""
    await imgextract.extract_from_file(file, ai_art)


@click.command()
@click.argument("url")
@click.option("-ai", "--ai_art", is_flag=True, default=False, 
              help="Indicated if arts is AI generated.")
async def extract_url(url:str, ai_art):
    await imgextract.extract_from_url(url, ai_art)


@click.command()
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
async def iqdb(file):
    """Check if iqdb can find image on imageboard sites."""
    await imgextract.iqdb(file)


commands.add_command(extract)
commands.add_command(extract_url)
commands.add_command(add_twitter_account)
commands.add_command(remove_twitter_account)
commands.add_command(iqdb)

if __name__ == "__main__":
    commands()
