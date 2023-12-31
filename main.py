# from python_nostr import RelayManager
# from python_nostr import PublicKey, PrivateKey
# from nostr.relay_manager import RelayManager
# from nostr.key import PublicKey
# from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import json
import os
import ssl
import time
import tweepy
import secrets
import ffmpeg
import sys

from append_json import *
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import find_dotenv
from dotenv import load_dotenv
from post_note import *
from python_nostr_package.nostr import PrivateKey
from python_nostr_package.nostr import PublicKey
from python_nostr_package.nostr import RelayManager
from set_query_filters import *
from store_stackjoin import *
from tweet_with_apiv2 import *
from turn_long_note_into_twitter_thread import *

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

consumer_key = os.environ.get("CONSUMER_KEY")
consumer_secret = os.environ.get("CONSUMER_SECRET")
access_token = os.environ.get("ACCESS_TOKEN")
access_token_secret = os.environ.get("ACCESS_TOKEN_SECRET")
public_key = PublicKey.from_npub(os.environ.get("PUBLIC_KEY"))
private_key = PrivateKey.from_nsec(os.environ.get("PRIVATE_KEY"))
HASHTAG = "relaytotwitter"

def query_nostr_relays(type_of_query, query_term, since=0):
  if type_of_query != "individual_event":
    event_id = ""
  request, filters, subscription_id = set_query_filters(type_of_query=type_of_query, query_term=query_term, since=since)

  print(request, filters)
  relay_manager = RelayManager()
  with open('relay_list.txt', 'r') as f:
    for line in f:
        relay_manager.add_relay(line.strip())
  relay_manager.add_subscription(subscription_id, filters)
  relay_manager.open_connections({"cert_reqs": ssl.CERT_NONE}) # NOTE: This disables ssl certificate verification
  time.sleep(1.25) # allow the connections to open
  message = json.dumps(request)
  relay_manager.publish_message(message)
  time.sleep(20) # allow the messages to send
  
  relay_manager.close_connections()
  return relay_manager.message_pool

def seenOnNostr(start_time_for_first_run = 0):
  print("\n*****\n"+datetime.now().isoformat()+": running seenOnNostr")
  with open('last_time_checked.json', 'r') as f:
    times_checked = json.load(f)
    last_time_checked = int(times_checked[0]['checked_time'])
  if start_time_for_first_run != 0:
    last_time_checked = start_time_for_first_run
    print(f"checking from datetime ISO {datetime.fromtimestamp(start_time_for_first_run).isoformat()}")
  else:
    print(f'last time checked ISO is {times_checked[0]["checked_time_iso"]}')

  # updating last time checked for new notes
  with open('last_time_checked.json', 'r+') as f:
    times_checked = json.load(f)
    times_checked.reverse()
    times_checked.append({"checked_time":datetime.now().timestamp(), "checked_time_iso": datetime.now().now().isoformat(), "number_of_checks":times_checked[len(times_checked)-1]['number_of_checks']+1})
    if len(times_checked) > 20:
      times_checked.pop(0)
    times_checked.reverse()
    f.seek(0)
    f.truncate(0)
    f.write(json.dumps(times_checked, indent=4))

  message_pool_relay_manager_hashtag = query_nostr_relays(since=last_time_checked, type_of_query="hashtag", query_term=HASHTAG)
  # message_pool_relay_manager_hashtag = query_nostr_relays(since=1688831890, type_of_query="hashtag", query_term=HASHTAG)
  # message_pool_relay_manager_hashtag = query_nostr_relays(since=last_time_checked, type_of_query="user_tag", query_term="273e5c07475e1edea1a60b762336fdd7a37a2b845f137d524a0460f9f0c44c4a")
  # message_pool_relay_manager_hashtag = query_nostr_relays(since=1688829988, type_of_query="individual_event", query_term="5315b4b3a8ccce6ea60f153c50d78bfeb8c808228837c623e059c51ed478a2a6")
  # message_pool_relay_manager_hashtag = query_nostr_relays(since=1688829988, type_of_query="individual_event", query_term="a9e34d3180183009b956370a07457f146a73bc722b0f81d18b83b76782acda66")
  
  print("queried nostr relays")
 
  while message_pool_relay_manager_hashtag.has_events():
    event_msg = message_pool_relay_manager_hashtag.get_event()
    print("\n\n___________NEW_EVENT__________")
    print(f"event.json: {event_msg.event.json}")

    # double-checking for HASHTAG
    has_hashtag = False
    for tag in event_msg.event.json[2]["tags"]:
      if "t" in tag:
        print("event tag found")
        for item in tag:
          if item == HASHTAG:
            print(f"{HASHTAG} hashtag found")
            if event_msg.event.json[0] == "EVENT":
              print(f"\n>> Poster's profile on snort.social: https://snort.social/p/{PublicKey.hex_to_bech32(event_msg.event.json[2]['pubkey'], 'Encoding.BECH32')}")
              print(f">> Event on snort.social: https://snort.social/e/{PublicKey.hex_to_bech32(event_msg.event.json[2]['id'], 'Encoding.BECH32')}")
            has_hashtag = True

    # additional check to see if event is already in json, hence already responded to
    new_event = True
    with open("events.json", "r") as f:
      events = json.load(f)
      for event in events:
        if event_msg.event.json[2]["id"] == event[2]["id"]:
          new_event = False
          print("found event on json, skipping append_json and posting")
    if new_event == True:
      print("didn't find event on json, moving forward to append_json and posting")

    if has_hashtag == True and new_event == True:
      append_json(event_msg = event_msg.event.json)

    # upon confirming it's a new event, checking if it's a reply or a new note
      non_mention_e_tags = []
      for tag in event_msg.event.json[2]["tags"]:
        if "e" in tag and "mention" not in tag:
          non_mention_e_tags.append(tag)
      if len(non_mention_e_tags) == 1:
        print("single non_mention tag, means it's the note to be retrieved")
        query_term = non_mention_e_tags[0][1]
      else:
        # more than 1 non_mention tag, verifying which one is the reply and which one is the root
        for tag in non_mention_e_tags:
          if "root" in tag or "reply" in tag:
            print('using marked "e" tags')
            if "reply" in tag:
              query_term = tag[1]
          else:
            print('using positional "e" tags')
            query_term = non_mention_e_tags[1][1]
      if non_mention_e_tags == []:
        print("new note")
        query_term = event_msg.event.json[2]["id"]

      message_pool_relay_manager_individual_event = query_nostr_relays(since=last_time_checked, type_of_query="individual_event", query_term=query_term)
      individual_event_message = message_pool_relay_manager_individual_event.get_event()

      # extracting media
      note_media_urls = []
      image_filetypes = []
      media_list = []
      with open('image_filetypes.txt', 'r') as f:
        for line in f:
          image_filetypes.append(line.strip())
      note_content = individual_event_message.event.json[2]["content"]
      if any(filetype in note_content for filetype in image_filetypes):
        print('has image')
        has_image_on_content = True
        while has_image_on_content == True:
            image_url, filename = extract_image_url_from_content(note_content, image_filetypes)
            note_media_urls.append({"url":image_url,'filename':filename})
            # content with image_url replaced to check again
            note_content = note_content.replace(image_url,"")
            # print(extract_image_url_from_content(content))
            if not any(filetype in note_content for filetype in image_filetypes):
                has_image_on_content = False
                print('no more media ')
            else:
                print('still has media on content')
        print(note_media_urls)
    
        # first using tweepy to upload media to twitter
        auth = tweepy.OAuth1UserHandler(
          consumer_key,
          consumer_secret,
          access_token,
          access_token_secret
        )

        for index, media in enumerate(note_media_urls):
          downloaded_media = requests.get(media["url"])
          if media["url"][media["url"].rfind(".")+1:] == "mov":
            print("found .mov file. Downloading and converting to mp4")
            with open(str(index)+"."+media["filename"][media["filename"].rfind(".")+1:],'wb') as temp_media_file:
                temp_media_file.write(downloaded_media.content)
            input_video = ffmpeg.input(str(index)+".mov")
            ffmpeg.output(input_video, str(index)+".mp4").global_args('-y').run(quiet=True)
            media["filename"] = str(index)+".mp4"

          if media["url"][media["url"].rfind(".")+1:] != "mov":
            with open(str(index)+"."+media["filename"][media["filename"].rfind(".")+1:],'wb') as temp_media_file:
                temp_media_file.write(downloaded_media.content)
            
          # try:
          api = tweepy.API(auth)
          print(str(index)+"."+media["filename"][media["filename"].rfind(".")+1:])
          media = api.media_upload(filename=str(index)+"."+media["filename"][media["filename"].rfind(".")+1:])
          media_list.append(media.media_id_string)
          print('media file ' + note_media_urls[index]["url"] + " uploaded successfully. media_id_string = "+media.media_id_string)
          # except:
            # print('error uploading media '+ note_media_urls[index]["url"] + " - skipping this media file")
      
      nostr_display_name = query_user_display_name(individual_event_message.event.json[2]['pubkey'])[:20]
      from_section_for_tweet_message = "from: "+nostr_display_name+" "+PublicKey.hex_to_bech32(individual_event_message.event.json[2]['pubkey'],"Encoding.BECH32")
      link_to_note_for_tweet_message = "view on Nostr: https://snort.social/e/"+PublicKey.hex_to_bech32(individual_event_message.event.json[2]["id"],"Encoding.BECH32")

      # first trying with media_list, if errors, tweets without image
      try: 
        if len(note_content) > 125:
          note_content_first_tweet_on_thread = note_content[:125]+note_content[125:125+note_content[125:].find(" ")]
          tweet_id = tweet_with_apiv2(from_section_for_tweet_message+"\n"+link_to_note_for_tweet_message+"\n\n"+note_content_first_tweet_on_thread+" /", media_list)
          turn_long_note_into_twitter_thread_and_post(note_content, tweet_id)
        else: 
          tweet_id = tweet_with_apiv2(from_section_for_tweet_message+"\n"+link_to_note_for_tweet_message+"\n\n"+note_content, media_list)
          print(f"tweet id is {tweet_id}")
      except: 
        print("error sending tweet with media")
        if len(note_content) > 125:
          note_content_first_tweet_on_thread = note_content[:125]+note_content[125:125+note_content[125:].find(" ")]
          tweet_id = tweet_with_apiv2(from_section_for_tweet_message+"\n"+link_to_note_for_tweet_message+"\n(video accessible on Nostr⬆️)\n\n"+note_content_first_tweet_on_thread+" /", media_list = [])
          turn_long_note_into_twitter_thread_and_post(note_content, tweet_id)
        else: 
          tweet_id = tweet_with_apiv2(from_section_for_tweet_message+"\n"+link_to_note_for_tweet_message+"\n(video accessible on Nostr⬆️)\n\n"+note_content, media_list = [])
          print(f"tweet id is {tweet_id}")

      note_response_content = "note relayed to twitter.\nview here: https://www.twitter.com/seenOnNostr/status/"+tweet_id+"\n."
      post_note(private_key=private_key, content=note_response_content, tags=[["e", event_msg.event.json[2]["id"]]])

  print("exited while message.pool.has_events")
    # print(f"{event_msg}\n")

  print("finished running seenOnNostr")

if __name__ == "__main__":
  #running main function once
  # seenOnNostr(start_time_for_first_run=1688849212)
  seenOnNostr(start_time_for_first_run=int(datetime.now().timestamp()))
  # seenOnNostr()

  scheduler = BlockingScheduler()
  scheduler.add_job(seenOnNostr, 'interval', seconds=90)
  print('\nstarting scheduler')
  scheduler.start()