from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate

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


class Assistant:
    def __init__(self, database, chat_model, embedding_model, namespace):
        self.database = database
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.namespace = namespace

    def get_data(self, prompt, top_k=4):
        embedding_data = self.embedding_model.embedding(prompt)
        kwargs = {
            "index_name": "rag-model",
            "embedding": embedding_data["Embedding"],
            "namespace": self.namespace,
            "top_k": top_k
        }
        vector_str = ""

        for embedding in self.database.query(**kwargs):
            vector_str += "\n\n" + '-' * 50 + "\n\n"
            vector_str += f"\nScore: {embedding['score']}\n\n"
            vector_str += embedding['metadata']['text']

        return self.chat_model.format_prompt(vector_str, prompt)

    def run(self):
        while True:
            print('\n' + ("-" * 55))
            user_input = input("User:")
            if user_input.lower() == "quit": break
            final_prompt = self.get_data(user_input)
            iterator = self.chat_model.invoke()
            for content in iterator():
                print(content, end="", flush=True)

    def iteratorFunc(self, user_input):
        finalPrompt = self.get_data(user_input)
        iterator = self.chat_model.invoke()
        return iterator


def main():
    chat_model: Model = OpenAI_Model(OPENAI_API_KEY)
    llm_database: VectorDatabase = PineconeDatabase()
    embedding_llm: Embeddings = text_embedding_3_large_openAI()
    llm_namespace = "test2_combined"
    assistant = Assistant(llm_database, chat_model, embedding_llm, llm_namespace)

    # print(assistant.get_data("show me the spray concentration of different concentration levels.. get me the table?"))
    assistant.run()


if __name__ == "__main__":
    main()

