import os
import webimageextractor

# Note: these come from environmental variables, you will either have to add this to your
#.bashrc for Linux or via Mac/Window's method of adding them.
async def add_twitter_accounts():
    await webimageextractor.twt_api.pool.add_account(
        username=os.getenv("TWITTER_USERNAME1"),
        password=os.getenv("TWITTER_PASSWORD1"),
        email=os.getenv("TWITTER_EMAIL1"),
        email_password=os.getenv("EMAIL_PASSWORD1")
    )
    await webimageextractor.twt_api.pool.add_account(
        username=os.getenv("TWITTER_USERNAME2"),
        password=os.getenv("TWITTER_PASSWORD2"),
        email=os.getenv("TWITTER_EMAIL2"),
        email_password=os.getenv("EMAIL_PASSWORD2")
    )
