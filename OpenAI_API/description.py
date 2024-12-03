import json
from utils import save_json_file


description_text = """
 
You are a chatbot designed to answer questions about Labels and SDS information. You can perform database searches to provide accurate, factual responses. Please follow these guidelines:

Request for Clarification: If the user does not specify the PDF or namespace to search in, ask them to clarify, e.g., "Please specify the PDF or namespace for the search."
"""

description_json = {
    "description": description_text
}


def main():
    save_json_file("description.json", description_json)
    print("model saved...")


if __name__ == "__main__":
    main()
