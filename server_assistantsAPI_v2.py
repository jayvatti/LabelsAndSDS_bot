# backend/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from dotenv import load_dotenv
import os
import markdown
from OpenAI_API.AssistantsAPI_streaming_v4 import AssistantAPI_streaming
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
            if data == "__STOP__":
                print("hey sup")
                assistant_run.cancelRun()
                print("Stopping current response")
                stop_event.set()
                if response_task:
                    response_task.cancel()
                # Optionally, send a confirmation message
                await websocket.send_text("Response stopped.")
                # Optionally, close the WebSocket if no further communication is expected
                # await websocket.close()
                continue

            assistant_run.prompt(data)

            # If there's an ongoing response task, cancel it before starting a new one
            if response_task and not response_task.done():
                response_task.cancel()
                try:
                    await response_task
                except asyncio.CancelledError:
                    print("Previous response task cancelled.")

            stop_event = asyncio.Event()
            response_task = asyncio.create_task(send_response(websocket, data, stop_event))

    except WebSocketDisconnect:
        print("Client disconnected")
        if response_task and not response_task.done():
            response_task.cancel()
    except Exception as e:
        print(f"Error: {e}")
        if response_task and not response_task.done():
            response_task.cancel()


async def send_response(websocket: WebSocket, message: str, stop_event: asyncio.Event):
    full_response = ''
    try:
        async for chunk in generate_response_chunks(message, stop_event):
            try:
                await websocket.send_text(chunk)
                full_response += chunk
            except RuntimeError as e:
                # This can happen if the WebSocket is already closed
                print(f"RuntimeError while sending: {e}")
                break
    except asyncio.CancelledError:
        print("Response task was cancelled")
    except Exception as e:
        print(f"Error in send_response: {e}")
    finally:
        # Optionally, perform any cleanup here
        pass


def main():
    message = "tell me a long ass peom about label and sds !!"
    for content in getIterator(message):
        print(content, end="", flush=True)


if __name__ == "__main__":
    main()
