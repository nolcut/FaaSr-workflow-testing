import json
import os

from pdf2image import convert_from_path
import pytesseract


def ocr_pdf(folder: str, input1: str, output1: str) -> None:
    """Perform OCR on an input PDF and write the extracted text as a JSON list of words.

    Reads the PDF (``input1``) from S3, rasterizes every page to an image, runs
    optical character recognition on each page image, concatenates the recognized
    text across all pages, splits it into words, and uploads the resulting word
    list as ``output1`` (a JSON array) for the downstream split stage.
    """
    local_pdf = "input.pdf"

    # Fetch the input PDF from S3.
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"ocr_pdf: input PDF '{input1}' in folder '{folder}' is missing or empty"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    faasr_log(f"ocr_pdf: fetched '{input1}' ({os.path.getsize(local_pdf)} bytes); rasterizing pages")

    # Rasterize each PDF page to a PIL image (requires the poppler utilities).
    try:
        pages = convert_from_path(local_pdf)
    except Exception as e:
        faasr_log(f"ocr_pdf: failed to rasterize PDF '{input1}': {e}")
        raise

    if not pages:
        msg = f"ocr_pdf: PDF '{input1}' produced no page images"
        faasr_log(msg)
        raise ValueError(msg)

    faasr_log(f"ocr_pdf: rasterized {len(pages)} page(s); running OCR")

    # Run OCR on each page and concatenate the recognized text.
    page_texts = []
    for i, page in enumerate(pages, start=1):
        try:
            text = pytesseract.image_to_string(page)
        except Exception as e:
            faasr_log(f"ocr_pdf: OCR failed on page {i} of '{input1}': {e}")
            raise
        faasr_log(f"ocr_pdf: page {i} recognized {len(text)} characters")
        page_texts.append(text)

    full_text = "\n".join(page_texts)

    # Split the recognized text into words.
    words = full_text.split()
    faasr_log(f"ocr_pdf: extracted {len(words)} words from {len(pages)} page(s)")

    # Write the word list as JSON and upload it to S3.
    local_out = "ocr_text.json"
    with open(local_out, "w") as f:
        json.dump(words, f)

    faasr_put_file(local_file=local_out, remote_folder=folder, remote_file=output1)
    faasr_log(f"ocr_pdf: wrote '{output1}' with {len(words)} words")

    # Clean up local temp files.
    for path in (local_pdf, local_out):
        if os.path.exists(path):
            os.remove(path)
