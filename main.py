import sys
import json
from praw import Reddit
from reddit_reader import RedditReader

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

def save_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(content)

subreddit = 'all'
if len(sys.argv) > 1:
    subreddit = sys.argv[1]

config = json.loads(open_file('config.json'))

reddit = Reddit(
    client_id=config["reddit_id"],
    client_secret=config["reddit_secret"],
    user_agent=config["reddit_app"]
)

reader = RedditReader(reddit, config["openai_key"], config["medium_key"])
post_url, post_id = reader.post_to_medium(subreddit, limit=20)
print('Post: ' + post_url)
