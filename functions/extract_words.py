import json
import os
import re

from pypdf import PdfReader


def extract_words(folder: str, input1: str, output1: str) -> None:
    # Download the source PDF from the MapReduce/ folder and derive the word
    # list purely from its text contents (no synthetic vocabulary generation).
    local_input = "words.pdf"
    faasr_get_file(local_file=local_input, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_input) or os.path.getsize(local_input) == 0:
        msg = f"PDF {folder}/{input1} is missing or empty; cannot extract words"
        faasr_log(msg)
        raise RuntimeError(msg)

    try:
        reader = PdfReader(local_input)
    except Exception as e:
        msg = f"Failed to read PDF {folder}/{input1}: {e}"
        faasr_log(msg)
        raise

    faasr_log(f"Read PDF {folder}/{input1} with {len(reader.pages)} page(s)")

    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    full_text = "\n".join(text_parts)

    # Tokenize into words: sequences of alphanumeric characters (and apostrophes),
    # lowercased so the downstream word count is case-insensitive.
    words = re.findall(r"[A-Za-z0-9']+", full_text.lower())

    if not words:
        msg = f"No words extracted from PDF {folder}/{input1}"
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(f"Extracted {len(words)} words from PDF text")

    local_output = "input_text.json"
    with open(local_output, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_output, remote_folder=folder, remote_file=output1)
    faasr_log(f"Wrote word list ({len(words)} words) to {folder}/{output1}")

    for f in (local_input, local_output):
        try:
            os.remove(f)
        except OSError:
            pass
