"""PDF operations independent of the web layer."""

import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class InputError(ValueError):
    """An input that cannot be processed."""


def read_pdf(upload: FileStorage, *, allow_encrypted: bool = False) -> PdfReader:
    name = upload.filename or ""
    if not name:
        raise InputError("Choose a PDF for every upload row.")
    if not name.lower().endswith(".pdf"):
        raise InputError(f"'{name}' must have a .pdf extension.")
    reader = PdfReader(upload.stream)
    if reader.is_encrypted:
        if allow_encrypted:
            return reader
        raise InputError(f"'{name}' is encrypted. Upload an unencrypted copy.")
    if not len(reader.pages):
        raise InputError(f"'{name}' contains no pages.")
    return reader


def analyze_pdf(upload: FileStorage) -> dict:
    reader = read_pdf(upload, allow_encrypted=True)
    upload.stream.seek(0, 2)
    summary = {
        "filename": upload.filename,
        "size_bytes": upload.stream.tell(),
        "encrypted": reader.is_encrypted,
        "page_count": None,
        "metadata": {},
        "document_properties": {},
        "pages": [],
    }
    if reader.is_encrypted:
        return summary
    summary["page_count"] = len(reader.pages)
    summary["metadata"] = {
        str(key).removeprefix("/"): str(value)
        for key, value in (reader.metadata or {}).items()
    }
    xmp = reader.xmp_metadata

    def xmp_text(value):
        if isinstance(value, dict):
            return value.get("x-default") or next(iter(value.values()), None)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) or None
        return str(value) if value is not None else None

    fields = [
        ("Title", "dc_title"),
        ("Author", "dc_creator"),
        ("Subject", "dc_description"),
        ("Keywords", "dc_subject"),
        ("Creator", "xmp_creator_tool"),
        ("Producer", "pdf_producer"),
        ("CreationDate", "xmp_create_date"),
        ("ModDate", "xmp_modify_date"),
    ]
    for name, xmp_field in fields:
        value = summary["metadata"].get(name)
        if not value or not value.strip():
            value = xmp_text(getattr(xmp, xmp_field)) if xmp is not None else None
        summary["document_properties"][name] = value
    for number, page in enumerate(reader.pages, 1):
        width = float(page.mediabox.width) * float(page.user_unit)
        height = float(page.mediabox.height) * float(page.user_unit)
        rotation = page.rotation % 360
        if rotation in (90, 270):
            width, height = height, width
        summary["pages"].append({
            "number": number,
            "width_points": round(width, 2),
            "height_points": round(height, 2),
            "rotation": rotation,
            "orientation": "Square" if width == height else (
                "Landscape" if width > height else "Portrait"
            ),
        })
    return summary


def parse_ranges(value: str, page_count: int) -> list[tuple[int, int]]:
    if not value.strip():
        raise InputError("Enter at least one page number or range.")
    ranges = []
    for item in value.split(","):
        match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?", item)
        if not match:
            raise InputError(
                f"Invalid range '{item.strip()}'. Use comma-separated entries such as 1-5, 6, 8-23."
            )
        try:
            start = int(match[1])
            end = int(match[2] or match[1])
        except ValueError as error:
            raise InputError("A page number is too large.") from error
        if start < 1 or end < start:
            raise InputError(f"Invalid range '{item.strip()}': use ascending page numbers starting at 1.")
        if end > page_count:
            raise InputError(
                f"Range '{item.strip()}' exceeds the PDF's {page_count} pages."
            )
        ranges.append((start, end))
    return ranges


def split_pdf(reader: PdfReader, ranges: list[tuple[int, int]],
              filename: str, destination: Path) -> list[dict]:
    stem = Path(secure_filename(filename)).stem or "document"
    # Keep space for suffixes within common filesystem filename limits.
    stem = stem[:120]
    results = []
    for index, (start, end) in enumerate(ranges, 1):
        label = str(start) if start == end else f"{start}-{end}"
        name = f"{stem}_part_{index:02d}_pages_{label}.pdf"
        with PdfWriter() as writer:
            for page in range(start - 1, end):
                writer.add_page(reader.pages[page])
            writer.write(destination / name)
        results.append({"name": name, "pages": end - start + 1})
    return results


def merge_pdfs(readers: list[PdfReader], destination: Path) -> int:
    page_count = 0
    with PdfWriter() as writer:
        for reader in readers:
            for page in reader.pages:
                writer.add_page(page)
                page_count += 1
        writer.write(destination)
    return page_count
