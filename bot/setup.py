

import os
import logging
from pathlib import Path
from typing import Optional

from openai import OpenAI
from bot.models.conversation import Conversation

VECTOR_STORE_ID_PATH = Path("./dbs/documentation/vector_store_id.txt")

client = OpenAI()


def build_vectorstore():
    ruleset_filepath = os.getenv('RULESET_FILEPATH')
    if not ruleset_filepath:
        raise ValueError("RULESET_FILEPATH environment variable is not set.")

    ruleset_path = Path(ruleset_filepath)
    if not ruleset_path.exists():
        raise FileNotFoundError(f"RULESET_FILEPATH does not exist at {ruleset_path}")

    print("Building the vector database")
    with ruleset_path.open("rb") as ruleset_file:
        uploaded_file = client.files.create(file=ruleset_file, purpose="assistants")

    vector_store = client.vector_stores.create(
        name="DungeonMasterBot Rulebook",
        file_ids=[uploaded_file.id],
    )

    VECTOR_STORE_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    VECTOR_STORE_ID_PATH.write_text(vector_store.id)

    return vector_store.id


def _load_existing_vector_store_id() -> Optional[str]:
    if not VECTOR_STORE_ID_PATH.exists():
        return None

    vector_store_id = VECTOR_STORE_ID_PATH.read_text().strip()
    if not vector_store_id:
        return None

    try:
        client.vector_stores.retrieve(vector_store_id)
        return vector_store_id
    except Exception as exc:  # noqa: BLE001 - bubbling up warning then rebuild
        logging.warning("Vector store %s invalid or unavailable: %s", vector_store_id, exc)
        return None

def check_and_build_vectorstore():
    existing_id = _load_existing_vector_store_id()
    if existing_id:
        return existing_id
    return build_vectorstore()

def initialize_bot():
    vector_store_id = check_and_build_vectorstore()
    conversation = Conversation("You are Matt Mercer (GPT), the greatest dungeon master of all time. You like to play Dungeons & Dragons. Help the user create a character using the rulebook provided to you. Make sure to enforce the rules - for example, if a level 1 Wizard tries to cast a level 9 spell, don't let them. Speak in the style and tone of Matt Mercer from Critical Role.")
    return conversation, vector_store_id
