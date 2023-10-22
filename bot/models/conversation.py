import tiktoken
import os
import logging
import json
from pathlib import Path

from bot.utils.functions import FUNCTIONS
from bot.utils.chat import chat_completion_request

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_FILE = BASE_DIR / "logs/debug.log"
SUMMARY_FILE = BASE_DIR / "logs/summaries.log"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
fh.setFormatter(formatter)
logger.addHandler(fh)

GPT_MODEL = os.getenv('GPT_MODEL')
CONTEXT_LIMITS = {
    'gpt-3.5-turbo-0613': 3500,
    'gpt-4-0613': 7500
}

class Conversation:
    def __init__(self, system_message="You are a helpful AI Assistant that wants to answer all questions truthfully."):
        self.encoding = tiktoken.encoding_for_model(GPT_MODEL)
        self.system_message_token_count = len(self.encoding.encode(f'"role": "system", "content": {system_message}'))
        self.functions_token_count = len(self.encoding.encode(json.dumps(FUNCTIONS)))
        self.messages = [{"role": 'system', "content": system_message, "token_count": self.system_message_token_count}]
        self.full_conversation_token_count = len(self.encoding.encode(json.dumps(self.messages))) + self.functions_token_count
        self._loginfo()

    def _loginfo(self):
        logger.debug(f"functions token count: {self.functions_token_count}")
        logger.debug(f"system message token count: {self.system_message_token_count}")
        logger.debug(f"conversation token count: {self.full_conversation_token_count}")
        logger.debug(self.get_messages())

    def add_system_message(self, content):
        token_count = len(self.encoding.encode(f'"role": "system", "content": {content}'))
        new_msg = {"role": 'system', "content": content, "token_count": token_count}
        if self.full_conversation_token_count + new_msg["token_count"] >= CONTEXT_LIMITS.get(GPT_MODEL, 3500):
            self._summarize()
        self.messages.append(new_msg)
        self.full_conversation_token_count = len(self.encoding.encode(json.dumps(self.messages))) + self.functions_token_count
        self._loginfo()
    
    def add_user_message(self, content):
        token_count = len(self.encoding.encode(f'"role": "user", "content": {content}'))
        new_msg = {"role": 'user', "content": content, "token_count": token_count}
        if self.full_conversation_token_count + new_msg["token_count"] >= CONTEXT_LIMITS.get(GPT_MODEL, 3500):
            self._summarize()
        self.messages.append(new_msg)
        self.full_conversation_token_count = len(self.encoding.encode(json.dumps(self.messages))) + self.functions_token_count
        self._loginfo()

    def add_assistant_message(self, content):
        token_count = len(self.encoding.encode(f'"role": "assistant", "content": {content}'))
        new_msg = {"role": 'assistant', "content": content, "token_count": token_count}
        if self.full_conversation_token_count + new_msg["token_count"] >= CONTEXT_LIMITS.get(GPT_MODEL, 3500):
            self._summarize()
        self.messages.append(new_msg)
        self.full_conversation_token_count = len(self.encoding.encode(json.dumps(self.messages))) + self.functions_token_count
        self._loginfo()
    
    def add_function_message(self, function_name, function_response):
        token_count = len(self.encoding.encode(f'"role": "function", "name": {function_name}, "content": {function_response}'))
        new_msg = {"role": 'function', "name": function_name, "content": function_response, "token_count": token_count}
        if self.full_conversation_token_count + new_msg["token_count"] >= CONTEXT_LIMITS.get(GPT_MODEL, 3500):
            self._summarize()
        self.messages.append(new_msg)
        self.full_conversation_token_count = len(self.encoding.encode(json.dumps(self.messages))) + self.functions_token_count
        self._loginfo()

    def get_messages(self):
        return [{k: v for k, v in message.items() if k != "token_count"} for message in self.messages]
        
    def _summarize(self):
        messages_to_be_summarized = []
        token_count_to_be_summarized = 0

        for message in self.messages:
            if message['role'] != 'system':
                # Include all fields except 'token_count'
                token_count_to_be_summarized += message['token_count']
                messages_to_be_summarized.append(message)
                
                if token_count_to_be_summarized > CONTEXT_LIMITS.get(GPT_MODEL, 3500) / 4:
                    existing_summaries = ""
                    for msg in self.messages:
                        if msg['role'] == 'system' and 'The story so far:' in msg['content']:
                            existing_summaries += msg['content'].split('The story so far:')[1] + "\n"

                    # Now, existing_summaries contain all previous summaries. Include this in the new text_to_summarize.
                    text_to_summarize = existing_summaries
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
                    print("summarizing")
                    summary = summary["choices"][0]["message"]["content"]
                    
                    # Append the summary to the first system message in the conversation
                    for msg in self.messages:
                        if msg['role'] == 'system':
                            if 'The story so far:' in msg['content']:
                                msg['content'] = msg['content'].split('The story so far:')[0] + "\nThe story so far: " + summary
                            else:
                                msg['content'] += "\nThe story so far: " + summary
                            msg['token_count'] = len(self.encoding.encode(f'{{"role": "system", "content": "{msg["content"]}"}}'))
                            break


                    # Remove the summarized messages from the conversation
                    self.messages = [msg for msg in self.messages if msg not in messages_to_be_summarized]

                    # Write out to a summaries.log file
                    with open(SUMMARY_FILE, "a") as file:
                        file.write(f"Messages summarized:\n{messages_to_be_summarized}\n")
                        file.write(f"Summary generated:\n{summary}\n")

                    # Reset the lists
                    messages_to_be_summarized = []
                    token_count_to_be_summarized = 0

                    return
                

        
