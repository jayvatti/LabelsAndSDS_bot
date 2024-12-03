from textractor.parsers import response_parser
import json
import os


def save_tables_to_excel_c(textract_response_path, output_excel_path):
    with open(textract_response_path, "r") as f:
        textract_response = json.load(f)
    document = response_parser.parse(textract_response)
    if not document.tables:
        print("No tables found in the document.")
        return

    os.makedirs(os.path.dirname(output_excel_path), exist_ok=True)
    document.export_tables_to_excel(filepath=output_excel_path)
    print(f"Tables have been successfully saved to {output_excel_path}")


if __name__ == "__main__":
    textract_response_path = "Cache/test2_4.json"
    output_excel_path = "output/tables_t2.xlsx"

    # Save tables to Excel
    save_tables_to_excel_c(textract_response_path, output_excel_path)

