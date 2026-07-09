import json
import os
import re

from pypdf import PdfReader


def extract_words(folder: str, input1: str, output1: str) -> None:
    # Fetch the source PDF from the MapReduce/ folder into a local temp file.
    local_pdf = "words.pdf"
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"Input PDF {folder}/{input1} is missing or empty; cannot extract words"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    # Read the PDF and extract text from every page.
    try:
        reader = PdfReader(local_pdf)
    except Exception as e:
        msg = f"Failed to parse PDF {folder}/{input1}: {e}"
        faasr_log(msg)
        raise

    text_parts = []
    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    faasr_log(f"Extracted text from {len(reader.pages)} page(s) of {folder}/{input1}")

    full_text = "\n".join(text_parts)

    # Tokenize into words. Derive the vocabulary purely from the PDF content:
    # a word is a maximal run of letters/digits (with internal apostrophes/hyphens),
    # lowercased for consistent downstream counting.
    tokens = re.findall(r"[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*", full_text)
    words = [t.lower() for t in tokens]

    if not words:
        msg = f"No words could be extracted from {folder}/{input1}"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"Tokenized {len(words)} words from {folder}/{input1}")

    # Write the word list as a JSON array to the local temp file, then upload.
    local_out = "input_text.json"
    with open(local_out, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"Wrote {len(words)} words to {folder}/{output1}")

    for tmp in (local_pdf, local_out):
        try:
            os.remove(tmp)
        except OSError:
            pass
