from abc import ABC, abstractmethod
from typing import Dict, List


class Embeddings(ABC):

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the name of the embedding model."""
        pass

    @abstractmethod
    def get_dimensions(self) -> int:
        """Return the dimension length of the embeddings."""
        pass

    @abstractmethod
    def format_representations(self) -> str:
        """Return the string representation showing the model name."""
        pass

    @abstractmethod
    def embedding(self,question: str) -> Dict[str, any]:
        """Return a dictionary containing the question and its embedding vector."""
        pass

