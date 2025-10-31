import os
import logging
import json
from pathlib import Path
from functools import lru_cache

import tiktoken
from dotenv import load_dotenv
from bot.utils.chat import (
    chat_completion_request,
    extract_response_text,
    extract_total_tokens,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_FILE = BASE_DIR / "logs/debug.log"
SUMMARY_FILE = BASE_DIR / "logs/summaries.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    datefmt='%H:%M:%S'
)

GPT_MODEL = os.getenv('GPT_MODEL')
GPT_ENCODING = os.getenv('GPT_ENCODING')

MODEL_CONTEXT_LIMITS = {
    "gpt-5-nano": 32000,
    "gpt-5": 400000,
    "gpt-4o": 128000,
    "gpt-5-mini": 400000
}
DEFAULT_CONTEXT_LIMIT = 50000


def _resolve_context_limit(model_name: str | None) -> int:
    if not model_name:
        return DEFAULT_CONTEXT_LIMIT
    model_key = model_name.lower()
    for prefix, limit in MODEL_CONTEXT_LIMITS.items():
        if model_key.startswith(prefix):
            return limit
    return DEFAULT_CONTEXT_LIMIT


CONTEXT_LIMIT = _resolve_context_limit(GPT_MODEL)


@lru_cache(maxsize=1)
def _get_encoding():
    if GPT_MODEL:
        try:
            return tiktoken.encoding_for_model(GPT_MODEL)
        except KeyError:
            logging.warning("Unknown model '%s' for tiktoken; falling back to GPT_ENCODING", GPT_MODEL)
    encoding_name = GPT_ENCODING or "cl100k_base"
    try:
        return tiktoken.get_encoding(encoding_name)
    except KeyError:
        logging.warning("Unknown encoding '%s'; falling back to cl100k_base", encoding_name)
        return tiktoken.get_encoding("cl100k_base")

class Conversation:
    def __init__(self, system_message="You are a helpful AI Assistant that wants to answer all questions truthfully."):
        encoding = _get_encoding()
        system_message_token_count = len(encoding.encode(system_message))
        self.messages = [
            {
                "type": "message",
                "role": "system",
                "content": system_message,
                "token_count": system_message_token_count,
            }
        ]
        logging.debug(self.get_messages())

    def add_system_message(self, content):
        encoding = _get_encoding()
        token_count = len(encoding.encode(content))
        self.messages.append(
            {"type": "message", "role": "system", "content": content, "token_count": token_count}
        )

    def add_user_message(self, content):
        encoding = _get_encoding()
        token_count = len(encoding.encode(content))
        self.messages.append(
            {"type": "message", "role": "user", "content": content, "token_count": token_count}
        )

    def add_assistant_response(self, response):
        encoding = _get_encoding()
        total_tokens = extract_total_tokens(response)

        for item in getattr(response, "output", []):
            item_type = getattr(item, "type", None)
            if item_type == "message":
                text_segments = []
                for content in getattr(item, "content", []):
                    if getattr(content, "type", None) == "output_text":
                        text_segments.append(content.text)
                assistant_text = "".join(text_segments).strip()
                if assistant_text:
                    token_count = len(encoding.encode(assistant_text))
                    self.messages.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": assistant_text,
                            "token_count": token_count,
                        }
                    )
            elif item_type == "function_call":
                self.messages.append(
                    {
                        "type": "function_call",
                        "role": "assistant",
                        "name": item.name,
                        "arguments": item.arguments,
                        "call_id": item.call_id,
                        "status": getattr(item, "status", None),
                        "token_count": 0,
                    }
                )

        if total_tokens and total_tokens > CONTEXT_LIMIT:
            self._summarize()

    def add_function_message(self, function_name, call_id, function_response):
        encoding = _get_encoding()
        if isinstance(function_response, str):
            payload = function_response
        else:
            payload = json.dumps(function_response)
        token_count = len(encoding.encode(payload))
        self.messages.append(
            {
                "type": "function_call_output",
                "name": function_name,
                "call_id": call_id,
                "content": payload,
                "token_count": token_count,
            }
        )

    def get_messages(self):
        serialized_messages = []
        for message in self.messages:
            message_type = message.get("type")
            if not message_type:
                logging.warning("Skipping message without type: %s", message)
                continue
            if message_type == "message":
                serialized_messages.append(
                    {
                        "type": "message",
                        "role": message["role"],
                        "content": message["content"],
                    }
                )
            elif message_type == "function_call":
                serialized_messages.append(
                    {
                        "type": "function_call",
                        "name": message["name"],
                        "arguments": message["arguments"],
                        "call_id": message["call_id"],
                    }
                )
            elif message_type == "function_call_output":
                serialized_messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": message["call_id"],
                        "output": message["content"],
                    }
                )
        return serialized_messages

    def _summarize(self):
        messages_to_be_summarized = []
        token_count_to_be_summarized = 0
        encoding = _get_encoding()

        for message in self.messages:
            if message["type"] != "message" or message["role"] == "system":
                continue

            token_count_to_be_summarized += message["token_count"]
            messages_to_be_summarized.append(message)

            if token_count_to_be_summarized > CONTEXT_LIMIT / 12:
                existing_summaries = ""
                for msg in self.messages:
                    if msg["type"] == "message" and msg["role"] == "system" and 'The story so far:' in msg['content']:
                        existing_summaries += msg['content'].split('The story so far:')[1] + "\n"

                text_to_summarize = existing_summaries
                for message in messages_to_be_summarized:
                    role = message["role"]
                    content = message["content"]
                    if role == 'assistant':
                        text_to_summarize += f"DungeonMaster: {content}\n"
                    elif role == 'user':
                        text_to_summarize += f"Player: {content}\n"

                summary_prompt = [
                    {
                        "type": "message",
                        "role": 'system',
                        "content": "You are a summarizer. Below you will find a series of interactions between a Dungeon Master and one or more players in a game of D&D. Please summarize the interactions. The summary you generate will be referenced by the Dungeon Master to remember important interactions and events that have occurred.",
                    },
                    {
                        "type": "message",
                        "role": 'user',
                        "content": f"Please summarize the following D&D session: {text_to_summarize}",
                    },
                ]

                summary_response = chat_completion_request(messages=summary_prompt, functions=[])
                print("summarizing")
                summary_text = extract_response_text(summary_response)

                for msg in self.messages:
                    if msg["type"] == "message" and msg["role"] == "system":
                        if 'The story so far:' in msg['content']:
                            msg['content'] = msg['content'].split('The story so far:')[0] + "\nThe story so far: " + summary_text
                        else:
                            msg['content'] += "\nThe story so far: " + summary_text
                        msg['token_count'] = len(encoding.encode(msg["content"]))
                        break

                self.messages = [msg for msg in self.messages if msg not in messages_to_be_summarized]

                with open(SUMMARY_FILE, "a") as file:
                    file.write(f"Messages summarized:\n{messages_to_be_summarized}\n")
                    file.write(f"Summary generated:\n{summary_text}\n")

                messages_to_be_summarized = []
                token_count_to_be_summarized = 0

                return
                

        
