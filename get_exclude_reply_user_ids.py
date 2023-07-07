def get_exclude_reply_user_ids(scraped_tweet):
    exclude_reply_user_ids = []
    if scraped_tweet["mentionedUsers"] != None:
        print("found mentioned users in scraped_tweet")
        for item in scraped_tweet['mentionedUsers']:
            # print(json_response['data']['author_id'])
            if item['id'] != scraped_tweet["user"]["id"]:
                exclude_reply_user_ids.append(str(item['id']))
    # if exclude_reply_user_ids == []:
    #     exclude_reply_user_ids = None
    # else:
    #     exclude_reply_user_ids = ",".join(exclude_reply_user_ids)
    return exclude_reply_user_ids