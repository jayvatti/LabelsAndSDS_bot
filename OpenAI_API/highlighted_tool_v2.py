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
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: File '{json_filepath}' is not valid JSON.")
        sys.exit(1)

    # Sort the data by 'Score' in descending order
    sorted_data = sorted(data, key=lambda x: x.get('Score', 0), reverse=True)

    return sorted_data

def clean_text(text):
    """
    Remove tags like <HEADING>, <BOLD>, etc., and remove table content.

    Args:
        text (str): The original text with tags.

    Returns:
        str: Cleaned text without specified tags and table content.
    """
    if not text:
        return ""
    # Remove table content
    text = re.sub(r'<TABLE EXTRACT.*?>.*?<TABLE EXTRACT\s*/>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove other tags
    text = re.sub(r'<[^>]+>', '', text)
    return text

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
        with open(json_filename, 'r', encoding='utf-8') as f:
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
        fitz.Rect: Converted bounding box or None if conversion fails.
    """
    try:
        x0 = bbox['Left'] * page_rect.width
        y0 = bbox['Top'] * page_rect.height
        width = bbox['Width'] * page_rect.width
        height = bbox['Height'] * page_rect.height
        x1 = x0 + width
        y1 = y0 + height
        # Ensure coordinates are within page bounds
        x0 = max(0, min(x0, page_rect.width))
        y0 = max(0, min(y0, page_rect.height))
        x1 = max(0, min(x1, page_rect.width))
        y1 = max(0, min(y1, page_rect.height))
        return fitz.Rect(x0, y0, x1, y1)
    except KeyError as e:
        print(f"Error: Missing key in bounding box: {e}")
        return None

def preprocess_text(text):
    """
    Lowercase, remove punctuation, and normalize whitespace.

    Args:
        text (str): The original text.

    Returns:
        str: Preprocessed text.
    """
    if not text:
        return ""
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
    if not original_text:
        return []
    original_lines = [line.strip() for line in original_text.split('\n') if line.strip()]
    preprocessed_lines = [preprocess_text(line) for line in original_lines]
    return list(zip(original_lines, preprocessed_lines))

def group_rects(rects, max_vertical_distance=70):
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

def log_matched_lines(section_idx, target_line, matched_line, similarity, page_num):
    """
    Logs the details of matched lines for debugging purposes.

    Args:
        section_idx (int): Index of the text section.
        target_line (str): The original target line.
        matched_line (str): The line that was matched.
        similarity (int): Similarity score.
        page_num (int): Current page number.
    """
    print(f"  [Page {page_num}] Section {section_idx}:")
    print(f"    Target Line: '{target_line}'")
    print(f"    Matched Line: '{matched_line}' (Similarity: {similarity})")

# Main Execution

if __name__ == "__main__":
    # Paths
    text_sections_json = 'vectorRes.json'
    pdf_name = 'AccordXRT2.pdf'  # Replace with your actual PDF file name if different
    pdf_path = f'../PDF_Extraction/AWS_Textract/Inputs/{pdf_name}'
    output_pdf_path = '../PDF_Extraction/AWS_Textract/GET/highlighted.pdf'

    # Load and sort data
    sorted_data = load_and_sort_data(text_sections_json)

    if not sorted_data:
        print("No data found in the JSON file. Exiting.")
        sys.exit(1)

    # Highlight colors
    highlight_colors = [
        (1, 1, 0),        # Yellow
        (0.5, 1, 0.5),    # Light Green
        (1, 0.75, 0.8),   # Light Pink
        (0.5, 0.5, 1),    # Light Blue
        (1, 0.5, 1),      # Magenta
        (0.5, 1, 1),      # Cyan
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

    # Create a mapping from page number (0-indexed) to list of text entry indices
    page_to_texts = defaultdict(list)
    for idx, entry in enumerate(sorted_data):
        pages = entry.get('Pages', [])
        if not isinstance(pages, list):
            print(f"Warning: 'Pages' for entry {idx} is not a list. Skipping this entry.")
            continue
        for page in pages:
            if isinstance(page, int):
                zero_indexed_page = page  # Pages are zero-indexed
                if 0 <= zero_indexed_page < num_pages:
                    page_to_texts[zero_indexed_page].append(idx)
                else:
                    print(f"Warning: Page number {page} for entry {idx} is out of range.")
            else:
                print(f"Warning: Page number {page} for entry {idx} is not an integer.")

    if not page_to_texts:
        print("No page mappings found. Exiting.")
        sys.exit(1)

    # Preprocess all text entries
    preprocessed_entries = []
    for idx, entry in enumerate(sorted_data):
        cleaned_text = clean_text(entry.get('Text', ''))
        split_text = split_into_lines(cleaned_text)
        preprocessed_entries.append(split_text)

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

        # Extract lines and their bounding boxes for this page
        lines = [block for block in textract_data.get('Blocks', []) if block.get('BlockType') == 'LINE']

        if not lines:
            print(f"  No text lines found on page {pdf_page_number}. Skipping annotation.")
            continue

        # Preprocess Textract lines
        for line in lines:
            line['ProcessedText'] = preprocess_text(line.get('Text', ''))

        # Get the list of text entries for this page
        text_indices = page_to_texts[page_idx]

        # Initialize matched_bboxes for each text entry
        matched_bboxes = {idx: [] for idx in text_indices}

        for section_idx in text_indices:
            target_lines = preprocessed_entries[section_idx]
            original_target_lines = [orig for orig, proc in preprocessed_entries[section_idx]]
            for target_line_original, target_line_processed in target_lines:
                target_length = len(target_line_processed)
                if target_length == 0:
                    continue

                min_length = max(int(target_length * 0.8), 1)  # Ensure at least 1
                max_length = int(target_length * 1.2)

                candidate_indices = [
                    idx for idx, line in enumerate(lines)
                    if min_length <= len(line['ProcessedText']) <= max_length
                ]

                # If no candidates are found, consider all lines
                if not candidate_indices:
                    candidate_indices = list(range(len(lines)))
                    candidate_texts = [line['ProcessedText'] for line in lines]
                else:
                    candidate_texts = [lines[idx]['ProcessedText'] for idx in candidate_indices]

                # Perform fuzzy matching
                best_match = process.extractOne(
                    target_line_processed,
                    candidate_texts,
                    scorer=fuzz.token_set_ratio
                )

                if best_match:
                    match_text, similarity, match_idx = best_match
                    actual_match_idx = candidate_indices[match_idx]
                    matched_original_text = lines[actual_match_idx].get('Text', '').strip()

                    # Log matched lines for debugging
                    log_matched_lines(section_idx, target_line_original, matched_original_text, similarity, pdf_page_number)

                    if similarity >= threshold:
                        bbox = lines[actual_match_idx].get('Geometry', {}).get('BoundingBox', {})
                        if bbox:
                            page = pdf_document[page_idx]
                            page_rect = page.rect
                            rect = convert_bbox(bbox, page_rect)
                            if rect:
                                matched_bboxes[section_idx].append(rect)
                            else:
                                print(f"    Failed to convert bounding box for matched line: '{matched_original_text}'")
                        else:
                            print(f"    No bounding box found for matched line: '{matched_original_text}'")
                    else:
                        print(f"    Low similarity ({similarity}) for line: '{target_line_original}'")
                else:
                    print(f"    No match found for line: '{target_line_original}'")

        # Highlight matches for each text entry
        for section_idx, rects in matched_bboxes.items():
            if not rects:
                print(f"  No bounding boxes matched for section {section_idx} on page {pdf_page_number}.")
                continue

            groups = group_rects(rects, max_vertical_distance=50)

            highlight_color = color_mapping[section_idx]

            for group in groups:
                # Calculate the encompassing rectangle for the group
                x0 = min(rect.x0 for rect in group)
                y0 = min(rect.y0 for rect in group)
                x1 = max(rect.x1 for rect in group)
                y1 = max(rect.y1 for rect in group)

                encompassing_rect = fitz.Rect(x0, y0, x1, y1)

                # Validate the rectangle
                if not encompassing_rect.is_valid:
                    print(f"    Invalid rectangle for section {section_idx} on page {pdf_page_number}. Skipping.")
                    continue

                # Add the rectangle annotation
                try:
                    annot = pdf_document[page_idx].add_rect_annot(encompassing_rect)
                    annot.set_colors(stroke=highlight_color, fill=highlight_color)
                    annot.set_border(width=0)
                    annot.set_opacity(0.3)
                    annot.update()
                except Exception as e:
                    print(f"    Error adding annotation: {e}")
                    continue

            print(f"  Highlighted section {section_idx} on page {pdf_page_number}.")

        print(f"Completed processing page {pdf_page_number}.")

    # Save the modified PDF
    try:
        pdf_document.save(output_pdf_path, garbage=4, deflate=True)
        print(f"All annotations added and saved to '{output_pdf_path}'.")
    except Exception as e:
        print(f"Error saving PDF file: {e}")
        sys.exit(1)
