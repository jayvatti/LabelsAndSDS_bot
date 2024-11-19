from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from LangChain.Model import Model
from LangChain.OpenAI_Model import OpenAI_Model
from Embeddings.Embedding import Embeddings
from Embeddings.text_embedding_3_large import text_embedding_3_large_openAI
import os
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

llm_database: VectorDatabase = PineconeDatabase()

embedding_llm: Embeddings = text_embedding_3_large_openAI()


def getPDFSummary(namespace):
    pass


def vectorDB_tool(userInput: str, namespace: str) -> str:
    top_k = 5
    embedding_data = embedding_llm.embedding(userInput)
    kwargs = {
        "index_name": "rag-model",
        "embedding": embedding_data["Embedding"],
        "namespace": namespace,
        "top_k": top_k
    }

    vector_str = "Query Search Results: "
    for embedding in llm_database.query(**kwargs):
        vector_str += "\n\n" + '-' * 50 + "\n\n"
        vector_str += f"\nScore: {embedding['score']}\n\n"
        vector_str += embedding['metadata']['text']

    vector_str += ". IMPORTANT: Only answer if the information is found in the Query Search Results. Do NOT make up or assume any information. If the information isn't available, clearly respond with something like 'I couldn't find the information in the database results.'"
    return vector_str



