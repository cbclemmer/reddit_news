import sys
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

reddit_client_id = open_file('keys/reddit_id.txt')
reddit_client_secret = open_file('keys/reddit_secret.txt')
reddit_user_agent = 'github_scraper'

medium_token=open_file('keys/medium.txt')
openai_key = open_file('keys/openai.txt')

reddit = Reddit(
    client_id=reddit_client_id,
    client_secret=reddit_client_secret,
    user_agent=reddit_user_agent
)

reader = RedditReader(reddit, openai_key, medium_token)
post_url, post_id = reader.post_to_medium(subreddit, limit=20)
print('Post: ' + post_url)
