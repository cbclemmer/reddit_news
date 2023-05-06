from urllib.parse import urlparse
from typing import List
import requests
import re

import PyPDF2

from gpt import GptChat
from reddit import PostReader
from util import open_file
from objects import Prompt, Conversation, Summary

class Bot(GptChat):
    post_reader: PostReader
    conversations: List[Conversation]

    def __init__(self, pr: PostReader, prompt_file: str):
        super().__init__(prompt_file)
        self.post_reader = pr
        self.completions = []

    def fetch_posts(self, subreddit: str, limit=10) -> List[Prompt]:
        return []

    def complete_promts(self, prompts: List[Prompt]) -> List[Summary]:
        summaries = []
        for prompt in prompts:
            print('\nPost:')
            print(prompt.url)

            self.reset_chat()
            summary = self.send(prompt.text)
            summaries.append(Summary(prompt.title, prompt.url, summary))
            
            print(summary)
            print('\n\n')

        self.reset_chat()
        return summaries

class Researcher(Bot):
    def __init__(self, pr: PostReader):
        super().__init__(pr, 'researcher')
    
    def fetch_arxiv(self, subreddit, limit=10, max_tokens=10000) -> List[Summary]:
        def cleanup_link(link):
            # Remove trailing characters like parentheses, brackets, and periods
            link = re.sub(r'[\)\]\.]+$', '', link)
            return link

        read_papers = open_file('arxiv_papers.txt').split('\n')
        ret_posts = [ ]

        posts = self.post_fetcher.get_posts(self, subreddit, 100)
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
                summary = self.read_paper(id, max_tokens)
                if summary == None:
                    continue
                ret_posts.append(summary)
        return ret_posts

    def read_paper(self, id: str, max_tokens: int = 20000, chunk_size: int = 2500) -> Summary | None:
        pdf_url = f'https://arxiv.org/pdf/{id}.pdf'
        response = requests.get(pdf_url)
        if response.status_code != 200:
            print("Could not find latex source for paper")
            return None
        pdfReader = PyPDF2.PdfFileReader(response.content)
        title = pdfReader.getText('title')
        print(f'Name: {title}')
        should_read = input('Read paper?: ')
        if should_read is not 'YES':
            return None
        print('What should I keep in mind while reading the paper? (leave blank if no notes)')
        notes = input('Notes: ')
        text = ''
        for page_num in range(0, pdfReader.numPages):
            page = pdfReader.getPage(page_num).extractText()
            text += ' ' + page
        tokens = self.encoding.encode(page)
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
        summary = ''
        first = False
        while len(tokens) > 0:
            chunk = tokens[:chunk_size]
            tokens = tokens[chunk_size:]
            text = self.encoding.decode(chunk)
            self.reset_chat()
            if notes is not '':
                self.add_message(f'Keep in mind that {notes}', 'user')
                self.add_message('Ok, I\'ll keep that in mind', 'assistant')
            if first:
                first = False
            else:
                self.add_message("What is the summary so far?", "user")
                self.add_message(summary, "assistant")
                self.add_message("Are you ready for the next page?", "user")
                self.add_message("Yes, please provide the next page of text", "assistant")
            summary = self.send(text, 500)
            print(f'\n\n\n{summary}\n\n\n')
        self.reset_chat()
        with open('arvix_papers.txt', 'a') as f:
            f.write(id)
        return Summary(title, summary, pdf_url)

class Editor(Bot):
    def __init__(self, post_reader: PostReader):
        super().__init__(post_reader, 'read_post')

    def fetch_posts(self, subreddit: str, limit=10) -> List[Prompt]:
        print(f'Getting posts from r/{subreddit}')
        ret_posts = []
        posts = self.post_reader.get_posts(subreddit, limit)

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
            ret_posts.append(Prompt(post.title, post_reader_prompt, post.url))
        return ret_posts