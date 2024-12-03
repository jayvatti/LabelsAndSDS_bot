import json
import os
import pandas as pd

from OpenAI_API.tool_calling import checkNamespace


def extract_tables(textract_response):
    """
    Extracts tables and their cells from the raw Textract JSON response.

    Args:
        textract_response (dict): The raw Textract JSON response.

    Returns:
        list of dict: A list of tables with their bounding box and cell data.
    """
    tables = []
    blocks = textract_response.get("Blocks", [])

    # Create a mapping from Block ID to Block
    block_map = {block["Id"]: block for block in blocks}

    # Identify all TABLE blocks
    table_blocks = [block for block in blocks if block["BlockType"] == "TABLE"]

    for table_block in table_blocks:
        # Extract bounding box for sorting purposes
        bbox = table_block["Geometry"]["BoundingBox"]
        top = bbox["Top"]
        left = bbox["Left"]

        # Find all CELL blocks that belong to this TABLE
        cell_ids = []
        for relationship in table_block.get("Relationships", []):
            if relationship["Type"] == "CHILD":
                cell_ids.extend(relationship["Ids"])

        # Extract cell information
        cells = []
        for cell_id in cell_ids:
            cell_block = block_map.get(cell_id)
            if not cell_block or cell_block["BlockType"] != "CELL":
                continue

            row_index = cell_block.get("RowIndex", 0)
            column_index = cell_block.get("ColumnIndex", 0)
            # Concatenate all text elements in the cell
            cell_text = ""
            for rel in cell_block.get("Relationships", []):
                if rel["Type"] == "CHILD":
                    for text_id in rel["Ids"]:
                        text_block = block_map.get(text_id)
                        if text_block and text_block["BlockType"] == "WORD":
                            cell_text += text_block.get("Text", "") + " "
            cell_text = cell_text.strip()

            cells.append({
                "RowIndex": row_index,
                "ColumnIndex": column_index,
                "Text": cell_text
            })

        # Organize cells into a DataFrame
        if not cells:
            continue  # Skip tables with no cells

        # Determine the maximum row and column indices
        max_row = max(cell["RowIndex"] for cell in cells)
        max_col = max(cell["ColumnIndex"] for cell in cells)

        # Initialize a list of lists to hold table data
        table_data = [["" for _ in range(max_col)] for _ in range(max_row)]

        for cell in cells:
            row = cell["RowIndex"] - 1  # Convert to 0-based index
            col = cell["ColumnIndex"] - 1
            table_data[row][col] = cell["Text"]

        # Create a DataFrame
        df = pd.DataFrame(table_data)

        tables.append({
            "BoundingBox": {
                "Top": top,
                "Left": left
            },
            "DataFrame": df
        })

    return tables

def sort_tables(tables, left_threshold=0.05):
    """
    Sorts tables based on their column grouping and top positions.

    Args:
        tables (list of dict): List of tables with bounding box and DataFrame.
        left_threshold (float): Threshold to group tables into the same column.

    Returns:
        list of dict: Sorted list of tables.
    """
    if not tables:
        return []

    # Sort tables by Left position
    tables_sorted_left = sorted(tables, key=lambda x: x["BoundingBox"]["Left"])

    # Group tables into columns based on Left positions
    columns = []
    current_column = []
    previous_left = None

    for table in tables_sorted_left:
        left = table["BoundingBox"]["Left"]
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
        column.sort(key=lambda x: x["BoundingBox"]["Top"])

    # Flatten the sorted columns into a single list
    sorted_tables = []
    for column in columns:
        sorted_tables.extend(column)

    return sorted_tables

def save_tables_to_excel(textract_response_path, output_excel_path):
    # Load the raw Textract JSON response
    with open(textract_response_path, "r") as f:
        textract_response = json.load(f)

    # Extract tables from the JSON
    tables = extract_tables(textract_response)

    if not tables:
        print("No tables found in the document.")
        return

    # Sort tables based on their positions
    sorted_tables = sort_tables(tables)

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_excel_path), exist_ok=True)

    # Initialize an Excel writer
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        for idx, table in enumerate(sorted_tables, start=1):
            try:
                df = table["DataFrame"]
                sheet_name = f"Table_{idx}"
                df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            except Exception as e:
                print(f"Error processing Table {idx}: {e}")

    print(f"Tables have been successfully saved to {output_excel_path}")



def getExcel(namespace, page_number, table_number):
    namespace = checkNamespace(namespace)
    if not namespace:
        return f"No namespace found for '{namespace}'."
    current_path = os.getcwd()
    print(f"Current Path: {current_path}\n")
    page_number = int(page_number) - 1
    table_number = int(table_number)
    """
    Saves tables extracted from a specific page of a Textract JSON file to an Excel file and provides relevant info.

    Args:
        namespace (str): The namespace for the JSON file.
        page_number (int): The 0-indexed page number.
        table_number (int): The specific table number to reference, or -1 to save all tables.

    Returns:
        str: A string with information about the saved table(s) and file location.
    """
    # Construct the JSON file path
    json_path = f"PDF_Extraction/AWS_Textract/Cache/{namespace}_{page_number}.json"
    output_excel_path = f"PDF_Extraction/AWS_Textract/GET/{namespace}_page{page_number}_tables.xlsx"

    # Check if the JSON file exists
    if not os.path.exists(json_path):
        return f"No JSON file found for namespace '{namespace}' and page {page_number}."

    # Load the raw Textract JSON response
    with open(json_path, "r") as f:
        textract_response = json.load(f)

    # Extract tables from the JSON
    tables = extract_tables(textract_response)

    if not tables:
        return f"No tables found on page {page_number}."

    # Sort tables based on their positions
    sorted_tables = sort_tables(tables)

    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_excel_path), exist_ok=True)

    # Save tables to Excel
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        for idx, table in enumerate(sorted_tables, start=1):
            try:
                df = table["DataFrame"]
                sheet_name = f"Table_{idx}"
                df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
            except Exception as e:
                return f"Error processing Table {idx}: {e}"

    if table_number == -1:
        response = f"All tables saved. File is available at: localhost:5151/{namespace}_page{page_number}_tables.xlsx"
    elif 1 <= table_number <= len(sorted_tables):
        response = f"Table {table_number} is in sheet Table_{table_number}. File is available at: localhost:5151/{namespace}_page{page_number}_tables.xlsx"
    else:
        response = f"No table {table_number} found on page {page_number}. File is available at: localhost:5151/{namespace}_page{page_number}_tables.xlsx"

    return response


if __name__ == "__main__":
    namespace = "test2"
    page_number = "4"
    table_number = "-1"

    print(getExcel(namespace, page_number, table_number))
