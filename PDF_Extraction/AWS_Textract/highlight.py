import json
import re
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
from difflib import SequenceMatcher


def clean_target_text(target_text):
    """
    Cleans the target text by removing <HEADING> tags and {['TITLE EXTRACT']} placeholder.
    """
    # Remove <HEADING> and </HEADING> tags
    cleaned_text = re.sub(r'</?HEADING>', '', target_text)

    # Remove {['TITLE EXTRACT']}
    cleaned_text = re.sub(r"\{\['TITLE EXTRACT'\]\}", '', cleaned_text)

    # Replace multiple spaces and newlines with a single space
    cleaned_text = ' '.join(cleaned_text.split())

    return cleaned_text


def load_textract_json(json_path):
    """
    Loads the Textract JSON response from the specified file.
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data


def extract_text_blocks(textract_data):
    """
    Extracts all LINE blocks from Textract JSON.
    """
    lines = []
    for block in textract_data.get('Blocks', []):
        if block.get('BlockType') == 'LINE':
            text = block.get('Text', '').strip()
            geometry = block.get('Geometry', {}).get('BoundingBox', {})
            if text:  # Ensure text is not empty
                lines.append({'Text': text, 'BoundingBox': geometry})
    return lines


def normalize_text(text):
    """
    Normalizes text for comparison: lowercasing and stripping extra whitespace.
    """
    return re.sub(r'\s+', ' ', text).strip().lower()


def find_matching_blocks(cleaned_text, lines, threshold=0.6):
    """
    Finds matching text blocks based on the cleaned text.
    """

    def similar(a, b):
        return SequenceMatcher(None, a, b).ratio()

    normalized_cleaned_text = normalize_text(cleaned_text)

    matched_blocks = []
    for line in lines:
        normalized_line = normalize_text(line['Text'])
        similarity = similar(normalized_cleaned_text, normalized_line)
        # If exact match or high similarity, consider it a match
        if normalized_cleaned_text == normalized_line or similarity >= threshold:
            matched_blocks.append(line)
        else:
            # Additionally, check if the line text is a substring of cleaned_text
            if normalized_line in normalized_cleaned_text:
                matched_blocks.append(line)

    return matched_blocks


def draw_boxes_on_image(image_path, matched_blocks, output_path):
    """
    Draws bounding boxes around matched text in the image.
    """
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    width, height = image.size

    for block in matched_blocks:
        bbox = block['BoundingBox']
        # Textract provides bounding boxes in normalized coordinates (0 to 1)
        left = bbox['Left'] * width
        top = bbox['Top'] * height
        right = (bbox['Left'] + bbox['Width']) * width
        bottom = (bbox['Top'] + bbox['Height']) * height
        draw.rectangle([left, top, right, bottom], outline='red', width=2)

    image.save(output_path)
    print(f"Highlighted image saved to {output_path}")


def display_image(image_path):
    """
    Displays the image using matplotlib.
    """
    image = Image.open(image_path)
    plt.figure(figsize=(12, 12))
    plt.imshow(image)
    plt.axis('off')
    plt.show()


def main():
    # Original target_text with tags and placeholders
    target_text = """
    <HEADING>Terms and Conditions of Use</HEADING>
    <HEADING>If terms of the following Warranty Disclaimer, Inherent Risks of Use and</HEADING>
    <HEADING>Limitation of Remedies are not acceptable, return unopened package</HEADING>
    at once to the seller for a full refund of purchase price paid. To the
    extent permitted by law, otherwise, use by the buyer or any other user
    constitutes acceptance of the terms under Warranty Disclaimer, Inherent
    Risks of Use and Limitation of Remedies.
    Warranty Disclaimer {['TITLE EXTRACT']}
    Corteva Agriscience warrants that this product conforms to the chemical
    description on the label and is reasonably fit for the purposes stated on
    the label when used in strict accordance with the directions, subject to
    the inherent risks set forth below. TO THE EXTENT PERMITTED BY LAW,
    CORTEVA AGRISCIENCE MAKES NO OTHER EXPRESS OR IMPLIED
    WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR
    PURPOSE OR 
    """

    # File paths
    json_path = 'Cache/test2_10.json'  # Path to Textract JSON
    image_path = 'PNG_Cache/test2_10.png'  # Path to the image
    output_path = 'test2_10_highlighted.png'  # Path to save the highlighted image

    # Step 1: Clean the target_text
    cleaned_text = clean_target_text(target_text)
    print("Cleaned Text:")
    print(cleaned_text)

    # Step 2: Load and parse Textract JSON
    textract_data = load_textract_json(json_path)
    lines = extract_text_blocks(textract_data)

    # Debug: Print extracted lines
    print("\nExtracted Textract Lines:")
    for idx, line in enumerate(lines, 1):
        print(f"{idx}: {line['Text']}")

    # Step 3: Find matching text blocks
    matched_blocks = find_matching_blocks(cleaned_text, lines, threshold=0.6)
    print(f"\nNumber of matched blocks: {len(matched_blocks)}")

    # Debug: Print matched lines
    if matched_blocks:
        print("\nMatched Blocks:")
        for block in matched_blocks:
            print(block['Text'])
    else:
        print("\nNo matches found. Consider lowering the similarity threshold or reviewing the matching logic.")

    # Step 4: Highlight matched text in the image
    if matched_blocks:
        draw_boxes_on_image(image_path, matched_blocks, output_path)
        # Optional: Display the highlighted image
        display_image(output_path)
    else:
        print("No bounding boxes to draw since no matches were found.")


if __name__ == "__main__":
    main()
