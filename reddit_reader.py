from praw import Reddit
import openai
from typing import List
import datetime
from medium import Client
import json
import tiktoken

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
    def __init__(self):
        super().__init__(open_file('prompts/read_post.prompt'))

    def read(self, post: str):
        return self.complete(post)

class Summarizer(GptCompletion):
    def __init__(self):
        super().__init__(open_file('prompts/summarizer.prompt'))

    def summarize(self, summaries: List[str]):
        response_tokens = 300
        list = ''
        for s in summaries:
            if len(self.encoding.encode(s)) + len(self.encoding.encode(list))  + self.system_prompt_tokens + response_tokens + 200 >= 4096:
                break
            list += f'\n\nPost:\n{s}'
        return self.complete(list, response_tokens)

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

class RedditReader:
    def __init__(self, reddit_client: Reddit, api_key: str, medium_token: str):
        openai.api_key = api_key
        self.reddit = reddit_client
        self.post_reader = PostReader()
        self.summarizer = Summarizer()
        self.director = Director()
        self.medium = Client(access_token=medium_token)
        user = self.medium.get_current_user()
        self.medium_user_id = user['id']
        self.completions = []

    def director_chat(self):
        self.director.loop()

    def read_posts(self, subreddit: str, limit: int = 10):
        print(f'Getting posts from r/{subreddit}')
        sub = self.reddit.subreddit(subreddit)
        summaries = []

        posts = list(sub.hot(limit=limit))
        posts.sort(key=lambda post: post.score, reverse=True)

        max_length = 4000
        for post in posts:
            post_url = f"https://www.reddit.com{post.permalink}"
            if hasattr(post, 'crosspost_parent_list'):
                original_post = json.loads(json.dumps(post.crosspost_parent_list[0]))
                body = original_post['selftext']
            else:
                original_post = post
                body = post.selftext

            post.comments.replace_more(limit=None)
            body_length = len(body[:max_length//2])
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
            post_reader_prompt = body[:characters_left] + '\nEND_POST\nBEGIN_COMMENTS:\n' + comments_text
            summary = self.post_reader.read(post_reader_prompt)
            self.completions.append({
                "system": self.post_reader.system_prompt,
                "prompt": post_reader_prompt,
                "completion": summary
            })
            summaries.append((post.title, post.score, post_url, summary))
            print(post_url)
            print('\nPost:')
            print(summary)
            print('\n\n')

        summary_texts = [summary for _, _, _, summary in summaries]
        overall_summary = self.summarizer.summarize(summary_texts)
        self.completions.append({
            "system": self.summarizer.system_prompt,
            "prompt": "\n\n".join(summary_texts),
            "completion": overall_summary
        })
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
