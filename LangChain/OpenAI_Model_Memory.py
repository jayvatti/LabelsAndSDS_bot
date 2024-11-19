from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import os
from LangChain.Model import Model

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class OpenAI_Model(Model):
    def __init__(self, API_KEY: str):
        super().__init__()
        self.chat_model = ChatOpenAI(model="gpt-4o",openai_api_key=API_KEY)
        self.prompt = ""

    def format_prompt(self, vectorDBdata: str, user_input: str, ) -> str:
        # promptTemplate = PromptTemplate.from_template(
        #     f"The Query Answers from the Database {vectorDBdata}. \n\n Answer the user's question: {user_input}?"
        # )
        # self.prompt = promptTemplate.format(
        #     vectorDBdata=vectorDBdata,
        #     user_input=user_input)

        self.prompt = f"ALWAYS ANSWER EVERY QUESTION IN CLEAR PROPER MARKDOWN PLEASE (NO MARKDOWN CODE SNIPPETS BUT GENERATE MARKDOWN)!!: The Query Answers from the Database {vectorDBdata}. \n\n Answer the user's question: {user_input}?"
        return self.prompt

    def invoke(self) -> iter:
        # answer = self.chat_model.invoke(self.prompt)
        def iterator():
            for chunk in self.chat_model.stream(self.prompt):
                yield chunk.content

        return iterator


def main():
    chatModel: Model = OpenAI_Model(OPENAI_API_KEY)
    chatModel.format_prompt("","Write me a long poem")
    iterator = chatModel.invoke()
    for content in iterator():
        print(content, end="", flush=True)


if __name__ == "__main__":
    main()



