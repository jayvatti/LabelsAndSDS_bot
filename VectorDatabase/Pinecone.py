from VectorDatabase.VectorDatabase import VectorDatabase
from dotenv import load_dotenv
import os
from pinecone import Pinecone, ServerlessSpec
from typing import Dict, List, Any, Tuple
import logging

load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
pinecone = Pinecone(api_key=PINECONE_API_KEY)


class PineconeDatabase(VectorDatabase):
    def __init__(self, k: int = 3, debug: bool = False, api_key: str = PINECONE_API_KEY):
        """
        Initialize the Pinecone database.

        Args:
            k (int): Number of closest vectors to retrieve.
        """
        super().__init__(k)
        self.k = k
        self.debug = debug

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG if self.debug else logging.INFO)
            formatter = logging.Formatter('%(levelname)s: %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    def upsert(self, **kwargs: Any) -> bool:
        """
        Upsert a vector embedding into the Pinecone index.
        """
        try:
            index_name = kwargs.get("index_name")
            embedding = kwargs.get("embedding")
            string = kwargs.get("string")
            namespace = kwargs.get("namespace")
            id_ = kwargs.get("id_")

            self.logger.debug(f"Upserting into index: {index_name} with ID: {id_}")

            index = pinecone.Index(index_name)
            vector = {
                "id": id_,
                "values": embedding,
                "metadata": {"text": string}
            }
            index.upsert(
                vectors=[vector],
                namespace=namespace
            )

            self.logger.debug("Upsert successful.")
            return True

        except Exception as e:
            self.logger.error(f"Upsert failed with exception: {e}")
            return False

    def query(self, **kwargs: Any) -> List[Tuple[List[float], str]]:
        """
        Query the Pinecone index to retrieve the top K the closest vectors to a given embedding.

        Returns:
            List[Tuple[List[float], str]]: List of tuples containing vectors and their associated strings.
        """
        try:
            index_name = kwargs.get("index_name")
            embedding = kwargs.get("embedding")
            namespace = kwargs.get("namespace")
            top_k = kwargs.get("top_k", self.k)

            self.logger.debug(f"Querying index: {index_name} with top_k: {top_k}")

            index = pinecone.Index(index_name)
            query = index.query(
                vector=embedding,
                namespace=namespace,
                top_k=top_k,
                include_values=True,
                include_metadata=True
            )

            self.logger.debug("Query successful.")
            return query['matches']
        except Exception as e:
            self.logger.error(f"Query failed with exception: {e}")
            return []

    def format_representation(self) -> str:
        """
        Return a string representation of the vector database's current state or metadata.

        Returns:
            str: A formatted string representing the database.
        """
        return f"VectorDatabase(database=Pinecone, top_k={self.k})"


