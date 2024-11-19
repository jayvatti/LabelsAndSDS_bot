from typing import *
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate

from Assistant import Assistant
from tool_calling import vectorDB_tool

from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from LangChain.Model import Model
from LangChain.OpenAI_Model import OpenAI_Model
from Embeddings.Embedding import Embeddings
from Embeddings.text_embedding_3_large import text_embedding_3_large_openAI
import os
from openai import OpenAI
from tool_calling import vectorDB_tool
import json
import time
from utils import load_json_file

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class AssistantAPI:
    def __init__(self, client, assistant_id):
        print("\nCreating a new assistant...\n")
        self.client = client
        self.assistant_id = assistant_id
        print("Creating a new thread...")
        self.thread = self.client.beta.threads.create()
        print("Created a new thread!!!")
        print("\nCreated a new assistant!!!\n")

    def run_assistant(self):
        run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant_id,
            instructions=None
        )
        while True:
            run_status = self.client.beta.threads.runs.retrieve(thread_id=self.thread.id,
                                                                run_id=run.id)
            if run_status.status == 'completed':
                break
            elif run_status.status == 'requires_action':
                print(f"\n---- Action Required: {run_status.status} ----\n")
                for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
                    if tool_call.function.name == "vectorDB_tool":
                        bot_input = json.loads(tool_call.function.arguments)
                        print("Tool call: ", tool_call.function.name, "INPUT: ", bot_input)
                        output = vectorDB_tool(bot_input["userInput"], bot_input["namespace"])
                        # print("OUTPUT: ", output)
                        thread_id = self.thread.id
                        self.client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id,
                                                                          run_id=run.id,
                                                                          tool_outputs=[{
                                                                              "tool_call_id":
                                                                                  tool_call.id,
                                                                              "output":
                                                                                  output
                                                                          }])
                time.sleep(0.5)

    def user_chat(self):
        print("\n------- llm_testing --------\n")
        print("Type 'QUIT' to exit the program.")
        print("--------------------------------")

        while True:
            message = input("\nUser: ")
            if message.upper() == "QUIT":
                print("\nQuitting...")
                break
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role="user",
                content=message
            )
            self.run_assistant()

            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread.id
            )

            print("llm_chatbot:", messages.data[0].content[0].text.value)

    def response(self, user_input):
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=user_input
        )
        self.run_assistant()

        messages = self.client.beta.threads.messages.list(
            thread_id=self.thread.id
        )
        return messages.data[0].content[0].text.value

    def __del__(self):
        try:
            print("\ndeleting user thread...")
            self.client.beta.threads.delete(self.thread.id)
            print("deleted user thread!!!\n")
        except Exception as e:
            print("Cleanup failed:", e)


def main():
    # llm_namespace = "test2_combined"
    # print(vectorDB_tool(userInput="mixing directions", namespace=llm_namespace))
    client = OpenAI(api_key=OPENAI_API_KEY)
    assistant_id_json = load_json_file("assistant_id.json")
    assistant_run = AssistantAPI(client,  assistant_id_json.get("assistant_id"))
    assistant_run.user_chat()


if __name__ == "__main__":
    main()
