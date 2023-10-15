
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
import os
from bot.models.conversation import Conversation

EMBEDDINGS_CHUNK_SIZE = os.getenv('EMBEDDINGS_CHUNK_SIZE')


def build_vectorstore():
    print("Building the vector database")
    # call main function in indexer.py

def check_and_build_vectorstore():
    if not os.path.exists("./dbs/documentation/faiss_index"):
        build_vectorstore()
    else:
        embeddings = OpenAIEmbeddings(chunk_size=EMBEDDINGS_CHUNK_SIZE)
        global VECTORSTORE
        VECTORSTORE=FAISS.load_local(folder_path="./dbs/documentation/faiss_index", embeddings=embeddings)

def initialize_conversation():
    conversation = Conversation("You are Matt Mercer (GPT), the greatest dungeon master of all time. You like to play Dungeons & Dragons. Help the user create a character using the rulebook provided to you. Make sure to enforce the rules - for example, if a level 1 Wizard tries to cast a level 9 spell, don't let them. Speak in the style and tone of Matt Mercer from Critical Role.")
    return conversation