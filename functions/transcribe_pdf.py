import os

from pypdf import PdfReader


def transcribe_pdf(folder: str, input1: str, output1: str) -> None:
    """Transcribe a PDF from S3 into a single concatenated text file.

    Downloads the input PDF (input1) from the workflow's S3 storage, extracts
    the text of every page in order, concatenates it into one transcription,
    and uploads the result as output1 for the downstream splitting stage.
    """
    local_pdf = "input.pdf"
    local_txt = "transcription.txt"

    faasr_log(f"transcribe_pdf: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"transcribe_pdf: input PDF '{input1}' is missing or empty after download"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"transcribe_pdf: opening PDF '{local_pdf}' with pypdf")
    try:
        reader = PdfReader(local_pdf)
    except Exception as e:
        msg = f"transcribe_pdf: failed to parse PDF '{input1}': {e}"
        faasr_log(msg)
        raise

    num_pages = len(reader.pages)
    faasr_log(f"transcribe_pdf: PDF has {num_pages} page(s); extracting text")
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

    if not transcription.strip():
        msg = (
            f"transcribe_pdf: no extractable text found in '{input1}' "
            f"(the PDF may be image-only/scanned)"
        )
        faasr_log(msg)
        raise ValueError(msg)

    with open(local_txt, "w", encoding="utf-8") as f:
        f.write(transcription)

    faasr_log(
        f"transcribe_pdf: wrote transcription of {len(transcription)} chars "
        f"from {num_pages} page(s)"
    )

    faasr_put_file(local_file=local_txt, remote_folder=folder, remote_file=output1)
    faasr_log(f"transcribe_pdf: uploaded transcription to '{output1}' in folder '{folder}'")
