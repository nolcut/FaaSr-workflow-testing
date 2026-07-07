import json
import os
import re

from pypdf import PdfReader


def read_pdf(folder: str, input1: str, output1: str) -> None:
    # Fixed vocabulary shared with the downstream catalog map/shuffle/reduce
    # stages. Only tokens belonging to this vocabulary may be emitted so that
    # the ranked `map_phase` word-count stage never sees an out-of-vocab token.
    VOCABULARY = ["cat", "dog", "bird", "horse", "pig"]
    VOCAB_SET = set(VOCABULARY)

    # `map_phase` runs as exactly 4 parallel instances; write one shard per
    # instance. This function is NOT ranked, so the count is hardcoded here.
    N_CHUNKS = 4

    faasr_log(f"read_pdf: fetching input PDF '{input1}' from folder '{folder}'")

    local_pdf = "words_input.pdf"
    faasr_get_file(local_file=local_pdf, remote_folder=folder, remote_file=input1)

    if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) == 0:
        msg = f"read_pdf: input PDF '{input1}' is missing or empty after fetch"
        faasr_log(msg)
        raise FileNotFoundError(msg)

    # Extract text content from every page and concatenate into one string.
    try:
        reader = PdfReader(local_pdf)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
        full_text = "\n".join(text_parts)
    except Exception as e:
        msg = f"read_pdf: failed to read/extract text from PDF '{input1}': {e}"
        faasr_log(msg)
        raise

    faasr_log(
        f"read_pdf: extracted {len(full_text)} characters from "
        f"{len(reader.pages)} page(s)"
    )

    # Tokenize on non-alphanumeric boundaries, lowercase, and keep only the
    # tokens that belong to the fixed vocabulary.
    raw_tokens = re.findall(r"[A-Za-z]+", full_text.lower())
    tokens = [t for t in raw_tokens if t in VOCAB_SET]

    faasr_log(
        f"read_pdf: tokenized into {len(raw_tokens)} raw tokens, "
        f"{len(tokens)} in-vocabulary tokens {VOCABULARY}"
    )

    if not tokens:
        msg = (
            f"read_pdf: no in-vocabulary tokens {VOCABULARY} found in "
            f"PDF '{input1}'"
        )
        faasr_log(msg)
        raise ValueError(msg)

    # Partition the in-vocabulary tokens into N_CHUNKS contiguous chunks so the
    # downstream parallel map stage can consume the raw text. Distribute the
    # remainder across the earlier chunks so sizes are as even as possible.
    n = len(tokens)
    base = n // N_CHUNKS
    rem = n % N_CHUNKS

    chunks = []
    start = 0
    for i in range(N_CHUNKS):
        size = base + (1 if i < rem else 0)
        chunks.append(tokens[start:start + size])
        start += size

    for i in range(1, N_CHUNKS + 1):
        chunk = chunks[i - 1]
        out_name = output1.replace("{rank}", str(i))
        local_out = f"text_chunk_{i}.json"
        with open(local_out, "w") as f:
            json.dump(chunk, f)

        faasr_put_file(
            local_file=local_out, remote_folder=folder, remote_file=out_name
        )
        faasr_log(
            f"read_pdf: wrote chunk {i}/{N_CHUNKS} with {len(chunk)} tokens "
            f"to {out_name}"
        )

        if os.path.exists(local_out):
            os.remove(local_out)

    if os.path.exists(local_pdf):
        os.remove(local_pdf)

    faasr_log("read_pdf: complete")
