import json
import os
import re

from pypdf import PdfReader


def extract_words(folder: str, input1: str, output1: str) -> None:
    # Download the source PDF from the MapReduce/ folder.
    local_pdf = "turing.pdf"
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"extract_words: input PDF {input1} is missing or empty in folder {folder}"
        faasr_log(msg)
        raise RuntimeError(msg)

    # Extract the full text from every page of the PDF.
    try:
        reader = PdfReader(local_pdf)
    except Exception as e:
        msg = f"extract_words: failed to open {input1} as a PDF: {e}"
        faasr_log(msg)
        raise

    page_texts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        page_texts.append(text)
    full_text = "\n".join(page_texts)

    faasr_log(
        f"extract_words: extracted text from {len(reader.pages)} page(s) of {input1} "
        f"({len(full_text)} characters)"
    )

    # Tokenize into individual words: split on any run of non-alphanumeric
    # characters (whitespace/punctuation), and normalize case to lowercase so
    # the downstream word count aggregates case-insensitively. This generalizes
    # to any document content and vocabulary — no word list is hardcoded.
    words = re.findall(r"[A-Za-z0-9]+", full_text)
    words = [w.lower() for w in words]

    if not words:
        msg = (
            f"extract_words: no words could be extracted from {input1} — "
            f"the PDF may contain no extractable text (e.g. scanned images)"
        )
        faasr_log(msg)
        raise RuntimeError(msg)

    faasr_log(f"extract_words: tokenized {len(words)} words from {input1}")

    # Write the flat list of words as a JSON array to the MapReduce/ folder.
    local_out = "raw_input_text.json"
    with open(local_out, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"extract_words: wrote {len(words)} words to {output1} in {folder}")

    for p in (local_pdf, local_out):
        if os.path.exists(p):
            os.remove(p)
