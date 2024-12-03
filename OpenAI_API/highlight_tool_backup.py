import re
import json
import fitz  # PyMuPDF
from rapidfuzz import fuzz, process
import os
import sys
from collections import defaultdict

# Function Definitions

def load_and_sort_data(json_filepath):
    """
    Loads text sections from a JSON file and sorts them by score in descending order.

    Args:
        json_filepath (str): Path to the JSON file containing text sections.

    Returns:
        list of dict: Sorted list of text entries with 'Text' and 'Pages'.
    """
    if not os.path.isfile(json_filepath):
        print(f"Error: JSON file '{json_filepath}' not found.")
        sys.exit(1)

    try:
        with open(json_filepath, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: File '{json_filepath}' is not valid JSON.")
        sys.exit(1)

    # Sort the data by 'Score' in descending order
    sorted_data = sorted(data, key=lambda x: x.get('Score', 0), reverse=True)

    return sorted_data

def clean_text_and_extract_tables(text):
    """
    Extract table content and remove tags like <HEADING>, <BOLD>, etc.

    Args:
        text (str): The original text with tags.

    Returns:
        tuple: (cleaned_text, table_contents)
            cleaned_text: Text without specified tags and table content.
            table_contents: List of table content strings.
    """
    # Extract table content
    table_contents = re.findall(r'<TABLE EXTRACT.*?>(.*?)<TABLE EXTRACT\s*/>', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove table content from text
    text = re.sub(r'<TABLE EXTRACT.*?>.*?<TABLE EXTRACT\s*/>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove other tags
    text = re.sub(r'<[^>]+>', '', text)
    return text, table_contents

def load_textract_json(page_number):
    """
    Loads the Textract JSON file for the given page number.
    Textract JSON files are named as 'test2_{page_number}.json' where page_number is 0-indexed.

    Args:
        page_number (int): The zero-based page number.

    Returns:
        dict or None: The loaded JSON data or None if file not found or invalid.
    """
    json_filename = f'../PDF_Extraction/AWS_Textract/Cache/test2_{page_number}.json'  # Updated path
    if not os.path.isfile(json_filename):
        print(f"Warning: Textract JSON file '{json_filename}' not found. Skipping page {page_number + 1}.")
        return None
    try:
        with open(json_filename, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: File '{json_filename}' is not valid JSON. Skipping page {page_number + 1}.")
        return None

def convert_bbox(bbox, page_rect):
    """
    Converts Textract bounding box to PyMuPDF's coordinate system.
    Textract provides normalized coordinates (0 to 1).

    Args:
        bbox (dict): Bounding box with 'Left', 'Top', 'Width', 'Height'.
        page_rect (fitz.Rect): The page rectangle from PyMuPDF.

    Returns:
        fitz.Rect: Converted bounding box.
    """
    x0 = bbox['Left'] * page_rect.width
    y0 = bbox['Top'] * page_rect.height
    width = bbox['Width'] * page_rect.width
    height = bbox['Height'] * page_rect.height
    x1 = x0 + width
    y1 = y0 + height
    return fitz.Rect(x0, y0, x1, y1)

def preprocess_text(text):
    """
    Lowercase, remove punctuation, and normalize whitespace.

    Args:
        text (str): The original text.

    Returns:
        str: Preprocessed text.
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace to single spaces
    return text.strip()

def split_into_lines(original_text):
    """
    Splits the original text into lines and preprocesses each line.
    Returns a list of tuples: (original_line, preprocessed_line)

    Args:
        original_text (str): The cleaned text.

    Returns:
        list of tuples: List containing (original_line, preprocessed_line).
    """
    original_lines = [line.strip() for line in original_text.split('\n') if line.strip()]
    preprocessed_lines = [preprocess_text(line) for line in original_lines]
    return list(zip(original_lines, preprocessed_lines))

def preprocess_table_contents(table_contents):
    preprocessed_tables = []
    for table_content in table_contents:
        preprocessed_text = preprocess_text(table_content)
        preprocessed_tables.append(preprocessed_text)
    return preprocessed_tables

def get_table_text(table_block, blocks_map):
    """
    Extract text content from a table block.

    Args:
        table_block (dict): The table block from Textract.
        blocks_map (dict): A mapping from block ID to block.

    Returns:
        str: The concatenated text content of the table.
    """
    table_text = ''
    if 'Relationships' in table_block:
        for rel in table_block['Relationships']:
            if rel['Type'] == 'CHILD':
                for child_id in rel['Ids']:
                    cell_block = blocks_map.get(child_id)
                    if cell_block and cell_block['BlockType'] == 'CELL':
                        # Cells have their own CHILD relationships to 'WORD' blocks
                        cell_text = ''
                        if 'Relationships' in cell_block:
                            for cell_rel in cell_block['Relationships']:
                                if cell_rel['Type'] == 'CHILD':
                                    for word_id in cell_rel['Ids']:
                                        word_block = blocks_map.get(word_id)
                                        if word_block and word_block['BlockType'] == 'WORD':
                                            cell_text += word_block.get('Text', '') + ' '
                        table_text += cell_text.strip() + ' '
    return table_text.strip()

def get_table_bounding_box(table_block, blocks_map, page_rect):
    """
    Get the bounding box of a table by combining the bounding boxes of its cells.

    Args:
        table_block (dict): The table block from Textract.
        blocks_map (dict): A mapping from block ID to block.
        page_rect (fitz.Rect): The page rectangle.

    Returns:
        fitz.Rect: The combined bounding box of the table.
    """
    cells = []
    if 'Relationships' in table_block:
        for rel in table_block['Relationships']:
            if rel['Type'] == 'CHILD':
                for child_id in rel['Ids']:
                    cell_block = blocks_map.get(child_id)
                    if cell_block and cell_block['BlockType'] == 'CELL':
                        bbox = cell_block.get('Geometry', {}).get('BoundingBox', {})
                        if bbox:
                            rect = convert_bbox(bbox, page_rect)
                            cells.append(rect)
    if cells:
        x0 = min(rect.x0 for rect in cells)
        y0 = min(rect.y0 for rect in cells)
        x1 = max(rect.x1 for rect in cells)
        y1 = max(rect.y1 for rect in cells)
        return fitz.Rect(x0, y0, x1, y1)
    else:
        return None

def group_rects(rects, max_vertical_distance=50):
    """
    Groups rectangles that are vertically close to each other.

    Args:
        rects (list of fitz.Rect): List of rectangles to group.
        max_vertical_distance (int): Maximum vertical distance to consider for grouping.

    Returns:
        list of list of fitz.Rect: Grouped rectangles.
    """
    if not rects:
        return []

    # Sort rectangles by y0 (top) then x0 (left)
    sorted_rects = sorted(rects, key=lambda r: (r.y0, r.x0))

    groups = []
    current_group = [sorted_rects[0]]

    for rect in sorted_rects[1:]:
        last_rect = current_group[-1]
        # Calculate the vertical distance between the current rect and the last rect in the group
        vertical_distance = rect.y0 - last_rect.y1
        if vertical_distance < max_vertical_distance:
            current_group.append(rect)
        else:
            groups.append(current_group)
            current_group = [rect]

    groups.append(current_group)
    return groups

# Main Execution

if __name__ == "__main__":
    # Paths
    text_sections_json = 'vectorRes.json'
    pdf_name = 'AccordXRT2.pdf'  # Replace with your actual PDF file name if different
    pdf_path = f'../PDF_Extraction/AWS_Textract/Inputs/{pdf_name}'
    output_pdf_path = '../PDF_Extraction/AWS_Textract/GET/highlighted.pdf'

    # Load and sort data
    sorted_data = load_and_sort_data(text_sections_json)

    # Highlight colors
    highlight_colors = [
        (1, 1, 0),  # Yellow
        (0.5, 1, 0.5),  # Light Green
        (1, 0.75, 0.8),  # Light Pink
        (0.5, 0.5, 1),  # Light Blue
        (1, 0.5, 1),  # Magenta
        (0.5, 1, 1),  # Cyan
    ]
    color_mapping = {idx: highlight_colors[idx % len(highlight_colors)] for idx in range(len(sorted_data))}

    # Similarity threshold
    threshold = 70  # You can adjust this if needed

    # Open the PDF
    try:
        pdf_document = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF file: {e}")
        sys.exit(1)

    num_pages = len(pdf_document)
    print(f"Total pages in PDF: {num_pages}")

    # Create a mapping from page number to list of text entry indices
    page_to_texts = defaultdict(list)
    for idx, entry in enumerate(sorted_data):
        for page in entry.get('Pages', []):
            page_to_texts[page].append(idx)

    # Preprocess all text entries
    preprocessed_entries = []
    for idx, entry in enumerate(sorted_data):
        cleaned_text, table_contents = clean_text_and_extract_tables(entry.get('Text', ''))
        split_text = split_into_lines(cleaned_text)
        preprocessed_tables = preprocess_table_contents(table_contents)
        color = color_mapping[idx]
        preprocessed_entries.append({
            'split_text': split_text,
            'table_contents': preprocessed_tables,
            'pages': entry.get('Pages', []),
            'color': color
        })

    # Process each page
    for page_idx in range(num_pages):
        pdf_page_number = page_idx + 1
        print(f"Processing page {pdf_page_number}/{num_pages}.")

        # Check if any text entries are associated with this page
        if page_idx not in page_to_texts:
            print(f"  No text entries associated with page {pdf_page_number}. Skipping.")
            continue

        # Load corresponding Textract JSON
        textract_data = load_textract_json(page_idx)
        if not textract_data:
            continue

        # Build a map from block ID to block
        blocks_map = {block['Id']: block for block in textract_data.get('Blocks', [])}

        # Extract lines and their bounding boxes for this page
        lines = [block for block in textract_data.get('Blocks', []) if block.get('BlockType') == 'LINE']

        if not lines:
            print(f"  No text lines found on page {pdf_page_number}. Skipping annotation.")
            continue

        # Preprocess Textract lines
        for line in lines:
            line['ProcessedText'] = preprocess_text(line.get('Text', ''))

        # Extract tables and their bounding boxes for this page
        tables = [block for block in textract_data.get('Blocks', []) if block.get('BlockType') == 'TABLE']

        if tables:
            # Preprocess Textract tables
            for table in tables:
                table_text = get_table_text(table, blocks_map)
                table['ProcessedText'] = preprocess_text(table_text)
        else:
            print(f"  No tables found on page {pdf_page_number}.")

        # Get the list of text entries for this page
        text_indices = page_to_texts[page_idx]

        for section_idx in text_indices:
            entry = preprocessed_entries[section_idx]
            target_lines = entry['split_text']
            target_tables = entry['table_contents']
            highlight_color = entry['color']

            matched_bboxes = []  # For text lines
            matched_table_bboxes = []  # For tables

            # Process text lines as before
            for target_line_original, target_line_processed in target_lines:
                target_length = len(target_line_processed)
                if target_length == 0:
                    continue

                min_length = int(target_length * 0.8)
                max_length = int(target_length * 1.2)

                candidate_indices = [
                    idx for idx, line in enumerate(lines)
                    if min_length <= len(line['ProcessedText']) <= max_length
                ]

                if not candidate_indices:
                    print(f"    No candidates for line: '{target_line_original}'")
                    continue

                candidate_texts = [lines[idx]['ProcessedText'] for idx in candidate_indices]

                best_match = process.extractOne(
                    target_line_processed,
                    candidate_texts,
                    scorer=fuzz.token_set_ratio
                )

                if best_match:
                    match_text, similarity, match_idx = best_match
                    actual_match_idx = candidate_indices[match_idx]
                    matched_original_text = lines[actual_match_idx].get('Text', '').strip()

                    if similarity >= threshold:
                        bbox = lines[actual_match_idx].get('Geometry', {}).get('BoundingBox', {})
                        if bbox:
                            page = pdf_document[page_idx]
                            page_rect = page.rect
                            rect = convert_bbox(bbox, page_rect)
                            matched_bboxes.append(rect)
                    else:
                        print(f"    Low similarity ({similarity}) for line: '{target_line_original}'")
                else:
                    print(f"    No match found for line: '{target_line_original}'")

            # Process tables
            for target_table in target_tables:
                target_length = len(target_table)
                if target_length == 0:
                    continue

                min_length = int(target_length * 0.8)
                max_length = int(target_length * 1.2)

                candidate_tables = [
                    table for table in tables
                    if min_length <= len(table['ProcessedText']) <= max_length
                ]

                if not candidate_tables:
                    print(f"    No candidate tables for table content of length {target_length}.")
                    continue

                candidate_texts = [table['ProcessedText'] for table in candidate_tables]

                best_match = process.extractOne(
                    target_table,
                    candidate_texts,
                    scorer=fuzz.token_set_ratio
                )

                if best_match:
                    match_text, similarity, match_idx = best_match
                    matched_table = candidate_tables[match_idx]

                    if similarity >= threshold:
                        page = pdf_document[page_idx]
                        page_rect = page.rect
                        bbox = get_table_bounding_box(matched_table, blocks_map, page_rect)
                        if bbox:
                            matched_table_bboxes.append(bbox)
                    else:
                        print(f"    Low similarity ({similarity}) for table content.")
                else:
                    print(f"    No match found for table content.")

            # Now, highlight matches for text lines
            if matched_bboxes:
                groups = group_rects(matched_bboxes, max_vertical_distance=50)

                for group in groups:
                    x0 = min(rect.x0 for rect in group)
                    y0 = min(rect.y0 for rect in group)
                    x1 = max(rect.x1 for rect in group)
                    y1 = max(rect.y1 for rect in group)

                    encompassing_rect = fitz.Rect(x0, y0, x1, y1)

                    annot = pdf_document[page_idx].add_rect_annot(encompassing_rect)
                    annot.set_colors(stroke=highlight_color, fill=highlight_color)
                    annot.set_border(width=0)
                    annot.set_opacity(0.3)
                    annot.update()

            # Now, draw borders around matched tables
            for rect in matched_table_bboxes:
                page = pdf_document[page_idx]
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=highlight_color)
                annot.set_border(width=2)  # Adjust the border width as needed
                annot.set_opacity(1)  # Full opacity
                annot.update()

        print(f"Completed processing page {pdf_page_number}.")

    # Save the modified PDF
    try:
        pdf_document.save(output_pdf_path)
        print(f"All annotations added and saved to '{output_pdf_path}'.")
    except Exception as e:
        print(f"Error saving PDF file: {e}")
        sys.exit(1)
