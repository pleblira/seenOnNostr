from requests_oauthlib import OAuth1Session
import os
import json
from dotenv import load_dotenv, find_dotenv
from get_exclude_reply_user_ids import *

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

consumer_key = os.environ.get("CONSUMER_KEY")
consumer_secret = os.environ.get("CONSUMER_SECRET")
access_token = os.environ.get("ACCESS_TOKEN")
access_token_secret = os.environ.get("ACCESS_TOKEN_SECRET")

def tweet_with_apiv2(tweet_message):

    # exclude_reply_user_ids = get_exclude_reply_user_ids(scraped_tweet)
    # payload = {"text": tweet_message, "reply":{"in_reply_to_tweet_id":str(scraped_tweet['id']), "exclude_reply_user_ids": exclude_reply_user_ids}}
    payload = {"text": tweet_message}

    # Make the request
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )

    # Making the request
    response = oauth.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
    )

    if response.status_code != 201:
        raise Exception(
            "Request returned an error: {} {}".format(response.status_code, response.text)
        )

    print("Response code: {}".format(response.status_code))

    # Saving the response as JSON
    json_response = response.json()
    print(json.dumps(json_response, indent=4, sort_keys=True))
