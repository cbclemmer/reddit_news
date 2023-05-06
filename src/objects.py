from typing import List

class RedditPost:
    url: str
    title: str
    body: str
    object: any

    def __init__(self, url: str, title: str, body: str, object: any):
        self.url = url
        self.title = title
        self.body = body
        self.object = object

class Prompt:
    title: str
    text: str
    url: str

    def __init__(self, title: str, text: str, url: str):
        self.title = title
        self.text = text
        self.url = url

class Summary(Prompt):
    def __init__(self, title: str, text: str, url: str):
        super().__init__(title, text, url)

class Message:
    role: str
    content: str

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

class Conversation:
    messages: List[Message]

    def __init__(self, messages: List[Message]):
        self.messages = messages

    def to_object(self):
        messages = []
        for m in self.messages:
            messages.append({
                "role": m.role,
                "content": m.content
            })
        return messages