
from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key=PINECONE_API_KEY)

data = [
    {"text": "The quick brown fox jumps over the lazy dog."},
    {"text": "The lazy dog is brown."},
    {"text": "The fox is brown."}
]
string = "The quick brown fox jumps over the lazy dog."

if __name__ == "__main__":
    embeddings = pc.inference.embed(
        model="pinecone-sparse-english-v0",
        inputs=string,
        parameters={"input_type": "passage", "return_tokens": True}
    )

    print(embeddings.data[0])
