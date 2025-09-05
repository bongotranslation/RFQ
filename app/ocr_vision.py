from __future__ import annotations
from typing import Dict, Any
import io

from google.cloud import vision

def ocr_image_bytes(img_bytes: bytes) -> Dict[str, Any]:
    """
    OCR изображения (bytes) через Google Cloud Vision (DOCUMENT_TEXT_DETECTION).
    Возвращает словарь с распознанным текстом и метаданными.
    """
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=img_bytes)

    resp = client.document_text_detection(image=image)
    if resp.error and resp.error.message:
        raise RuntimeError(f"Vision OCR error: {resp.error.message}")

    text = resp.full_text_annotation.text if resp.full_text_annotation else ""
    return {
        "text": text or "",
        "text_len": len(text or ""),
    }
