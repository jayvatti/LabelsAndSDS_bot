import re
from langchain.text_splitter import TextSplitter
from typing import List, Optional
import logging


class HeaderTableTextSplitter(TextSplitter):
    def __init__(
        self,
        target_chunk_size: int = 1000,
        debug: bool = False,
        minimum_content_length: int = 300,
        max_chunk_size: Optional[int] = None,
    ):
        super().__init__(chunk_size=target_chunk_size)
        self.target_chunk_size = target_chunk_size
        self.debug = debug
        self.minimum_content_length = minimum_content_length
        self.max_chunk_size = max_chunk_size if max_chunk_size else int(target_chunk_size * 1.5)
        if self.debug:
            logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    def is_tag_with_number(self, segment: str) -> bool:
        """
        Checks if the first 55 characters of a segment contain a <BOLD> or <HEADING>
        tag with a number inside.

        :param segment: The text segment to check.
        :return: True if it contains a tag with a number, False otherwise.
        """
        snippet = segment[:55]
        pattern = r'<(BOLD|HEADING)[^>]*>\s*\d+\s*</\1>'
        match = re.search(pattern, snippet, flags=re.IGNORECASE)
        if self.debug:
            logging.debug(f"Checking for tag with number in snippet: {snippet}")
            logging.debug(f"Tag with number found: {bool(match)}")
        return bool(match)

    def split_text(self, text: str) -> List[str]:
        if self.debug:
            logging.debug("Starting text splitting process.")

        # Define regex pattern for splitting text before <HEADING> or <BOLD> tags
        split_pattern = r'(?=<HEADING[^>]*?>)|(?=<BOLD[^>]*?>)'

        # Split the text at positions before a <HEADING> or <BOLD> tag
        segments = re.split(split_pattern, text, flags=re.DOTALL)

        # Filter out empty strings
        segments = [seg.strip() for seg in segments if seg.strip()]

        if self.debug:
            logging.debug(f"Total segments identified: {len(segments)}")

        chunks: List[str] = []
        current_chunk: List[str] = []

        for idx, segment in enumerate(segments):
            if self.debug:
                snippet = (segment[:50] + '...') if len(segment) > 50 else segment
                logging.debug(f"Processing segment {idx + 1}: {snippet}")

            # Check if the segment starts with a tag containing a number
            if self.is_tag_with_number(segment):
                # Merge the segment with the previous chunk
                if self.debug:
                    logging.debug("Merging segment with previous chunk due to tag with number.")
                current_chunk.append(segment)
                continue

            # Add the current segment to the chunk
            current_chunk.append(segment)

            # Check if the combined chunk meets the minimum content length
            combined_chunk = "\n".join(current_chunk)
            if len(combined_chunk) >= self.minimum_content_length:
                # Emit the combined chunk
                chunks.append(combined_chunk.strip())
                if self.debug:
                    logging.debug(f"Emitting chunk: {combined_chunk[:50]}...")
                # Reset current_chunk
                current_chunk = []

        # Finalize any remaining content in the current chunk
        if current_chunk:
            final_chunk = "\n".join(current_chunk).strip()
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
        minimum_content_length=300,      # Minimum content length
        max_chunk_size=1500              # Maximum chunk size (optional)
    )
    chunks = splitter.split_text(text)

    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i}:\n{chunk}")
        print('-' * 40)


if __name__ == "__main__":
    main()
