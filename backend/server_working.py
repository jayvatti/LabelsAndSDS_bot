# backend/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def generate_response_chunks(message: str, stop_event: asyncio.Event):
    """
    Simulate generating response chunks from the chatbot.
    Replace this with your actual chatbot streaming logic.
    """
    response = f"Echo: {message}"
    for char in response:
        if stop_event.is_set():
            print("Response generation stopped")
            break
        yield char
        await asyncio.sleep(0.05)


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
    try:
        async for chunk in generate_response_chunks(message, stop_event):
            await websocket.send_text(chunk)
    except asyncio.CancelledError:
        print("Response task was cancelled")
