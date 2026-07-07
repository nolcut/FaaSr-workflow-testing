import os

from pypdf import PdfReader


def transcribe_pdf(folder: str, input1: str, output1: str) -> None:
    """Transcribe a PDF into a plain-text file.

    Fetches the input PDF (``input1``) from S3, extracts the text of every
    page in reading order, concatenates it into a single transcription, and
    uploads it as ``output1`` for the downstream split function.
    """
    local_pdf = "input.pdf"
    local_txt = "transcription.txt"

    faasr_log(f"transcribe_pdf: fetching PDF '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"transcribe_pdf: input PDF '{input1}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    try:
        reader = PdfReader(local_pdf)
    except Exception as exc:
        msg = f"transcribe_pdf: failed to open PDF '{input1}': {exc}"
        faasr_log(msg)
        raise

    num_pages = len(reader.pages)
    faasr_log(f"transcribe_pdf: opened PDF with {num_pages} page(s)")
    if num_pages == 0:
        msg = f"transcribe_pdf: PDF '{input1}' contains no pages"
        faasr_log(msg)
        raise ValueError(msg)

    page_texts = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        page_texts.append(text)
        faasr_log(f"transcribe_pdf: extracted {len(text)} chars from page {i}/{num_pages}")

    transcription = "\n".join(page_texts)

    with open(local_txt, "w", encoding="utf-8") as f:
        f.write(transcription)

    faasr_log(
        f"transcribe_pdf: wrote transcription of {len(transcription)} chars "
        f"from {num_pages} page(s) -> '{output1}'"
    )
    faasr_put_file(local_file=local_txt, remote_folder=folder, remote_file=output1)
    faasr_log("transcribe_pdf: complete")
