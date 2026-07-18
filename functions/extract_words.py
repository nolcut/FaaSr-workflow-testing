import json
import os
import re

from pypdf import PdfReader


def extract_words(folder: str, input1: str, output1: str) -> None:
    # Source node: read the PDF placed in the workflow folder, extract its full
    # text, tokenize into individual words, and emit a JSON array consumed by
    # `split` (which reads remote_file="input_text.json").
    local_pdf = "words.pdf"
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"Source PDF {folder}/{input1} is missing or empty; cannot extract words."
        faasr_log(msg)
        raise RuntimeError(msg)

    try:
        reader = PdfReader(local_pdf)
    except Exception as e:
        msg = f"Failed to open PDF {folder}/{input1} with pypdf: {e}"
        faasr_log(msg)
        raise

    faasr_log(f"Opened {folder}/{input1}: {len(reader.pages)} page(s)")

    # Concatenate the text of every page.
    text_parts = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
        faasr_log(f"Extracted {len(page_text)} chars from page {i + 1}")
    full_text = "\n".join(text_parts)

    # Tokenize into words: lowercase, keep alphanumeric sequences (with internal
    # apostrophes) so downstream counting operates on normalized tokens. The
    # vocabulary is derived entirely from the PDF content — nothing hardcoded.
    words = re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*", full_text.lower())

    if not words:
        msg = (
            f"No words could be extracted from {folder}/{input1}. The PDF may "
            f"contain only images/scanned pages with no embedded text."
        )
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(f"Tokenized {len(words)} words from {folder}/{input1}")

    local_output = "input_text.json"
    with open(local_output, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Wrote {len(words)} words to {folder}/{output1}")

    for p in (local_pdf, local_output):
        try:
            os.remove(p)
        except OSError:
            pass
