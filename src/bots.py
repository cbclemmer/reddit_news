from urllib.parse import urlparse
from typing import List
import requests
import re
import os
import io
from bs4 import BeautifulSoup

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

class ReaserchSummarizer(Bot):
    def __init__(self, pr: PostReader):
        super().__init__(pr, 'research_summarizer')

    def summarize_chunk_list(self, overall_summary = '', list = [], note = ''):
        if len(list) == 0:
            return ''
        self.reset_chat()
        print('Creating overall summary:')
        if len(note) > 0:
            self.add_message('Please keep this note in mind:\n' + note, 'user')
            self.add_message('Ok, I\' keep that in mind', 'assistant')
        if len(overall_summary) > 0:
            print(f'Overall summary is {len(self.encoding.encode(overall_summary))} tokens')
            self.add_message('What is the summary overall?', 'user')
            self.add_message(overall_summary, 'assistant')
        self.add_message('Ok, I\'m now going to give you the new notes', 'user')
        self.add_message('Ok, I\'m ready for the new notes', 'assistant')
        total_summary_tokens = 0
        for summary in list:
            current_summary_tokens = len(self.encoding.encode(summary))
            print(f'Summary is {current_summary_tokens} tokens')
            total_summary_tokens += current_summary_tokens
            self.add_message(summary, 'user')
            self.add_message('Ok, I\'m ready for the next note', 'assistant')
        print(f'All Summaries are {total_summary_tokens} tokens')
        return self.send('That is all the summaries, what is the new overall summary?', 700)

class Researcher(Bot):
    def __init__(self, pr: PostReader):
        super().__init__(pr, 'researcher')
        self.summarizer = ReaserchSummarizer(pr)
    
    def fetch_arxiv(self, subreddit, limit=10, max_tokens=10000) -> List[Summary]:
        def cleanup_link(link):
            # Remove trailing characters like parentheses, brackets, and periods
            link = re.sub(r'[\)\]\.]+$', '', link)
            return link

        papers_file = '../arxiv_papers.txt'
        read_papers = []
        if os.path.exists(papers_file):
            read_papers = open_file(papers_file).split('\n')
        ret_posts = [ ]

        print("Fetching posts...")
        posts = self.post_reader.get_posts(subreddit, 100)
        print("Posts fetched")
        arxiv_pattern = re.compile(r'(https?:\/\/arxiv\.org\/[^\s\)\]]+)')
        for post in posts:
            paper_urls = []
            url_domain = urlparse(post.url).netloc
            if url_domain == 'arxiv' or url_domain == 'www.arxiv':
                paper_urls = post.url
            for match in arxiv_pattern.finditer(post.body):
                paper_urls.append(cleanup_link(post.body[match.start():match.end()]))

            if len(paper_urls) > 0:
                print(post.url)
                print(f"Found {len(paper_urls)} papers")

            for url in paper_urls:
                print(url)
                id = url.split("/")[-1]
                if id in read_papers:
                    continue
                print('Found paper id: ' + id)
                summary = self.read_paper(id, max_tokens)
                if summary == None:
                    continue
                ret_posts.append(summary)
        return ret_posts

    def read_paper(self, id: str, max_tokens: int = 30000, chunk_size: int = 2500) -> Summary | None:
        abs_url = f'https://arxiv.org/abs/{id}'
        response = requests.get(abs_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        print(f'Name: {soup.title.string}')
        abstract_elem = soup.find('blockquote', {'class': 'abstract'})
        print(abstract_elem.text)
        should_read = input('Read paper?: ')
        if should_read.lower() != 'yes':
            return None

        print("Downloading pdf")
        pdf_url = f'https://arxiv.org/pdf/{id}.pdf'
        response = requests.get(pdf_url)
        if response.status_code != 200:
            print("Could not find pdf for paper")
            return None
        pdfReader = PyPDF2.PdfReader(io.BytesIO(response.content))
        print('What should I keep in mind while reading the paper? (leave blank if no notes)')
        notes = input('Notes: ')
        text = ''
        print(f"Paper has {len(pdfReader.pages)} pages")
        for page_num in range(0, len(pdfReader.pages)):
            page = pdfReader.pages[page_num].extract_text()
            text += ' ' + page
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)
        print(f"Paper has {len(tokens)} tokens")
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
        first = False
        processed_tokens = 0
        summary_list = []
        last_summary = ''
        overall_summary = ''
        while len(tokens) > 0:
            chunk = tokens[:chunk_size]
            tokens = tokens[chunk_size:]
            last_summary = self.read_chunk(overall_summary, chunk, first, notes)
            summary_list.append(last_summary)
            if len(summary_list) > 4:
                summary_list = summary_list[1:5]
            if len(summary_list) > 1:
                overall_summary = self.summarizer.summarize_chunk_list(overall_summary, summary_list)
            else:
                overall_summary = last_summary
            print(f'\n\n\nOverall Summary:{overall_summary}\n\n\n')
            print(f'\n\n\nCurrent Summary:{last_summary}\n\n\n')
            processed_tokens += chunk_size
            print(f"Processed {processed_tokens} of {total_tokens} tokens")
        self.reset_chat()
        with open('../arvix_papers.txt', 'a') as f:
            f.write(id + '\n')
        return Summary(soup.title.string, overall_summary, pdf_url)
    
    def read_chunk(self, current_summary, chunk, first, notes):
        text = self.encoding.decode(chunk)
        self.reset_chat()
        if notes != '':
            self.add_message(f'Keep in mind this note:\n{notes}', 'user')
            self.add_message('Ok, I\'ll keep that in mind', 'assistant')
        if first:
            first = False
        else:
            self.add_message("What is the summary so far?", "user")
            self.add_message(current_summary, "assistant")
            self.add_message("Are you ready for the next page?", "user")
            self.add_message("Yes, please provide the next page of text", "assistant")
        return self.send(text, 500)


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