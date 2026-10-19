import io
import os
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from zipfile import ZipFile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, FloatObject, NameObject
from werkzeug.datastructures import MultiDict

from app import create_app
from pdf_tools import InputError, parse_ranges


def pdf_bytes(widths=(101, 102, 103, 104), encrypted=False):
    stream = io.BytesIO()
    with PdfWriter() as writer:
        for width in widths:
            writer.add_blank_page(width=width, height=200)
        if encrypted:
            writer.encrypt("password")
        writer.write(stream)
    stream.seek(0)
    return stream


def widths(data):
    return [int(page.mediabox.width) for page in PdfReader(io.BytesIO(data)).pages]


class RangeTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_ranges(" 1 - 3, 4, 2-2 ", 4), [(1, 3), (4, 4), (2, 2)])

    def test_invalid(self):
        for value in ("", " ", "0", "-1", "3-2", "1-5", "5", "1,", ",1",
                      "1,,2", "1.5", "a", "1-2-3", "1;2", "1 2", "9" * 5000):
            with self.subTest(value=value[:40]), self.assertRaises(InputError):
                parse_ranges(value, 4)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "outputs"
        self.app = create_app({
            "TESTING": True,
            "OUTPUT_DIR": str(self.root),
            "OUTPUT_TTL_SECONDS": 3600,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def download(self, url):
        response = self.client.get(url)
        data = response.get_data()
        response.close()
        self.assertEqual(response.status_code, 200)
        return data

    def split(self, ranges="1-2, 3, 4"):
        return self.client.post("/api/split", data={
            "file": (pdf_bytes(), "report.pdf"), "ranges": ranges,
        })

    def test_home_and_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Split a PDF", response.data)
        self.assertEqual(response.data.count(b'class="secondary reset"'), 3)
        self.assertGreater(response.data.index(b'id="analyze-title"'),
                           response.data.index(b'id="merge-title"'))
        self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        for path in ("/static/app.js", "/static/style.css"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_split_pages_names_and_zip(self):
        response = self.split()
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([file["pages"] for file in payload["files"]], [2, 1, 1])
        expected = [[101, 102], [103], [104]]
        for file, pages in zip(payload["files"], expected):
            self.assertTrue(file["name"].startswith("report_part_"))
            self.assertEqual(widths(self.download(file["url"])), pages)
        with ZipFile(io.BytesIO(self.download(payload["archive"]["url"]))) as archive:
            self.assertEqual(archive.namelist(), [file["name"] for file in payload["files"]])
            for file, pages in zip(payload["files"], expected):
                self.assertEqual(widths(archive.read(file["name"])), pages)

    def test_duplicate_and_overlapping_ranges_preserve_request_order(self):
        payload = self.split("4, 1-2, 1-2").get_json()
        self.assertEqual(len({file["name"] for file in payload["files"]}), 3)
        self.assertEqual(
            [widths(self.download(file["url"])) for file in payload["files"]],
            [[104], [101, 102], [101, 102]],
        )

    def test_out_of_bounds_is_atomic(self):
        response = self.split("1, 5")
        self.assertEqual(response.status_code, 400)
        self.assertIn("4 pages", response.get_json()["error"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_merge_preserves_file_and_page_order(self):
        response = self.client.post("/api/merge", data=MultiDict([
            ("files", (pdf_bytes((301, 302)), "same.pdf")),
            ("files", (pdf_bytes((101,)), "same.pdf")),
            ("files", (pdf_bytes((201, 202)), "third.pdf")),
        ]))
        self.assertEqual(response.status_code, 200)
        file = response.get_json()["file"]
        self.assertRegex(file["name"], r"^Merged PDFs \d{8}-\d{6}\.pdf$")
        self.assertEqual(file["pages"], 5)
        self.assertEqual(widths(self.download(file["url"])), [301, 302, 101, 201, 202])

    def test_missing_uploads(self):
        for endpoint in ("split", "merge"):
            response = self.client.post(f"/api/{endpoint}", data={})
            self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/merge", data={"files": (pdf_bytes(), "one.pdf")})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/split", data=MultiDict([
            ("file", (pdf_bytes(), "a.pdf")), ("file", (pdf_bytes(), "b.pdf")),
            ("ranges", "1"),
        ]))
        self.assertEqual(response.status_code, 400)

    def test_invalid_pdf_inputs(self):
        cases = [
            (b"not a PDF", "bad.pdf"), (b"", "empty.pdf"),
            (pdf_bytes().getvalue(), "wrong.txt"),
            (pdf_bytes(encrypted=True).getvalue(), "locked.pdf"),
            (pdf_bytes(()).getvalue(), "no-pages.pdf"),
            (pdf_bytes().getvalue(), ""),
        ]
        for data, filename in cases:
            with self.subTest(filename=filename):
                response = self.client.post("/api/split", data={
                    "file": (io.BytesIO(data), filename), "ranges": "1",
                })
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bad_merge_does_not_publish_partial_output(self):
        response = self.client.post("/api/merge", data=MultiDict([
            ("files", (pdf_bytes(), "valid.pdf")),
            ("files", (io.BytesIO(b"bad"), "invalid.pdf")),
        ]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_safe_output_names_and_isolated_operations(self):
        response = self.client.post("/api/split", data={
            "file": (pdf_bytes(), "../../report.pdf"), "ranges": "1",
        })
        file = response.get_json()["files"][0]
        self.assertEqual(file["name"], "report_part_01_pages_1.pdf")
        second_file = self.split("1").get_json()["files"][0]
        self.assertNotEqual(file["url"], second_file["url"])
        self.assertEqual(widths(self.download(file["url"])), [101])

    def test_expiration_and_cleanup(self):
        payload = self.split().get_json()
        job = next(self.root.iterdir())
        old = time.time() - 3700
        os.utime(job, (old, old))
        response = self.client.get(payload["files"][0]["url"])
        self.assertEqual(response.status_code, 410)
        result = self.app.test_cli_runner().invoke(args=["cleanup-outputs"])
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(job.exists())
        self.assertEqual(self.client.get(payload["archive"]["url"]).status_code, 404)

    def test_new_operation_cleans_expired_outputs(self):
        self.split()
        old_job = next(self.root.iterdir())
        old = time.time() - 3700
        os.utime(old_job, (old, old))
        self.assertEqual(self.split().status_code, 200)
        self.assertFalse(old_job.exists())

    def test_unknown_and_traversal_downloads(self):
        for url in ("/downloads/no-job/test.pdf",
                    f"/downloads/{'a' * 32}/test.pdf",
                    "/missing"):
            self.assertEqual(self.client.get(url).status_code, 404)
        file = self.split("1").get_json()["files"][0]
        base = file["url"].rsplit("/", 1)[0]
        self.assertEqual(self.client.get(base + "/..%5Capp.py").status_code, 404)

    def test_request_limit(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 512
        response = self.client.post("/api/split", data={
            "file": (io.BytesIO(b"x" * 1024), "large.pdf"), "ranges": "1",
        })
        self.assertEqual(response.status_code, 413)
        self.assertIn("Upload too large", response.get_json()["error"])

    def test_reset_deletes_only_selected_job(self):
        split = self.split().get_json()
        merge = self.client.post("/api/merge", data=MultiDict([
            ("files", (pdf_bytes(), "a.pdf")),
            ("files", (pdf_bytes(), "b.pdf")),
        ])).get_json()
        self.assertEqual(self.client.delete(split["cleanup_url"]).status_code, 204)
        for file in [*split["files"], split["archive"]]:
            self.assertEqual(self.client.get(file["url"]).status_code, 404)
        self.assertEqual(widths(self.download(merge["file"]["url"])), [101, 102, 103, 104] * 2)
        self.assertEqual(self.client.delete(merge["cleanup_url"]).status_code, 204)
        self.assertEqual(self.client.get(merge["file"]["url"]).status_code, 404)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_reset_missing_or_invalid_job(self):
        payload = self.split().get_json()
        for _ in range(2):
            self.assertEqual(self.client.delete(payload["cleanup_url"]).status_code, 204)
        self.assertEqual(self.client.delete("/api/jobs/" + "a" * 32).status_code, 204)
        self.assertEqual(self.client.delete("/api/jobs/invalid").status_code, 404)
        self.assertEqual(self.client.delete("/api/jobs/..%5Coutputs").status_code, 404)

    def test_reset_reports_cleanup_failure(self):
        payload = self.split("1").get_json()
        with patch("app.shutil.rmtree", side_effect=PermissionError("File in use")):
            with self.assertLogs(self.app.logger, level="ERROR"):
                response = self.client.delete(payload["cleanup_url"])
        self.assertEqual(response.status_code, 409)
        self.assertIn("try Reset again", response.get_json()["error"])
        self.assertEqual(widths(self.download(payload["files"][0]["url"])), [101])
        self.assertEqual(self.client.delete(payload["cleanup_url"]).status_code, 204)

    def test_analysis_summary_metadata_and_page_dimensions(self):
        stream = io.BytesIO()
        with PdfWriter() as writer:
            portrait = writer.add_blank_page(width=100, height=200)
            portrait[NameObject("/UserUnit")] = FloatObject(2)
            writer.add_blank_page(width=100, height=200).rotate(90)
            writer.add_blank_page(width=100, height=100)
            writer.add_metadata({"/Title": "<script>Example</script>", "/Author": "Test Author"})
            writer.write(stream)
        size = stream.tell()
        stream.seek(0)
        response = self.client.post("/api/analyze", data={"file": (stream, "summary.pdf")})
        self.assertEqual(response.status_code, 200)
        analysis = response.get_json()["analysis"]
        self.assertEqual(analysis["filename"], "summary.pdf")
        self.assertEqual(analysis["size_bytes"], size)
        self.assertFalse(analysis["encrypted"])
        self.assertEqual(analysis["page_count"], 3)
        self.assertEqual(analysis["metadata"]["Title"], "<script>Example</script>")
        self.assertEqual(analysis["metadata"]["Author"], "Test Author")
        self.assertEqual(analysis["document_properties"]["Author"], "Test Author")
        self.assertIsNone(analysis["document_properties"]["Subject"])
        self.assertEqual(analysis["pages"], [
            {"number": 1, "width_points": 200, "height_points": 400,
             "rotation": 0, "orientation": "Portrait"},
            {"number": 2, "width_points": 200, "height_points": 100,
             "rotation": 90, "orientation": "Landscape"},
            {"number": 3, "width_points": 100, "height_points": 100,
             "rotation": 0, "orientation": "Square"},
        ])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_analysis_encrypted_pdf(self):
        stream = pdf_bytes(encrypted=True)
        size = len(stream.getvalue())
        response = self.client.post("/api/analyze", data={"file": (stream, "locked.pdf")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["analysis"], {
            "filename": "locked.pdf", "size_bytes": size, "encrypted": True,
            "page_count": None, "metadata": {}, "document_properties": {}, "pages": [],
        })
        self.assertEqual(list(self.root.iterdir()), [])

    def test_analysis_invalid_uploads(self):
        self.assertEqual(self.client.post("/api/analyze").status_code, 400)
        for stream, filename in [
            (io.BytesIO(b"invalid"), "bad.pdf"), (io.BytesIO(), "empty.pdf"),
            (pdf_bytes(()), "zero.pdf"), (pdf_bytes(), "wrong.txt"),
        ]:
            with self.subTest(filename=filename):
                response = self.client.post("/api/analyze", data={"file": (stream, filename)})
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_analysis_multiple_files_and_individual_errors(self):
        response = self.client.post("/api/analyze", data=MultiDict([
            ("file", (pdf_bytes((100,)), "same.pdf")),
            ("file", (io.BytesIO(b"invalid"), "broken.pdf")),
            ("file", (pdf_bytes((200, 300)), "same.pdf")),
            ("file", (pdf_bytes(encrypted=True), "locked.pdf")),
            ("file", (pdf_bytes(), "wrong.txt")),
        ]))
        self.assertEqual(response.status_code, 200)
        results = response.get_json()["analyses"]
        self.assertEqual(len(results), 5)
        self.assertEqual(results[0]["analysis"]["page_count"], 1)
        self.assertEqual(results[1]["filename"], "broken.pdf")
        self.assertIn("error", results[1])
        self.assertEqual(results[2]["analysis"]["page_count"], 2)
        self.assertTrue(results[3]["analysis"]["encrypted"])
        self.assertIn("error", results[4])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_analysis_xmp_metadata_and_info_precedence(self):
        stream = io.BytesIO()
        with PdfWriter() as writer:
            writer.add_blank_page(width=100, height=200)
            writer.add_metadata({"/Title": "Info title", "/Author": " "})
            xmp = DecodedStreamObject()
            xmp.set_data(b'''<x:xmpmeta xmlns:x="adobe:ns:meta/">
              <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
                <rdf:Description rdf:about=""
                  xmlns:dc="http://purl.org/dc/elements/1.1/"
                  xmlns:xmp="http://ns.adobe.com/xap/1.0/"
                  xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
                  <dc:creator><rdf:Seq><rdf:li>First Author</rdf:li>
                    <rdf:li>Second Author</rdf:li></rdf:Seq></dc:creator>
                  <dc:title><rdf:Alt><rdf:li xml:lang="x-default">XMP title</rdf:li></rdf:Alt></dc:title>
                  <dc:description><rdf:Alt><rdf:li xml:lang="x-default">XMP subject</rdf:li></rdf:Alt></dc:description>
                  <dc:subject><rdf:Bag><rdf:li>Example</rdf:li></rdf:Bag></dc:subject>
                  <xmp:CreatorTool>Example Tool</xmp:CreatorTool>
                  <xmp:CreateDate>2026-10-19T10:00:00Z</xmp:CreateDate>
                </rdf:Description>
              </rdf:RDF>
            </x:xmpmeta>''')
            xmp[NameObject("/Type")] = NameObject("/Metadata")
            xmp[NameObject("/Subtype")] = NameObject("/XML")
            writer.root_object[NameObject("/Metadata")] = writer._add_object(xmp)
            writer.write(stream)
        stream.seek(0)
        response = self.client.post("/api/analyze", data={"file": (stream, "xmp.pdf")})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["analysis"], payload["analyses"][0]["analysis"])
        properties = payload["analysis"]["document_properties"]
        self.assertEqual(properties["Author"], "First Author, Second Author")
        self.assertEqual(properties["Title"], "Info title")
        self.assertEqual(properties["Subject"], "XMP subject")
        self.assertEqual(properties["Keywords"], "Example")
        self.assertEqual(properties["Creator"], "Example Tool")
        self.assertTrue(properties["CreationDate"].startswith("2026-10-19"))
        self.assertIsNone(properties["ModDate"])

    def test_analysis_does_not_change_existing_job(self):
        payload = self.split("1").get_json()
        response = self.client.post("/api/analyze", data={"file": (pdf_bytes(), "test.pdf")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(widths(self.download(payload["files"][0]["url"])), [101])

    def test_analysis_request_limit(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 512
        response = self.client.post("/api/analyze", data={
            "file": (io.BytesIO(b"x" * 1024), "large.pdf"),
        })
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
