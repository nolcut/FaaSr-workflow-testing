from pypdf import PdfReader
import re


def extract_words(folder="MapReduce", input_pdf="words.pdf", output_file="words.txt"):
    """Extract words from a PDF stored in S3 and persist them as a newline-separated
    word list back to S3.

    Reads:  {folder}/{input_pdf}
    Writes: {folder}/{output_file}
    """
    # Download the source PDF from S3 into the local working directory
    faasr_get_file(
        remote_folder=folder,
        remote_file=input_pdf,
        local_folder=".",
        local_file="words.pdf",
    )

    # Extract raw text from every page of the PDF
    reader = PdfReader("words.pdf")
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    full_text = "\n".join(text_parts)

    # Tokenize into lowercase alphabetic words
    words = re.findall(r"[A-Za-z']+", full_text.lower())

    # Write the word list, one word per line
    with open("words.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(words))

    # Persist the extracted word list back to S3
    faasr_put_file(
        local_folder=".",
        local_file="words.txt",
        remote_folder=folder,
        remote_file=output_file,
    )

    faasr_log(
        f"extract_words: extracted {len(words)} words from {folder}/{input_pdf} "
        f"-> {folder}/{output_file}"
    )
