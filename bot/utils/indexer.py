from langchain.document_loaders import PyPDFDirectoryLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from dotenv import load_dotenv

import openai
import os
import ssl

load_dotenv()

RULESET_FILEPATH = os.getenv('RULESET_FILEPATH')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GPT_MODEL = os.getenv('GPT_MODEL')
EMBEDDINGS_CHUNK_SIZE = os.getenv('EMBEDDINGS_CHUNK_SIZE')

openai.api_key = OPENAI_API_KEY

def main():
    embeddings = OpenAIEmbeddings(chunk_size=EMBEDDINGS_CHUNK_SIZE)
    loader = PyPDFDirectoryLoader(path=RULESET_FILEPATH)
    documents = loader.load_and_split()

    db = FAISS.from_documents(documents=documents, embedding=embeddings)
    db.save_local("./dbs/documentation/faiss_index")

if __name__ == "__main__":
    main()