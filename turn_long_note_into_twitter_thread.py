import json
from tweet_with_apiv2 import *
import time

def turn_long_note_into_twitter_thread_and_post(note_content, tweet_id):
    print(note_content)

    note_content_first_tweet_on_thread = note_content[:125]+note_content[125:125+note_content[125:].find(" ")]
    print(note_content_first_tweet_on_thread)

    note_content = note_content.replace(note_content_first_tweet_on_thread,"").strip()
    print(note_content)

    thread_tweet_list= json.loads("[]")
    tweet_number = 1
    while len(note_content) > 262:
        cropping_and_respecting_words = note_content[:262]+note_content[262:262+note_content[262:].find(" ")]
        note_content = note_content.replace(cropping_and_respecting_words, "").strip()
        if len(note_content) > 262:
            cropping_and_respecting_words += " /"
        thread_tweet_list.append({"tweet_number":tweet_number, "tweet_message":cropping_and_respecting_words, "tweet_length":len(cropping_and_respecting_words)})
        tweet_number += 1
    if note_content != "":
        thread_tweet_list.append({"tweet_number":tweet_number, "tweet_message":note_content[:251]})

    # print(json.dumps(thread_tweet_list, indent=4))

    for tweet in thread_tweet_list:
        tweet_id = tweet_with_apiv2(tweet["tweet_message"], media_list=[], in_reply_to_tweet_id=tweet_id)
        time.sleep(2)

if __name__ == "__main__":
    string = "0testing "

    for number in range(1,80):
        string += str(number)+"testing "

    turn_long_note_into_twitter_thread_and_post(string, "1678730354470064130")
    # 1678730354470064130