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

    # Since each JSON is per page, we can skip grouping by page
    # Proceed to sort tables based on Left and Top within the page

    # Sort tables by Left
    tables_sorted_left = sorted(tables_sorted, key=lambda x: x["Left"])

    # Group tables into columns based on Left positions
    columns = []
    current_column = []
    previous_left = None

    for table in tables_sorted_left:
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

    for column in columns:
        column.sort(key=lambda x: x["Top"])

    sorted_tables = []
    for column in columns:
        sorted_tables.extend(column)

    return sorted_tables


def visualize_tables_on_image(image_path, sorted_tables, output_image_path, highlight_specific=True, specific_table=None):
    """
    Draws bounding boxes and table numbers on the image.

    Args:
        image_path (str): Path to the image file.
        sorted_tables (list of dict): Sorted list of tables with bounding boxes.
        output_image_path (str): Path to save the annotated image.
        highlight_specific (bool): Whether to highlight specific tables.
        specific_table (list of int): List of table indices to highlight. Ignored if highlight_specific is False.
    """
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", size=20)
    except IOError:
        font = ImageFont.load_default()

    if not highlight_specific:
        tables_to_highlight = sorted_tables
    else:
        tables_to_highlight = []
        for table_idx in specific_table:
            if 1 <= table_idx <= len(sorted_tables):
                tables_to_highlight.append(sorted_tables[table_idx - 1])
            else:
                print(f"Warning: Table number {table_idx} is out of range for this page.")

    for idx, table in enumerate(tables_to_highlight, start=1):
        bbox = table["BoundingBox"]
        img_width, img_height = image.size
        left = bbox["Left"] * img_width
        top = bbox["Top"] * img_height
        width = bbox["Width"] * img_width
        height = bbox["Height"] * img_height
        right = left + width
        bottom = top + height


        draw.rectangle([(left, top), (right, bottom)], outline="red", width=3)

        if not highlight_specific:
            text = f"Table {idx}"
        else:
            text = f"Table {specific_table[idx - 1]}"

        text_bbox = font.getbbox(text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        padding = 5
        text_background = (
            left,
            top - text_height - padding,
            left + text_width + padding,
            top
        )

        draw.rectangle(text_background, fill="red")

        draw.text((left + 2, top - text_height - padding), text, fill="white", font=font)

    # Save and display the annotated image
    image.save(output_image_path)
    image.show()


def visualize_table(namespace, page_number, table_number):
    """
    Visualizes and highlights tables on a specified page based on the table number.

    Args:
        namespace (str): The namespace identifier used in file naming.
        page_number (int): The 0-indexed page number to process.
        table_number (int):
            - If -1: Highlights all tables on the specified page.
            - If >=1: Highlights only the specified table number on the page.

    Returns:
        str: The message indicating where the output image is saved or if no tables were found.
    """
    json_filename = f"{namespace}_{page_number}.json"
    image_filename = f"{namespace}_{page_number}.png"

    json_path = os.path.join("../Cache", json_filename)
    image_path = os.path.join("../PNG_Cache", image_filename)

    if not os.path.isfile(json_path):
        return f"Error: JSON file '{json_path}' does not exist."
    if not os.path.isfile(image_path):
        return f"Error: Image file '{image_path}' does not exist."

    with open(json_path, "r") as f:
        textract_response = json.load(f)

    tables = extract_tables(textract_response)

    tables_on_page = tables

    if not tables_on_page:
        return f"No tables were found on page {page_number}."

    sorted_tables = sort_tables(tables_on_page)

    if table_number == -1:
        highlight_specific = False
        specific_table = []
    else:
        highlight_specific = True
        specific_table = [table_number]

    if table_number != -1:
        if not (1 <= table_number <= len(sorted_tables)):
            return f"Error: Table number {table_number} is out of range. There are {len(sorted_tables)} tables on page {page_number}."

    if table_number == -1:
        output_filename = f"visualized_{namespace}_{page_number}_all_tables.png"
    else:
        output_filename = f"visualized_{namespace}_{page_number}_table{table_number}.png"
    output_path = os.path.join("../GET", output_filename)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    visualize_tables_on_image(
        image_path=image_path,
        sorted_tables=sorted_tables,
        output_image_path=output_path,
        highlight_specific=highlight_specific,
        specific_table=specific_table
    )

    if table_number == -1:
        return f"All tables on page {page_number} are saved at http://localhost:5151/{output_path}"
    else:
        return f"Table {table_number} is saved at http://localhost:5151/{output_path}"


if __name__ == "__main__":
    result = visualize_table(namespace="test2", page_number=4, table_number=1)
    print(result)
