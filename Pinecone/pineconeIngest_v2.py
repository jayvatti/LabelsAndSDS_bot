import time
import os
import json
from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from Embeddings.Embedding import Embeddings
from Embeddings.text_embedding_3_large import text_embedding_3_large_openAI
from LangChain.HeaderTableTextSplitter_AWS_v2 import HeaderTableTextSplitter
from pinecone import Pinecone
from dotenv import load_dotenv
import re


import re

def remove_tags(text):
    # Remove HTML-like tags
    text = re.sub(r"</?\s*\w+(?:\s*[^>]*)?>", "", text)
    # Remove chunks surrounded by {[ ]}
    text = re.sub(r"\{\[.*?\]\}", "", text)
    # Remove numbers
    text = re.sub(r"\b\d+\b", "", text)
    # Remove individual letters
    text = re.sub(r"\b[a-zA-Z]\b", "", text)
    # Remove URLs and links
    text = re.sub(r"\bhttps?://\S+|localhost:\S+\b", "", text)
    # Remove concatenated stopwords like is/are, and/or
    text = re.sub(r"\b\w+/\w+\b", "", text)
    return text.strip()


def remove_tags_and_stopwords(text):
    # Remove HTML-like tags
    text = re.sub(r"</?\s*\w+(?:\s*[^>]*)?>", "", text)
    # Path to stopwords file
    stopwords_file = "../english.txt"
    # Remove chunks surrounded by {[ ]}
    text = re.sub(r"\{\[.*?\]\}", "", text)
    # Remove numbers
    text = re.sub(r"\b\d+\b", "", text)
    # Remove individual letters
    text = re.sub(r"\b[a-zA-Z]\b", "", text)
    # Remove URLs and links
    text = re.sub(r"\bhttps?://\S+|localhost:\S+\b", "", text)
    # Remove concatenated stopwords like is/are, and/or
    text = re.sub(r"\b\w+/\w+\b", "", text)

    # Load stopwords
    with open(stopwords_file, 'r') as file:
        stopwords = set(word.strip().lower() for word in file.readlines())

    # Remove stopwords
    words = text.split()
    filtered_words = [word for word in words if word.lower() not in stopwords]
    text = ' '.join(filtered_words)

    return text.strip()

load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
pinecone = Pinecone(api_key=PINECONE_API_KEY)


def main():
    filepath = "../PDF_Extraction/AWS_Textract/Outputs/"
    pinecone_json_path = "../Pinecone/pinecone.json"

    # Load the list of already processed files
    with open(pinecone_json_path, "r") as json_file:
        data = json.load(json_file)
        files_set = set(data["files"])

    # Identify new files to process
    files = [f for f in os.listdir(filepath) if os.path.isfile(os.path.join(filepath, f))]
    files_needed = [file for file in files if file not in files_set]

    added_files = []
    for file in files_needed:
        namespace = file.replace(".txt", "")
        added_files.append(file)
        vectorDatabase: VectorDatabase = PineconeDatabase(debug=True)
        embedding_model: Embeddings = text_embedding_3_large_openAI()

        # Read the content of the file
        with open(os.path.join(filepath, file), 'r', encoding='utf-8') as read_file:
            content = read_file.read()

        # Split the content into chunks
        splitter = HeaderTableTextSplitter()
        chunks = splitter.split_text(content)
        print(f"(file={file}) has {len(chunks)} chunks")

        batch = []
        for i, chunk in enumerate(chunks, start=1):
            embedding_vector = embedding_model.embedding(remove_tags(chunk))["Embedding"]
            sparse_vector = pinecone.inference.embed(
                model="pinecone-sparse-english-v0",
                inputs=remove_tags_and_stopwords(chunk),
                parameters={"input_type": "passage", "return_tokens": True}
            )
            indices_list=sparse_vector.data[0]["sparse_indices"]
            values_list=sparse_vector.data[0]["sparse_values"]
            tokens_list=sparse_vector.data[0]["sparse_tokens"]
            vector_data = {
                "index_name": "rag-model",
                "id_": f"id_{i}",
                "embedding": embedding_vector,
                "string": chunk,
                "indices": indices_list,
                "values": values_list,
                "tokens": tokens_list,
                "namespace": namespace
            }
            batch.append(vector_data)

            # If batch size reaches 10, upsert the batch
            if len(batch) == len(chunks):
                print(f"Ingesting batch of 10 vectors for {file}...")
                for vector in batch:
                    vectorDatabase.upsert(**vector)
                batch = []
                time.sleep(5)  # Wait for 5 seconds between batches

        # Upsert any remaining vectors in the last batch
        if batch:
            print(f"Ingesting final batch of {len(batch)} vectors for {file}...")
            for vector in batch:
                vectorDatabase.upsert(**vector)
            time.sleep(5)

    print("-" * 55)
    print("Ingesting done!!!")
    print("-" * 55)

    # Update the list of processed files
    with open(pinecone_json_path, "r") as json_file:
        data = json.load(json_file)
        files_set = set(data["files"])

    files_set.update(added_files)
    data["files"] = list(files_set)

    with open(pinecone_json_path, "w") as json_file:
        json.dump(data, json_file, indent=4)


if __name__ == "__main__":
    main()
