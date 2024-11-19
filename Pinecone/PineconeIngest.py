from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from Embeddings.Embedding import Embeddings
from Embeddings.text_embedding_3_large import text_embedding_3_large_openAI
from LangChain.HeaderTableTextSplitter_AWS import HeaderTableTextSplitter

import os
import json


def main():
    filepath = "../PDF_Extraction/AWS_Textract/Outputs/"

    files = [f for f in os.listdir(filepath) if os.path.isfile(os.path.join(filepath, f))]
    pinecone_json_path = "../Pinecone/pinecone.json"
    with open(pinecone_json_path, "r") as json_file:
        data = json.load(json_file)
        files_set = set(data["files"])

    files_needed = [file for file in files if file not in files_set]

    added_files = []
    for file in files_needed:
        namespace = file.replace(".txt", "")
        added_files.append(file)
        vectorDatabase: VectorDatabase = PineconeDatabase(debug=True)
        embedding_model: Embeddings = text_embedding_3_large_openAI()

        with open(filepath + file, 'r', encoding='utf-8') as read_file:
            content = read_file.read()

        splitter = HeaderTableTextSplitter()
        chunks = splitter.split_text(content)
        print(f"(file={file}) has {len(chunks)} chunks")
        for i, chunk in enumerate(chunks, start=1):
            embedding_vector = embedding_model.embedding(chunk)["Embedding"]
            kwargs = {
                "index_name": "rag-model",
                "id_": f"id_{i}",
                "embedding": embedding_vector,
                "string": chunk,
                "namespace": namespace
            }
            print(f"Ingesting {file}(chunk={i})...")
            vectorDatabase.upsert(**kwargs)
            print("-"*55)

    print("-" * 55)
    print("Ingesting done!!!")
    print("-" * 55)

    with open(pinecone_json_path, "r") as json_file:
        data = json.load(json_file)
        files_set = set(data["files"])

    files_set.update(added_files)

    data["files"] = list(files_set)

    with open(pinecone_json_path, "w") as json_file:
        json.dump(data, json_file, indent=4)


if __name__ == "__main__":
    main()

