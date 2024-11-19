from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing import Any
from langchain.agents import create_tool_calling_agent, AgentExecutor
from queue import Queue, Empty
from langchain.prompts import PromptTemplate
from langchain.callbacks.base import BaseCallbackHandler
from threading import Thread

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class QueueCallback(BaseCallbackHandler):
    """Callback handler for streaming LLM responses to a queue."""

    def __init__(self, q):
        self.q = q

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.q.put(token)

    def on_llm_end(self, *args, **kwargs: Any) -> None:
        return self.q.empty()

q = Queue()
job_done = object()


callbacks = [QueueCallback(q)]
llm_model = ChatOpenAI(model="gpt-4-mini", openai_api_key=OPENAI_API_KEY)
template = """Question: {question}

Answer: Let's work this out in a step by step way to be sure we have the right answer."""

prompt = PromptTemplate(template=template, input_variables=["question"])


def answer(question):
    def task():
        response = llm_model(question)
        q.put(job_done)

    t = Thread(target=task)
    t.start()


# ✅ LangChain tool
@tool
def exponentiate(x: float, y: float) -> float:
    """Raise 'x' to the 'y'."""
    return x ** y


# ✅ Function

def subtract(x: float, y: float) -> float:
    """Subtract 'x' from 'y'."""
    return y - x


# ✅ OpenAI-format dict
# Could also pass in a JSON schema with "title" and "description"
add = {
    "name": "add",
    "description": "Add 'x' and 'y'.",
    "parameters": {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "First number to add"},
            "y": {"type": "number", "description": "Second number to add"}
        },
        "required": ["x", "y"]
    }
}


@tool
def magic_function(input: int) -> int:
    """Applies a magic function to an input."""
    return input + 2


tools_t = [magic_function]


query = "what is the magic function of magic_function(3)?"



def main():
    prompt_temp = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    agent_t = create_tool_calling_agent(llm_model, tools_t, prompt_temp)
    agent_executor = AgentExecutor(agent=agent_t, tools=tools_t)

    response = agent_executor.invoke({"input": query})
    print(response)


if __name__ == "__main__":
    main()
