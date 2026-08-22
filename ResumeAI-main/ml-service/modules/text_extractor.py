"""
text_extractor.py
-----------------
Extract raw text from resume files.

Improvements over v1:
- Supports .pdf, .docx, and .txt files (routed by extension/MIME).
- Scanned/image PDFs raise a clear ValueError instead of returning empty string.
- Stream position is reset before reading (seeks to 0 if seekable).
"""

import io
import re
import logging
from typing import Union

logger = logging.getLogger(__name__)


def extract_text(file_obj, filename: str = "") -> str:
    """
    Extract text from a resume file.

    Accepts a file-like object (Flask FileStorage, io.BytesIO, or open file).
    Routes to the appropriate extractor based on file extension.

    Supported formats: .pdf, .docx, .txt

    Raises:
        ValueError: if the file cannot be parsed or is an image-only PDF.
    """
    # Reset stream position to avoid partial-read issues
    if hasattr(file_obj, "seekable") and file_obj.seekable():
        file_obj.seek(0)

    ext = _get_extension(filename, file_obj)

    if ext == ".pdf":
        return _extract_pdf(file_obj)
    elif ext == ".docx":
        return _extract_docx(file_obj)
    elif ext == ".txt":
        return _extract_txt(file_obj)
    else:
        # Unknown extension — try PDF first, then docx
        logger.warning("Unknown file extension '%s' — attempting PDF extraction.", ext)
        try:
            return _extract_pdf(file_obj)
        except Exception:
            pass
        if hasattr(file_obj, "seekable") and file_obj.seekable():
            file_obj.seek(0)
        try:
            return _extract_docx(file_obj)
        except Exception:
            raise ValueError(
                f"Unsupported file format '{ext}'. "
                "Please upload a .pdf, .docx, or .txt file."
            )


# ── Back-compat alias used by app.py ──────────────────────────────────────────
def extract_text_from_pdf(file_obj) -> str:
    """
    Legacy alias — extract text from a PDF file object.
    Use extract_text() for new code (supports docx/txt too).
    """
    return _extract_pdf(file_obj)


# ── Format extractors ──────────────────────────────────────────────────────────

def _extract_pdf(file_obj) -> str:
    """Extract text from a PDF using pdfplumber."""
    try:
        import pdfplumber

        if hasattr(file_obj, "read"):
            content = file_obj.read()
            source  = io.BytesIO(content)
        else:
            source = file_obj

        with pdfplumber.open(source) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            full_text = "\n".join(pages_text)

        full_text = _clean(full_text)

        if len(full_text.strip()) < 50:
            raise ValueError(
                "This appears to be a scanned or image-based PDF — no selectable text "
                "was found. Please upload a text-based PDF or convert to .docx/.txt."
            )

        return full_text

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"PDF extraction failed: {e}")


def _extract_docx(file_obj) -> str:
    """Extract text from a .docx file using python-docx."""
    try:
        from docx import Document

        if hasattr(file_obj, "read"):
            content = file_obj.read()
            source  = io.BytesIO(content)
        else:
            source = file_obj

        doc       = Document(source)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text  = "\n".join(paragraphs)
        full_text  = _clean(full_text)

        if len(full_text.strip()) < 50:
            raise ValueError(
                "The .docx file appears to be empty or contains no readable text."
            )

        return full_text

    except ImportError:
        raise ValueError(
            "python-docx is not installed. Run: pip install python-docx"
        )
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"DOCX extraction failed: {e}")


def _extract_txt(file_obj) -> str:
    """Extract text from a plain .txt file."""
    try:
        if hasattr(file_obj, "read"):
            raw = file_obj.read()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
        else:
            raw = str(file_obj)

        full_text = _clean(raw)

        if len(full_text.strip()) < 50:
            raise ValueError("The .txt file appears to be empty.")

        return full_text

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"TXT extraction failed: {e}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Normalize excessive whitespace."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _get_extension(filename: str, file_obj) -> str:
    """Determine file extension from filename or FileStorage content_type."""
    if filename:
        dot = filename.rfind(".")
        if dot != -1:
            return filename[dot:].lower()

    # Flask FileStorage has a content_type attribute
    ct = getattr(file_obj, "content_type", "") or ""
    if "pdf" in ct:
        return ".pdf"
    if "word" in ct or "docx" in ct or "officedocument" in ct:
        return ".docx"
    if "text" in ct:
        return ".txt"

    return ""
