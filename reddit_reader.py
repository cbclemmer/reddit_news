from praw import Reddit
import openai
from typing import List
import datetime
from medium import Client
import json
import tiktoken
import re
import requests
from urllib.parse import urlparse
import PyPDF2

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

def save_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(content)

class GptCompletion:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        self.system_prompt_tokens = len(self.encoding.encode(self.system_prompt))
        self.total_tokens = 0

    def complete(self, prompt: str, response_tokens: int = 100, config: dict = {}):
        prompt_tokens = len(self.encoding.encode(prompt))
        total_tokens = self.system_prompt_tokens + prompt_tokens + response_tokens
        if total_tokens >= 4096:
            raise "Chat completion error: too many tokens requested: " + total_tokens
        defaultConfig = {
            "model": 'gpt-3.5-turbo',
            "max_tokens": response_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.5
        }

        defaultConfig.update(config)
        res = openai.ChatCompletion.create(**defaultConfig)
        msg = res.choices[0].message.content.strip()
        self.total_tokens += res.usage.total_tokens
        return msg

class GptChat:
    def __init__(self, system_prompt_file: str) -> None:
        self.system_prompt = open_file('prompts/' + system_prompt_file)
        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        self.system_prompt_tokens = len(self.encoding.encode(self.system_prompt))
        self.messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]
        self.total_tokens = 0

    def get_message_tokens(self):
        message_tokens = 0
        for m in self.messages:
            message_tokens += len(self.encoding.encode(m["content"]))
        return message_tokens

    def send(self, message: str):
        message_tokens = self.get_message_tokens()
        message_tokens += len(self.encoding.encode(message))
        
        if message_tokens >= 4096 - 200:
            raise "Chat Error too many tokens"
        
        self.messages.append({
            "role": "user",
            "content": message
        })
        
        defaultConfig = {
            "model": 'gpt-3.5-turbo',
            "max_tokens": 100,
            "messages": self.messages,
            "temperature": 0.5
        }

        res = openai.ChatCompletion.create(**defaultConfig)
        msg = res.choices[0].message.content.strip()
        self.messages.append({
            "role": "assistant",
            "content": msg
        })
        self.total_tokens += res.usage.total_tokens
        return msg

class PostReader(GptCompletion):
    def __init__(self, system_prompt):
        super().__init__(system_prompt)

    def read(self, post: str):
        return self.complete(post)

class Secretary(GptCompletion):
    def __init__(self):
        super().__init__(open_file('prompts/secretary.prompt'))
    
    def summarize(self, messages):
        response_tokens = 300
        list = ''
        for m in messages:
            list += f'\n\n{m["role"]}:\n{m["content"]}'
        return self.complete(list, response_tokens)

class Director(GptChat):
    def __init__(self):
        super().__init__('news_director.prompt')
        self.secretary = Secretary()
    
    def loop(self):
        res = self.send('Here is the your notes about the companies current state of affairs:\n' + open_file('director_notes.txt'))
        print(f'\nDirector:\n{res}')
        while True:
            user_input = input('\n\nUser:\n')
            if user_input == 'SAVE' or self.get_message_tokens() > 4000:
                print('Summarizing')
                notes = self.secretary.summarize(self.messages)
                save_file('director_notes.txt', notes)
                print('Notes saved')
                break
            res = self.send(user_input)
            print(f'\n\nDirector:\n{res}')

class RedditPostFetcher(GptCompletion):
    def __init__(self, id: str, secret: str, user_agent: str):
        super().__init__(open_file('prompts/research_assistant.prompt'))
        self.client = Reddit(
            client_id=id,
            client_secret=secret,
            user_agent=user_agent
        )

    def _get_posts(self, subreddit, limit):
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
            ret_posts.append({
                "url": post_url,
                "title": post.title,
                "body": body,
                "object": post
            })
        return ret_posts

    def fetch_arxiv(self, subreddit, limit=10):
        def cleanup_link(link):
            # Remove trailing characters like parentheses, brackets, and periods
            link = re.sub(r'[\)\]\.]+$', '', link)
            return link

        read_papers = open_file('arxiv_papers').split('\n')
        ret_posts = [ ]

        posts = self._get_posts(self, subreddit, 100)
        arxiv_pattern = re.compile(r'(https?:\/\/arxiv\.com\/[^\s\)\]]+)')
        for post in posts:
            paper_urls = []
            url_domain = urlparse(post.url).netloc
            if url_domain == 'arxiv' or url_domain == 'www.arxiv':
                paper_urls = post.url
            for match in arxiv_pattern.finditer(post.body):
                paper_urls.append(cleanup_link(match))
            for url in paper_urls:
                id = url.split("/")[-1].split(".")[0]
                if id in read_papers:
                    continue
                print('Found paper id: ' + id)
                pdf_url = f'https://arxiv.org/pdf/{id}.pdf'
                response = requests.get(pdf_url)
                if response.status_code != 200:
                    print("Could not find latex source for paper")
                    continue
                pdfReader = PyPDF2.PdfFileReader(response.content)
                for page_num in range(0, pdfReader.numPages):
                    page = pdfReader.getPage(page_num).extractText()
                    tokens = self.encoding.encode(page)

    def fetch_posts(self, subreddit, limit=10):
        print(f'Getting posts from r/{subreddit}')
        ret_posts = []
        posts = self._get_posts(subreddit, limit)

        max_length = 4000
        for post in posts:
            post.object.comments.replace_more(limit=None)
            body_length = len(post.body[:max_length//2])
            comments_text = ''
            characters_left = max_length
            post_comments = post.object.comments.list()
            if (len(post_comments) > 0):
                top_comments = sorted(post_comments, key=lambda comment: comment.score, reverse=True)
                selected_comments = top_comments[:5]
                comment_length = (max_length - body_length) // len(selected_comments)
                comments_text = '\n'.join([f"{comment.author}: {comment.body[:comment_length]}" for comment in selected_comments])
                comment_index = 5
                while body_length + len(comments_text) < max_length and comment_index < len(top_comments):
                    comment = top_comments[comment_index]
                    comments_text += f'\n{comment.author}: {comment.body[:comment_length]}'
                    comment_index += 1

            characters_left -= len(comments_text)
            post_reader_prompt = post.body[:characters_left] + '\nEND_POST\nBEGIN_COMMENTS:\n' + comments_text
            ret_posts.append({
                "title": post.object.title,
                "text": post_reader_prompt,
                "url": post.url
            })
        return ret_posts

class BotReader:
    def __init__(self, 
            api_key: str, 
            medium_token: str,
            reader_prompt: str
        ):
        openai.api_key = api_key
        self.post_reader = PostReader(reader_prompt)
        self.director = Director()
        self.medium = Client(access_token=medium_token)
        user = self.medium.get_current_user()
        self.medium_user_id = user['id']
        self.completions = []

    def director_chat(self):
        self.director.loop()

    def read_posts(self, posts):
        summaries = []
        for post in posts:
            summary = self.post_reader.read(post.post)
            self.completions.append({
                "system": self.post_reader.system_prompt,
                "prompt": post.text,
                "completion": summary
            })
            summaries.append((post.title, post.url, summary))
            print('\nPost:')
            print(post.url)
            print(summary)
            print('\n\n')

        return summaries

    def post_to_medium(self, posts, title):
        summaries = self.read_posts(posts)

        today = datetime.date.today().strftime("%Y-%m-%d")
        # title = f"r/{subreddit.capitalize()} Daily Digest - {today}"

        content = f"\
        <h1>{title}</h1>\
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

        text = ''
        for completion in self.completions:
            text += json.dumps(completion) + '\n'
        save_file(f'completions/{subreddit}_{today}.jsonl', text)

        return post['url'], post['id']
