import re

from pypdf import PdfReader


def extract_words(folder="MapReduce", input_pdf="words.pdf", output_file="words.txt"):
    """
    Stage 1 of the MapReduce pipeline.

    Downloads the source PDF from the `folder` prefix in S3, extracts every
    text token, normalizes it (lowercase, alphabetic characters only) and
    writes the resulting whitespace-separated word list back to S3 as a single
    text file. This word list is the dataset that the rest of the pipeline
    (split -> map -> reduce -> visualize) operates on.
    """
    # 1. Pull the input PDF from the MapReduce/ folder in the S3 bucket.
    faasr_log(f"extract_words: downloading {folder}/{input_pdf}")
    faasr_get_file(
        remote_folder=folder,
        remote_file=input_pdf,
        local_folder=".",
        local_file="words.pdf",
    )

    # 2. Read all pages and collect their text.
    reader = PdfReader("words.pdf")
    full_text = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        full_text.append(page_text)
    raw_text = "\n".join(full_text)

    # 3. Tokenize into lowercase alphabetic words.
    words = re.findall(r"[A-Za-z]+", raw_text)
    words = [w.lower() for w in words]

    faasr_log(f"extract_words: extracted {len(words)} words from {input_pdf}")

    # 4. Persist the cleaned word list (one big whitespace-separated file).
    with open("words.txt", "w") as fh:
        fh.write(" ".join(words))

    faasr_put_file(
        local_folder=".",
        local_file="words.txt",
        remote_folder=folder,
        remote_file=output_file,
    )

    faasr_log(f"extract_words: wrote word list to {folder}/{output_file}")
