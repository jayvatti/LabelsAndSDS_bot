from pdf2image import convert_from_path
from collections import defaultdict, Counter
from typing import List, Dict, Any, Union, Tuple
import os


def save_all_pages_as_png(pdf_filepath: str, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    images = convert_from_path(pdf_filepath)

    for i, image in enumerate(images):
        output_filepath = os.path.join(output_dir, f"test2_{i}.png")
        image.save(output_filepath, 'PNG')
        print(f"Page {i} saved as {output_filepath}")


if __name__ == "__main__":
    pdf_filepath = 'Inputs/AccordXRT2.pdf'
    output_dir = 'PNG_Cache'
    save_all_pages_as_png(pdf_filepath, output_dir)
