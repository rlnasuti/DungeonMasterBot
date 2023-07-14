import PyPDF2
import os
import logging
import openai
import json

from dotenv import load_dotenv
from tenacity import retry, wait_random_exponential, stop_after_attempt
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from functions import FUNCTIONS
from character import Character

load_dotenv()  # take environment variables from .env.

RULESET_FILEPATH = os.getenv('RULESET_FILEPATH')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GPT_MODEL = os.getenv('GPT_MODEL')
EMBEDDINGS_CHUNK_SIZE = os.getenv('EMBEDDINGS_CHUNK_SIZE')
VECTORSTORE = "built by function"

openai.api_key = OPENAI_API_KEY

logging.basicConfig(
    filename='debug.log',
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(message)s',
    datefmt='%H:%M:%S'
)

# Add a new logging level called CONVERSATION with a level of 25
logging.addLevelName(25, "CONVERSATION")

# Now you can use the new level in your loggers
logger = logging.getLogger()
logger.setLevel("CONVERSATION")

handler = logging.FileHandler('conversation.log')
handler.setLevel("CONVERSATION")

formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s', datefmt='%H:%M:%S')
handler.setFormatter(formatter)

logger.addHandler(handler)

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
    return json.dumps(new_character.__dict__)


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

def check_and_build_vectorstore():
    if not os.path.exists("./dbs/documentation/faiss_index"):
        build_vectorstore()
    else:
        embeddings = OpenAIEmbeddings(chunk_size=EMBEDDINGS_CHUNK_SIZE)
        global VECTORSTORE
        VECTORSTORE=FAISS.load_local(folder_path="./dbs/documentation/faiss_index", embeddings=embeddings)

def build_vectorstore():
    print("Building the vector database")
    # call main function in indexer.py


def main():
    # Build vectorstore if it doesn't already exist
    check_and_build_vectorstore()

    # Instantiate and initialize the messages class with the system message
    messages = []
    messages.append({"role": "system", "content": "You are Matt Mercer (GPT), the greatest dungeon master of all time. You like to play Dungeons & Dragons. Help the user create a character using the rulebook provided to you. Make sure to enforce the rules - for example, if a level 1 Wizard tries to cast a level 9 spell, don't let them. Speak in the style and tone of Matt Mercer from Critical Role."})

    while(True):
        user_input = input("Me: ")
        messages.append({"role": "user", "content": f"{user_input}"})
        
        chat_response = chat_completion_request(messages)
        logger.log(level=25, msg=f"user: {user_input}")

        assistant_message = chat_response["choices"][0]["message"]
        messages.append(assistant_message)

        if chat_response["choices"][0]["message"].get("content"):
            print(f"Matt Mercer (GPT): {assistant_message['content']}")
            logger.log(level=25, msg=f"Matt Mercer (GPT): {assistant_message['content']}")
        
        if chat_response["choices"][0]["message"].get("function_call"):
            function_name = chat_response["choices"][0]["message"]["function_call"]["name"]
            function_args = json.loads(chat_response["choices"][0]["message"]["function_call"]["arguments"])
            # Step 3, call the function
            if function_name == "consult_rulebook":
                function_response = consult_rulebook(
                    question=function_args.get("question"),
                )
            if function_name == "create_and_save_character":
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

            logger.log(level=25, msg="####FUNCTION CALLED####")
            logger.log(level=25, msg=f"function name: {function_name}")
            logger.log(level=25, msg=f"function parameters: {function_args}")
            logger.log(level=25, msg=f"function response: {function_response}\n")

            # Step 4, send model the info on the function call and function response
            messages.append({"role": "function", "name": function_name, "content": function_response})
            chat_response = chat_completion_request(
                messages, function_call="none"
            )
            logging.debug(chat_response)
            assistant_message = chat_response["choices"][0]["message"]
            messages.append(assistant_message)
            if chat_response["choices"][0]["message"].get("content"):
                print(f"Matt Mercer (GPT): {assistant_message['content']}")
                logger.log(level=25, msg=f"Matt Mercer (GPT): {assistant_message['content']}")

if __name__ == "__main__":
    main()
