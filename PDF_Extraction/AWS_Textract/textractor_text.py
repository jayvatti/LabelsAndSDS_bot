from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from textractor import Textractor
from textractor.parsers import response_parser
import json
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
import os

def load_document(json_path: str):
    """
    Load and parse the Textract JSON output.

    Args:
        json_path (str): Path to the Textract JSON file.

    Returns:
        Document: Parsed document object containing pages and extracted data.
    """
    with open(json_path, "r") as f:
        document = response_parser.parse(json.load(f))
    return document

def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and removing special characters."""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    return text.strip()

def calculate_cosine_similarity(text1: str, text2: str) -> float:
    """Calculate cosine similarity between two texts using TF-IDF vectors."""
    text1 = normalize_text(text1)
    text2 = normalize_text(text2)

    vectorizer = TfidfVectorizer().fit([text1, text2])
    vectors = vectorizer.transform([text1, text2])

    similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
    return similarity

def visualize_extracted_text_with_similarity(
    image_path: str,
    document,
    target_text: str,
    output_path: str = "output_visualization_similarity.png",
    similarity_threshold: float = 0.5
):
    """
    Overlay extracted text, bounding boxes, and similarity scores on the image.

    Args:
        image_path (str): Path to the PNG image.
        document (Document): Parsed document object from Textract.
        target_text (str): The text to compare against extracted text.
        output_path (str, optional): Path to save the visualized image.
        similarity_threshold (float, optional): Threshold to determine box color.
    """
    if not os.path.exists(image_path):
        print(f"Image file not found: {image_path}")
        return

    # Open the image
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    image_width, image_height = image.size

    # Attempt to load a TrueType font; fall back to default if unavailable
    try:
        font = ImageFont.truetype("arial.ttf", size=15)
    except IOError:
        font = ImageFont.load_default()

    # Iterate over pages and lines to draw bounding boxes, text, and similarity scores
    for page in document.pages:
        for line in page.lines:
            # Initialize lists to hold all x and y coordinates of words in the line
            x_coords = []
            y_coords = []

            # Iterate through each word in the line to collect bounding box coordinates
            for word in line.words:
                if hasattr(word, 'bounding_box') and hasattr(word.bounding_box, 'vertices'):
                    vertices = word.bounding_box.vertices
                    x_coords.extend([vertex.x for vertex in vertices])
                    y_coords.extend([vertex.y for vertex in vertices])
                else:
                    print(f"No bounding_box found for word: {word.text}")

            # If no bounding boxes were found for any words in the line, skip the line
            if not x_coords or not y_coords:
                print(f"No bounding_box found for line: {line.text}")
                continue

            # Compute the bounding box for the entire line
            min_x = min(x_coords) * image_width
            max_x = max(x_coords) * image_width
            min_y = min(y_coords) * image_height
            max_y = max(y_coords) * image_height

            # Calculate similarity score with target text
            similarity_score = calculate_cosine_similarity(target_text, line.text)

            # Determine the color based on similarity threshold
            outline_color = "red" if similarity_score < similarity_threshold else "green"

            # Draw rectangle around the line
            draw.rectangle([(min_x, min_y), (max_x, max_y)], outline=outline_color, width=2)

            # Prepare similarity text
            similarity_text = f"{similarity_score:.2f}"

            # Draw the similarity score above the bounding box
            similarity_position = (min_x, max(0, min_y - 15))
            draw.text(similarity_position, f"Similarity: {similarity_text}", fill="purple", font=font)

            # Draw the extracted text above the similarity score
            text_position = (min_x, max(0, min_y - 30))
            draw.text(text_position, line.text, fill="blue", font=font)

    # Save the visualized image
    image.save(output_path)
    print(f"Visualization with similarity scores saved to {output_path}")

    # Display the image using matplotlib
    plt.figure(figsize=(15, 15))
    plt.imshow(image)
    plt.axis('off')
    plt.show()

if __name__ == "__main__":
    # Define paths
    json_path = "Cache/test2_0.json"  # Path to your Textract JSON output
    page_image = "page_image.png"  # Replace with your actual image path

    # Verify that the JSON file exists
    if not os.path.exists(json_path):
        print(f"JSON file not found: {json_path}")
        exit(1)

    # Verify that the image file exists
    if not os.path.exists(page_image):
        print(f"Image file not found: {page_image}")
        exit(1)

    # Load the document
    document = load_document(json_path)

    # Define the target text for similarity comparison
    target_text = "Warranty Disclaimer"  # Replace with your actual target text

    # Visualize the extracted text with similarity scores on the image
    visualize_extracted_text_with_similarity(
        page_image,
        document,
        target_text,
        output_path="output_visualization_similarity.png",
        similarity_threshold=0.2  # Adjust threshold as needed
    )
