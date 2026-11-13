import os
import string
import tempfile

import fitz  # pymupdf


def extract_words(folder: str, input1: str, output1: str) -> None:
    local_pdf = tempfile.mktemp(suffix=".pdf")
    local_txt = tempfile.mktemp(suffix=".txt")
    try:
        faasr_log(f"Downloading '{input1}' from folder '{folder}'")
        faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

        doc = fitz.open(local_pdf)
        if doc.page_count == 0:
            msg = f"PDF '{input1}' contains no pages"
            faasr_log(msg)
            raise ValueError(msg)

        words = []
        translator = str.maketrans("", "", string.punctuation)
        for page_num in range(doc.page_count):
            page_text = doc[page_num].get_text()
            for token in page_text.split():
                cleaned = token.lower().translate(translator)
                if cleaned:
                    words.append(cleaned)
        num_pages = doc.page_count
        doc.close()

        if not words:
            msg = f"No words extracted from '{input1}'"
            faasr_log(msg)
            raise ValueError(msg)

        faasr_log(f"Extracted {len(words)} words from {num_pages} page(s)")

        with open(local_txt, "w", encoding="utf-8") as fh:
            fh.write("\n".join(words))

        faasr_log(f"Uploading word list as '{output1}' to folder '{folder}'")
        faasr_put_file(local_file=local_txt, remote_folder=folder, remote_file=output1)
        faasr_log("extract_words complete")
    finally:
        for path in (local_pdf, local_txt):
            if os.path.exists(path):
                os.unlink(path)
