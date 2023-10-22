import PyPDF2
import os
import openai
import json
import random

from dotenv import load_dotenv
from tenacity import retry, wait_random_exponential, stop_after_attempt
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from bot.utils.functions import FUNCTIONS
from bot.models.character import Character
from bot.models.conversation import Conversation
from bot.utils.chat import chat_completion_request, chat_completion_stream
from bot.setup import initialize_conversation

load_dotenv()  # take environment variables from .env.

RULESET_FILEPATH = os.getenv('RULESET_FILEPATH')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GPT_MODEL = os.getenv('GPT_MODEL')
EMBEDDINGS_CHUNK_SIZE = os.getenv('EMBEDDINGS_CHUNK_SIZE')
VECTORSTORE = "built by function"

openai.api_key = OPENAI_API_KEY

@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(3))
def consult_rulebook(question):
    llm = ChatOpenAI(model_name=GPT_MODEL, temperature=0)
    qa_chain = RetrievalQA.from_chain_type(llm,retriever=VECTORSTORE.as_retriever())
    answer = qa_chain({"query": question})
    return(answer['result'])

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

def roll_dice(num_dice: int, dice_sides: int):
    return [random.randint(1, dice_sides) for _ in range(num_dice)]
