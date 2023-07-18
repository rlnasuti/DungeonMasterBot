import tiktoken
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename='debug.log',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    datefmt='%H:%M:%S'
)

GPT_MODEL = os.getenv('GPT_MODEL')

class Conversation:
    def __init__(self, system_message="You are a helpful AI Assistant that wants to answer all questions truthfully."):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        token_count = len(encoding.encode(f'"role": "system", "content": {system_message}'))
        self.messages = [{"role": 'system', "content": system_message, "token_count": token_count}]
        logging.debug(self.get_messages())

    def add_system_message(self, content):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        token_count = len(encoding.encode(f'"role": "system", "content": {content}'))
        self.messages.append({"role": 'system', "content": content, "token_count": token_count})
    
    def add_user_message(self, content):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        token_count = len(encoding.encode(f'"role": "user", "content": {content}'))
        self.messages.append({"role": 'user', "content": content, "token_count": token_count})

    def add_assistant_message(self, content):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        message_content = content.get("content") or f'Calling function {content.get("function_call").get("name")} with arguments: {content.get("function_call").get("arguments")}'
        token_count = len(encoding.encode(str(message_content)))
        self.messages.append({"role": 'assistant', "content": message_content, "token_count": token_count})
    
    def add_function_message(self, function_name, function_response):
        encoding = tiktoken.encoding_for_model(GPT_MODEL)
        token_count = len(encoding.encode(f'"role": "function", "name": {function_name}, "content": {function_response}'))
        self.messages.append({"role": "function", "name": function_name, "content": function_response, "token_count": token_count})

    def get_messages(self):
        return [{k: v for k, v in message.items() if k != "token_count"} for message in self.messages]
        # return [{"role": message["role"], "content": message["content"]} for message in self.messages]
