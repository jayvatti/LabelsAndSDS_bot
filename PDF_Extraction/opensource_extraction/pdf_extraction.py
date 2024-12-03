import fitz  # PyMuPDF


def extract_text_and_tables_to_txt(pdf_path, output_file="output.txt"):
    """
    Extracts text and tables from a PDF and saves them in a plain text file in array format.
    """
    doc = fitz.open(pdf_path)
    output_lines = []

    for page_num, page in enumerate(doc, start=1):
        output_lines.append(f"Page {page_num}:\n")

        # Extract plain text
        text = page.get_text()
        output_lines.append("Plain Text:\n")
        output_lines.append(text.strip() + "\n")

        # Extract tables (approximating based on structured text blocks)
        tables = page.get_text("dict")  # Get the page content as a dictionary
        if tables and "blocks" in tables:
            output_lines.append("Tables:\n")
            for block in tables["blocks"]:
                if "lines" in block:  # Structured text
                    for line in block["lines"]:
                        row = [
                            span["text"] for span in line["spans"] if span["text"].strip()
                        ]
                        if row:  # Avoid empty rows
                            output_lines.append(f"{row}\n")

        output_lines.append("\n" + "=" * 40 + "\n")  # Page separator

    # Save to a plain text file
    with open(output_file, "w", encoding="utf-8") as file:
        file.writelines(output_lines)

    print(f"Text and tables extracted and saved to {output_file}")


# Example Usage
if __name__ == "__main__":
    pdf_path = "example.pdf"  # Input PDF
    output_txt = "output.txt"  # Output plain text file
    extract_text_and_tables_to_txt(pdf_path, output_txt)
