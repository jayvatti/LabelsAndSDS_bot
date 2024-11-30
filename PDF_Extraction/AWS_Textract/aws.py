import argparse
import os

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
        print(f"Page {page_number + 1} saved as {output_filepath}")
    else:
        print(f"Page {page_number + 1} not found in the PDF.")


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
                            table[row_index - 1][col_index - 1] = cell_text.strip()
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

    for block_info in blocks_with_position:
        distances = [abs(block_info['Left'] - c) for c in centroids]
        block_info['Column'] = distances.index(min(distances))

    columns: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for block_info in blocks_with_position:
        columns[block_info['Column']].append(block_info)

    for column_blocks in columns.values():
        column_blocks.sort(key=lambda x: x['Top'])

    title_found = False
    extracted_text: List[str] = []

    sorted_centroid_indices = sorted(range(len(centroids)), key=lambda i: centroids[i])
    for idx in sorted_centroid_indices:
        column_blocks = columns[idx]
        for block_info in column_blocks:
            block_type = block_info['BlockType']
            block = block_info['Block']
            if block_type == 'LINE':
                line_bbox = block_info['BoundingBox']
                overlaps_table = any(
                    bbox_overlap(line_bbox, table_bbox) for table_bbox in table_bboxes)
                if not overlaps_table:
                    if not title_found and is_title(block, max_line_height, top_threshold):
                        extracted_text.append(f"{block['Text']} {{['TITLE EXTRACT']}}")
                        title_found = True
                    else:
                        extracted_text.append(block['Text'])
            elif block_type == 'TABLE':
                table_count += 1
                table = extract_tables(blocks_map, block)
                extracted_text.append(f"<'TABLE EXTRACT (TABLE NUMBER: {table_count}, PAGE NUMBER: )'>")
                extracted_text.extend(str(row) for row in table)
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
                extracted_text.append(f"Table extracted to {image_url}")
                extracted_text.append(f"<'TABLE EXTRACT DONE - NUMBER: {table_count}'/>")

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
    for block in blocks:
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text = span.get('text', '').strip()
                size = span.get('size', 0)
                color = span.get('color', '')
                flags = span.get('flags', 0)

                is_heading = size >= size_threshold or color != regular_color or (flags == 20 and size > regular_size)

                if is_heading and text != '':
                    tagged_spans.append((text, 'HEADING'))
                elif flags == 20 and text != '':
                    tagged_spans.append((text, 'BOLD'))

    pdf_document.close()

    return "\n".join(f"<{tag}>{text}</{tag}>" for text, tag in tagged_spans)


def replace_headings(parsed_output: str, tagged_text: str) -> str:
    tagged_dict = {re.match(r"<(\w+)>(.*?)</\w+>", item).group(2): re.match(r"<(\w+)>(.*?)</\w+>", item).group(1) for
                   item in tagged_text.strip().split("\n") if re.match(r"<(\w+)>(.*?)</\w+>", item)}

    output_lines = parsed_output.splitlines()
    matched_tags: set = set()
    updated_output: List[str] = []

    inside_table = False
    for line in output_lines:
        stripped_line = line.strip()

        if stripped_line.startswith("{['TABLE EXTRACT']}"):
            inside_table = True
            updated_output.append(stripped_line)
            continue

        if stripped_line.startswith("{['TABLE EXTRACT DONE']}"):
            inside_table = False
            updated_output.append(stripped_line)
            continue

        if inside_table:
            updated_output.append(stripped_line)
            continue

        for tag_text, tag_type in tagged_dict.items():
            if re.search(re.escape(tag_text), stripped_line, re.IGNORECASE) and tag_text not in matched_tags:
                updated_output.append(f"<{tag_type}>{stripped_line}</{tag_type}>")
                matched_tags.add(tag_text)
                break
        else:
            updated_output.append(stripped_line)

    return "\n".join(updated_output)

import argparse
import os

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
        print(f"Page {page_number + 1} saved as {output_filepath}")
    else:
        print(f"Page {page_number + 1} not found in the PDF.")


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
                            table[row_index - 1][col_index - 1] = cell_text.strip()
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

    for block_info in blocks_with_position:
        distances = [abs(block_info['Left'] - c) for c in centroids]
        block_info['Column'] = distances.index(min(distances))

    columns: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for block_info in blocks_with_position:
        columns[block_info['Column']].append(block_info)

    for column_blocks in columns.values():
        column_blocks.sort(key=lambda x: x['Top'])

    title_found = False
    extracted_text: List[str] = []

    sorted_centroid_indices = sorted(range(len(centroids)), key=lambda i: centroids[i])
    for idx in sorted_centroid_indices:
        column_blocks = columns[idx]
        for block_info in column_blocks:
            block_type = block_info['BlockType']
            block = block_info['Block']
            if block_type == 'LINE':
                line_bbox = block_info['BoundingBox']
                overlaps_table = any(
                    bbox_overlap(line_bbox, table_bbox) for table_bbox in table_bboxes)
                if not overlaps_table:
                    if not title_found and is_title(block, max_line_height, top_threshold):
                        extracted_text.append(f"{block['Text']} {{['TITLE EXTRACT']}}")
                        title_found = True
                    else:
                        extracted_text.append(block['Text'])
            elif block_type == 'TABLE':
                table_count += 1
                table = extract_tables(blocks_map, block)
                extracted_text.append("{['TABLE EXTRACT']}")
                extracted_text.extend(str(row) for row in table)
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
                extracted_text.append(f"Table extracted to {image_url}")
                extracted_text.append("{['TABLE EXTRACT DONE']}")

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
    for block in blocks:
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text = span.get('text', '').strip()
                size = span.get('size', 0)
                color = span.get('color', '')
                flags = span.get('flags', 0)

                is_heading = size >= size_threshold or color != regular_color or (flags == 20 and size > regular_size)

                if is_heading and text != '':
                    tagged_spans.append((text, 'HEADING'))
                elif flags == 20 and text != '':
                    tagged_spans.append((text, 'BOLD'))

    pdf_document.close()

    return "\n".join(f"<{tag}>{text}</{tag}>" for text, tag in tagged_spans)


def replace_headings(parsed_output: str, tagged_text: str) -> str:
    tagged_dict = {re.match(r"<(\w+)>(.*?)</\w+>", item).group(2): re.match(r"<(\w+)>(.*?)</\w+>", item).group(1) for
                   item in tagged_text.strip().split("\n") if re.match(r"<(\w+)>(.*?)</\w+>", item)}

    output_lines = parsed_output.splitlines()
    matched_tags: set = set()
    updated_output: List[str] = []

    inside_table = False
    for line in output_lines:
        stripped_line = line.strip()

        if stripped_line.startswith("{['TABLE EXTRACT']}"):
            inside_table = True
            updated_output.append(stripped_line)
            continue

        if stripped_line.startswith("{['TABLE EXTRACT DONE']}"):
            inside_table = False
            updated_output.append(stripped_line)
            continue

        if inside_table:
            updated_output.append(stripped_line)
            continue

        for tag_text, tag_type in tagged_dict.items():
            if re.search(re.escape(tag_text), stripped_line, re.IGNORECASE) and tag_text not in matched_tags:
                updated_output.append(f"<{tag_type}>{stripped_line}</{tag_type}>")
                matched_tags.add(tag_text)
                break
        else:
            updated_output.append(stripped_line)

    return "\n".join(updated_output)


def final_output(response: Dict[str, Any], pdf_filepath: str, page_number: int, image_path: str, output_dir: str, pdf_name: str, padding: int = 10) -> str:
    json_text = json_to_text(response, image_path, output_dir, pdf_name, page_number, padding)
    tagged_text = extract_headings_and_bold_text(pdf_page=pdf_filepath, page_number=page_number)

    return replace_headings(json_text, tagged_text)


def save_combined_text(accumulated_text: List[str], file: str) -> None:
    output_dir = 'Outputs'
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.basename(file).replace('.pdf', '')
    output_filepath = os.path.join(output_dir, f"{base_name}_combined.txt")

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
        print(f"Processing page {page_number + 1} of {pdf_filepath}")

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

def final_output(response: Dict[str, Any], pdf_filepath: str, page_number: int, image_path: str, output_dir: str, pdf_name: str, padding: int = 10) -> str:
    json_text = json_to_text(response, image_path, output_dir, pdf_name, page_number, padding)
    tagged_text = extract_headings_and_bold_text(pdf_page=pdf_filepath, page_number=page_number)

    return replace_headings(json_text, tagged_text)


def save_combined_text(accumulated_text: List[str], file: str) -> None:
    output_dir = 'Outputs'
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.basename(file).replace('.pdf', '')
    output_filepath = os.path.join(output_dir, f"{base_name}_combined.txt")

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
        print(f"Processing page {page_number + 1} of {pdf_filepath}")

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
