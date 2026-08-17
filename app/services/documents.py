"""Extract text from an uploaded file (blueprint §13). PDF via PyMuPDF, DOCX via
python-docx, plain text directly. Images are stored but not OCR'd yet."""
from __future__ import annotations

import io

MAX_CHARS = 20000


def extract_text(filename: str, mimetype: str, data: bytes) -> str:
    name = (filename or "").lower()
    mt = (mimetype or "").lower()
    try:
        if mt == "application/pdf" or name.endswith(".pdf"):
            import fitz  # PyMuPDF

            doc = fitz.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)[:MAX_CHARS]
        if name.endswith(".docx") or "word" in mt or "officedocument.wordprocessing" in mt:
            import docx

            d = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in d.paragraphs)[:MAX_CHARS]
        if mt.startswith("text/") or name.endswith((".txt", ".md", ".csv", ".json")):
            return data.decode("utf-8", "ignore")[:MAX_CHARS]
        if mt.startswith("image/"):
            return ""  # OCR not enabled yet; the image is stored, text is empty
    except Exception:
        return ""
    # Unknown type — best-effort decode.
    try:
        return data.decode("utf-8", "ignore")[:MAX_CHARS]
    except Exception:
        return ""


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks for embedding/retrieval."""
    text = " ".join((text or "").split())
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks[:50]  # cap chunks per document
