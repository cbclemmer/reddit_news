import sys
import json
from praw import Reddit
from reddit_reader import RedditNews

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

def save_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(content)

command = 'chat'
subreddit = 'all'
if len(sys.argv) > 1:
    command = sys.argv[1]
    subreddit = sys.argv[2]
else:
    raise "Not enough arguments must be in form python main.py [Command] [Subreddit]\nwhere command is chat, news, research_news, or read_paper"

config = json.loads(open_file('../config.json'))

reddit_client = Reddit(
    client_id=config["reddit_id"],
    client_secret=config["reddit_secret"],
    user_agent=config["reddit_app"]
)

reader = RedditNews(config["openai_key"], config["medium_key"], reddit_client)

post_url = ''
if command == 'chat':
    reader.director_chat()
elif command == 'news':
    post_url, post_id = reader.create_news_article(subreddit)
elif command == 'research_news':
    post_url, post_id = reader.find_papers(subreddit)
elif command == 'read_paper':
    ret_val = reader.read_paper(subreddit)
    if ret_val != None:
        post_url = ret_val[0]
print('Post: ' + post_url)