# backend/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from LangChain.Model import Model
from LangChain.OpenAI_Model import OpenAI_Model
from Embeddings.Embedding import Embeddings
from Embeddings.text_embedding_3_large import text_embedding_3_large_openAI
from dotenv import load_dotenv
from Assistant import Assistant
from langchain_community.chat_message_histories import ChatMessageHistory
import os
from langchain_core.runnables.history import RunnableWithMessageHistory
import markdown


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_model: Model = OpenAI_Model(OPENAI_API_KEY)
llm_database: VectorDatabase = PineconeDatabase()
embedding_llm: Embeddings = text_embedding_3_large_openAI()
llm_namespace = "test2_combined"
assistant = Assistant(llm_database, chat_model, embedding_llm, llm_namespace)
chat_history = ChatMessageHistory()


def getIterator(message: str):
    iterator = assistant.iteratorFunc(message)
    return iterator


async def generate_response_chunks(message: str, stop_event: asyncio.Event):
    response = f"Echo: {message}"
    for char in getIterator(message)():
        if stop_event.is_set():
            print("Response generation stopped")
            break
        yield char
        await asyncio.sleep(0.01)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    response_task = None
    stop_event = asyncio.Event()
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received message: {data}")
            chat_history.add_user_message(data)
            print(chat_history.messages)
            if data == "__STOP__":
                print("Stopping current response")
                stop_event.set()
                if response_task:
                    response_task.cancel()
                continue

            stop_event = asyncio.Event()

            response_task = asyncio.create_task(send_response(websocket, data, stop_event))

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")


async def send_response(websocket: WebSocket, message: str, stop_event: asyncio.Event):
    full_response = ''
    try:
        async for chunk in generate_response_chunks(message, stop_event):
            await websocket.send_text(chunk)
            full_response += chunk
    except asyncio.CancelledError:
        print("Response task was cancelled")
    finally:
        chat_history.add_ai_message(full_response)


def main():
    message = "suppp!!!"

    for content in getIterator(message)():
        print(content, end="", flush=True)


if __name__ == "__main__":
    main()
