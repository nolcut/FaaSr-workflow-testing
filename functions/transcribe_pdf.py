def transcribe_pdf(folder: str, input1: str, output1: str) -> None:
    """Transcribe a PDF into a single plain-text file.

    Downloads the input PDF (input1) from S3 into the working directory,
    extracts the text of every page in order using pypdf, concatenates the
    per-page text, and uploads the result as a single plain-text file
    (output1). This text becomes the source that the downstream split
    function partitions into map batches.
    """
    import os
    from pypdf import PdfReader

    local_pdf = "input.pdf"
    local_txt = "transcription.txt"

    # Retrieve the real input PDF from S3 into the working directory.
    faasr_log(f"transcribe_pdf: downloading '{input1}' from folder '{folder}'")
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"transcribe_pdf: input PDF '{input1}' is missing or empty after download"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    # Extract text from every page in order.
    try:
        reader = PdfReader(local_pdf)
    except Exception as e:
        msg = f"transcribe_pdf: failed to open PDF '{input1}': {e}"
        faasr_log(msg)
        raise

    num_pages = len(reader.pages)
    faasr_log(f"transcribe_pdf: opened '{input1}' with {num_pages} page(s)")
    if num_pages == 0:
        msg = f"transcribe_pdf: PDF '{input1}' contains no pages"
        faasr_log(msg)
        raise ValueError(msg)

    page_texts = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        faasr_log(f"transcribe_pdf: extracted {len(text)} chars from page {i}/{num_pages}")
        page_texts.append(text)

    transcription = "\n".join(page_texts)

    total_chars = len(transcription)
    if total_chars == 0:
        msg = (
            f"transcribe_pdf: no extractable text found in '{input1}' "
            f"({num_pages} page(s)); the PDF may be image-only/scanned"
        )
        faasr_log(msg)
        raise ValueError(msg)

    with open(local_txt, "w", encoding="utf-8") as f:
        f.write(transcription)

    faasr_log(
        f"transcribe_pdf: writing {total_chars} chars of transcribed text "
        f"to '{output1}'"
    )
    faasr_put_file(local_file=local_txt, remote_folder=folder, remote_file=output1)
    faasr_log("transcribe_pdf: complete")
