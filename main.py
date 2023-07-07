import json
import ssl
import time
from python_nostr_package.nostr import RelayManager
from python_nostr_package.nostr import PublicKey, PrivateKey
# from python_nostr import RelayManager
# from python_nostr import PublicKey, PrivateKey
# from nostr.relay_manager import RelayManager
# from nostr.key import PublicKey
import datetime
# from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from post_note import *
from set_query_filters import *
import os
import time
from append_json import *
from store_stackjoin import *
from dotenv import load_dotenv, find_dotenv
from tweet_with_apiv2 import *

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

public_key = PublicKey.from_npub(os.environ.get("PUBLIC_KEY"))
private_key = PrivateKey.from_nsec(os.environ.get("PRIVATE_KEY"))

HASHTAG = "seenOnNostr"

def timer(func):
    def wrapper():
        before = time.time()
        func()
        print("check_json_for_new_notes_and_reply function took: ", time.time() - before, "seconds")    
    return wrapper

def query_nostr_relays(public_key, type_of_query, query_term, since=0, first_run=False):
  if type_of_query != "specific_event":
    event_id = ""
  request, filters, subscription_id = set_query_filters(public_key, type_of_query=type_of_query, query_term=query_term, since=since)

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
  time.sleep(1) # allow the messages to send

  while relay_manager.message_pool.has_events():
    # print(f"since is {since}")
    event_msg = relay_manager.message_pool.get_event()
    print("\n\n___________NEW_EVENT__________")
    # print(f"{event_msg}\n")
    # print(event_msg.event.content)
    # print(f"created_at: {event_msg.event.created_at}")
    # print(f"created at ISO: {datetime.datetime.fromtimestamp(event_msg.event.created_at)}")
    # print(f"event.tags: {event_msg.event.tags}")
    # print(f"event.kind: {event_msg.event.kind}")
    # print(event_msg.event.public_key)
    # print(event_msg.event.signature)
    # print(f"event.id: {event_msg.event.id}")
    # print(f"event.json: {event_msg.event.json}")
    # print(f"event.json[2]['id']: {event_msg.event.json[2]['id']}")
    for tag in event_msg.event.json[2]["tags"]:
      if "t" in tag:
        print("event tag found")
        for item in tag:
          if item == HASHTAG:
            print(f"{HASHTAG} hashtag found")
            append_json(event_msg = event_msg.event.json)
      else:
        print("other type of tag")
    if type_of_query == "specific_event":
        tweet_with_apiv2(event_msg.event.json[2]["content"]+"\n\nCheck it out on Nostr: https://snort.social/e/"+PublicKey.hex_to_bech32(event[2]["id"],"Encoding.BECH32"))

  relay_manager.close_connections()

  if first_run == True:
    with open('events.json', 'r+') as f:
      events = json.load(f)
      events.reverse()
      f.seek(0)
      f.write(json.dumps(events, indent=4))

# def close_connections(relay_manager):
#   relay_manager.close_connections()

@timer
def query_relays_check_json_for_new_notes_and_reply():
  print("running check_json_for_new_notes")

  with open('events.json', 'r') as f:
    events = json.load(f)
    datetime_of_last_queried_event = int(datetime.fromisoformat(events[len(events)-1][3]['datetime_event_was_queried']).timestamp())

  with open('last_time_checked.json', 'r') as f:
    times_checked = json.load(f)
    last_time_checked = times_checked[len(times_checked)-1]['checked_time']

  print(f"last queried event datetime {datetime_of_last_queried_event}")

  query_nostr_relays(public_key.hex(), since=last_time_checked, type_of_query="hashtag", query_term=HASHTAG)
 
  with open('events.json', 'r') as f:
    events = json.load(f)
    for event in events:
      if datetime.fromisoformat(event[3]['datetime_event_was_queried']).timestamp() > last_time_checked:
        print("new event found on json")
        
        # post_note(private_key, "content todo", [["e",event[2]['id']]])
        print(f'event public key is {PublicKey.hex_to_bech32(event[2]["id"],"Encoding.BECH32")}')

        # checking if event is a reply
        # post to twitter
        if "e" in event[2]["tags"]:
          print("will tweet")
          query_nostr_relays(public_key.hex(), since=datetime_of_last_queried_event, type_of_query="specific_event", query_term=event[2]["id"])
        else:
          print("event is not a reply")
  
  with open('last_time_checked.json', 'r+') as f:
    times_checked = json.load(f)
    times_checked.append({"checked_time":datetime.now().timestamp(), "number_of_checks":times_checked[len(times_checked)-1]['number_of_checks']+1})
    if len(times_checked) > 5:
      # times_checked[:len(times_checked)-5] = ""
      times_checked.pop(0)
    f.seek(0)
    f.truncate(0)
    f.write(json.dumps(times_checked, indent=4))

if __name__ == "__main__":
  with open('events.json','w') as f:
    f.write("[]")

  # how many seconds in the past to retrieve events for first run
  since = int(datetime.now().timestamp()-2000)

  query_nostr_relays(public_key.hex(), since=since, first_run=True, type_of_query="hashtag", query_term=HASHTAG)

  #adding sample event in case initial query brings no results
  with open('events.json','r+') as f:
    events = json.load(f)
    if events == []:
      events.append(["EVENT","a98d1b50fd8411edbf29804a14673ee3",{"content": "sample event","created_at": int(datetime.now().timestamp()),"id":"b3fb0066aa7defc45cad1eee9c3b03d49012cf9001c4eb22b04e7010be52fb87","kind": 1,"pubkey":"b76e5023a8fffcc2c3b4bebeb7a2dd6d7676d9c2122753e364b6427ddd065bb7","sig":"fb7baec1aff77c8acde69f524b32da2c8c09cbf8be1ba90d314e964d59296c03eed07c0871c1b7525fff60ce7fee73ef9e80997716c7882ef180267fb73b61c7","tags": []},{"datetime_event_was_queried": datetime.fromtimestamp(datetime.now().timestamp()).isoformat()}])
    f.seek(0)
    f.write(json.dumps(events, indent=4))

  with open('last_time_checked.json','w') as f:
    f.write("[]")
    times_checked = []
    times_checked.append({"checked_time": datetime.now().timestamp(), "number_of_checks":0})
    f.seek(0)
    f.write(json.dumps(times_checked, indent=4))

  #running check_json once
  time.sleep(1)
  query_relays_check_json_for_new_notes_and_reply()

  # scheduler = BackgroundScheduler()
  scheduler = BlockingScheduler()
  scheduler.add_job(query_relays_check_json_for_new_notes_and_reply, 'interval', seconds=10)
  print('\nstarting scheduler')
  scheduler.start()