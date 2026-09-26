
from __future__ import annotations
from pathlib import Path
import os
import fitz  # PyMuPDF

def _ocr_page(page, language="eng+fra", dpi=200):
    try:
        tp = page.get_textpage_ocr(language=language, dpi=dpi, full=True)
        return page.get_text("text", textpage=tp)
    except Exception as exc:
        return f"\n[OCR ERROR: {exc}]\n"

def extract_pdf_text(pdf_path: Path, language="eng+fra", min_chars=40):
    doc = fitz.open(pdf_path)
    pages = []
    ocr_used = False
    for i, page in enumerate(doc):
        normal = page.get_text("text") or ""
        if len(normal.strip()) < min_chars:
            ocr = _ocr_page(page, language=language)
            pages.append(f"\n--- PAGE {i+1} [OCR] ---\n{ocr}")
            ocr_used = True
        else:
            pages.append(f"\n--- PAGE {i+1} ---\n{normal}")
    return "\n".join(pages), ocr_used

def extract_image_text(image_path: Path, language="eng+fra", dpi=200):
    try:
        pix = fitz.Pixmap(str(image_path))
        pdf_bytes = pix.pdfocr_tobytes(language=language)
        doc = fitz.open("pdf", pdf_bytes)
        return doc[0].get_text("text"), True
    except Exception as exc:
        return f"[OCR ERROR: {exc}]", False
