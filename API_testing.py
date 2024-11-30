import asyncio
import websockets
import os


async def test():
    uri = "ws://localhost:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to the WebSocket server.")
            while True:
                message = input("Enter message (type QUIT to exit): ")
                if message.strip().upper() == "QUIT":
                    print("Exiting the conversation.")
                    break
                await websocket.send(message)
                print(f"Sent: {message}")

                # Collect response chunks
                full_response = ''
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        full_response += response
                except asyncio.TimeoutError:
                    # No more chunks are coming for this message
                    if full_response:
                        # Print the full response and the current working directory
                        print(f"Received full response: {full_response}")
                        current_path = os.getcwd()
                        print(f"Current Path: {current_path}\n")
                    else:
                        print("No response received.\n")
        print("WebSocket connection closed.")
    except ConnectionRefusedError:
        print("Failed to connect to the WebSocket server. Ensure the server is running.")
    except websockets.exceptions.ConnectionClosedOK:
        print("WebSocket connection closed gracefully.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(test())
