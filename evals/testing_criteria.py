"""
Evaluation criteria for DungeonMasterBot tool-call regressions.

These criteria assume each eval item provides:
  - item.expected_tool: canonical tool name (string)
  - item.expected_params: canonical JSON string for key arguments
  - item.actual_tool: actual tool triggered by the model (string)
  - item.actual_params: canonical JSON string for actual arguments
  - item.conversation_turn_1: conversation up to (and including) the first assistant reply
  - item.conversation_turn_2: full conversation including tool output and follow-up
  - item.assistant_initial_message: assistant text prior to tool output
  - item.assistant_followup_message: assistant text after receiving tool output
  - item.character_brief: optional lore for bespoke character builds
  - item.mock_tool_response: synthetic function output injected for grading
"""

from __future__ import annotations

__all__ = ["testing_criteria"]

TOOL_NAME_MATCH: dict = {
    "type": "string_check",
    "name": "Correct tool was called",
    "operation": "eq",
    "reference": "{{ item.expected_tool }}",
    "input": "{{ item.actual_tool }}",
}

TOOL_ARGUMENT_SCORER: dict = {
    "type": "score_model",
    "name": "Tool arguments satisfy request",
    "model": "gpt-4o-mini",
    "range": [1, 3],
    "pass_threshold": 3,
    "input": [
        {
            "role": "system",
            "content": (
                "You grade whether the assistant's tool arguments fulfill the player's needs. "
                "Provide a score of 1 (fail), 2 (partial), or 3 (pass)."
            ),
        },
        {
            "role": "user",
            "content": (
                "Item id: {{ item.id }}\n"
                "Conversation (turn 1): {{ item.conversation_turn_1 }}\n"
                "Expected tool: {{ item.expected_tool }}\n"
                "Reference arguments (if provided): {{ item.expected_params }}\n"
                "Actual tool: {{ item.actual_tool }}\n"
                "Actual arguments: {{ item.actual_params }}\n"
                "Mock tool response provided to the assistant: {{ item.mock_tool_response }}\n"
                "Character brief: {{ item.character_brief }}\n\n"
                "Rubric:\n"
                "- For item 'create_character_thom_merrilin':\n"
                "  * Score 3 when the assistant uses create_and_save_character and the JSON payload covers "
                "the character-creation schema (name, class, race, level, background, alignment, ability scores, "
                "hit points, skills, equipment, languages, features, spells, notes) while aligning with the brief's "
                "gleeman persona.\n"
                "  * Score 2 when the right tool is used but parts of the schema are missing or the character drifts "
                "from the brief.\n"
                "  * Score 1 otherwise.\n"
                "- For all other items: score 3 when the assistant's arguments exactly satisfy the player's request and "
                "match the reference payload (allowing for JSON key reordering). Score 1 otherwise; use 2 only when the "
                "assistant is close but has minor omissions (e.g., missing a single optional field while still conveying "
                "the requested update).\n"
            ),
        },
    ],
}

ASSISTANT_BEHAVIOR_SCORER: dict = {
    "type": "score_model",
    "name": "Assistant response stays in character",
    "model": "gpt-4o-mini",
    "range": [1, 3],
    "pass_threshold": 3,
    "input": [
        {
            "role": "system",
            "content": (
                "You grade whether the assistant's reply maintains Matt Mercer's voice and sets the "
                "right expectations about the requested action. Award 3 when the tone matches Matt Mercer "
                "and the assistant either (a) signals they are checking or preparing to act without "
                "overstating success, or (b) accurately reflects tool results once available. Award 2 when "
                "the voice is mostly right but slips slightly or shows mild overconfidence. Award 1 only when "
                "the reply breaks character, contradicts the player's request, or confidently claims success "
                "before any evidence is available."
            ),
        },
        {
            "role": "user",
            "content": (
                "Conversation context (turn 1): {{ item.conversation_turn_1 }}\n"
                "Expected tool: {{ item.expected_tool }}\n"
                "Assistant initial message (before tool output): {{ item.assistant_initial_message }}\n"
                "Assistant follow-up message (after tool output): {{ item.assistant_followup_message }}\n"
                "Conversation context (turn 2): {{ item.conversation_turn_2 }}\n\n"
                "Does the reply stay in Matt Mercer's tone and handle the action with appropriate confidence?\n"
                "Remember: waiting to confirm until tool results arrive is acceptable."
            ),
        },
    ],
}

testing_criteria = [TOOL_NAME_MATCH, TOOL_ARGUMENT_SCORER, ASSISTANT_BEHAVIOR_SCORER]
