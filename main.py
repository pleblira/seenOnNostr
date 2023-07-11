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

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

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

  # while relay_manager.message_pool.has_events():
  #   event_msg = relay_manager.message_pool.get_event()
  #   print("\n\n___________NEW_EVENT__________")
  #   print(f"event.json: {event_msg.event.json}")
  # quit()  

  return relay_manager.message_pool

def seenOnNostr(start_time_for_first_run = 0):
  print("\n*****\n"+datetime.now().isoformat()+": running seenOnNostr")

  with open('events.json', 'r') as f:
    events = json.load(f)
    # datetime_of_last_queried_event = int(datetime.fromisoformat(events[len(events)-1][3]['datetime_event_was_queried']).timestamp())

  with open('last_time_checked.json', 'r') as f:
    times_checked = json.load(f)
    last_time_checked = int(times_checked[0]['checked_time'])
    print(f'last time checked ISO is {times_checked[0]["checked_time_iso"]}')

  if start_time_for_first_run != 0:
    last_time_checked = start_time_for_first_run

  message_pool_relay_manager_hashtag = query_nostr_relays(since=last_time_checked, type_of_query="hashtag", query_term=HASHTAG)
  # message_pool_relay_manager_hashtag = query_nostr_relays(since=1688831890, type_of_query="hashtag", query_term=HASHTAG)
  # message_pool_relay_manager_hashtag = query_nostr_relays(since=last_time_checked, type_of_query="user_tag", query_term="273e5c07475e1edea1a60b762336fdd7a37a2b845f137d524a0460f9f0c44c4a")
  # message_pool_relay_manager_hashtag = query_nostr_relays(since=1688829988, type_of_query="individual_event", query_term="799f8ffe1e596454b39318b5475b435084f9f086d709f436f7f06ae8ec09a47e")
  
  print("queried nostr relays")
 
  while message_pool_relay_manager_hashtag.has_events():
    event_msg = message_pool_relay_manager_hashtag.get_event()
    print("\n\n___________NEW_EVENT__________")
    print(f"event.json: {event_msg.event.json}")
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
            append_json(event_msg = event_msg.event.json)
            has_hashtag = True
    if has_hashtag == True:
    # checking if it's a reply
      for tag in event_msg.event.json[2]["tags"]:
        if "e" in tag:
          print("note is a reply, trying to query note")
          message_pool_relay_manager_individual_event = query_nostr_relays(since=last_time_checked, type_of_query="individual_event", query_term=tag[1])
          individual_event_message = message_pool_relay_manager_individual_event.get_event()

          # extracting media
          note_media_urls = []
          image_filetypes = []
          media_list = []
          with open('image_filetypes.txt', 'r') as f:
            for line in f:
              image_filetypes.append(line.strip())
          content = individual_event_message.event.json[2]["content"]
          if any(filetype in content for filetype in image_filetypes):
            print('has image')
            has_image_on_content = True
            while has_image_on_content == True:
                image_url, filename = extract_image_url_from_content(content, image_filetypes)
                note_media_urls.append({"url":image_url,'filename':filename})
                # content with image_url replaced to check again
                content = content.replace(image_url,"")
                # print(extract_image_url_from_content(content))
                if not any(filetype in content for filetype in image_filetypes):
                    has_image_on_content = False
                    print('has image on content false')
                else:
                    print('still has image on content')
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
              with open(str(index)+"."+media["filename"][media["filename"].rfind(".")+1:],'wb') as temp_media_file:
                  temp_media_file.write(downloaded_media.content)

              try:
                api = tweepy.API(auth)
                media = api.media_upload(filename=str(index)+"."+media["filename"][media["filename"].rfind(".")+1:])
                media_list.append(media.media_id_string)
              except:
                print('error uploading media '+ note_media_urls[index]["url"] + " - skipping this media file")
          
          nostr_display_name = query_user_display_name(individual_event_message.event.json[2]['pubkey'])
          tweet_message = "from: "+nostr_display_name+" ("+PublicKey.hex_to_bech32(individual_event_message.event.json[2]['pubkey'],"Encoding.BECH32")+")\n\n"
          
          if len(content) > 120:
            content = content[:120]+content[120:120+content[120:].find(" ")]+"..."
          tweet_id = tweet_with_apiv2(tweet_message+content+"\n\nCheck it out on Nostr: https://snort.social/e/"+PublicKey.hex_to_bech32(individual_event_message.event.json[2]["id"],"Encoding.BECH32")+" ["+secrets.token_hex(1)+"]", media_list)
          print(f"tweet id is {tweet_id}")
          note_response_content = "Note posted to twitter.\nCheck it out here: https://www.twitter.com/seenOnNostr/status/"+tweet_id+"\n\n."

          post_note(private_key=private_key, content=note_response_content, tags=[["e", event_msg.event.json[2]["id"]]])

  print("exited has events")
    # print(f"{event_msg}\n")


  with open('events.json', 'r') as f:
    events = json.load(f)
    for event in events:z
    if datetime.fromisoformat(event[3]['datetime_event_was_queried']).timestamp() > last_time_checked:
        print("new event found on json")
        
  #       # post_note(private_key, "content todo", [["e",event[2]['id']]])
  #       print(f'event public key is {PublicKey.hex_to_bech32(event[2]["id"],"Encoding.BECH32")}')

  #       # checking if event is a reply
  #       # post to twitter
  #       if "e" in event[2]["tags"]:
  #         print("will tweet")
  #         query_nostr_relays(public_key.hex(), since=datetime_of_last_queried_event, type_of_query="specific_event", query_term=event[2]["id"])
  #       else:
  #         print("event is not a reply")
  
  # updating last time checked for new notes
  with open('last_time_checked.json', 'r+') as f:
    times_checked = json.load(f)
    times_checked.reverse()
    # times_checked = sorted(times_checked, key=lambda d: d['number_of_checks'], reverse=False)
    times_checked.append({"checked_time":datetime.now().timestamp(), "checked_time_iso": datetime.now().now().isoformat(), "number_of_checks":times_checked[len(times_checked)-1]['number_of_checks']+1})
    if len(times_checked) > 20:
      # times_checked[:len(times_checked)-5] = ""
      times_checked.pop(0)
    times_checked.reverse()
    f.seek(0)
    f.truncate(0)
    f.write(json.dumps(times_checked, indent=4))

  print("finished updating json")

if __name__ == "__main__":
  # with open('events.json','w') as f:
  #   f.write("[]")

  # how many seconds in the past to retrieve events for first run
  # since = int(datetime.now().timestamp()-2000)

  # query_nostr_relays(public_key.hex(), since=since, first_run=True, type_of_query="hashtag", query_term=HASHTAG)

  #adding sample event in case initial query brings no results
  # with open('events.json','r+') as f:
  #   events = json.load(f)
  #   if events == []:
  #     events.append(["EVENT","a98d1b50fd8411edbf29804a14673ee3",{"content": "sample event","created_at": int(datetime.now().timestamp()),"id":"b3fb0066aa7defc45cad1eee9c3b03d49012cf9001c4eb22b04e7010be52fb87","kind": 1,"pubkey":"b76e5023a8fffcc2c3b4bebeb7a2dd6d7676d9c2122753e364b6427ddd065bb7","sig":"fb7baec1aff77c8acde69f524b32da2c8c09cbf8be1ba90d314e964d59296c03eed07c0871c1b7525fff60ce7fee73ef9e80997716c7882ef180267fb73b61c7","tags": []},{"datetime_event_was_queried": datetime.fromtimestamp(datetime.now().timestamp()).isoformat()}])
  #   f.seek(0)
  #   f.write(json.dumps(events, indent=4))

  # with open('last_time_checked.json','r+') as f:
  #   f.write("[]")
  #   times_checked = []
  #   times_checked.append({"checked_time": datetime.now().timestamp(), "number_of_checks":0})
  #   f.seek(0)
  #   f.write(json.dumps(times_checked, indent=4))

  #running main function once
  # time.sleep(1)
  # seenOnNostr(start_time_for_first_run=1688849212)
  seenOnNostr()

  scheduler = BlockingScheduler()
  scheduler.add_job(seenOnNostr, 'interval', seconds=90)
  print('\nstarting scheduler')
  scheduler.start()