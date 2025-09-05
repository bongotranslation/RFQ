from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

from app.config import settings
from app import storage
from app import utils
from app import pdf_utils
from app import docx_utils
from app.pdf_utils import update_pdf_stats_with_ocr
from app.docx_utils import update_docx_stats_with_ocr
from typing import Optional, Dict, Any, List

from concurrent.futures import ThreadPoolExecutor, as_completed
from app.analysis_config import analysis_config

import io
from app import pdf_utils
from app.ocr_vision import ocr_image_bytes
from app.analysis_config import analysis_config 


app = FastAPI(title="doc-analyzer")


class AnalyzeRequest(BaseModel):
    bucket: str = Field(..., description="GCS bucket name, e.g. my-bucket")
    name: str = Field(..., description="Object path inside the bucket")
    contentType: Optional[str] = Field(None, description="GCS object content type (MIME)")
    force_ocr: bool = False
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional extra metadata")
class BatchRequest(BaseModel):
    bucket: str
    objects: List[str]  # список имён объектов в бакете (keys)
class BatchRequest(BaseModel):
    bucket: str
    objects: List[str]
    mode: str = "summary"  # "summary" | "full"
class BatchPrefixRequest(BaseModel):
    bucket: str
    prefix: str = ""
    limit: int = 50          # максимум объектов, которые заберём
    mode: str = "summary"    # "summary" | "full"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    if not req.bucket or not req.name:
        raise HTTPException(status_code=400, detail="bucket and name are required")

    # 1) head объекта
    try:
        obj_meta = storage.head_object(req.bucket, req.name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GCS head error: {e}")

    # 2) download → /tmp
    try:
        local_path, size = storage.download_to_tmp(req.bucket, req.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GCS download error: {e}")

    # 3) определяем тип файла и выбираем стратегию обработки
    file_type = utils.get_file_type(local_path)
    content_type = req.contentType or (obj_meta.get("content_type") or "")
    
    document_stats = None
    converted_pdf_path = None
    pdf_path = None
    
    if file_type == "pdf" or content_type.startswith("application/pdf"):
        # PDF файл - анализируем напрямую
        pdf_path = local_path
        try:
            document_stats = pdf_utils.analyze_pdf_basic(pdf_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF analyze error: {e}")
            
    elif file_type == "docx":
        # DOCX файл - анализируем напрямую
        try:
            document_stats = docx_utils.analyze_docx_basic(local_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DOCX analyze error: {e}")
            
    else:
        # Другой формат - конвертируем в PDF и анализируем
        try:
            converted_pdf_path = utils.soffice_convert_to_pdf(local_path)
            pdf_path = converted_pdf_path
            document_stats = pdf_utils.analyze_pdf_basic(pdf_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Convert and analyze error: {e}")

    # 4) анализ завершен
    if not document_stats:
        raise HTTPException(status_code=500, detail=f"PDF analyze error: {e}")

    # 4.1 OCR нужных страниц
    ocr_pages = []
    try:
        do_ocr = analysis_config.ENABLE_OCR and (
            req.force_ocr or any(p.get("needs_ocr") for p in document_stats.get("by_page", []))
        )
        if do_ocr:
            # Для OCR нужен PDF - если это DOCX, конвертируем его
            ocr_pdf_path = pdf_path
            if file_type == "docx" and not pdf_path:
                try:
                    converted_pdf_path = utils.soffice_convert_to_pdf(local_path)
                    ocr_pdf_path = converted_pdf_path
                except Exception as e:
                    print(f"Warning: Could not convert DOCX to PDF for OCR: {e}")
                    ocr_pdf_path = None
            
            if ocr_pdf_path:
                import fitz  # PyMuPDF
                dpi = analysis_config.OCR_DPI
                q = analysis_config.OCR_JPEG_QUALITY
                doc = fitz.open(ocr_pdf_path)
                try:
                    pages_to_process = [p for p in document_stats.get("by_page", []) if req.force_ocr or p.get("needs_ocr")]
                    total_pages = len(pages_to_process)
                    print(f"OCR: Начинаю обработку {total_pages} страниц...")
                    
                    for idx, pinfo in enumerate(pages_to_process, 1):
                        pnum = pinfo["p"] - 1
                        # Для DOCX может быть меньше страниц в PDF, чем предполагается
                        if pnum >= doc.page_count:
                            continue
                            
                        print(f"OCR: Обработка страницы {pinfo['p']} ({idx}/{total_pages})...")
                        
                        page = doc.load_page(pnum)
                        scale = dpi / 72.0
                        mat = fitz.Matrix(scale, scale)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img_bytes = pix.tobytes("jpeg")

                        ocr = ocr_image_bytes(img_bytes)
                        ocr_pages.append({
                            "p": pinfo["p"],
                            "ocr_text_len": ocr["text_len"],
                            "ocr_words": ocr["words"],
                            "ocr_words_by_language": ocr["words_by_language"],
                            "sample": (ocr["text"][:120] + "...") if ocr["text_len"] > 120 else ocr["text"],
                        })
                    
                    print(f"OCR: Завершена обработка всех {total_pages} страниц.")
                    
                finally:
                    doc.close()
    except Exception as e:
        ocr_pages = [{"error": str(e)}]

    # 4.2) Обновляем статистику документа с учетом OCR результатов
    if ocr_pages and not any("error" in page for page in ocr_pages):
        if file_type == "docx":
            document_stats = update_docx_stats_with_ocr(document_stats, ocr_pages)
        else:
            document_stats = update_pdf_stats_with_ocr(document_stats, ocr_pages)

    # 5) краткая сводка - вычисляем из данных по страницам
    by_page = document_stats.get("by_page", [])
    words_total = sum(p.get("words", 0) for p in by_page)
    images_total = sum(p.get("images", 0) for p in by_page)
    
    # Агрегация слов по языкам
    from collections import defaultdict
    words_by_language = defaultdict(int)
    for page in by_page:
        for lang, count in page.get("words_by_language", {}).items():
            words_by_language[lang] += count
    
    summary = {
        "pages_total": document_stats.get("pages_total", 0),
        "images_total": images_total,
        "pages_ocr_applied": sum(1 for p in by_page if p.get("ocr_applied")),
        "words_total": words_total,
        "words_by_language": dict(words_by_language),
        "file_type": file_type  # добавляем информацию о типе файла
    }

    # 6) формируем результат
    result = {
        "document": document_stats,  # переименовываем с "pdf" на "document"
        "summary": summary,
    }

    # 7) сохраняем JSON в RESULTS_BUCKET
    try:
        base_name = os.path.basename(req.name)
        # Добавляем timestamp для уникальности
        import time
        timestamp = int(time.time())
        ocr_suffix = "_ocr_test" if req.force_ocr else ""
        out_name = f"analysis/{base_name}.{timestamp}{ocr_suffix}.analysis.json"
        results_uri = storage.upload_json(settings.RESULTS_BUCKET, out_name, result)
    except Exception:
        results_uri = None

    result["results_uri"] = results_uri
    return result

# @app.post("/batch_analyze")
# def batch_analyze(req: BatchRequest):
#     # 0) лимит
#     maxn = analysis_config.BATCH_MAX
#     if len(req.objects) > maxn:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Too many objects in batch: {len(req.objects)} > {maxn}. "
#                    f"Split your request or increase BATCH_MAX env."
#         )

#     results = []

#     def _process(name: str):
#         try:
#             single = analyze(AnalyzeRequest(bucket=req.bucket, name=name))
#             if req.mode == "full":
#                 return {"name": name, "status": "ok", "result": single}
#             else:
#                 return {
#                     "name": name,
#                     "status": "ok",
#                     "summary": single.get("summary"),
#                     "results_uri": single.get("results_uri"),
#                 }
#         except Exception as e:
#             return {"name": name, "status": "error", "error": str(e)}

#     workers = max(1, analysis_config.BATCH_WORKERS)
#     with ThreadPoolExecutor(max_workers=workers) as ex:
#         futs = {ex.submit(_process, name): name for name in req.objects}
#         for fut in as_completed(futs):
#             results.append(fut.result())

#     return {
#         "bucket": req.bucket,
#         "count": len(req.objects),
#         "mode": req.mode,
#         "workers": workers,
#         "results": results
#     }

# @app.post("/batch_analyze_prefix")
# def batch_analyze_prefix(req: BatchPrefixRequest):
#     # 1) листим объекты по префиксу
#     try:
#         all_names = storage.list_objects(req.bucket, req.prefix, max_items=max(1, req.limit))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"GCS list error: {e}")

#     # 2) ограничим по BATCH_MAX (глобальный лимит)
#     maxn = analysis_config.BATCH_MAX
#     names = all_names[:maxn] if len(all_names) > maxn else all_names

#     # 3) переиспользуем существующий батч
#     br = BatchRequest(bucket=req.bucket, objects=names, mode=req.mode)
#     return batch_analyze(br)