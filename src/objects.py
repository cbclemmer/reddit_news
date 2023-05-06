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

class Completion:
    system: str
    prompt: str
    completion: str

    def __init__(self, system: str, prompt: str, completion: str):
        self.system = system
        self.prompt = prompt
        self.completion = completion