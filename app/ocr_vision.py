from __future__ import annotations
from typing import Dict, Any
import io
import re
from collections import defaultdict

from google.cloud import vision

def _count_words(text: str) -> int:
    """Подсчет слов в тексте"""
    return len([w for w in text.split() if w.strip()])

def _count_words_by_language(text: str, language_hints: list) -> Dict[str, int]:
    """
    Подсчет слов по языкам на основе простой эвристики.
    Для более точного определения используем основные языки из конфига.
    """
    if not text.strip():
        return {}
    
    words_by_lang = defaultdict(int)
    words = [w for w in text.split() if w.strip()]
    
    # Простая эвристика определения языка по символам
    for word in words:
        # Проверяем на кириллицу (русский)
        if re.search(r'[а-яё]', word.lower()):
            words_by_lang['ru'] += 1
        # Проверяем на латиницу (английский/европейские)
        elif re.search(r'[a-z]', word.lower()):
            words_by_lang['en'] += 1
        # Другие символы - неопределенный язык
        else:
            words_by_lang['other'] += 1
    
    return dict(words_by_lang)

def ocr_image_bytes(img_bytes: bytes) -> Dict[str, Any]:
    """
    OCR изображения (bytes) через Google Cloud Vision (DOCUMENT_TEXT_DETECTION).
    Возвращает словарь с распознанным текстом и метаданными, включая подсчет слов по языкам.
    """
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=img_bytes)

    resp = client.document_text_detection(image=image)
    if resp.error and resp.error.message:
        raise RuntimeError(f"Vision OCR error: {resp.error.message}")

    text = resp.full_text_annotation.text if resp.full_text_annotation else ""
    words_count = _count_words(text or "")
    
    # Подсчет слов по языкам
    words_by_language = _count_words_by_language(text or "", [])
    
    return {
        "text": text or "",
        "text_len": len(text or ""),
        "words": words_count,
        "words_by_language": words_by_language,
    }
