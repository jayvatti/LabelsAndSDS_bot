# backend/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI()

# Configure CORS to allow connections from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],  # Update this if your frontend runs on a different host/port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Wait to receive a message from the client
            data = await websocket.receive_text()
            print(f"Received message: {data}")

            # Simulate streaming responses
            for chunk in generate_response_chunks(data):
                await websocket.send_text(chunk)
                await asyncio.sleep(0.05)  # Adjust delay as needed

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
