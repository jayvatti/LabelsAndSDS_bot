from abc import ABC, abstractmethod
from typing import Any, List, Tuple


class VectorDatabase(ABC):
    def __init__(self, k: int):
        """
        Initialize the vector database with the number of closest vectors (k) to retrieve.

        Args:
            k (int): Number of closest vectors to retrieve during queries.
        """
        self.k = k

    @abstractmethod
    def upsert(self, **kwargs: Any) -> bool:
        """
        Add or update an embedding with an associated string in the vector database.
        """
        pass

    @abstractmethod
    def query(self, **kwargs: Any) -> List[Tuple[List[float], str]]:
        """
        Retrieve the top K the closest vectors from the database.

        Returns:
            List[Tuple[List[float], str]]: List of tuples containing vectors and their associated strings.
        """
        pass

    @abstractmethod
    def format_representation(self) -> str:
        """
        Return a string representation of the vector database's current state or metadata.

        Returns:
            str: A formatted string representing the database.
        """
        pass
