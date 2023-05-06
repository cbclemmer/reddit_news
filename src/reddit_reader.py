import openai
from typing import List
import datetime
from medium import Client
from reddit import PostReader
from bots import Editor, Researcher

class RedditNews:
    def __init__(self, 
            api_key: str, 
            medium_token: str,
            reddit_client
        ):
        openai.api_key = api_key
        post_reader = PostReader(reddit_client)
        self.editor = Editor(post_reader)
        self.researcher = Researcher(post_reader)
        self.medium = Client(access_token=medium_token)
        user = self.medium.get_current_user()
        self.medium_user_id = user['id']
        self.completions = []

    def director_chat(self):
        self.director.loop()

    def create_news_article(self, subreddit: str, limit: int=10):
        prompts = self.editor.fetch_posts(subreddit, limit)
        posts = self.editor.complete_promts(prompts)

        self.editor.save_completions(f'{subreddit}_news')

        self.post_to_medium(posts, f'Reddit News: r/{subreddit}')

    def post_to_medium(self, summaries, title):
        today = datetime.date.today().strftime("%Y-%m-%d")
        content = f"\
        <h1>{title} - {today}</h1>\
        "

        for post_title, post_url, summary in summaries:
            content += f"<h3><a href='{post_url}'>{post_title}</a></h3><p>{summary}</p>"

        post = self.medium.create_post(
            user_id=self.medium_user_id,
            title=title,
            content=content,
            content_format='html',
            publish_status='public'
        )

        print(f'Tokens: {self.post_reader.total_tokens + self.summarizer.total_tokens}')

        return post['url'], post['id']
