"""
file_tool.py — Document Reader
=================================
Extracts text from uploaded documents for analysis and summarisation.

Formats: ``.txt`` ``.md`` ``.log`` ``.pdf`` ``.csv`` ``.tsv`` ``.json``
``.docx`` ``.xlsx`` ``.html`` ``.py`` and other plain-text source files.

Structured formats get structured previews rather than a raw dump: a CSV
returns its shape, column names, dtypes and head, which is far more useful
to a model than the first 10 KB of comma-separated values.

Reads are confined to the project's upload directory and working tree, so
a model cannot be talked into reading ``/etc/passwd`` or ``~/.ssh/id_rsa``.
"""

from __future__ import annotations

import csv
import io
import json
import os

from tools.base import Tool
from tools.common import ToolError, clean_input, truncate

MAX_CHARS = 10000
MAX_FILE_BYTES = 25 * 1024 * 1024

# Extensions treated as plain text even without a dedicated handler.
TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".ini", ".cfg", ".conf",
    ".toml", ".yaml", ".yml", ".py", ".js", ".ts", ".java", ".c", ".cpp",
    ".h", ".go", ".rs", ".rb", ".php", ".sh", ".sql", ".r", ".xml", ".env.example",
}

# Reads are restricted to these roots (resolved at call time so the tool
# still works regardless of the process's working directory).
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ALLOWED_ROOTS = [
    os.path.join(_PROJECT_ROOT, "static", "uploads"),
    os.path.join(_PROJECT_ROOT, "data"),
    _PROJECT_ROOT,
]

# Never readable, even inside an allowed root.
_DENIED_NAMES = {".env", ".git", "id_rsa", "id_ed25519", "credentials",
                 ".streamlit/secrets.toml"}


def _resolve(path: str) -> str:
    """
    Resolve a user-supplied path and confirm it stays inside an allowed root.

    ``os.path.realpath`` collapses ``..`` and follows symlinks *before* the
    prefix check, which is what stops ``uploads/../../../etc/passwd`` and a
    symlink pointing outside the tree.
    """
    candidate = os.path.realpath(os.path.expanduser(path))

    for root in _ALLOWED_ROOTS:
        root_real = os.path.realpath(root)
        if candidate == root_real or candidate.startswith(root_real + os.sep):
            break
    else:
        raise ToolError(
            "That path is outside the project directory.",
            "Only files under the project (including static/uploads) can be read.",
        )

    lowered = candidate.lower()
    if any(part in lowered for part in _DENIED_NAMES):
        raise ToolError("That file is protected and cannot be read.")

    if not os.path.exists(candidate):
        raise ToolError(
            f"No such file: '{path}'.",
            "Check the filename, or upload the document first.",
        )
    if not os.path.isfile(candidate):
        raise ToolError(f"'{path}' is a directory, not a file.")

    size = os.path.getsize(candidate)
    if size > MAX_FILE_BYTES:
        raise ToolError(
            f"File is too large ({size // (1024 * 1024)} MB; limit is "
            f"{MAX_FILE_BYTES // (1024 * 1024)} MB).",
        )

    return candidate


def _read_text(path: str) -> str:
    """Read a text file, tolerating imperfect encodings."""
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as handle:
                return handle.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _read_pdf(path: str) -> str:
    """Extract per-page text from a PDF."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise ToolError("PyPDF2 is not installed.", "Run: pip install PyPDF2")

    reader = PdfReader(path)
    total = len(reader.pages)
    pages = []
    for index, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            pages.append(f"--- Page {index} ---\n{text.strip()}")

    if not pages:
        raise ToolError(
            "No extractable text in this PDF.",
            "It is probably a scanned image; OCR would be required.",
        )

    header = f"📄 PDF: {os.path.basename(path)} ({total} pages)\n\n"
    return header + truncate("\n\n".join(pages), MAX_CHARS,
                             note=f"{total} pages total")


def _read_csv(path: str, delimiter: str = ",") -> str:
    """
    Summarise a CSV: shape, columns, dtypes and a head sample.

    A structured profile answers far more questions per token than raw rows,
    and pandas is already a dependency of the Python sandbox.
    """
    try:
        import pandas as pd
        frame = pd.read_csv(path, sep=delimiter, nrows=5000)
    except ImportError:
        # Fall back to the stdlib reader if pandas is unavailable.
        with open(path, newline="", encoding="utf-8", errors="replace") as handle:
            rows = list(csv.reader(handle, delimiter=delimiter))
        if not rows:
            raise ToolError("The CSV file is empty.")
        head = "\n".join(", ".join(r) for r in rows[:20])
        return (f"📊 CSV: {os.path.basename(path)} "
                f"({len(rows)} rows, {len(rows[0])} columns)\n\n{head}")
    except Exception as exc:
        raise ToolError(f"Could not parse the CSV: {exc}")

    buffer = io.StringIO()
    buffer.write(f"📊 CSV: {os.path.basename(path)}\n")
    buffer.write(f"Shape: {frame.shape[0]:,} rows × {frame.shape[1]} columns\n\n")
    buffer.write("Columns:\n")
    for column in frame.columns:
        non_null = frame[column].notna().sum()
        buffer.write(f"  • {column} ({frame[column].dtype}, {non_null:,} non-null)\n")
    buffer.write(f"\nFirst rows:\n{frame.head(10).to_string()}\n")

    numeric = frame.select_dtypes("number")
    if not numeric.empty:
        buffer.write(f"\nNumeric summary:\n{numeric.describe().to_string()}\n")

    return truncate(buffer.getvalue(), MAX_CHARS)


def _read_json(path: str) -> str:
    """Pretty-print JSON, describing the top-level shape first."""
    raw = _read_text(path)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToolError(f"Invalid JSON on line {exc.lineno}: {exc.msg}")

    if isinstance(payload, list):
        shape = f"array of {len(payload)} items"
    elif isinstance(payload, dict):
        shape = f"object with keys: {', '.join(list(payload)[:20])}"
    else:
        shape = type(payload).__name__

    body = json.dumps(payload, indent=2, ensure_ascii=False)
    return (f"📋 JSON: {os.path.basename(path)} ({shape})\n\n"
            + truncate(body, MAX_CHARS))


def _read_docx(path: str) -> str:
    """Extract paragraphs and tables from a .docx via its XML parts."""
    import xml.etree.ElementTree as ET
    import zipfile

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ToolError(f"Could not read the .docx file: {exc}")

    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for para in root.iter(f"{{{namespace['w']}}}p"):
        text = "".join(node.text or "" for node in para.iter(f"{{{namespace['w']}}}t"))
        if text.strip():
            paragraphs.append(text.strip())

    if not paragraphs:
        raise ToolError("No text found in the document.")

    return (f"📝 Word document: {os.path.basename(path)} "
            f"({len(paragraphs)} paragraphs)\n\n"
            + truncate("\n\n".join(paragraphs), MAX_CHARS))


def _read_xlsx(path: str) -> str:
    """Summarise every sheet in a workbook."""
    try:
        import pandas as pd
        sheets = pd.read_excel(path, sheet_name=None, nrows=200)
    except ImportError:
        raise ToolError("pandas and openpyxl are needed to read .xlsx files.",
                        "Run: pip install pandas openpyxl")
    except Exception as exc:
        raise ToolError(f"Could not read the spreadsheet: {exc}")

    parts = [f"📈 Excel: {os.path.basename(path)} ({len(sheets)} sheet(s))\n"]
    for name, frame in sheets.items():
        parts.append(
            f"--- Sheet '{name}' — {frame.shape[0]} rows × {frame.shape[1]} cols ---\n"
            f"{frame.head(10).to_string()}\n"
        )
    return truncate("\n".join(parts), MAX_CHARS)


def read_file(file_path: str) -> str:
    """
    Read a document and return its text or a structured summary.

    Args:
        file_path: Path to the file, typically under ``static/uploads/``.

    Returns:
        Extracted content, or an actionable error message.
    """
    raw = clean_input(file_path)
    if not raw:
        return str(ToolError("No file path provided."))

    try:
        path = _resolve(raw)
    except ToolError as exc:
        return str(exc)

    extension = os.path.splitext(path)[1].lower()

    try:
        if extension == ".pdf":
            return _read_pdf(path)
        if extension == ".csv":
            return _read_csv(path)
        if extension in (".tsv", ".tab"):
            return _read_csv(path, delimiter="\t")
        if extension == ".json":
            return _read_json(path)
        if extension == ".docx":
            return _read_docx(path)
        if extension in (".xlsx", ".xlsm"):
            return _read_xlsx(path)

        if extension in TEXT_EXTENSIONS or extension in ("", ".text"):
            content = _read_text(path)
            if not content.strip():
                return str(ToolError("The file is empty."))
            return (f"📄 File: {os.path.basename(path)} "
                    f"({len(content):,} characters)\n\n"
                    + truncate(content, MAX_CHARS))

        return str(ToolError(
            f"Unsupported file type '{extension}'.",
            "Supported: .txt .md .pdf .csv .tsv .json .docx .xlsx and "
            "common source-code files.",
        ))

    except ToolError as exc:
        return str(exc)
    except Exception as exc:
        return str(ToolError(f"Could not read the file: {exc}"))


file_tool = Tool(
    name="read_file",
    description=(
        "Read an uploaded document and return its text or a structured "
        "summary. Handles PDF, DOCX, XLSX, CSV/TSV (shape, columns, dtypes "
        "and sample rows), JSON, Markdown, plain text and source files. "
        "Input is the file path, e.g. 'static/uploads/report.pdf'."
    ),
    function=read_file,
)
