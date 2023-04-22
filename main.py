import sys
import json
from praw import Reddit
from reddit_reader import BotReader, RedditPostFetcher

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

post_fetcher = RedditPostFetcher(
    config["reddit_id"],
    config["reddit_secret"],
    config["reddit_app"]
)

posts = post_fetcher.fetch()

reader = BotReader(posts, config["openai_key"], config["medium_key"])
if subreddit == 'CHAT':
    reader.director_chat()
else:
    post_url, post_id = reader.post_to_medium(subreddit, limit=20)
    print('Post: ' + post_url)
