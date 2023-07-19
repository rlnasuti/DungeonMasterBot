import tiktoken
import os
import logging
import json

from dotenv import load_dotenv
from functions import FUNCTIONS
from utils import chat_completion_request

load_dotenv()

logging.basicConfig(
    filename='debug.log',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    datefmt='%H:%M:%S'
)

GPT_MODEL = os.getenv('GPT_MODEL')
CONTEXT_LIMIT = 2000

class Conversation:
    def __init__(self, system_message="You are a helpful AI Assistant that wants to answer all questions truthfully."):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        system_message_token_count = len(encoding.encode(f'"role": "system", "content": {system_message}'))
        functions_token_count = len(encoding.encode(json.dumps(FUNCTIONS)))
        self.messages = [{"role": 'system', "content": system_message, "token_count": system_message_token_count}]
        self.token_count = system_message_token_count + functions_token_count
        logging.debug(self.get_messages())

    def add_system_message(self, content):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        token_count = len(encoding.encode(f'"role": "system", "content": {content}'))
        self.token_count += token_count
        self.messages.append({"role": 'system', "content": content, "token_count": token_count})
        if self.token_count > CONTEXT_LIMIT:
            self._summarize()
    
    def add_user_message(self, content):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        token_count = len(encoding.encode(f'"role": "user", "content": {content}'))
        self.token_count += token_count
        self.messages.append({"role": 'user', "content": content, "token_count": token_count})
        if self.token_count > CONTEXT_LIMIT:
            self._summarize()

    def add_assistant_message(self, content):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        message_content = content.get("content") or f'Calling function {content.get("function_call").get("name")} with arguments: {content.get("function_call").get("arguments")}'
        token_count = len(encoding.encode(str(message_content)))
        self.token_count += token_count
        self.messages.append({"role": 'assistant', "content": message_content, "token_count": token_count})
        if self.token_count > CONTEXT_LIMIT:
            self._summarize()
    
    def add_function_message(self, function_name, function_response):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        token_count = len(encoding.encode(f'"role": "function", "name": {function_name}, "content": {function_response}'))
        self.messages.append({"role": "function", "name": function_name, "content": function_response, "token_count": token_count})
        self.token_count += token_count
        if self.token_count > CONTEXT_LIMIT:
            self._summarize()

    def get_messages(self):
        return [{k: v for k, v in message.items() if k != "token_count"} for message in self.messages]
        
    def _summarize(self):
        messages_to_be_summarized = []
        token_count_to_be_summarized = 0
        encoding = tiktoken.encoding_for_model(GPT_MODEL)

        for message in self.messages:
            if message['role'] != 'system':
                # Include all fields except 'token_count'
                token_count_to_be_summarized += message['token_count']
                messages_to_be_summarized.append(message)
                
                if token_count_to_be_summarized > CONTEXT_LIMIT / 2:
                    text_to_summarize = ""
                    for message in messages_to_be_summarized:
                        role = message["role"]
                        content = message["content"]
                        if role == 'assistant':
                            text_to_summarize += f"DungeonMaster: {content}\n"
                        elif role == 'user':
                            text_to_summarize += f"Player: {content}\n"
                    
                    # Build the messages list for the request for summary
                    summary_prompt = []
                    summary_prompt.append({"role": 'system', "content": "You are a summarizer. Below you will find a series of interactions between a Dungeon Master and one or more players in a game of D&D. Please summarize the interactions. The summary you generate will be referenced by the Dungeon Master to remember important interactions and events that have occurred."})
                    summary_prompt.append({"role": 'user', "content": f"Please summarize the following D&D session: {text_to_summarize}"})

                    # Get the summary
                    summary = chat_completion_request(messages=summary_prompt)
                    print(summary)
                    summary = summary["choices"][0]["message"]["content"]
                    
                    # Append the summary to the first system message in the conversation
                    for msg in self.messages:
                        if msg['role'] == 'system':
                            if 'The story so far:' in msg['content']:
                                msg['content'] = msg['content'].split('The story so far:')[0] + "\nThe story so far: " + summary
                            else:
                                msg['content'] += "\nThe story so far: " + summary
                            self.token_count = self.token_count - msg['token_count']
                            msg['token_count'] = len(encoding.encode(f'{{"role": "system", "content": "{msg["content"]}"}}'))
                            self.token_count = self.token_count + msg['token_count']
                            break


                    # Remove the summarized messages from the conversation
                    self.messages = [msg for msg in self.messages if msg not in messages_to_be_summarized]

                    # Write out to a summaries.log file
                    with open("summaries.log", "a") as file:
                        file.write(f"Messages summarized:\n{messages_to_be_summarized}\n")
                        file.write(f"Summary generated:\n{summary}\n")

                    # Reset the lists
                    messages_to_be_summarized = []
                    token_count_to_be_summarized = 0

                    # Resize the token count
                    self.token_count = self.token_count - token_count_to_be_summarized

                    return


        
