from praw import Reddit
from typing import List
from objects import RedditPost
import json

# Gets a list of posts from a subreddit
class PostReader:
    def __init__(self, client: Reddit):
        self.client = client

    def get_posts(self, subreddit, limit) -> List[RedditPost]:
        ret_posts = []
        sub = self.client.subreddit(subreddit)

        posts = list(sub.hot(limit=limit))
        posts.sort(key=lambda post: post.score, reverse=True)
        for post in posts:
            post_url = f"https://www.reddit.com{post.permalink}"
            if hasattr(post, 'crosspost_parent_list'):
                original_post = json.loads(json.dumps(post.crosspost_parent_list[0]))
                body = original_post['selftext']
            else:
                original_post = post
                body = post.selftext
            ret_posts.append(RedditPost(post_url, post.title, body, post))
        return ret_posts