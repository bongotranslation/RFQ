from __future__ import annotations
import pathlib
import shutil
import subprocess
import uuid

TMP_DIR = "/tmp/doc-analyzer"

def ensure_tmp_dir() -> str:
    pathlib.Path(TMP_DIR).mkdir(parents=True, exist_ok=True)
    return TMP_DIR

def is_pdf(path: str) -> bool:
    return pathlib.Path(path).suffix.lower() == ".pdf"

def soffice_convert_to_pdf(input_path: str) -> str:
    """
    Конвертирует файл (docx/pptx/xlsx/...) в PDF с помощью LibreOffice (soffice --headless).
    Возвращает путь к итоговому PDF в /tmp/doc-analyzer/*.pdf
    """
    ensure_tmp_dir()
    in_path = pathlib.Path(input_path).resolve()
    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")

    # Выходной файл положим в TMP_DIR со случайным именем, чтобы избежать коллизий
    out_name = f"conv_{uuid.uuid4().hex}.pdf"
    out_dir = pathlib.Path(TMP_DIR)
    out_path = out_dir / out_name

    # soffice складывает PDF в указанную папку (--outdir) с именем <stem>.pdf
    cmd = [
        "soffice", "--headless",
        "--convert-to", "pdf:writer_pdf_Export",
        "--outdir", str(out_dir),
        str(in_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"soffice conversion failed: {e.stderr or e.stdout}") from e

    # Найдём созданный PDF
    produced = out_dir / (in_path.stem + ".pdf")
    if not produced.exists():
        candidates = list(out_dir.glob(in_path.stem + "*.pdf"))
        if candidates:
            produced = candidates[0]
        else:
            raise FileNotFoundError("Converted PDF not found after soffice run")

    # Переместим под предсказуемое имя
    shutil.move(str(produced), str(out_path))
    return str(out_path)
