"""PDF operations independent of the web layer."""

import logging
import os
import re
import shutil
import tempfile
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


class InputError(ValueError):
    """An input that cannot be processed."""


class OfficeUnavailable(RuntimeError):
    """Microsoft Office automation is not available."""


IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
DOCUMENT_EXTENSIONS = {
    ".csv", ".doc", ".docm", ".docx", ".html", ".htm", ".odp", ".ods",
    ".odt", ".ppt", ".pptm", ".pptx", ".rtf", ".txt", ".xls", ".xlsm",
    ".xlsx",
}
OFFICE_APPLICATIONS = {
    ".doc": ("Word.Application", "word"),
    ".docm": ("Word.Application", "word"),
    ".docx": ("Word.Application", "word"),
    ".html": ("Word.Application", "word"),
    ".htm": ("Word.Application", "word"),
    ".odt": ("Word.Application", "word"),
    ".rtf": ("Word.Application", "word"),
    ".txt": ("Word.Application", "word"),
    ".csv": ("Excel.Application", "excel"),
    ".ods": ("Excel.Application", "excel"),
    ".xls": ("Excel.Application", "excel"),
    ".xlsm": ("Excel.Application", "excel"),
    ".xlsx": ("Excel.Application", "excel"),
    ".odp": ("PowerPoint.Application", "powerpoint"),
    ".ppt": ("PowerPoint.Application", "powerpoint"),
    ".pptm": ("PowerPoint.Application", "powerpoint"),
    ".pptx": ("PowerPoint.Application", "powerpoint"),
}


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


def images_to_pdf(uploads: list[FileStorage], destination: Path) -> int:
    if not uploads:
        raise InputError("Upload at least one image to convert.")

    ordered = sorted(
        uploads,
        key=lambda upload: ((upload.filename or "").casefold(), upload.filename or ""),
    )
    pages = []
    try:
        for upload in ordered:
            filename = upload.filename or ""
            if not filename:
                raise InputError("Choose a filename for every image.")
            if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
                raise InputError(f"'{filename}' is not a supported image file.")
            try:
                upload.stream.seek(0)
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(upload.stream) as image:
                        image.load()
                        image = ImageOps.exif_transpose(image)
                        rgba = image.convert("RGBA")
                        page = Image.new("RGB", rgba.size, "white")
                        page.paste(rgba, mask=rgba.getchannel("A"))
                        pages.append(page)
            except (
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
                UnidentifiedImageError,
                OSError,
                EOFError,
                SyntaxError,
                ValueError,
            ) as error:
                raise InputError(
                    f"'{filename}' is empty, damaged, or too large to process as an image."
                ) from error
        pages[0].save(
            destination,
            "PDF",
            save_all=True,
            append_images=pages[1:],
            resolution=100.0,
        )
    finally:
        for page in pages:
            page.close()
    return len(pages)


def document_to_pdf(upload: FileStorage, destination: Path) -> None:
    filename = upload.filename or ""
    if not filename:
        raise InputError("Choose a document to convert.")
    suffix = Path(filename).suffix.lower()
    if suffix not in DOCUMENT_EXTENSIONS:
        raise InputError(
            f"'{filename}' is not a supported document type. Choose a Word, Excel, "
            "PowerPoint, OpenDocument, RTF, CSV, HTML, or text file."
        )
    if suffix not in OFFICE_APPLICATIONS:
        raise InputError(f"'{filename}' is not supported for Office conversion.")
    if os.name != "nt":
        raise OfficeUnavailable(
            "Document conversion requires Windows with Microsoft Office installed."
        )
    try:
        import pythoncom
        import pywintypes
        from win32com.client import DispatchEx
    except ImportError as error:
        raise OfficeUnavailable(
            "Document conversion requires pywin32. Install the application "
            "requirements in its Windows environment."
        ) from error

    safe_name = secure_filename(filename) or f"document{suffix}"
    with tempfile.TemporaryDirectory(prefix="document-convert-") as temporary:
        work = Path(temporary)
        source = work / safe_name
        upload.save(source)
        prog_id, office_type = OFFICE_APPLICATIONS[suffix]
        pythoncom.CoInitialize()
        application = None
        document = None
        try:
            try:
                application = DispatchEx(prog_id)
            except pywintypes.com_error as error:
                raise OfficeUnavailable(
                    f"Could not start {prog_id}. Make sure Microsoft Office is "
                    "installed and activated for the account running this app."
                ) from error
            try:
                application.Visible = False
                application.DisplayAlerts = 0
                application.AutomationSecurity = 3
                converted = work / f"{source.stem}.pdf"
                if office_type == "word":
                    document = application.Documents.Open(
                        str(source),
                        ConfirmConversions=False,
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        Visible=False,
                        OpenAndRepair=False,
                    )
                    document.ExportAsFixedFormat(str(converted), 17)
                elif office_type == "excel":
                    document = application.Workbooks.Open(
                        str(source),
                        UpdateLinks=0,
                        ReadOnly=True,
                        IgnoreReadOnlyRecommended=True,
                    )
                    document.ExportAsFixedFormat(0, str(converted))
                else:
                    document = application.Presentations.Open(
                        str(source),
                        ReadOnly=True,
                        Untitled=False,
                        WithWindow=False,
                    )
                    document.SaveAs(str(converted), 32)
            except pywintypes.com_error as error:
                raise InputError(
                    f"'{filename}' could not be opened or exported by Microsoft "
                    "Office. Check that the file is valid and supported."
                ) from error
            if not converted.is_file() or converted.stat().st_size == 0:
                raise InputError(
                    f"Microsoft Office did not create a PDF for '{filename}'."
                )
            shutil.copyfile(converted, destination)
        finally:
            if document is not None:
                try:
                    document.Close(False)
                except pywintypes.com_error:
                    logger.exception("Could not close Office document after conversion.")
            if application is not None:
                try:
                    application.Quit()
                except pywintypes.com_error:
                    logger.exception("Could not close Office application after conversion.")
            pythoncom.CoUninitialize()


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
