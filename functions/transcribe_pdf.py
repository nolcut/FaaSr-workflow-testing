from pypdf import PdfReader


def transcribe_pdf(folder: str, input1: str, output1: str) -> None:
    """Extract all text from the input PDF and write it to a transcription text file.

    input1  : remote PDF filename (e.g. 'turing.pdf')
    output1 : remote transcription filename (e.g. 'transcription.txt')
    """
    local_in = "input.pdf"
    local_out = "transcription.txt"

    faasr_log(f"transcribe_pdf: fetching PDF '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_in, remote_folder=folder, remote_file=input1)

    import os
    if not os.path.exists(local_in) or os.path.getsize(local_in) == 0:
        msg = f"transcribe_pdf: input PDF '{input1}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    try:
        reader = PdfReader(local_in)
    except Exception as e:
        msg = f"transcribe_pdf: failed to open PDF '{input1}': {e}"
        faasr_log(msg)
        raise

    num_pages = len(reader.pages)
    faasr_log(f"transcribe_pdf: PDF opened, {num_pages} page(s) to transcribe")

    page_texts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        page_texts.append(text)
        faasr_log(f"transcribe_pdf: extracted {len(text)} chars from page {i + 1}/{num_pages}")

    transcription = "\n".join(page_texts)

    if not transcription.strip():
        msg = f"transcribe_pdf: no text could be extracted from '{input1}'"
        faasr_log(msg)
        raise ValueError(msg)

    with open(local_out, "w", encoding="utf-8") as f:
        f.write(transcription)

    faasr_log(
        f"transcribe_pdf: wrote transcription ({len(transcription)} chars) -> '{output1}'"
    )
    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log("transcribe_pdf: transcription complete")
