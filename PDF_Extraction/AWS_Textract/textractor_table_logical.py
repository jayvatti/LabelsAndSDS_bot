import json
import os
from PIL import Image, ImageDraw, ImageFont

def extract_tables(textract_response):
    """
    Extracts tables and their bounding boxes from the raw Textract JSON response.

    Args:
        textract_response (dict): The raw Textract JSON response.

    Returns:
        list of dict: A list of tables with their bounding box and page number.
    """
    tables = []
    blocks = textract_response.get("Blocks", [])

    # Create a mapping from Block ID to Block for quick access
    block_map = {block["Id"]: block for block in blocks}

    # Identify all TABLE blocks
    table_blocks = [block for block in blocks if block["BlockType"] == "TABLE"]

    for table_block in table_blocks:
        # Extract bounding box information
        bbox = table_block["Geometry"]["BoundingBox"]
        top = bbox["Top"]
        left = bbox["Left"]
        page = table_block.get("Page", 1)  # Default to page 1 if not present

        tables.append({
            "Page": page,
            "Top": top,
            "Left": left,
            "BoundingBox": bbox
        })

    return tables

def sort_tables(tables, left_threshold=0.05):
    """
    Sorts tables based on their column grouping and top positions.

    Args:
        tables (list of dict): List of tables with bounding box and page number.
        left_threshold (float): Threshold to group tables into the same column.

    Returns:
        list of dict: Sorted list of tables.
    """
    if not tables:
        return []

    # Sort tables by Page first, then Left
    tables_sorted = sorted(tables, key=lambda x: (x["Page"], x["Left"]))

    # Group tables by Page
    pages = {}
    for table in tables_sorted:
        page = table["Page"]
        if page not in pages:
            pages[page] = []
        pages[page].append(table)

    sorted_tables = []
    for page in sorted(pages.keys()):
        page_tables = pages[page]
        # Sort tables within the page by Left
        page_tables_sorted_left = sorted(page_tables, key=lambda x: x["Left"])

        # Group tables into columns based on Left positions
        columns = []
        current_column = []
        previous_left = None

        for table in page_tables_sorted_left:
            left = table["Left"]
            if previous_left is None:
                current_column.append(table)
                previous_left = left
            else:
                if abs(left - previous_left) < left_threshold:
                    current_column.append(table)
                    # Update the average left position for the current column
                    previous_left = (previous_left + left) / 2
                else:
                    columns.append(current_column)
                    current_column = [table]
                    previous_left = left
        if current_column:
            columns.append(current_column)

        # Sort each column by Top position
        for column in columns:
            column.sort(key=lambda x: x["Top"])

        # Flatten the sorted columns into a single list for the page
        for column in columns:
            sorted_tables.extend(column)

    return sorted_tables

def visualize_tables_on_image(image_path, sorted_tables, output_image_path):
    """
    Draws bounding boxes and table numbers on the image.

    Args:
        image_path (str): Path to the image file.
        sorted_tables (list of dict): Sorted list of tables with bounding boxes.
        output_image_path (str): Path to save the annotated image.
    """
    # Open the image
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    # Load a font
    try:
        # Adjust the font path as needed or use a default font
        font = ImageFont.truetype("arial.ttf", size=20)
    except IOError:
        # If the font is not found, load the default font
        font = ImageFont.load_default()

    for idx, table in enumerate(sorted_tables, start=1):
        bbox = table["BoundingBox"]
        # Textract uses normalized coordinates (0 to 1), convert them to pixel values
        img_width, img_height = image.size
        left = bbox["Left"] * img_width
        top = bbox["Top"] * img_height
        width = bbox["Width"] * img_width
        height = bbox["Height"] * img_height
        right = left + width
        bottom = top + height

        # Draw rectangle around the table
        draw.rectangle([(left, top), (right, bottom)], outline="red", width=3)

        # Prepare the table number label
        text = f"Table {idx}"
        # Use getbbox to determine the size of the text
        text_bbox = font.getbbox(text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Define the background rectangle for the text
        padding = 5  # Padding around the text
        text_background = (
            left,
            top - text_height - padding,
            left + text_width + padding,
            top
        )

        # Draw background for the text for better visibility
        draw.rectangle(text_background, fill="red")

        # Draw the table number text
        draw.text((left + 2, top - text_height - padding), text, fill="white", font=font)

    # Save and display the annotated image
    image.save(output_image_path)
    image.show()

def visualize_sorted_tables(textract_response_path, image_path, output_image_path, left_threshold=0.05):
    """
    Orchestrates the extraction, sorting, and visualization of tables.

    Args:
        textract_response_path (str): Path to the Textract JSON response.
        image_path (str): Path to the corresponding image file.
        output_image_path (str): Path to save the annotated image.
        left_threshold (float): Threshold to group tables into the same column.
    """
    # Load the raw Textract JSON response
    with open(textract_response_path, "r") as f:
        textract_response = json.load(f)

    tables = extract_tables(textract_response)

    if not tables:
        print("No tables found in the document.")
        return

    sorted_tables = sort_tables(tables, left_threshold=left_threshold)

    visualize_tables_on_image(image_path, sorted_tables, output_image_path)

    print(f"Visualized image saved to {output_image_path}")


if __name__ == "__main__":
    textract_response_path = "Cache/test2_3.json"
    image_path = "PNG_Cache/test2_3.png"
    output_image_path = "output/visualized_test2_3_logical.png"

    os.makedirs(os.path.dirname(output_image_path), exist_ok=True)

    visualize_sorted_tables(textract_response_path, image_path, output_image_path, left_threshold=0.05)
