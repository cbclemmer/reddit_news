from praw import Reddit
import openai
from typing import List
import datetime
from medium import Client

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
            "max_tokens": 150,
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
        return self.complete(prompt)

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

        for post in posts:
            post_url = f"https://www.reddit.com{post.permalink}"
            if hasattr(post, 'crosspost_parent_list'):
                original_post = json.loads(json.dumps(post.crosspost_parent_list[0]))
                body = original_post['selftext']
            else:
                original_post = post
                body = post.selftext

            post.comments.replace_more(limit=None)
            top_comments = sorted(post.comments.list(), key=lambda comment: comment.score, reverse=True)[:5]
            comments_text = '\n'.join([f"{comment.author}: {comment.body[:200]}" for comment in top_comments])
            summary = self.post_reader.read(body[:1000] + '\nEND_POST\nBEGIN_COMMENTS:\n' + comments_text)
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
        title = f"Reddit {subreddit.capitalize()} Daily Digest - {today}"

        content = f"<h2>Overall Summary</h2><p>{overall_summary}</p><h2>Curated List</h2>"

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