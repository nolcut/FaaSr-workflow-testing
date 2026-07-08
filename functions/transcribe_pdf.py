from pypdf import PdfReader


def transcribe_pdf(folder, pdf_file, output):
    """
    Stage 1 - Transcription.

    Download the input PDF (turing.pdf) from S3, extract the text of every
    page, and write it out as a plain-text transcription file that the rest of
    the MapReduce pipeline consumes.

    Arguments (supplied via the workflow JSON "Arguments" object):
      folder   : S3 folder that holds the input PDF and receives the output.
      pdf_file : name of the input PDF in `folder` (e.g. "turing.pdf").
      output   : name of the transcription file to write (e.g. "transcription.txt").
    """
    # Pull the source PDF from the object store onto local disk.
    faasr_get_file(remote_folder=folder, remote_file=pdf_file, local_file=pdf_file)

    reader = PdfReader(pdf_file)
    faasr_log(f"transcribe_pdf: reading '{pdf_file}' with {len(reader.pages)} page(s)")

    # Extract text page-by-page. A missing extraction returns None, so guard it.
    pages_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)

    transcription = "\n".join(pages_text)

    with open(output, "w", encoding="utf-8") as f:
        f.write(transcription)

    # Persist the transcription back to S3 for the downstream split stage.
    faasr_put_file(local_file=output, remote_folder=folder, remote_file=output)

    faasr_log(
        f"transcribe_pdf: wrote {len(transcription)} characters to "
        f"{folder}/{output}"
    )
