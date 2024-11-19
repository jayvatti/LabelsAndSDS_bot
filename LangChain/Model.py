from abc import ABC, abstractmethod


class Model(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def format_prompt(self, vectorDBdata: str, prompt: str,) -> str:
        """
        Abstract method to format a prompt before passing it to the assistant.

        :param vectorDBdata:
        :param prompt: The input string that needs to be formatted.
        :return: The formatted string.
        """
        pass

    @abstractmethod
    def invoke(self) -> iter:
        """
        Abstract method to invoke the assistant with a given prompt.

        :return: The assistant's iterator
        """
        pass
