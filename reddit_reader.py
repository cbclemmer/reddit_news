from praw import Reddit
import openai
from typing import List
import datetime
from medium import Client
import json

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

class GptCompletion:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        openai.api_key = self.api_key
        self.total_tokens = 0

    def complete(self, prompt: str, config: dict = {}):
        defaultConfig = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": 175,
            "n": 1,
            "stop": None,
            "temperature": 0.8
        }

        defaultConfig.update(config)
        res = openai.Completion.create(**defaultConfig)
        msg = res.choices[0].text.strip()
        self.total_tokens += res.usage.total_tokens
        return msg


class PostReader(GptCompletion):
    def __init__(self, api_key: str):
        super().__init__(api_key, 'text-davinci-003')
        self.post_read_prompt = open_file('prompts/read_post.prompt')

    def read(self, post: str):
        prompt = self.post_read_prompt.replace('<<INPUT>>', post)
        print('PROMPT:\n' + prompt + '\n\n')
        return self.complete(prompt)

class Summarizer(GptCompletion):
    def __init__(self, api_key: str):
        super().__init__(api_key, 'text-davinci-003')
        self.summarize_prompt = open_file('prompts/summarizer.prompt')

    def summarize(self, summaries: List[str]):
        input_text = "\n\n".join(summaries)
        prompt = self.summarize_prompt.replace('<<INPUT>>', input_text)
        print('PROMPT:\n' + prompt + '\n\n')
        return self.complete(prompt, {
            "max_tokens": 500
        })

class RedditReader:
    def __init__(self, reddit_client: Reddit, api_key: str, medium_token: str):
        self.reddit = reddit_client
        self.post_reader = PostReader(api_key)
        self.summarizer = Summarizer(api_key)
        self.medium = Client(access_token=medium_token)

    def read_posts(self, subreddit: str, limit: int = 10):
        print(f'Getting posts from r/{subreddit}')
        sub = self.reddit.subreddit(subreddit)
        summaries = []

        posts = list(sub.hot(limit=limit))
        posts.sort(key=lambda post: post.score, reverse=True)

        max_length = 2000
        for post in posts:
            post_url = f"https://www.reddit.com{post.permalink}"
            if hasattr(post, 'crosspost_parent_list'):
                original_post = json.loads(json.dumps(post.crosspost_parent_list[0]))
                body = original_post['selftext']
            else:
                original_post = post
                body = post.selftext

            post.comments.replace_more(limit=None)
            body_length = len(body[:1000])
            comments_text = ''
            characters_left = max_length
            if (len(post.comments.list()) > 0):
                top_comments = sorted(post.comments.list(), key=lambda comment: comment.score, reverse=True)
                selected_comments = top_comments[:5]
                comment_length = (max_length - body_length) // len(selected_comments)
                comments_text = '\n'.join([f"{comment.author}: {comment.body[:comment_length]}" for comment in selected_comments])
                comment_index = 5
                while body_length + len(comments_text) < max_length and comment_index < len(top_comments):
                    comment = top_comments[comment_index]
                    comments_text += f'\n{comment.author}: {comment.body[:comment_length]}'
                    comment_index += 1

            characters_left -= len(comments_text)
            summary = self.post_reader.read(body[:characters_left] + '\nEND_POST\nBEGIN_COMMENTS:\n' + comments_text)
            summaries.append((post.title, post.score, post_url, summary))
            print(post_url)
            print('\nPost:')
            print(summary)
            print('\n\n')

        overall_summary = self.summarizer.summarize([summary for _, _, _, summary in summaries])
        print('Overall:')
        print(overall_summary)
        return overall_summary, summaries

    def post_to_medium(self, subreddit: str, limit: int = 10):
        overall_summary, summaries = self.read_posts(subreddit, limit)

        today = datetime.date.today().strftime("%Y-%m-%d")
        title = f"r/{subreddit.capitalize()} Daily Digest - {today}"

        content = f"\
        <h1>{title}</h1>\
        <p>{overall_summary}</p><h2>Posts</h2>"

        for post_title, upvotes, post_url, summary in summaries:
            content += f"<h3>^ {upvotes} - <a href='{post_url}'>{post_title}</a></h3><p>{summary}</p>"

        user = self.medium.get_current_user()
        user_id = user['id']

        post = self.medium.create_post(
            user_id=user_id,
            title=title,
            content=content,
            content_format='html',
            publish_status='public'
        )

        print(f'Tokens: {self.post_reader.total_tokens + self.summarizer.total_tokens}')

        return post['url'], post['id']
