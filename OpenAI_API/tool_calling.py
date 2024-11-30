from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from VectorDatabase.VectorDatabase import VectorDatabase
from VectorDatabase.Pinecone import PineconeDatabase
from LangChain.Model import Model
from LangChain.OpenAI_Model import OpenAI_Model
from Embeddings.Embedding import Embeddings
from Embeddings.text_embedding_3_large import text_embedding_3_large_openAI
import os
import json
from OpenAI_API.utils import *
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

llm_database: VectorDatabase = PineconeDatabase()

embedding_llm: Embeddings = text_embedding_3_large_openAI()


def getPDFSummary(namespace):
    pass


# def vectorDB_tool(userInput: str, namespace: str) -> str:
#     top_k = 5
#     embedding_data = embedding_llm.embedding(userInput)
#     kwargs = {
#         "index_name": "rag-model",
#         "embedding": embedding_data["Embedding"],
#         "namespace": namespace,
#         "top_k": top_k
#     }
#
#     vector_str = "Query Search Results: (Please Render LocalHost Links if Available. Always put the LocalHost Link whenever the user asks for the table) "
#     for embedding in llm_database.query(**kwargs):
#         vector_str += "\n\n" + '-' * 50 + "\n\n"
#         vector_str += f"\nScore: {embedding['score']}\n\n"
#         temp_searchStr = embedding['metadata']['text']
#         vector_str += temp_searchStr
#
#     vector_str += ". IMPORTANT: Only answer if the information is found in the Query Search Results. Do NOT make up or assume any information. If the information isn't available, clearly respond with something like 'I couldn't find the information in the database results.' PLEASE STRICTLY FOLLOW THIS AND DO NOT MAKE THINGS UP OR SAY SOMETHING IS THERE WHEN IT ISN'T!!"
#     return vector_str

import os
import json
import fitz  # PyMuPDF
from rapidfuzz import fuzz
from textractoverlayer.t_overlay import DocumentDimensions, get_bounding_boxes
from textractcaller.t_call import Textract_Types


def highlight_search_strings_in_pdf(
        textract_json_path: str,
        pdf_path: str,
        search_strings: list,
        output_path: str,
        match_threshold: int = 80,
        highlight_color: tuple = (1, 0, 0)  # Red color in RGB
) -> None:
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF file '{pdf_path}' not found.")
        return

    # Check if Textract JSON exists
    if not os.path.exists(textract_json_path):
        print(f"ERROR: Textract JSON file '{textract_json_path}' not found.")
        return

    # Load Textract JSON
    with open(textract_json_path, 'r') as f:
        textract_json = json.load(f)

    # Open the PDF
    doc = fitz.open(pdf_path)

    # Assume all pages have the same dimensions as the first page
    # Alternatively, handle varying page sizes
    page_dimensions = [(page.rect.width, page.rect.height) for page in doc]

    # Extract bounding boxes for words using textractoverlayer
    document_dimension = DocumentDimensions(
        doc_width=page_dimensions[0][0],
        doc_height=page_dimensions[0][1]
    )

    # Get all bounding boxes for WORD type across all pages
    bounding_box_list = get_bounding_boxes(
        textract_json=textract_json,
        document_dimensions=document_dimension,
        overlay_features=[Textract_Types.WORD]
    )

    # Load bounding boxes into a list of dictionaries for easier processing
    # Each bbox should have xmin, ymin, xmax, ymax, page_number, text
    # Assuming get_bounding_boxes provides these attributes
    # If not, adjust accordingly based on the actual structure
    matched_bboxes = []

    for search_string in search_strings:
        best_match = None
        best_ratio = 0
        best_bbox = None

        for bbox in bounding_box_list:
            block_text = bbox.text.strip()
            if not block_text:
                continue

            match_ratio = fuzz.ratio(search_string.lower(), block_text.lower())
            if match_ratio > best_ratio:
                best_ratio = match_ratio
                best_match = block_text
                best_bbox = bbox

        if best_match and best_ratio >= match_threshold:
            matched_bboxes.append(best_bbox)
            print(f"Matched '{search_string}' to '{best_match}' with ratio {best_ratio}")
        else:
            print(f"No sufficient match found for '{search_string}' (best ratio: {best_ratio})")

    # Highlight matched bounding boxes in the PDF
    for bbox in matched_bboxes:
        page_number = bbox.page_number - 1  # Zero-based index
        if page_number < 0 or page_number >= len(doc):
            print(f"WARNING: Page number {bbox.page_number} out of range.")
            continue

        page = doc[page_number]

        # Define the rectangle coordinates
        # Assuming bbox coordinates are in pixels and match PyMuPDF's coordinate system
        rect = fitz.Rect(bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax)

        # Add a rectangle annotation
        highlight = page.add_rect_annot(rect)
        highlight.set_colors(stroke=highlight_color)  # Set border color
        highlight.set_border(width=2)  # Border width
        highlight.update()

    # Save the highlighted PDF
    doc.save(output_path)
    doc.close()

    print(f"Highlights added! Saved as '{output_path}'")


def vectorDB_tool(userInput: str, namespace: str):
    top_k = 5
    embedding_data = embedding_llm.embedding(userInput)
    kwargs = {
        "index_name": "rag-model",
        "embedding": embedding_data["Embedding"],
        "namespace": namespace,
        "top_k": top_k
    }

    # Query the vector database
    query_results = llm_database.query(**kwargs)

    vector_str = "Query Search Results: (Please Render LocalHost Links if Available. Always put the LocalHost Link whenever the user asks for the table) "
    search_strings = []
    vector_array = []

    for embedding in query_results:
        vector_str += "\n\n" + '-' * 50 + "\n\n"
        vector_str += f"\nScore: {embedding['score']}\n\n"
        temp_searchStr = embedding['metadata']['text']
        vector_str += temp_searchStr
        search_strings.append(temp_searchStr)
        vector_entry = {
            "Score": embedding["score"],
            "Text": embedding["metadata"]["text"]
        }
        vector_array.append(vector_entry)

    with open("vectorRes.json", "w") as json_file:
        json.dump(vector_array, json_file, indent=2)

    add_pages_to_json("vectorRes.json", "vectorRes.json")

    vector_str += ". IMPORTANT: Only answer if the information is found in the Query Search Results. Do NOT make up or assume any information. If the information isn't available, clearly respond with something like 'I couldn't find the information in the database results.' PLEASE STRICTLY FOLLOW THIS AND DO NOT MAKE THINGS UP OR SAY SOMETHING IS THERE WHEN IT ISN'T!!."
    return vector_str


def returnPDF(namespace: str, page_number: str):
    page_number = int(page_number)
    if page_number < 0:
        return f"The PDF for the namespace is at localhost:5151/{namespace}.pdf"
    else:
        return f"The PDF for the {page_number+1} is localhost:5151/{namespace}.pdf#page={page_number+1}"
