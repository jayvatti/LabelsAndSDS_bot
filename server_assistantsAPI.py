# backend/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from dotenv import load_dotenv
import os
import markdown
from OpenAI_API.AssistantAPI_streaming_v3 import AssistantAPI_streaming
from OpenAI_API.utils import *
from openai import OpenAI

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

client = OpenAI(api_key=OPENAI_API_KEY)
assistant_id_json = load_json_file("OpenAI_API/assistant_id.json")
assistant_run = AssistantAPI_streaming(client, assistant_id_json.get("assistant_id"))


def getIterator(message: str):
    iterator = assistant_run.user_chat(message)
    return iterator


async def generate_response_chunks(message: str, stop_event: asyncio.Event):
    response = f"Echo: {message}"
    for char in getIterator(message):
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
            assistant_run.prompt(data)
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


def main():
    message = "tell me a long ass peom about label and sds !!"
    for content in getIterator(message):
        print(content, end="", flush=True)


if __name__ == "__main__":
    main()
