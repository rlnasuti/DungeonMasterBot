import openai
import os

from dotenv import load_dotenv
from tenacity import retry, wait_random_exponential, stop_after_attempt
from functions import FUNCTIONS

load_dotenv()  # take environment variables from .env.

RULESET_FILEPATH = os.getenv('RULESET_FILEPATH')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GPT_MODEL = os.getenv('GPT_MODEL')

@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(messages, functions=FUNCTIONS, model=GPT_MODEL, function_call="auto"):
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=messages,
            functions=functions,
            function_call=function_call,
        )
        return response
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        exit()