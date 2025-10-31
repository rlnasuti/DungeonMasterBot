import json
import logging
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt

from bot.utils.functions import FUNCTIONS

load_dotenv()  # take environment variables from .env

logging.basicConfig(
    filename='logs/debug.log',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    datefmt='%H:%M:%S'
)

GPT_MODEL = os.getenv('GPT_MODEL')

client = OpenAI()


def _format_tools(functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for function in functions:
        tool: Dict[str, Any] = {"type": "function"}
        for key in ("name", "description", "parameters", "strict"):
            if key in function:
                tool[key] = function[key]
        tools.append(tool)
    return tools


def extract_response_text(response) -> str:
    text_fragments: List[str] = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", None) == "message":
            for content in getattr(item, "content", []):
                if getattr(content, "type", None) == "output_text":
                    text_fragments.append(content.text)
    return "".join(text_fragments).strip()


def extract_function_calls(response) -> List[Dict[str, str]]:
    calls: List[Dict[str, str]] = []
    for item in getattr(response, "output", []):
        if getattr(item, "type", None) == "function_call":
            calls.append(
                {
                    "call_id": item.call_id,
                    "name": item.name,
                    "arguments": item.arguments,
                    "status": getattr(item, "status", None),
                }
            )
    return calls


def extract_total_tokens(response) -> int | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return getattr(usage, "total_tokens", None)


@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(
    messages,
    functions: List[Dict[str, Any]] = FUNCTIONS,
    model: str | None = GPT_MODEL,
    tool_choice: str = "auto",
):
    logging.debug(json.dumps(messages))
    try:
        kwargs: Dict[str, Any] = {"model": model, "input": messages}
        tool_definitions = _format_tools(functions) if functions else []
        if tool_definitions:
            kwargs["tools"] = tool_definitions
            kwargs["tool_choice"] = tool_choice
        response = client.responses.create(**kwargs)
        logging.debug(response.model_dump())
        return response
    except Exception as e:  # noqa: BLE001 - exit to surface configuration error quickly
        print("Unable to generate response via OpenAI Responses API")
        print(f"Exception: {e}")
        raise
