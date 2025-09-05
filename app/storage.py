from __future__ import annotations
import os
import pathlib
from typing import Optional, Tuple
from google.cloud import storage

# Cloud Run позволяет писать только в /tmp
DEFAULT_TMP_DIR = "/tmp/doc-analyzer"

def _ensure_tmp_dir(tmp_dir: Optional[str] = None) -> str:
    d = tmp_dir or DEFAULT_TMP_DIR
    pathlib.Path(d).mkdir(parents=True, exist_ok=True)
    return d

def get_gcs_client() -> storage.Client:
    # Использует ADC (Application Default Credentials) на Cloud Run
    return storage.Client()

def download_to_tmp(bucket: str, name: str, tmp_dir: Optional[str] = None) -> Tuple[str, int]:
    """
    Скачивает gs://bucket/name в локальный файл внутри /tmp.
    Возвращает (local_path, size_bytes).
    """
    tmp_dir = _ensure_tmp_dir(tmp_dir)
    safe_name = name.replace("/", "__")  # простая «безопасная» локальная запись
    local_path = os.path.join(tmp_dir, safe_name)

    client = get_gcs_client()
    b = client.bucket(bucket)
    blob = b.blob(name)

    # Проверим, что объект существует
    if not blob.exists():
        raise FileNotFoundError(f"Object not found: gs://{bucket}/{name}")

    blob.download_to_filename(local_path)
    size = os.path.getsize(local_path)
    return local_path, size

def head_object(bucket: str, name: str) -> dict:
    """
    Возвращает метаданные объекта (content_type, size, updated, crc32c, md5_hash, custom metadata и т.д.)
    """
    client = get_gcs_client()
    b = client.bucket(bucket)
    blob = b.get_blob(name)
    if blob is None:
        raise FileNotFoundError(f"Object not found: gs://{bucket}/{name}")

    return {
        "bucket": bucket,
        "name": name,
        "size": blob.size,
        "content_type": blob.content_type,
        "updated": blob.updated.isoformat() if blob.updated else None,
        "crc32c": blob.crc32c,
        "md5_hash": blob.md5_hash,
        "metadata": dict(blob.metadata or {}),
        "storage_class": blob.storage_class,
        "generation": blob.generation,
        "etag": blob.etag,
    }
import json
from typing import Any, Dict

def upload_json(bucket: str, name: str, payload: Dict[str, Any]) -> str:
    """
    Загружает JSON в GCS по пути gs://bucket/name.
    Возвращает URI (gs://...).
    """
    client = get_gcs_client()
    b = client.bucket(bucket)
    blob = b.blob(name)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    blob.upload_from_string(data, content_type="application/json; charset=utf-8")
    return f"gs://{bucket}/{name}"
from typing import List

def list_objects(bucket: str, prefix: str = "", max_items: int = 1000) -> List[str]:
    """
    Возвращает имена объектов (keys) из GCS-бакета по префиксу.
    """
    client = get_gcs_client()
    b = client.bucket(bucket)
    it = client.list_blobs(b, prefix=prefix, max_results=max_items)
    names: List[str] = []
    for blob in it:
        # пропускаем "папки"-заглушки, если вдруг встретятся
        if blob.name.endswith("/"):
            continue
        names.append(blob.name)
    return names
