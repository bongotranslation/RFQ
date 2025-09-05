from __future__ import annotations
from typing import Dict, Any, List
import fitz  # PyMuPDF
import pathlib

from app.analysis_config import analysis_config

MIN_IMG_AREA_FRAC = analysis_config.MIN_IMG_AREA_FRAC
LARGE_IMG_AREA_FRAC = analysis_config.LARGE_IMG_AREA_FRAC

def _count_words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])

def analyze_pdf_basic(pdf_path: str) -> Dict[str, Any]:
    """
    Мини-анализ PDF с фильтрацией изображений и эвристикой needs_ocr:
      - pages_total
      - by_page: [{p, words, images, large_images, needs_ocr}]
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

            # изображения из rawdict.type == 1 с фильтрацией по площади
            raw = page.get_text("rawdict") or {}
            blocks = raw.get("blocks", []) if isinstance(raw, dict) else []
            images = 0
            large_images = 0
            for b in blocks:
                if b.get("type") != 1:
                    continue
                bbox = b.get("bbox") or [0, 0, 0, 0]
                bw = max(bbox[2] - bbox[0], 0)
                bh = max(bbox[3] - bbox[1], 0)
                area_frac = (bw * bh) / page_area
                if area_frac >= MIN_IMG_AREA_FRAC:
                    images += 1
                    if area_frac >= LARGE_IMG_AREA_FRAC:
                        large_images += 1

            # эвристика needs_ocr
            needs_ocr = False
            if words <= analysis_config.NEEDS_OCR_WORDS_THR and (large_images > 0 or images > 0):
                needs_ocr = True

            by_page.append({
                "p": i + 1,
                "words": words,
                "images": images,
                "large_images": large_images,
                "needs_ocr": needs_ocr
            })

        return {
            "pages_total": doc.page_count,
            "by_page": by_page,
            "words_total": sum(p["words"] for p in by_page),
            "images_total": sum(p["images"] for p in by_page),
            "large_images_total": sum(p["large_images"] for p in by_page),
            "thresholds": {
                "min_img_area_frac": MIN_IMG_AREA_FRAC,
                "large_img_area_frac": LARGE_IMG_AREA_FRAC,
                "needs_ocr_words_thr": analysis_config.NEEDS_OCR_WORDS_THR,
            },
        }
    finally:
        doc.close()
