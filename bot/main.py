import os
import logging
import json

from dotenv import load_dotenv
from tenacity import retry, wait_random_exponential, stop_after_attempt
from openai import OpenAI

from bot.models.character import Character
from bot.utils.chat import (
    chat_completion_request,
    extract_function_calls,
    extract_response_text,
)
from bot.setup import initialize_bot

load_dotenv()  # take environment variables from .env.

GPT_MODEL = os.getenv('GPT_MODEL')
VECTOR_STORE_ID = None

logging.basicConfig(
    filename='../logs/debug.log',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    datefmt='%H:%M:%S'
)

client = OpenAI()

@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def consult_rulebook(question):
    if not VECTOR_STORE_ID:
        raise RuntimeError("Vector store has not been initialized.")
    response = client.responses.create(
        model=GPT_MODEL,
        input=[
            {"role": "system", "content": "You are a Dungeons & Dragons rule expert. Answer questions using the provided rulebook resources and quote rules when helpful."},
            {"role": "user", "content": question},
        ],
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": [VECTOR_STORE_ID]}},
        temperature=0,
    )
    return extract_response_text(response)

def create_and_save_character(
    name, 
    character_class, 
    race, 
    level, 
    background,
    alignment,
    experience_points,
    strength,
    dexterity,
    constitution,
    intelligence,
    wisdom,
    charisma, 
    proficiency_bonus, 
    skills, 
    saving_throws, 
    max_hit_points,
    hit_dice,
    death_saves,
    equipment, 
    spells,
    languages,
    features_and_traits,
    notes
):
    # Create a new character
    new_character = Character(
        name=name,
        character_class=character_class,
        race=race,
        level=level,
        background=background,
        alignment=alignment,
        experience_points=experience_points,
        strength=strength,
        dexterity=dexterity,
        constitution=constitution,
        intelligence=intelligence,
        wisdom=wisdom,
        charisma=charisma,
        proficiency_bonus=proficiency_bonus,
        skills=skills,
        saving_throws=saving_throws,
        max_hit_points=max_hit_points,
        hit_dice=hit_dice,
        death_saves=death_saves,
        equipment=equipment,
        spells=spells,
        languages=languages,
        features_and_traits=features_and_traits,
        notes=notes
    )
    
    # Save the character to a JSON file
    new_character.save(f"characters/{name}_character.json")
    
    # Return the new character
    return json.dumps(new_character.__dict__, indent=4)

def get_character_state(name):
    character = Character.load(name)

    return json.dumps(character.__dict__)

def load_game(name):
    filename = f"data/saved_games/{name}_game.json"
    with open(filename, 'r') as f:
        messages = json.load(f)
    
    return messages

def save_game(name, messages):
    filename = f"saved_games/{name}_game.json"
    with open(filename, 'w') as f:
        json.dump(messages, f)
    
    return f"Game saved in {filename}"

def update_character(
        name,
        additional_experience_points=None,
        additional_death_saves_successes=None,
        additional_death_saves_failures=None,
        delta_hit_points=None,
        additional_level_1_spell_slots_used=None
):
    character = Character.load(name)

    if additional_experience_points is not None:
        experience_points = character.experience_points
        character.experience_points = experience_points + additional_experience_points
    if additional_death_saves_successes is not None:
        death_saves_successes = character.death_saves["successes"]
        character.death_saves["successes"] = death_saves_successes + additional_death_saves_successes
    if additional_death_saves_failures is not None:
        death_saves_failures = character.death_saves["failures"]
        character.death_saves["failures"] = death_saves_failures + additional_death_saves_failures
    if delta_hit_points is not None:
        current_hit_points = character.current_hit_points
        character.current_hit_points = current_hit_points + delta_hit_points
    if additional_level_1_spell_slots_used is not None:
        spells_slots_level_1_used = character.spells_slots_level_1_used
        character.spells_slots_level_1_used = spells_slots_level_1_used + additional_level_1_spell_slots_used

    character.save(f"characters/{name}_character.json")
    return json.dumps(character.__dict__)

conversation, VECTOR_STORE_ID = initialize_bot()

def process_message(user_input):
    conversation.add_user_message(user_input)
    chat_response = chat_completion_request(conversation.get_messages())
    conversation.add_assistant_response(chat_response)
    logging.debug(conversation.get_messages())

    assistant_message = extract_response_text(chat_response)
    tool_calls = extract_function_calls(chat_response)

    while tool_calls:
        for call in tool_calls:
            function_name = call["name"]
            call_id = call["call_id"]
            arguments = call.get("arguments") or "{}"
            try:
                function_args = json.loads(arguments)
            except json.JSONDecodeError:
                function_args = {}

            # Get the response from the function and add it to the conversation context
            if function_name == "consult_rulebook":
                function_response = consult_rulebook(
                    question=function_args.get("question"),
                )
            elif function_name == "create_and_save_character":
                function_response = create_and_save_character(
                    name=function_args.get("name"),
                    character_class=function_args.get("character_class"),
                    race=function_args.get("race"),
                    level=function_args.get("level"),
                    background=function_args.get("background"),
                    alignment=function_args.get("alignment"),
                    experience_points=function_args.get("experience_points"),
                    strength=function_args.get("strength"),
                    dexterity=function_args.get("dexterity"),
                    constitution=function_args.get("constitution"),
                    wisdom=function_args.get("wisdom"),
                    intelligence=function_args.get("intelligence"),
                    charisma=function_args.get("charisma"),
                    proficiency_bonus=function_args.get("proficiency_bonus"),
                    skills=function_args.get("skills"),
                    saving_throws=function_args.get("saving_throws"),
                    max_hit_points=function_args.get("max_hit_points"),
                    hit_dice=function_args.get("hit_dice"),
                    death_saves=function_args.get("death_saves"),
                    equipment=function_args.get("equipment"),
                    spells=function_args.get("spells"),
                    languages=function_args.get("languages"),
                    features_and_traits=function_args.get("features_and_traits"),
                    notes=function_args.get("notes")
                )
            elif function_name == "update_character":
                function_response = update_character(
                    name=function_args.get("name"),
                    additional_experience_points=function_args.get("additional_experience_points"),
                    additional_death_saves_successes=function_args.get("additional_death_saves_successes"),
                    additional_death_saves_failures=function_args.get("additional_death_saves_failures"),
                    delta_hit_points=function_args.get("delta_hit_points"),
                    additional_level_1_spell_slots_used=function_args.get("additional_level_1_spell_slots_used"),
                )
            elif function_name == "load_game":
                name = function_args.get("name")
                conversation.messages = load_game(name)
                function_response = f"The game for {name} was stopped by the user after the prior save. Everything worked perfectly and now it has now been successfully reloaded. Respond with a summary of what hsa happened and the user will pick the game back up."
            elif function_name == "save_game":
                function_response = save_game(function_args.get("name"), conversation.messages)
            elif function_name == "get_character_state":
                function_response = get_character_state(function_args.get("name"))
            else:
                function_response = None

            if function_response is not None:
                conversation.add_function_message(
                    function_name=function_name,
                    call_id=call_id,
                    function_response=function_response,
                )

        chat_response = chat_completion_request(conversation.get_messages())
        conversation.add_assistant_response(chat_response)
        assistant_message = extract_response_text(chat_response)
        tool_calls = extract_function_calls(chat_response)

    if assistant_message:
        return f"Matt Mercer (GPT): {assistant_message}"

    return "Matt Mercer (GPT):"
