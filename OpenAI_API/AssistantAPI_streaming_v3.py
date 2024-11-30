import threading
from queue import Queue
from typing import Generator, override
from openai import AssistantEventHandler
from OpenAI_API.tool_calling import vectorDB_tool
import json
from OpenAI_API.utils import load_json_file
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class EventHandler(AssistantEventHandler):
    def __init__(self, client, text_queue):
        super().__init__()
        self.current_run_id = None
        self.client = client
        self.text_queue = text_queue
        self.run_id = None

    @override
    def on_text_created(self, text) -> None:
        if hasattr(text, 'value'):
            pass
        else:
            self.text_queue.put(str(text))

    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                self.text_queue.put(delta.code_interpreter.input)
            if delta.code_interpreter.outputs:
                self.text_queue.put("\n\noutput >")
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        self.text_queue.put(f"\n{output.logs}")

    @override
    def on_event(self, event):
        if event.event == 'thread.run.created':
            self.current_run_id = event.data.id
            print(f"Run ID: {self.current_run_id}")

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
        tempHandler = EventHandler(self.client, self.text_queue)
        with self.client.beta.threads.runs.submit_tool_outputs_stream(
                thread_id=self.current_run.thread_id,
                run_id=self.current_run.id,
                tool_outputs=tool_outputs,
                event_handler=tempHandler,
        ) as stream:
            for text in stream.text_deltas:
                if hasattr(text, 'value'):
                    pass
                else:
                    self.text_queue.put(str(text))
        self.text_queue.put(None)


class AssistantAPI_streaming:
    def __init__(self, client, assistant):
        self.client = client
        self.thread = self.client.beta.threads.create()
        self.assistant_id = assistant
        self.current_run_id = None

    def prompt(self, message):
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=message,
        )

    def user_chat(self, user_input: str) -> Generator[str, None, None]:
        """Generates responses based on the user's input, yielding each response incrementally."""
        self.prompt(user_input)
        text_queue = Queue()
        tempEventHandler = EventHandler(self.client, text_queue)

        def run_stream():
            self.current_run = self.client.beta.threads.runs.stream(
                    thread_id=self.thread.id,
                    assistant_id=self.assistant_id,
                    event_handler=tempEventHandler
            )

            self.current_run_id = tempEventHandler.current_run_id
            with self.current_run as stream:
                for text in stream.text_deltas:
                    if hasattr(text, 'value'):
                        pass
                    else:
                        text_queue.put(str(text))
            text_queue.put(None)

        threading.Thread(target=run_stream).start()

        while True:
            text = text_queue.get()
            if text is None:
                break
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
            iterator = self.user_chat(message)
            for text in iterator:
                print(text, end="", flush=True)

    def getThread(self):
        return self.thread

    def cancelRun(self):
        self.client.beta.threads.runs.cancel(thread_id=self.thread.id, run_id=self.current_run_id)


def main():
    client = OpenAI(api_key=OPENAI_API_KEY)
    assistant_id_json = load_json_file("assistant_id.json")
    assistant_run = AssistantAPI_streaming(client, assistant_id_json.get("assistant_id"))
    assistant_run.iterator_testing()


if __name__ == "__main__":
    main()
