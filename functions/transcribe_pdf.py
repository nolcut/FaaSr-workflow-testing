import os

from pypdf import PdfReader


def transcribe_pdf(folder: str, input1: str, output1: str) -> None:
    """Transcribe a PDF into a single plain-text file.

    Retrieves the input PDF via the FaaSr file API, extracts text page by
    page, concatenates the extracted text across all pages, and writes the
    result to a single output text file that downstream stages consume.
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
    except Exception as e:
        msg = f"transcribe_pdf: failed to open PDF '{input1}': {e}"
        faasr_log(msg)
        raise

    num_pages = len(reader.pages)
    faasr_log(f"transcribe_pdf: PDF opened with {num_pages} page(s)")

    page_texts = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            faasr_log(f"transcribe_pdf: page {i}/{num_pages} has no extractable text")
        else:
            faasr_log(
                f"transcribe_pdf: extracted {len(text)} chars from page {i}/{num_pages}"
            )
        page_texts.append(text)

    transcription = "\n".join(page_texts)

    with open(local_txt, "w", encoding="utf-8") as f:
        f.write(transcription)

    faasr_log(
        f"transcribe_pdf: wrote transcription ({len(transcription)} chars) "
        f"-> '{output1}'"
    )
    faasr_put_file(local_file=local_txt, remote_folder=folder, remote_file=output1)
    faasr_log("transcribe_pdf: complete")
