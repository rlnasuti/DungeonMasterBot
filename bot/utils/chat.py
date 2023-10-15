import openai
import os
import logging
import json

from dotenv import load_dotenv
from tenacity import retry, wait_random_exponential, stop_after_attempt
from bot.utils.functions import FUNCTIONS

load_dotenv()  # take environment variables from .env

logging.basicConfig(
    filename='logs/debug.log',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    datefmt='%H:%M:%S'
)

RULESET_FILEPATH = os.getenv('RULESET_FILEPATH')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GPT_MODEL = os.getenv('GPT_MODEL')

@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(messages, functions=FUNCTIONS, model=GPT_MODEL, function_call="auto"):
    logging.debug(json.dumps(messages))
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=messages,
            functions=functions,
            function_call=function_call,
        )
        logging.debug(response)
        return response
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        exit()

@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def chat_completion_stream(messages, functions=FUNCTIONS, model=GPT_MODEL, function_call="auto"):
    logging.debug(json.dumps(messages))
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=messages,
            functions=functions,
            function_call=function_call,
            stream = True
        )
        logging.debug(response)
        return response
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        exit()