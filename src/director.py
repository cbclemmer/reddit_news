from gpt import GptCompletion, GptChat
from util import save_file, open_file

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
        super().__init__('news_director')
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