from __future__ import annotations
from typing import Dict, Any, List
import fitz  # PyMuPDF
import pathlib
import re
from collections import defaultdict

from app.analysis_config import analysis_config

MIN_IMG_AREA_FRAC = analysis_config.MIN_IMG_AREA_FRAC

def _count_words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])

def _count_words_by_language(text: str) -> Dict[str, int]:
    """
    Подсчет слов по языкам на основе простой эвристики.
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

def analyze_pdf_basic(pdf_path: str) -> Dict[str, Any]:
    """
    Мини-анализ PDF с фильтрацией изображений и эвристикой needs_ocr:
      - pages_total
      - by_page: [{p, words, images, needs_ocr}]
      - totals + thresholds
    """
    path = pathlib.Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    try:
        by_page: List[Dict[str, int | bool]] = []
        for i in range(doc.page_count):
            page = doc.load_page(i)
            w, h = page.rect.width, page.rect.height
            page_area = max(w * h, 1.0)

            # текст
            text = page.get_text("text") or ""
            words = _count_words(text)
            words_by_language = _count_words_by_language(text)

            # изображения из rawdict.type == 1 с фильтрацией по площади
            raw = page.get_text("rawdict") or {}
            blocks = raw.get("blocks", []) if isinstance(raw, dict) else []
            images = 0
            for b in blocks:
                if b.get("type") != 1:
                    continue
                bbox = b.get("bbox") or [0, 0, 0, 0]
                bw = max(bbox[2] - bbox[0], 0)
                bh = max(bbox[3] - bbox[1], 0)
                area_frac = (bw * bh) / page_area
                if area_frac >= MIN_IMG_AREA_FRAC:
                    images += 1

            # эвристика needs_ocr - OCR нужен если мало текста и есть изображения >0.2% площади
            needs_ocr = False
            if words <= analysis_config.NEEDS_OCR_WORDS_THR and images > 0:
                needs_ocr = True

            by_page.append({
                "p": i + 1,
                "words": words,
                "words_by_language": words_by_language,
                "images": images,
                "needs_ocr": needs_ocr
            })

        # Агрегация слов по языкам
        total_words_by_language = defaultdict(int)
        for page in by_page:
            for lang, count in page.get("words_by_language", {}).items():
                total_words_by_language[lang] += count

        return {
            "pages_total": doc.page_count,
            "by_page": by_page,
            "thresholds": {
                "min_img_area_frac": MIN_IMG_AREA_FRAC,
                "needs_ocr_words_thr": analysis_config.NEEDS_OCR_WORDS_THR,
            },
        }
    finally:
        doc.close()

def update_pdf_stats_with_ocr(pdf_stats: Dict[str, Any], ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Обновляет статистику PDF с учетом результатов OCR.
    Добавляет OCR слова к исходным словам страниц и пересчитывает totals.
    """
    if not ocr_results or not pdf_stats.get("by_page"):
        return pdf_stats
    
    # Создаем словарь OCR результатов по номерам страниц
    ocr_by_page = {}
    for ocr_result in ocr_results:
        if isinstance(ocr_result, dict) and "p" in ocr_result:
            page_num = ocr_result["p"]
            ocr_words = ocr_result.get("ocr_words", 0)
            ocr_words_by_language = ocr_result.get("ocr_words_by_language", {})
            ocr_by_page[page_num] = {
                "words": ocr_words,
                "words_by_language": ocr_words_by_language
            }
    
    # Обновляем статистику страниц
    updated_by_page = []
    for page_info in pdf_stats["by_page"]:
        page_num = page_info["p"]
        original_words = page_info["words"]
        original_words_by_lang = page_info.get("words_by_language", {})
        
        ocr_data = ocr_by_page.get(page_num, {"words": 0, "words_by_language": {}})
        ocr_words = ocr_data["words"]
        ocr_words_by_lang = ocr_data["words_by_language"]
        
        # Объединяем слова по языкам
        combined_words_by_lang = defaultdict(int)
        for lang, count in original_words_by_lang.items():
            combined_words_by_lang[lang] += count
        for lang, count in ocr_words_by_lang.items():
            combined_words_by_lang[lang] += count
        
        updated_page = page_info.copy()
        updated_page["words"] = original_words + ocr_words
        updated_page["words_by_language"] = dict(combined_words_by_lang)
        updated_page["ocr_applied"] = ocr_words > 0
        
        # Обновляем needs_ocr - если OCR уже применен, то больше не нужен
        if ocr_words > 0:
            updated_page["needs_ocr"] = False
            
        updated_by_page.append(updated_page)
    
    # Обновляем статистику
    updated_stats = pdf_stats.copy()
    updated_stats["by_page"] = updated_by_page
    
    return updated_stats
