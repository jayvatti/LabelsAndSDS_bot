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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received message: {data}")

            for chunk in generate_response_chunks(data):
                await websocket.send_text(chunk)
                await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        print("Client disconnected")


def generate_response_chunks(message: str):
    """
    Simulate generating response chunks from the chatbot.
    Replace this with your actual chatbot streaming logic.
    """
    response = f"Echo: {message}"
    for char in response:
        yield char
