"""
Helper utilities for inspecting eval run results.
"""

from __future__ import annotations

from openai import OpenAI


def get_eval_run_score(run_id: str, eval_id: str) -> tuple[int | None, int | None]:
    """
    Retrieve an eval run's aggregate pass/total counts.

    Args:
        run_id: Identifier of the eval run.
        eval_id: Identifier of the parent evaluation.

    Returns:
        A tuple of (passed, total) if available, otherwise (None, None).
    """
    client = OpenAI()
    run = client.evals.runs.retrieve(run_id, eval_id=eval_id)
    result_counts = getattr(run, "result_counts", None)
    if result_counts is None:
        return None, None
    passed = getattr(result_counts, "passed", None)
    total = getattr(result_counts, "total", None)
    return passed, total

