from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from Embeddings.Embedding import Embeddings
from Embeddings.text_embedding_3_large import text_embedding_3_large_openAI
from pinecone import Pinecone, ServerlessSpec
import os
from dotenv import load_dotenv
from collections import Counter

load_dotenv()


def main():
    # vectorDatabase: VectorDatabase = PineconeDatabase(k=3)
    # embedding_model: Embeddings = text_embedding_3_large_openAI()
    # question = "What is the mixing??"
    # embedding_vector = embedding_model.embedding(question)["Embedding"]
    # kwargs = {"index_name": "rag-model", "embedding": embedding_vector, "string": "question", "namespace": "test2"}
    # print(vectorDatabase.upsert(**kwargs))

    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    pinecone = Pinecone(api_key=PINECONE_API_KEY)

    index_main = pinecone.Index("rag-model")
    ids_list = [str(item) for sublist in index_main.list(namespace='test2_combined') for item in (sublist if isinstance(sublist, list) else [sublist])]
    ids_list.sort(key=lambda x: int(x.split('_')[1]))
    for ids in ids_list:
        print(ids)

    print(f"Length is: {len(ids_list)}")
    id_counts = Counter(ids_list)
    duplicates = {id_: count for id_, count in id_counts.items() if count > 1}

    if duplicates:
        print("Duplicate IDs and their counts:")
        for id_, count in duplicates.items():
            print(f"{id_}: {count}")
    else:
        print("No duplicates found.")


if __name__ == "__main__":
    main()
