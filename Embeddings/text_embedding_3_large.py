from abc import ABC, abstractmethod
import os
from typing import Dict, List, Any
import logging
from openai import OpenAI

from Embeddings.Embedding import Embeddings
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


class text_embedding_3_large_openAI(Embeddings):
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG if self.debug else logging.INFO)
            formatter = logging.Formatter('%(levelname)s: %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    def get_model_name(self) -> str:
        model_name = "text-embedding-3-large"
        self.logger.debug(f"Model name: {model_name}")
        return model_name

    def get_dimensions(self) -> int:
        dimensions = 3072
        self.logger.debug(f"Embedding dimensions: {dimensions}")
        return dimensions

    def embedding(self, question: str) -> Dict[str, Any]:
        self.logger.debug(f"Generating embedding for question: {question}")

        response = client.embeddings.create(
            input=question,
            model=self.get_model_name()
        )

        embedding = response.data[0].embedding
        self.logger.debug(f"Received embedding: {embedding[:10]}...")  #Logs the first 10 values for brevity
        return {"Question": question, "Embedding": embedding}

    def format_representations(self) -> str:
        representation = f"Embeddings(model_name={self.get_model_name()}, dimensions={self.get_dimensions()})"
        self.logger.debug(f"Representation: {representation}")
        return representation


def main():
    logging.getLogger("openai").setLevel(logging.WARNING)
    embedding_model: Embeddings = text_embedding_3_large_openAI(debug=True)
    # print(embedding_model.get_model_name())
    # print(embedding_model.format_representations())
    # print(embedding_model.get_dimensions())
    print(embedding_model.embedding("Tell me about mixing?"))


if __name__ == "__main__":
    main()
