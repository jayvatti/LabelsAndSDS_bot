import os
import threading
from queue import Queue, Empty
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# Define a callback handler to stream tokens to the queue
class QueueCallbackHandler(BaseCallbackHandler):
    def __init__(self, queue: Queue):
        self.queue = queue

    def on_llm_new_token(self, token: str, **kwargs):
        self.queue.put(token)  # Add each token to the queue

    def on_llm_end(self, *args, **kwargs):
        self.queue.put(None)  # Signal that generation is done



# Define a tool for LangChain
@tool
def magic_function(input: int) -> int:
    """Applies a magic function to an input."""
    return input + 2


# Set up the LLM with streaming enabled
llm_model = ChatOpenAI(model="gpt-4", openai_api_key=OPENAI_API_KEY, streaming=True)
tools = [magic_function]
query = "what is the magic function of magic_function(3)?"


# Main function to handle prompt and streaming
def main():
    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    # Queue to store streamed tokens
    token_queue = Queue()
    callback_handler = QueueCallbackHandler(token_queue)

    # Create the agent and executor with callback
    agent = create_tool_calling_agent(llm_model, tools, prompt_template)
    agent_executor = AgentExecutor(agent=agent, tools=tools, callback_handler=callback_handler)

    # Start response generation in a separate thread
    threading.Thread(target=lambda: agent_executor.invoke({"input": query})).start()

    # Stream tokens from the queue to the terminal
    print("Response:", end=" ", flush=True)
    while True:
        try:
            token = token_queue.get(timeout=1)
            if token is None:  # Generation is complete
                break
            print(token, end="", flush=True)  # Print each token as it arrives
        except Empty:
            continue
    print("\nDone.")


if __name__ == "__main__":
    main()
