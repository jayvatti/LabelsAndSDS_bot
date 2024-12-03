import re
from langchain.text_splitter import TextSplitter
from typing import List, Optional
import logging


class HeaderTableTextSplitter(TextSplitter):
    def __init__(self, chunk_size: int = 1000, debug: bool = False):
        super().__init__(chunk_size)
        self.chunk_size = chunk_size
        self.debug = debug
        if self.debug:
            logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    def split_text(self, text: str) -> List[str]:
        if self.debug:
            logging.debug("Starting text splitting process.")

        split_pattern = re.split(r'(<HEADING>.*?</HEADING>|\{.*?TABLE EXTRACT DONE})', text, flags=re.DOTALL)
        chunks: List[str] = []
        current_chunk: Optional[str] = None
        inside_table: bool = False

        for part in split_pattern:
            if self.debug:
                logging.debug(f"Processing part: {part[:50]}...")  # Logs the beginning of each part for context

            if part.startswith("{['TABLE EXTRACT']}"):
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    if self.debug:
                        logging.debug(f"Appended chunk: {current_chunk[:50]}...")
                current_chunk = part
                inside_table = True
            elif inside_table:
                current_chunk = (current_chunk or "") + "\n" + part
                if part.startswith("{['TABLE EXTRACT DONE']}"):
                    chunks.append(current_chunk.strip())
                    if self.debug:
                        logging.debug(f"Appended table chunk: {current_chunk[:50]}...")
                    current_chunk = None
                    inside_table = False
            elif part.startswith("<HEADING>") and not inside_table:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    if self.debug:
                        logging.debug(f"Appended header chunk: {current_chunk[:50]}...")
                current_chunk = part
            else:
                if current_chunk:
                    current_chunk += "\n" + part

        if current_chunk:
            chunks.append(current_chunk.strip())
            if self.debug:
                logging.debug(f"Final appended chunk: {current_chunk[:50]}...")

        if self.debug:
            logging.debug("Finished text splitting.")

        return [chunk.strip() for chunk in chunks if chunk.strip()]


def main():
    def read_text_file(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    file_path = '../PDF_Extraction/AWS_Textract/Outputs/test2_combined_v2.txt'

    text = read_text_file(file_path)

    splitter = HeaderTableTextSplitter()
    chunks = splitter.split_text(text)

    for chunk in chunks[:15]:
        print(chunk)
        print('-' * 40)


if __name__ == "__main__":
    main()
