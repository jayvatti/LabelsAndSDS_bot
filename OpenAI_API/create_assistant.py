import os
from openai import OpenAI
from dotenv import load_dotenv
import json
from utils import load_json_file, save_json_file

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def create_assistant():
    assistant_id_path = "assistant_id.json"
    if os.path.exists(assistant_id_path):
        with open(assistant_id_path, 'r') as f:
            assistant_data = json.load(f)
        if "assistant_id" in assistant_data:
            return assistant_data["assistant_id"]

    client = OpenAI(api_key=OPENAI_API_KEY)

    data = load_json_file("tools.json")
    description = load_json_file("description.json")["description"]

    my_assistant = client.beta.assistants.create(
        name="llm_chatbot",
        instructions=description,
        model="gpt-4o-mini",
        tools=data,
        top_p=0.5,
        temperature=0.4
    )
    assistant_id = my_assistant.id
    save_json_file(assistant_id_path, {"assistant_id": assistant_id})
    return assistant_id


if __name__ == "__main__":
    create_assistant()

