import re
from langchain.text_splitter import TextSplitter
from typing import List, Optional
import logging


class HeaderTableTextSplitter(TextSplitter):
    def __init__(self, chunk_size: int = 1000, debug: bool = False, minimum_content_length: int = 200):
        """
        Initializes the HeaderTableTextSplitter.

        :param chunk_size: Maximum size of each chunk.
        :param debug: If True, enables debug logging.
        :param minimum_content_length: Minimum number of characters to consider a chunk substantial.
        """
        super().__init__(chunk_size)
        self.chunk_size = chunk_size
        self.debug = debug
        self.minimum_content_length = minimum_content_length
        if self.debug:
            logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    def split_text(self, text: str) -> List[str]:
        if self.debug:
            logging.debug("Starting text splitting process.")

        # Pattern to match either <HEADING> tags or {TABLE EXTRACT} tags
        split_pattern = re.split(r'(<HEADING.*?>|<\/HEADING>|\{.*?TABLE EXTRACT DONE\})', text, flags=re.DOTALL)

        chunks: List[str] = []
        current_chunk: Optional[str] = None
        heading_buffer: List[str] = []
        inside_table: bool = False

        for part in split_pattern:
            if self.debug:
                logging.debug(f"Processing part: {part[:50]}...")  # Logs the beginning of each part for context

            # Check for table extract tags
            if part.startswith("{['TABLE EXTRACT']}"):
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    if self.debug:
                        logging.debug(f"Appended chunk: {current_chunk[:50]}...")
                current_chunk = part
                inside_table = True
                heading_buffer = []  # Clear heading buffer when entering table
                continue
            elif part.startswith("{['TABLE EXTRACT DONE']}"):
                if inside_table and current_chunk:
                    chunks.append(current_chunk.strip())
                    if self.debug:
                        logging.debug(f"Appended table chunk: {current_chunk[:50]}...")
                    current_chunk = None
                    inside_table = False
                continue

            # Check for heading tags
            if re.match(r'<HEADING.*?>', part, flags=re.DOTALL):
                # Buffer the heading
                heading_buffer.append(part)
                if self.debug:
                    logging.debug(f"Buffered heading: {part[:50]}...")
                continue
            elif re.match(r'<\/HEADING>', part, flags=re.DOTALL):
                # Closing heading tag, can ignore or process if needed
                continue

            # If part is content
            if heading_buffer:
                # If there's buffered headings, prepend them to the current chunk
                buffered_headings = "\n".join(heading_buffer)
                heading_buffer = []  # Clear the buffer

                if current_chunk:
                    # Check if adding buffered headings exceeds chunk size
                    if len(current_chunk) + len(buffered_headings) + len(part) > self.chunk_size:
                        # Finalize the current chunk
                        chunks.append(current_chunk.strip())
                        if self.debug:
                            logging.debug(f"Appended chunk with buffered headings: {current_chunk[:50]}...")
                        current_chunk = buffered_headings + "\n" + part
                    else:
                        # Append buffered headings to the current chunk
                        current_chunk += "\n" + buffered_headings + "\n" + part
                else:
                    current_chunk = buffered_headings + "\n" + part
                if self.debug:
                    logging.debug(f"Added buffered headings to current chunk.")
            else:
                if current_chunk:
                    # Check if adding the new part would exceed chunk size
                    if len(current_chunk) + len(part) > self.chunk_size:
                        # Check if current_chunk has substantial content
                        content_length = len(re.sub(r'<HEADING.*?>|<\/HEADING>|\{.*?\}', '', current_chunk))
                        if content_length >= self.minimum_content_length:
                            chunks.append(current_chunk.strip())
                            if self.debug:
                                logging.debug(f"Appended substantial chunk: {current_chunk[:50]}...")
                            current_chunk = part
                        else:
                            # If not enough content, append to current chunk without splitting
                            current_chunk += "\n" + part
                            if self.debug:
                                logging.debug(f"Appended to chunk without splitting due to insufficient content.")
                    else:
                        current_chunk += "\n" + part
                else:
                    current_chunk = part

        # After processing all parts, handle any remaining buffer and chunk
        if heading_buffer:
            buffered_headings = "\n".join(heading_buffer)
            if current_chunk:
                if len(current_chunk) + len(buffered_headings) <= self.chunk_size:
                    current_chunk += "\n" + buffered_headings
                else:
                    chunks.append(current_chunk.strip())
                    if self.debug:
                        logging.debug(f"Appended final chunk before adding buffered headings.")
                    current_chunk = buffered_headings
            else:
                current_chunk = buffered_headings

        if current_chunk:
            chunks.append(current_chunk.strip())
            if self.debug:
                logging.debug(f"Final appended chunk: {current_chunk[:50]}...")

        if self.debug:
            logging.debug("Finished text splitting.")

        # Optionally, filter out empty chunks and ensure stripping
        return [chunk.strip() for chunk in chunks if chunk.strip()]


def main():
    def read_text_file(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    file_path = '../PDF_Extraction/AWS_Textract/Outputs/test2.txt'

    text = read_text_file(file_path)

    splitter = HeaderTableTextSplitter(debug=True, minimum_content_length=200)
    chunks = splitter.split_text(text)

    for i, chunk in enumerate(chunks[:50], 1):
        print(f"Chunk {i}:\n{chunk}")
        print('-' * 40)


if __name__ == "__main__":
    main()
