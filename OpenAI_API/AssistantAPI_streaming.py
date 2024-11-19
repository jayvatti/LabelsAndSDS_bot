from sched import Event
from typing import override, Generator
from openai import AssistantEventHandler

from Assistant import Assistant
from tool_calling import vectorDB_tool
import json
from utils import load_json_file
from openai import OpenAI
import os
from dotenv import load_dotenv


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class EventHandler(AssistantEventHandler):
    def __init__(self, client):
        super().__init__()
        self.client = client

    @override
    def on_text_created(self, text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                print(delta.code_interpreter.input, end="", flush=True)
            if delta.code_interpreter.outputs:
                print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)

    @override
    def on_event(self, event):
        if event.event == 'thread.run.requires_action':
            run_id = event.data.id
            self.handle_requires_action(event.data, run_id)

    def handle_requires_action(self, data, run_id):
        tool_outputs = []

        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "vectorDB_tool":
                bot_input = json.loads(tool.function.arguments)
                output = vectorDB_tool(bot_input["userInput"], bot_input["namespace"])
                tool_outputs.append({"tool_call_id": tool.id, "output": output})

        self.submit_tool_outputs(tool_outputs, run_id)

    def submit_tool_outputs(self, tool_outputs, run_id):
        tempHandler = EventHandler(self.client)
        with self.client.beta.threads.runs.submit_tool_outputs_stream(
                thread_id=self.current_run.thread_id,
                run_id=self.current_run.id,
                tool_outputs=tool_outputs,
                event_handler=tempHandler,
        ) as stream:
            print("printing------")
            for text in stream.text_deltas:
                print(text, end="", flush=True)
            print()


class AssistantAPI_streaming:
    def __init__(self, client, assistant):
        self.client = client
        self.thread = self.client.beta.threads.create()
        self.assistant_id = assistant

    def prompt(self, message):
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=message,
        )

    def user_chat(self):
        #static console chat
        print("\n------- llm_testing --------\n")
        print("Type 'quit' to exit the program.")
        print("--------------------------------")
        while True:
            message = input("\nuser > ")
            if message.upper() == "QUIT":
                print("\nquitting...")
                break
            self.prompt(message)
            #print(self.client.beta.threads.messages.list(self.thread.id))
            print("\nllm_testing: ", end=" ")
            tempEventHandler = EventHandler(self.client)
            with self.client.beta.threads.runs.stream(
                    thread_id=self.thread.id,
                    assistant_id=self.assistant_id,
                    event_handler=tempEventHandler
            ) as stream:
                stream.until_done()

    def get_iterator(self, user_input: str) -> Generator[str, None, None]:
        self.prompt(user_input)
        tempEventHandler = EventHandler(self.client)
        with self.client.beta.threads.runs.stream(
                thread_id=self.thread.id,
                assistant_id=self.assistant_id,
                event_handler=tempEventHandler
        ) as stream:
            for text in stream.text_deltas:
                yield text

    def iterator_testing(self):
        print("\n--- llm_testing_iterator ----\n")
        print("Type 'quit' to exit the program.")
        print("--------------------------------")
        while True:
            message = input("\nuser > ")
            if message.upper() == "QUIT":
                print("\nquitting...")
                break
            iterator = self.get_iterator(message)
            for char in iterator:
                print(char, end="")

    def getThread(self):
        return self.thread


def main():
    client = OpenAI(api_key=OPENAI_API_KEY)
    assistant_id_json = load_json_file("assistant_id.json")
    assistant_run = AssistantAPI_streaming(client, assistant_id_json.get("assistant_id"))
    assistant_run.iterator_testing()


if __name__ == "__main__":
    main()

