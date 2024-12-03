import json
import re

def extract_tags_and_pages(text):
    """
    Extracts page numbers from tags in the given text.
    Args:
        text (str): The input text containing tags.
    Returns:
        list: A sorted list of unique page numbers found in the text.
    """
    # Regular expression to find all tags enclosed in <>
    tags = re.findall(r'<([^<>]+)>', text)
    pages = set()

    for tag in tags:
        # Regular expression to find 'PAGE NUMBER = X' where X is a number
        match = re.search(r'PAGE\s*NUMBER\s*=\s*(\d+)', tag, re.IGNORECASE)
        if match:
            page_num = int(match.group(1))
            pages.add(page_num)

    return sorted(pages)

def add_pages_to_json(input_file, output_file):
    """
    Reads a JSON file, extracts page numbers from 'Text' fields,
    adds them as a 'Pages' field, and writes the updated JSON to a new file.
    Args:
        input_file (str): Path to the input JSON file.
        output_file (str): Path to save the updated JSON file.
    """
    # Read the JSON file
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Process each entry to extract page numbers
    for entry in data:
        text = entry.get('Text', '')
        pages = extract_tags_and_pages(text)
        entry['Pages'] = pages

    # Write the updated JSON back to a new file
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    input_file = 'vectorRes.json'
    output_file = 'vectorRes.json'
    add_pages_to_json(input_file, output_file)
