import argparse
import os
from difflib import SequenceMatcher

from PIL import Image
from dotenv import load_dotenv
import json
import boto3
from pdf2image import convert_from_path
from collections import defaultdict, Counter
from typing import List, Dict, Any, Union, Tuple
import fitz
import re


def extract_single_page_as_png(pdf_filepath: str, page_number: int, output_filepath: str) -> None:
    images = convert_from_path(pdf_filepath, first_page=page_number + 1, last_page=page_number + 1)

    if images:
        image = images[0]
        image.save(output_filepath, 'PNG')
        print(f"Page {page_number} saved as {output_filepath}")
    else:
        print(f"Page {page_number} not found in the PDF.")


def extract_png_with_cache(pdf_filepath: str, page_number: int, client: boto3.client, filepath: str) -> Dict[str, Any]:
    pdf_filename = os.path.splitext(os.path.basename(pdf_filepath))[0]

    cache_dir = os.path.join("Cache")
    json_file_path = os.path.join(cache_dir, f"{pdf_filename}_{page_number}.json")

    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as json_file:
            print(f"Loading cached data from {json_file_path}")
            return json.load(json_file)
    else:
        os.makedirs(cache_dir, exist_ok=True)

        with open(filepath, 'rb') as file:
            img_test = file.read()
            bytes_test = bytearray(img_test)

        response = client.analyze_document(Document={'Bytes': bytes_test}, FeatureTypes=['TABLES', 'FORMS'])

        with open(json_file_path, 'w') as json_file:
            json.dump(response, json_file)

        print(f"Cached data created at {json_file_path}")
        return response


def bbox_overlap(bbox1: Dict[str, float], bbox2: Dict[str, float]) -> bool:
    left1, right1 = bbox1['Left'], bbox1['Left'] + bbox1['Width']
    top1, bottom1 = bbox1['Top'], bbox1['Top'] + bbox1['Height']
    left2, right2 = bbox2['Left'], bbox2['Left'] + bbox2['Width']
    top2, bottom2 = bbox2['Top'], bbox2['Top'] + bbox2['Height']

    return not (left1 >= right2 or left2 >= right1 or top1 >= bottom2 or top2 >= bottom1)


def is_title(line_block: Dict[str, Any], max_line_height: float, top_threshold: float) -> bool:
    line_bbox = line_block['Geometry']['BoundingBox']
    line_height, line_top = line_bbox['Height'], line_bbox['Top']
    is_max_height = line_height >= max_line_height * 0.9
    is_top_of_page = line_top <= top_threshold
    return is_max_height and is_top_of_page


def json_to_text(response: Dict[str, Any], image_path: str, output_dir: str, pdf_name: str, page_number: int, padding: int = 10) -> str:
    def extract_tables(blocks_map: Dict[str, Any], table_block: Dict[str, Any]) -> List[List[Union[str, None]]]:
        table: List[List[Union[str, None]]] = []
        if 'Relationships' in table_block:
            for relationship in table_block['Relationships']:
                if relationship['Type'] == 'CHILD':
                    for cell_id in relationship['Ids']:
                        cell_block = blocks_map[cell_id]
                        if cell_block['BlockType'] == 'CELL':
                            cell_text = ""
                            if 'Relationships' in cell_block:
                                for cell_relationship in cell_block['Relationships']:
                                    if cell_relationship['Type'] == 'CHILD':
                                        for child_id in cell_relationship['Ids']:
                                            word_block = blocks_map[child_id]
                                            if word_block['BlockType'] == 'WORD':
                                                cell_text += word_block['Text'] + " "
                            row_index = cell_block['RowIndex']
                            col_index = cell_block['ColumnIndex']
                            while len(table) < row_index:
                                table.append([])
                            while len(table[row_index - 1]) < col_index:
                                table[row_index - 1].append(None)
                            table[row_index - 1][col_index - 1] = cell_text.strip().lower()  # Convert to lowercase
        return table

    def map_bbox_to_pixels(bbox, image_width, image_height):
        left = bbox['Left'] * image_width
        top = bbox['Top'] * image_height
        width = bbox['Width'] * image_width
        height = bbox['Height'] * image_height
        return left, top, left + width, top + height

    # Read the image
    image = Image.open(image_path)
    image_width, image_height = image.size

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Initialize table count
    table_count = 0

    blocks_map = {block['Id']: block for block in response['Blocks']}
    table_bboxes = [block['Geometry']['BoundingBox'] for block in response['Blocks'] if block['BlockType'] == 'TABLE']

    blocks_with_position = []
    line_heights: List[float] = []
    max_line_height = 0.0

    for block in response['Blocks']:
        if block['BlockType'] in ['LINE', 'TABLE']:
            bbox = block['Geometry']['BoundingBox']
            top, left = bbox['Top'], bbox['Left']
            block_info = {
                'BlockType': block['BlockType'],
                'Top': top,
                'Left': left,
                'Block': block,
                'BoundingBox': bbox
            }
            if block['BlockType'] == 'LINE':
                line_height = bbox['Height']
                line_heights.append(line_height)
                max_line_height = max(max_line_height, line_height)
            blocks_with_position.append(block_info)

    top_threshold = 0.2

    def kmeans_1d(data: List[float], k: int = 2, max_iterations: int = 100) -> List[float]:
        centroids = [min(data), max(data)]
        for _ in range(max_iterations):
            clusters = [[] for _ in range(k)]
            for value in data:
                distances = [abs(value - c) for c in centroids]
                clusters[distances.index(min(distances))].append(value)
            new_centroids = [sum(cluster) / len(cluster) if cluster else centroids[i] for i, cluster in
                             enumerate(clusters)]
            if new_centroids == centroids:
                break
            centroids = new_centroids
        return centroids

    left_positions = [block_info['Left'] for block_info in blocks_with_position]
    centroids = kmeans_1d(left_positions, k=2)

    # New: Determine the number of columns based on centroid distance and cluster sizes
    def determine_column_count(blocks_with_position, centroids, threshold_distance=0.1, min_cluster_ratio=0.2) -> int:
        # Assign blocks to clusters
        clusters = defaultdict(list)
        for block_info in blocks_with_position:
            left = block_info['Left']
            distance = [abs(left - c) for c in centroids]
            cluster = distance.index(min(distance))
            clusters[cluster].append(block_info)

        # Calculate the ratio of each cluster
        total_blocks = len(blocks_with_position)
        for cluster_id, blocks in clusters.items():
            if len(blocks) / total_blocks < min_cluster_ratio:
                return 1  # Single column
        # Check distance between centroids
        distance_between_centroids = abs(centroids[0] - centroids[1])
        if distance_between_centroids < threshold_distance:
            return 1  # Single column
        return 2  # Two columns

    num_columns = determine_column_count(blocks_with_position, centroids)

    if num_columns == 1:
        # Assign all blocks to a single column
        columns = defaultdict(list)
        for block_info in blocks_with_position:
            columns[0].append(block_info)
        sorted_columns = [0]
    else:
        # Assign blocks to columns based on centroids
        # Assign 'center' column if Left is between 0.45 and 0.55
        columns = defaultdict(list)
        for block_info in blocks_with_position:
            left = block_info['Left']
            if 0.45 <= left <= 0.55:
                columns['center'].append(block_info)
            else:
                # Assign to the nearest centroid
                distances = [abs(left - c) for c in centroids]
                cluster = distances.index(min(distances))
                columns[cluster].append(block_info)

        # Build column_centroids mapping
        column_centroids: Dict[Union[int, str], float] = {}
        for idx, centroid in enumerate(centroids):
            column_centroids[idx] = centroid
        if 'center' in columns:
            column_centroids['center'] = 0.5  # Center of the page

        # Sort columns based on centroids
        sorted_columns = sorted(columns.keys(), key=lambda k: column_centroids[k])

    title_found = False
    extracted_text: List[str] = []

    for col_key in sorted_columns:
        column_blocks = columns[col_key]
        # Sort blocks within the column by 'Top' position
        column_blocks.sort(key=lambda x: x['Top'])
        for block_info in column_blocks:
            block_type = block_info['BlockType']
            block = block_info['Block']
            if block_type == 'LINE':
                line_bbox = block_info['BoundingBox']
                overlaps_table = any(
                    bbox_overlap(line_bbox, table_bbox) for table_bbox in table_bboxes)
                if not overlaps_table:
                    if not title_found and is_title(block, max_line_height, top_threshold):
                        # Increment page_number by 1 for output
                        extracted_text.append(f"{block['Text'].lower()} {{['TITLE EXTRACT']}}")  # Convert to lowercase
                        title_found = True
                    else:
                        extracted_text.append(block['Text'].lower())  # Convert to lowercase
            elif block_type == 'TABLE':
                table_count += 1
                table = extract_tables(blocks_map, block)
                # Increment page_number by 1 for output
                extracted_text.append(f"<TABLE EXTRACT (TABLE NUMBER = {table_count}, PAGE NUMBER = {page_number +1})>")
                # Convert each row's text to lowercase
                extracted_text.extend(str(row).lower() for row in table)
                # Now, get the bounding box
                bbox = block_info['BoundingBox']
                # Map bbox to pixels
                left, top, right, bottom = map_bbox_to_pixels(bbox, image_width, image_height)
                # Add padding
                left_padded = max(left - padding, 0)
                top_padded = max(top - padding, 0)
                right_padded = min(right + padding, image_width)
                bottom_padded = min(bottom + padding, image_height)
                # Crop the image
                cropped_image = image.crop((left_padded, top_padded, right_padded, bottom_padded))
                # Prepare output filename
                output_filename = f"{pdf_name}_{page_number}_table_{table_count}.png"
                output_file = os.path.join(output_dir, output_filename)
                # Save the cropped image
                cropped_image.save(output_file)
                print(f"Cropped table image saved to {output_file}")
                # Include the image file path in the extracted_text
                image_url = f"localhost:5151/{output_filename}"
                extracted_text.append(f"table extracted to {image_url}")  # Convert to lowercase
                extracted_text.append("<TABLE EXTRACT />")

    return "\n".join(extracted_text)


def extract_headings_and_bold_text(pdf_page: str, page_number: int) -> str:
    pdf_document = fitz.open(pdf_page)
    page = pdf_document.load_page(page_number)
    blocks = page.get_text("dict").get('blocks', [])

    sizes = [span.get('size', 0) for block in blocks for line in block.get('lines', []) for span in
             line.get('spans', [])]
    colors = [span.get('color', '') for block in blocks for line in block.get('lines', []) for span in
              line.get('spans', [])]

    regular_size = Counter(sizes).most_common(1)[0][0]
    regular_color = Counter(colors).most_common(1)[0][0]
    size_threshold = regular_size * 1.2

    tagged_spans: List[Tuple[str, str]] = []
    page_height = page.rect.height  # Get the height of the page
    bottom_threshold_ratio = 0.05  # Define threshold (e.g., bottom 5% of the page)
    bottom_threshold = page_height * bottom_threshold_ratio

    for block in blocks:
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text = span.get('text', '').strip().lower()  # Convert to lowercase
                size = span.get('size', 0)
                color = span.get('color', '')
                flags = span.get('flags', 0)
                bbox = span.get('bbox', [0, 0, 0, 0])  # [x0, y0, x1, y1]
                y1 = bbox[3]  # Bottom y-coordinate of the span

                is_heading = size >= size_threshold or color != regular_color or (flags == 20 and size > regular_size)

                # Initialize a flag to determine if the span should be tagged
                should_tag = False

                if is_heading and text != '':
                    # Check if it's a potential page number at the bottom
                    if flags == 20:
                        is_page_number = (
                            text.isdigit() and
                            int(text) == (page_number + 1) and
                            y1 >= page_height - bottom_threshold
                        )
                        # Additionally, ensure the span contains only the page number without extra text
                        if is_page_number:
                            # Do not tag as HEADING
                            pass
                        else:
                            # Tag as HEADING
                            tagged_spans.append((text, 'HEADING'))
                    else:
                        # Tag as HEADING
                        tagged_spans.append((text, 'HEADING'))
                elif flags == 20 and text != '':
                    # Check if it's a potential page number at the bottom
                    is_page_number = (
                        text.isdigit() and
                        int(text) == (page_number + 1) and
                        y1 >= page_height - bottom_threshold
                    )
                    # Additionally, ensure the span contains only the page number without extra text
                    if is_page_number:
                        # Do not tag as BOLD
                        pass
                    else:
                        # Tag as BOLD
                        tagged_spans.append((text, 'BOLD'))

    pdf_document.close()

    return "\n".join(
        f"<{tag} (PAGE NUMBER = {page_number +1})>{text}< {tag} />" if tag == 'HEADING' else
        f"<{tag} (PAGE NUMBER = {page_number +1})>{text}</{tag}>" if tag == 'BOLD' else
        f"<{tag}>{text}</{tag}>"
        for text, tag in tagged_spans
    )


def is_similar(a, b, threshold=0.8):
    return SequenceMatcher(None, a, b).ratio() >= threshold


def replace_headings(parsed_output: str, tagged_text: str, page_number: int) -> str:
    # Build a list of tagged_spans
    tagged_spans = []
    for item in tagged_text.strip().split("\n"):
        heading_match = re.match(r"<(\w+) \(PAGE NUMBER = (\d+)\)>(.*?)< \1 />", item)
        if heading_match:
            tag, page_num_str, text = heading_match.groups()
            page_num = int(page_num_str)
            if page_num == page_number + 1:
                tagged_spans.append({'tag': tag, 'page_number': page_num, 'text': text})
        else:
            bold_match = re.match(r"<(\w+) \(PAGE NUMBER = (\d+)\)>(.*?)</\w+>", item)
            if bold_match:
                tag, page_num_str, text = bold_match.groups()
                page_num = int(page_num_str)
                if page_num == page_number + 1:
                    tagged_spans.append({'tag': tag, 'page_number': page_num, 'text': text})
            else:
                other_match = re.match(r"<(\w+)>(.*?)</\w+>", item)
                if other_match:
                    tag, text = other_match.groups()
                    tagged_spans.append({'tag': tag, 'text': text})

    output_lines = parsed_output.splitlines()
    matched_tags: set = set()
    updated_output: List[str] = []

    inside_table = False
    for line in output_lines:
        stripped_line = line.strip()

        if re.match(r"<TABLE EXTRACT \(TABLE NUMBER = \d+, PAGE NUMBER = \d+\)>", stripped_line):
            inside_table = True
            updated_output.append(stripped_line)
            continue

        if stripped_line == "<TABLE EXTRACT />":
            inside_table = False
            updated_output.append(stripped_line)
            continue

        if inside_table:
            updated_output.append(stripped_line)
            continue

        matched = False
        for span in tagged_spans:
            # Ensure the span is relevant to the current page
            if 'page_number' in span and span['page_number'] != page_number + 1:
                continue  # Skip spans from other pages

            if is_similar(span['text'], stripped_line) and span['text'] not in matched_tags:
                if span['tag'] == 'HEADING':
                    updated_output.append(f"<{span['tag']} (PAGE NUMBER = {page_number +1})>{stripped_line}< {span['tag']} />")
                elif span['tag'] == 'BOLD':
                    updated_output.append(f"<{span['tag']} (PAGE NUMBER = {page_number +1})>{stripped_line}</{span['tag']}>")
                else:
                    updated_output.append(f"<{span['tag']}>{stripped_line}</{span['tag']}>")
                matched_tags.add(span['text'])
                matched = True
                break

        if not matched:
            updated_output.append(stripped_line)

    return "\n".join(updated_output)


def final_output(response: Dict[str, Any], pdf_filepath: str, page_number: int, image_path: str, output_dir: str, pdf_name: str, padding: int = 10) -> str:
    json_text = json_to_text(response, image_path, output_dir, pdf_name, page_number, padding)
    tagged_text = extract_headings_and_bold_text(pdf_page=pdf_filepath, page_number=page_number)

    return replace_headings(json_text, tagged_text, page_number)


def save_combined_text(accumulated_text: List[str], file: str) -> None:
    output_dir = 'Outputs'
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.basename(file).replace('.pdf', '')
    output_filepath = os.path.join(output_dir, f"{base_name}.txt")

    with open(output_filepath, 'w', encoding='utf-8') as text_file:
        text_file.write('\n'.join(accumulated_text))

    print(f'Combined text saved to {output_filepath}')


def extract_entire_pdf(pdf_filepath: str, client: boto3.client, output_filepath: str) -> None:
    pdf_document = fitz.open(pdf_filepath)
    num_pages = pdf_document.page_count
    accumulated_text: List[str] = []

    pdf_name = os.path.basename(pdf_filepath).replace('.pdf', '')
    output_dir = 'GET'

    for page_number in range(num_pages):
        print(f"Processing page {page_number} of {pdf_filepath}")

        extract_single_page_as_png(pdf_filepath, page_number, output_filepath)
        response = extract_png_with_cache(pdf_filepath, page_number, client, output_filepath)

        accumulated_text.append(final_output(
            response=response,
            pdf_filepath=pdf_filepath,
            page_number=page_number,
            image_path=output_filepath,
            output_dir=output_dir,
            pdf_name=pdf_name,
            padding=10
        ))
        print("PAGE DONE!!\n")

    save_combined_text(accumulated_text, pdf_filepath)
    print("PDF FINISHED")


def main(pdf_filepath: str) -> None:
    output_filepath = "page_image.png"

    load_dotenv()
    ACCESS_KEY = os.getenv('ACCESS_KEY')
    SECRET_ACCESS_KEY = os.getenv('SECRET_ACCESS_KEY')
    aws_region = 'us-west-2'
    client = boto3.client(
        'textract',
        region_name=aws_region,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_ACCESS_KEY
    )

    extract_entire_pdf(pdf_filepath, client, output_filepath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a PDF and extract text.")
    parser.add_argument("--input", required=True, help="Path to the PDF file.")
    args = parser.parse_args()
    main(args.input)
