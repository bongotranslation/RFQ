import os
from typing import List, Dict, Any

def _get_str(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key, default)
    return val if (val is None or isinstance(val, str)) else str(val)

def _get_int(key: str, default: int | None = None) -> int | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"ENV {key} must be int, got: {val!r}")

def _get_float(key: str, default: float | None = None) -> float | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except ValueError:
        raise ValueError(f"ENV {key} must be float, got: {val!r}")

def _get_bool(key: str, default: bool | None = None) -> bool | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return str(val).lower() in {"1", "true", "yes", "y", "on"}

def _get_csv(key: str, default: str = "") -> List[str]:
    raw = os.getenv(key, default)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]

class Settings:
    # === Project / region ===
    PROJECT_ID: str | None
    PROJECT_NUMBER: str | None
    REGION: str | None

    # === Buckets ===
    SOURCE_BUCKET: str | None
    RESULTS_BUCKET: str | None
    TMP_BUCKET: str | None

    # === OCR / Analyzer tuning ===
    ENABLE_OCR: bool
    OCR_LANGS: List[str]
    OCR_DPI: int | None
    OCR_MAX_SIDE_PX: int | None
    OCR_JPEG_QUALITY: int | None
    MIN_IMG_AREA_FRAC: float | None
    LARGE_IMG_AREA_FRAC: float | None
    NEEDS_OCR_WORDS_THR: int | None

    def __init__(self) -> None:
        # project
        self.PROJECT_ID = _get_str("PROJECT_ID")
        self.PROJECT_NUMBER = _get_str("PROJECT_NUMBER")
        self.REGION = _get_str("REGION")

        # buckets
        self.SOURCE_BUCKET = _get_str("SOURCE_BUCKET")
        self.RESULTS_BUCKET = _get_str("RESULTS_BUCKET")
        self.TMP_BUCKET = _get_str("TMP_BUCKET")

        # tuning
        self.ENABLE_OCR = bool(_get_bool("ENABLE_OCR", False))
        self.OCR_LANGS = _get_csv("OCR_LANGS", "")
        self.OCR_DPI = _get_int("OCR_DPI")
        self.OCR_MAX_SIDE_PX = _get_int("OCR_MAX_SIDE_PX")
        self.OCR_JPEG_QUALITY = _get_int("OCR_JPEG_QUALITY")
        self.MIN_IMG_AREA_FRAC = _get_float("MIN_IMG_AREA_FRAC")
        self.LARGE_IMG_AREA_FRAC = _get_float("LARGE_IMG_AREA_FRAC")
        self.NEEDS_OCR_WORDS_THR = _get_int("NEEDS_OCR_WORDS_THR")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "PROJECT_ID": self.PROJECT_ID,
            "PROJECT_NUMBER": self.PROJECT_NUMBER,
            "REGION": self.REGION,
            "SOURCE_BUCKET": self.SOURCE_BUCKET,
            "RESULTS_BUCKET": self.RESULTS_BUCKET,
            "TMP_BUCKET": self.TMP_BUCKET,
            "ENABLE_OCR": self.ENABLE_OCR,
            "OCR_LANGS": self.OCR_LANGS,
            "OCR_DPI": self.OCR_DPI,
            "OCR_MAX_SIDE_PX": self.OCR_MAX_SIDE_PX,
            "OCR_JPEG_QUALITY": self.OCR_JPEG_QUALITY,
            "MIN_IMG_AREA_FRAC": self.MIN_IMG_AREA_FRAC,
            "LARGE_IMG_AREA_FRAC": self.LARGE_IMG_AREA_FRAC,
            "NEEDS_OCR_WORDS_THR": self.NEEDS_OCR_WORDS_THR,
        }

# <<< ВАЖНО: этот объект должен существовать >>>
settings = Settings()
