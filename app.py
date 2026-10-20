"""Flask application and temporary download lifecycle."""

import os
import re
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import click
from flask import Flask, jsonify, render_template, request, send_from_directory, url_for
from pypdf.errors import PdfReadError
from werkzeug.exceptions import HTTPException

from pdf_tools import (
    ConverterUnavailable,
    InputError,
    analyze_pdf,
    document_to_pdf,
    images_to_pdf as convert_images_to_pdf,
    merge_pdfs,
    parse_ranges,
    read_pdf,
    split_pdf,
)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024,
        OUTPUT_TTL_SECONDS=int(os.environ.get("OUTPUT_TTL_SECONDS", "3600")),
        OUTPUT_DIR=os.environ.get(
            "PDF_OUTPUT_DIR", str(Path(app.instance_path) / "outputs")
        ),
    )
    if test_config:
        app.config.update(test_config)
    if app.config["OUTPUT_TTL_SECONDS"] <= 0:
        raise ValueError("OUTPUT_TTL_SECONDS must be positive.")
    if app.config["MAX_CONTENT_LENGTH"] <= 0:
        raise ValueError("MAX_UPLOAD_MB must be positive.")
    output_root = Path(app.config["OUTPUT_DIR"]).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    def cleanup_outputs():
        cutoff = time.time() - app.config["OUTPUT_TTL_SECONDS"]
        for directory in output_root.iterdir():
            if re.fullmatch(r"[0-9a-f]{32}", directory.name) and directory.is_dir():
                try:
                    if directory.stat().st_mtime < cutoff:
                        shutil.rmtree(directory)
                except FileNotFoundError:
                    # Another worker may have removed the same expired output.
                    continue

    @app.cli.command("cleanup-outputs")
    def cleanup_command():
        """Remove expired output directories."""
        cleanup_outputs()
        click.echo("Expired outputs removed.")

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            max_upload_mb=app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
            retention_minutes=app.config["OUTPUT_TTL_SECONDS"] / 60,
        )

    def download_info(job, name, **metadata):
        return {
            "name": name,
            "url": url_for("download", job=job, filename=name),
            **metadata,
        }

    @app.post("/api/analyze")
    def analyze():
        uploads = request.files.getlist("file")
        if not uploads:
            raise InputError("Upload at least one PDF to analyze.")
        if len(uploads) == 1:
            analysis = analyze_pdf(uploads[0])
            return jsonify(analysis=analysis, analyses=[{"analysis": analysis}])
        results = []
        for upload in uploads:
            try:
                results.append({"analysis": analyze_pdf(upload)})
            except InputError as error:
                results.append({"filename": upload.filename, "error": str(error)})
            except PdfReadError as error:
                app.logger.warning("PDF could not be analyzed: %s", error)
                results.append({
                    "filename": upload.filename,
                    "error": "This PDF is empty, damaged, or unreadable. Upload a valid PDF.",
                })
        return jsonify(analyses=results)

    @app.post("/api/split")
    def split():
        cleanup_outputs()
        uploads = request.files.getlist("file")
        if len(uploads) != 1:
            raise InputError("Upload exactly one PDF to split.")
        reader = read_pdf(uploads[0])
        ranges = parse_ranges(request.form.get("ranges", ""), len(reader.pages))
        job = uuid4().hex
        with tempfile.TemporaryDirectory(prefix="split-") as working:
            work = Path(working)
            results = split_pdf(reader, ranges, uploads[0].filename, work)
            archive_name = "Split PDFs.zip"
            with ZipFile(work / archive_name, "w", ZIP_DEFLATED) as archive:
                for result in results:
                    archive.write(work / result["name"], result["name"])
            shutil.copytree(work, output_root / job)
            os.utime(output_root / job, None)
        return jsonify(
            cleanup_url=url_for("delete_job", job=job),
            files=[download_info(job, **result) for result in results],
            archive=download_info(job, archive_name),
        )

    @app.post("/api/merge")
    def merge():
        cleanup_outputs()
        uploads = request.files.getlist("files")
        if len(uploads) < 2:
            raise InputError("Upload at least two PDFs to merge.")
        readers = [read_pdf(upload) for upload in uploads]
        job = uuid4().hex
        name = f"Merged PDFs {datetime.now():%Y%m%d-%H%M%S}.pdf"
        with tempfile.TemporaryDirectory(prefix="merge-") as working:
            work = Path(working)
            pages = merge_pdfs(readers, work / name)
            shutil.copytree(work, output_root / job)
            os.utime(output_root / job, None)
        return jsonify(
            cleanup_url=url_for("delete_job", job=job),
            file=download_info(job, name, pages=pages),
        )

    @app.post("/api/images-to-pdf")
    def images_to_pdf():
        cleanup_outputs()
        uploads = request.files.getlist("files")
        if not uploads:
            raise InputError("Upload at least one image to convert.")
        job = uuid4().hex
        name = f"Images to PDF {datetime.now():%Y%m%d-%H%M%S}.pdf"
        with tempfile.TemporaryDirectory(prefix="images-to-pdf-") as working:
            work = Path(working)
            pages = convert_images_to_pdf(uploads, work / name)
            shutil.copytree(work, output_root / job)
            os.utime(output_root / job, None)
        return jsonify(
            cleanup_url=url_for("delete_job", job=job),
            file=download_info(job, name, pages=pages),
        )

    @app.post("/api/document-to-pdf")
    def document_to_pdf_route():
        cleanup_outputs()
        uploads = request.files.getlist("file")
        if len(uploads) != 1:
            raise InputError("Upload exactly one document to convert.")
        stem = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            Path(uploads[0].filename or "document").stem,
        ).strip("._")[:120] or "document"
        name = f"Converted {stem}.pdf"
        job = uuid4().hex
        with tempfile.TemporaryDirectory(prefix="document-to-pdf-") as working:
            work = Path(working)
            document_to_pdf(uploads[0], work / name)
            shutil.copytree(work, output_root / job)
            os.utime(output_root / job, None)
        return jsonify(
            cleanup_url=url_for("delete_job", job=job),
            file=download_info(job, name),
        )

    @app.delete("/api/jobs/<job>")
    def delete_job(job):
        if not re.fullmatch(r"[0-9a-f]{32}", job):
            return jsonify(error="Job not found."), 404
        try:
            shutil.rmtree(output_root / job)
        except FileNotFoundError:
            # Reset also succeeds if expiry cleanup already removed the job.
            pass
        except OSError:
            app.logger.exception("Could not remove output job %s", job)
            return jsonify(
                error="Could not clean up the previous job. Finish any active downloads and try Reset again."
            ), 409
        return "", 204

    @app.get("/downloads/<job>/<filename>")
    def download(job, filename):
        if not re.fullmatch(r"[0-9a-f]{32}", job):
            return jsonify(error="Download not found."), 404
        directory = output_root / job
        try:
            expired = time.time() - directory.stat().st_mtime >= app.config["OUTPUT_TTL_SECONDS"]
        except FileNotFoundError:
            return jsonify(error="Download not found or expired. Process your PDFs again."), 404
        if expired:
            return jsonify(error="Download expired. Process your PDFs again."), 410
        return send_from_directory(directory, filename, as_attachment=True, max_age=0)

    @app.errorhandler(InputError)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(ConverterUnavailable)
    def converter_unavailable(error):
        return jsonify(error=str(error)), 503

    @app.errorhandler(PdfReadError)
    def invalid_pdf(error):
        app.logger.warning("PDF could not be processed: %s", error)
        return jsonify(error="A PDF is empty, damaged, or unreadable. Upload a valid PDF."), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        if error.code == 413:
            message = "Upload too large. The total request limit is " + str(
                app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
            ) + " MB."
        else:
            message = error.description
        return jsonify(error=message), error.code

    @app.errorhandler(500)
    def server_error(error):
        return jsonify(error="Processing failed unexpectedly. Please check the server logs."), 500

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
