import re
from pypdf import PdfReader


def extract_words(folder="MapReduce", input_pdf="words.pdf", output_file="words.txt"):
    """Extract words from a PDF stored in S3 and write them (one per line) back to S3.

    Reads  : <folder>/<input_pdf>
    Writes : <folder>/<output_file>
    """
    # Download the source PDF from S3 into the local runtime.
    faasr_get_file(remote_folder=folder, remote_file=input_pdf,
                   local_folder=".", local_file=input_pdf)

    # Extract raw text from every page of the PDF.
    reader = PdfReader(input_pdf)
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    full_text = "\n".join(text_parts)

    # Tokenize: keep alphabetic words only, normalize to lowercase.
    words = re.findall(r"[A-Za-z]+", full_text.lower())

    # Persist the extracted word list (one word per line).
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(words))

    faasr_put_file(local_folder=".", local_file=output_file,
                   remote_folder=folder, remote_file=output_file)

    faasr_log(f"extract_words: extracted {len(words)} words from "
              f"{folder}/{input_pdf} -> {folder}/{output_file}")
