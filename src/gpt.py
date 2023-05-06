import datetime
import json

import tiktoken
import openai
from util import open_file, save_file
from objects import Conversation


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
        self.system_prompt = open_file('prompts/' + system_prompt_file + '.prompt')
        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        self.system_prompt_tokens = len(self.encoding.encode(self.system_prompt))
        self.conversations = []
        self.reset_chat()
        self.total_tokens = 0

    def save_completions(self, file_name):
        text = ''
        for completion in self.conversations:
            text += json.dumps(completion) + '\n'
        today = datetime.date.today().strftime("%Y-%m-%d")
        save_file(f'completions/{file_name}_{today}.jsonl', text)

    def add_message(self, message: str, role: str):
        self.messages.append({
            "role": role,
            "content": message
        })

    def reset_chat(self):
        if len(self.messages) > 1:
            self.conversations.append(Conversation(self.system_prompt, self.messages))
        self.messages = [ ]
        self.add_message(self.system_prompt, "system")

    def get_message_tokens(self) -> int:
        message_tokens = 0
        for m in self.messages:
            message_tokens += len(self.encoding.encode(m["content"]))
        return message_tokens

    def send(self, message: str, max_tokens=100) -> str:
        message_tokens = self.get_message_tokens()
        message_tokens += len(self.encoding.encode(message))
        
        if message_tokens >= 4096 - 200:
            raise "Chat Error too many tokens"
        
        self.add_message(message, "user")
        
        defaultConfig = {
            "model": 'gpt-3.5-turbo',
            "max_tokens": 100,
            "messages": max_tokens,
            "temperature": 0.5
        }

        res = openai.ChatCompletion.create(**defaultConfig)
        msg = res.choices[0].message.content.strip()
        self.add_message(msg, "assistant")
        self.total_tokens += res.usage.total_tokens
        return msg