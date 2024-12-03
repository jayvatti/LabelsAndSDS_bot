import re
from langchain.text_splitter import TextSplitter
from typing import List, Optional
import logging


class HeaderTableTextSplitter(TextSplitter):
    def __init__(
        self,
        target_chunk_size: int = 1000,
        debug: bool = False,
        minimum_content_length: int = 700,
        max_chunk_size: Optional[int] = None,
    ):
        super().__init__(chunk_size=target_chunk_size)
        self.target_chunk_size = target_chunk_size
        self.debug = debug
        self.minimum_content_length = minimum_content_length
        self.max_chunk_size = max_chunk_size if max_chunk_size else int(target_chunk_size * 1.5)
        if self.debug:
            logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    def is_page_number_tag(self, segment: str, tag: str) -> bool:
        """
        Checks if the segment is a specified tag (<BOLD> or <HEADING>) containing only a page number.

        :param segment: The text segment to check.
        :param tag: The tag type ('BOLD' or 'HEADING').
        :return: True if it's a page number tag, False otherwise.
        """
        # Add debug logging to see the segment being processed
        if self.debug:
            logging.debug(f"Checking if segment is a page number tag: {segment}")

        # Adjusted pattern to handle variations in whitespace
        pattern = rf'^<{tag}\s*\(\s*PAGE NUMBER\s*=\s*(\d+)\s*\)>\s*(\d+)\s*</{tag}>\s*$'
        match = re.match(pattern, segment)

        if match:
            page_number_in_attr = match.group(1)
            page_number_in_content = match.group(2)
            is_match = page_number_in_attr == page_number_in_content

            # Log the matching result
            if self.debug:
                logging.debug(
                    f"Page number tag match found: {is_match} (Attr: {page_number_in_attr}, Content: {page_number_in_content})")
            return is_match

        if self.debug:
            logging.debug("No match for page number tag.")
        return False

    def split_text(self, text: str) -> List[str]:
        if self.debug:
            logging.debug("Starting text splitting process.")

        # Define regex pattern for splitting text before <HEADING> or <BOLD> tags
        split_pattern = r'(?=<HEADING.*?>)|(?=<BOLD.*?>)'

        # Split the text at positions before a <HEADING> or <BOLD> tag
        segments = re.split(split_pattern, text, flags=re.DOTALL)

        # Filter out empty strings
        segments = [seg.strip() for seg in segments if seg.strip()]

        if self.debug:
            logging.debug(f"Total segments identified: {len(segments)}")

        chunks: List[str] = []
        current_chunk: List[str] = []
        buffer: List[str] = []

        idx = 0
        while idx < len(segments):
            segment = segments[idx]
            if self.debug:
                snippet = (segment[:50] + '...') if len(segment) > 50 else segment
                logging.debug(f"Processing segment {idx + 1}: {snippet}")

            # Check for page number tags
            is_bold_page_number = self.is_page_number_tag(segment, "BOLD")
            is_heading_page_number = self.is_page_number_tag(segment, "HEADING")
            is_page_number = is_bold_page_number or is_heading_page_number

            if is_page_number:
                # Append the page number tag to the current chunk
                current_chunk.append(segment)
                idx += 1
                # Collect the following segments up to the next <BOLD> or <HEADING> tag
                while idx < len(segments) and not segments[idx].startswith('<BOLD') and not segments[idx].startswith('<HEADING'):
                    current_chunk.append(segments[idx])
                    idx += 1
                continue

            # Add the current segment to the chunk
            current_chunk.append(segment)
            idx += 1

            # Check if the combined chunk (including buffer) meets the minimum content length
            combined_chunk = "\n".join(buffer + current_chunk)
            if len(combined_chunk) >= self.minimum_content_length:
                # Emit the combined chunk
                chunks.append(combined_chunk.strip())
                if self.debug:
                    logging.debug(f"Emitting chunk: {combined_chunk[:50]}...")
                # Reset buffer and current_chunk
                buffer = []
                current_chunk = []

        # Finalize any remaining content in the buffer and current chunk
        if buffer or current_chunk:
            final_chunk = "\n".join(buffer + current_chunk).strip()
            if final_chunk:
                chunks.append(final_chunk)
                if self.debug:
                    logging.debug(f"Emitting final chunk: {final_chunk[:50]}...")

        if self.debug:
            logging.debug(f"Total chunks created: {len(chunks)}")

        return chunks


def main():
    def read_text_file(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    # Update the file path as needed
    file_path = '../PDF_Extraction/AWS_Textract/Outputs/DuPontMatrixLabel.txt'

    text = read_text_file(file_path)

    # Initialize the splitter with desired parameters
    splitter = HeaderTableTextSplitter(
        target_chunk_size=1000,          # Desired chunk size
        debug=True,                      # Enable debug logging
        minimum_content_length=1500,     # Increased minimum content length
        max_chunk_size=1500              # Maximum chunk size (optional)
    )
    chunks = splitter.split_text(text)

    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i}:\n{chunk}")
        print('-' * 40)


if __name__ == "__main__":
    main()
