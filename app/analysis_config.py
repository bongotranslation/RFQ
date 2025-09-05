import os
from typing import List

def _get_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None or v == "":
        return default
    return str(v).lower() in {"1", "true", "yes", "y", "on"}

def _get_int(key: str, default: int) -> int:
    v = os.getenv(key)
    return default if v in (None, "") else int(v)

def _get_float(key: str, default: float) -> float:
    v = os.getenv(key)
    return default if v in (None, "") else float(v)

def _get_csv(key: str, default: str) -> List[str]:
    raw = os.getenv(key, default)
    return [s.strip() for s in raw.split(",") if s.strip()]

class AnalysisConfig:
    ENABLE_OCR: bool
    OCR_LANGS: List[str]
    OCR_DPI: int
    OCR_MAX_SIDE_PX: int
    OCR_JPEG_QUALITY: int
    MIN_IMG_AREA_FRAC: float
    LARGE_IMG_AREA_FRAC: float
    NEEDS_OCR_WORDS_THR: int
    BATCH_MAX: int
    BATCH_WORKERS: int
    

    def __init__(self) -> None:
        self.ENABLE_OCR = _get_bool("ENABLE_OCR", True)
        self.OCR_LANGS = _get_csv("OCR_LANGS", "en,ru")
        self.OCR_DPI = _get_int("OCR_DPI", 150)
        self.OCR_MAX_SIDE_PX = _get_int("OCR_MAX_SIDE_PX", 2500)
        self.OCR_JPEG_QUALITY = _get_int("OCR_JPEG_QUALITY", 80)
        self.MIN_IMG_AREA_FRAC = _get_float("MIN_IMG_AREA_FRAC", 0.002)
        self.LARGE_IMG_AREA_FRAC = _get_float("LARGE_IMG_AREA_FRAC", 0.5)
        self.NEEDS_OCR_WORDS_THR = _get_int("NEEDS_OCR_WORDS_THR", 5)
                # batch settings
        self.BATCH_MAX = _get_int("BATCH_MAX", 50)          # максимум объектов в одном batch
        self.BATCH_WORKERS = _get_int("BATCH_WORKERS", 4)   # количество параллельных воркеров


analysis_config = AnalysisConfig()
