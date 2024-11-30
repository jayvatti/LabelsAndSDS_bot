from textractor.parsers import response_parser
from PIL import Image
import json

if __name__ == "__main__":
    with open("Cache/test2_5.json", "r") as f:
        textract_response = json.load(f)

    document = response_parser.parse(textract_response)

    image_path = "PNG_Cache/test2_5.png"
    image = Image.open(image_path)

    for page in document.pages:
        page.image = image

    for i, table in enumerate(document.tables):
        visualized_image = table.visualize(with_words=False)
        visualized_image.show()
        visualized_image.save(f"visualized_test2_5_{i}.png")
