"""
End-to-end runner for DungeonMasterBot tool-call evals.

Workflow:
    1. Load eval scenarios from evals/data/tool_call_samples.jsonl.
    2. For each scenario, invoke the target model with tool definitions and capture the
       actual tool call plus assistant preamble.
    3. Package expected inputs and actual outputs into an inline JSONL data source.
    4. Create an OpenAI eval using the shared testing criteria and run it.
    5. Poll until the eval run finishes and print a concise summary.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from bot.utils.chat import extract_function_calls, extract_response_text
from bot.utils.functions import FUNCTIONS
from evals.results_helper import get_eval_run_score
from evals.testing_criteria import testing_criteria

load_dotenv()

DEFAULT_MODEL = os.getenv("GPT_MODEL") or "gpt-4o-mini"
DEFAULT_POLL_INTERVAL_SECONDS = 3


def _format_tools(functions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for function in functions:
        tool: Dict[str, Any] = {"type": "function"}
        for key in ("name", "description", "parameters", "strict"):
            if key in function:
                tool[key] = function[key]
        tools.append(tool)
    return tools


def _pick_expected_subset(actual: Any, expected: Any) -> Any:
    """
    Recursively extract from `actual` only the keys present in `expected`.

    This keeps the comparison focused on fields we care about without failing when
    optional keys show up in the model response.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        return {
            key: _pick_expected_subset(actual.get(key), value)
            for key, value in expected.items()
        }
    if isinstance(expected, list) and isinstance(actual, list):
        return actual
    return actual


def _normalize_tool_output(mock_output: Any) -> str:
    if mock_output is None:
        return ""
    if isinstance(mock_output, str):
        return mock_output
    try:
        return json.dumps(mock_output, sort_keys=True)
    except (TypeError, ValueError):
        return str(mock_output)


class ToolCallEvalItem(BaseModel):
    id: str
    description: str
    conversation: List[Dict[str, str]]
    expected_tool_name: str
    expected_arguments: Dict[str, Any] = Field(default_factory=dict)
    character_brief: str | None = None
    mock_tool_response: Any | None = None

    @property
    def expected_arguments_json(self) -> str:
        return json.dumps(self.expected_arguments, sort_keys=True)


class ToolCallEvalSample(BaseModel):
    actual_tool: str
    actual_params: str
    conversation_turn_1: List[Dict[str, Any]]
    conversation_turn_2: List[Dict[str, Any]]
    assistant_initial_message: str
    assistant_followup_message: str
    raw_tool_call_arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolCallEvalRecord(BaseModel):
    id: str
    description: str
    conversation_turn_1: List[Dict[str, Any]]
    conversation_turn_2: List[Dict[str, Any]]
    expected_tool: str
    actual_tool: str
    expected_params: str
    actual_params: str
    assistant_initial_message: str
    assistant_followup_message: str
    character_brief: str | None = None
    mock_tool_response: str | None = None


def load_eval_items(data_file: Path) -> List[ToolCallEvalItem]:
    items: List[ToolCallEvalItem] = []
    with data_file.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, 1):
            payload = line.strip()
            if not payload:
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {idx} of {data_file}: {exc}") from exc
            item_data = obj.get("item", obj)
            try:
                items.append(ToolCallEvalItem(**item_data))
            except ValidationError as exc:
                raise ValueError(f"Invalid eval item structure on line {idx}: {exc}") from exc
    if not items:
        raise ValueError(f"No eval items found in {data_file}")
    return items


@dataclass
class ScenarioResult:
    item: ToolCallEvalItem
    sample: ToolCallEvalSample


def gather_actual_outputs(
    client: OpenAI,
    items: Iterable[ToolCallEvalItem],
    model: str,
    tools: List[Dict[str, Any]],
) -> List[ScenarioResult]:
    results: List[ScenarioResult] = []
    for item in items:
        print(f"[generate] {item.id}: generating response with model '{model}'")
        response = client.responses.create(
            model=model,
            input=item.conversation,
            tools=tools,
            tool_choice="auto",
        )
        assistant_message = extract_response_text(response)
        function_calls = extract_function_calls(response)
        tool_call_name = ""
        raw_arguments: Dict[str, Any] = {}
        canonical_arguments_json = "{}"
        assistant_followup_message = assistant_message
        mock_output = _normalize_tool_output(item.mock_tool_response)
        conversation_turn_1: List[Dict[str, Any]] = [
            {"type": "message", "role": msg["role"], "content": msg["content"]}
            for msg in item.conversation
        ]
        if assistant_message:
            conversation_turn_1.append(
                {"type": "message", "role": "assistant", "content": assistant_message}
            )
        conversation_turn_2: List[Dict[str, Any]] = list(conversation_turn_1)

        if function_calls:
            first_call = function_calls[0]
            tool_call_name = first_call.get("name") or ""
            raw_args_str = first_call.get("arguments") or "{}"
            try:
                parsed_args = json.loads(raw_args_str)
            except json.JSONDecodeError:
                parsed_args = {}
            raw_arguments = parsed_args if isinstance(parsed_args, dict) else {}
            filtered_args = _pick_expected_subset(raw_arguments, item.expected_arguments)
            canonical_arguments_json = json.dumps(filtered_args, sort_keys=True)

            call_id = first_call.get("call_id") or f"{item.id}-call"
            if mock_output:
                followup_messages: List[Dict[str, Any]] = []
                for message in item.conversation:
                    followup_messages.append(
                        {
                            "type": "message",
                            "role": message["role"],
                            "content": message["content"],
                        }
                    )
                if assistant_message:
                    followup_messages.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": assistant_message,
                        }
                    )
                followup_messages.append(
                    {
                        "type": "function_call",
                        "name": tool_call_name,
                        "arguments": raw_args_str,
                        "call_id": call_id,
                    }
                    )
                followup_messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": mock_output,
                    }
                )
                followup_response = client.responses.create(
                    model=model,
                    input=followup_messages,
                    tools=tools,
                    tool_choice="auto",
                )
                assistant_followup_message = extract_response_text(followup_response)
                if assistant_followup_message:
                    followup_messages.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": assistant_followup_message,
                        }
                    )
                conversation_turn_2 = followup_messages
        else:
            canonical_arguments_json = "{}"

        results.append(
            ScenarioResult(
                item=item,
                sample=ToolCallEvalSample(
                    actual_tool=tool_call_name,
                    actual_params=canonical_arguments_json,
                    conversation_turn_1=conversation_turn_1,
                    conversation_turn_2=conversation_turn_2,
                    assistant_initial_message=assistant_message,
                    assistant_followup_message=assistant_followup_message,
                    raw_tool_call_arguments=raw_arguments,
                ),
            )
        )
    return results


def build_file_content(results: Iterable[ScenarioResult]) -> List[Dict[str, Any]]:
    jsonl_payload: List[Dict[str, Any]] = []
    for result in results:
        record = ToolCallEvalRecord(
            id=result.item.id,
            description=result.item.description,
            conversation_turn_1=result.sample.conversation_turn_1,
            conversation_turn_2=result.sample.conversation_turn_2,
            expected_tool=result.item.expected_tool_name,
            actual_tool=result.sample.actual_tool,
            expected_params=result.item.expected_arguments_json,
            actual_params=result.sample.actual_params,
            assistant_initial_message=result.sample.assistant_initial_message,
            assistant_followup_message=result.sample.assistant_followup_message,
            character_brief=result.item.character_brief,
            mock_tool_response=_normalize_tool_output(result.item.mock_tool_response),
        )
        jsonl_payload.append({"item": record.model_dump()})
    return jsonl_payload


def _wait_for_run_completion(
    client: OpenAI,
    eval_id: str,
    run_id: str,
    poll_interval_seconds: int,
    timeout_seconds: int = 600,
) -> Any:
    terminal_states = {"completed", "failed", "canceled"}
    start_time = time.time()
    while True:
        eval_run = client.evals.runs.retrieve(run_id, eval_id=eval_id)
        status = getattr(eval_run, "status", None)
        print(f"[poll] Eval run status: {status}")
        if status in terminal_states:
            return eval_run
        if time.time() - start_time > timeout_seconds:
            raise TimeoutError(f"Eval run {run_id} exceeded timeout of {timeout_seconds} seconds")
        time.sleep(poll_interval_seconds)


def run_tool_call_eval(
    data_file: Path,
    model: str,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
) -> Tuple[str, str]:
    items = load_eval_items(data_file)
    client = OpenAI()
    tools = _format_tools(FUNCTIONS)

    print(f"Loaded {len(items)} eval scenarios from {data_file}")
    results = gather_actual_outputs(client, items, model=model, tools=tools)

    file_content = build_file_content(results)

    run_uuid = str(uuid.uuid4())
    eval_name = f"DungeonMasterBot-tool-evals-{run_uuid}"

    eval_obj = client.evals.create(
        name=eval_name,
        data_source_config={
            "type": "custom",
            "item_schema": ToolCallEvalRecord.model_json_schema(),
        },
        testing_criteria=testing_criteria,
    )

    run_name = f"{eval_name}-run"
    run = client.evals.runs.create(
        eval_id=eval_obj.id,
        name=run_name,
        data_source={
            "type": "jsonl",
            "source": {
                "type": "file_content",
                "content": file_content,
            },
        },
    )
    print(f"Started eval run {run.id} for eval {eval_obj.id}")

    completed_run = _wait_for_run_completion(
        client,
        eval_id=eval_obj.id,
        run_id=run.id,
        poll_interval_seconds=poll_interval_seconds,
    )

    status = getattr(completed_run, "status", None)
    print(f"Eval run finished with status: {status}")
    passed, total = get_eval_run_score(run.id, eval_obj.id)
    if passed is not None and total is not None:
        print(f"Eval score: {passed}/{total} items passed")
    else:
        print("Eval score: unavailable (result counts missing)")

    return eval_obj.id, run.id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run tool-call evals against DungeonMasterBot.")
    parser.add_argument(
        "--data-file",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "tool_call_samples.jsonl",
        help="Path to the JSONL file containing eval scenarios.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Target model to evaluate. Defaults to GPT_MODEL env var or gpt-4o-mini.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds between polling the eval run status.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    eval_id, run_id = run_tool_call_eval(
        data_file=args.data_file,
        model=args.model,
        poll_interval_seconds=args.poll_interval,
    )
    print(f"Eval ID: {eval_id}")
    print(f"Run ID: {run_id}")
