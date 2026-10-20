# NR's PDF Workshop

A Python web application for converting images and documents to PDF, splitting,
merging, and analyzing PDF documents.
The responsive browser interface supports uploads, processing indicators, readable validation
errors, and direct downloads. No Node.js, database, external PDF API, or frontend
build step is required.

## Features

- **Split:** enter comma-separated page ranges or individual pages, for example
  `1-5, 6, 7, 8-23`. Each entry produces a separate PDF in the order entered.
  Page numbers start at 1; endpoints are inclusive. Overlapping and repeated
  entries are allowed and produce independently named files.
- **Validation:** an invalid, reversed, zero-based, or out-of-bounds range rejects
  the entire operation without publishing partial results. Empty, unreadable,
  non-PDF, and unencrypted zero-page inputs show errors. Splitting and merging
  also reject encrypted inputs; analysis reports their encryption status.
- **Split downloads:** download every generated PDF separately, or download all
  of them in one ZIP. `report.pdf` with `1-5, 6` produces
  `report_part_01_pages_1-5.pdf` and `report_part_02_pages_6.pdf`.
- **Merge:** enter the number of PDFs (at least two), click **Set upload rows**,
  and select one PDF per row. Use **Move up** / **Move down** to change order.
  All pages in the first row precede all pages in the second row, and so on.
  Increasing the row count preserves existing selections; decreasing it removes
  selections in the discarded bottom rows.
- **Merged download:** one file named `Merged PDFs YYYYMMDD-HHMMSS.pdf`, using the
  server's local date and time. Separate operation directories prevent filename
  collisions even when multiple merges finish in the same second.
- **Images to PDF:** upload one or more BMP, GIF, JPEG, PNG, TIFF, or WebP images
  to create one PDF. Pages are ordered by uploaded filename in case-insensitive
  ascending order, regardless of picker selection order. Each image contributes
  one page; transparent areas are rendered white.
- **Documents to PDF:** convert a single Word, Excel, PowerPoint, OpenDocument,
  RTF, CSV, HTML, or text file to PDF using locally installed Microsoft Office.
  Conversion uses Word, Excel, or PowerPoint automation as appropriate. The
  converter runs locally; files are not sent to a third-party service.
  Unsupported or invalid files return an error.
- **Loading state:** each operation disables its controls and displays a spinner
  throughout upload and processing. The page stays responsive, and each form can
  be used independently. This is an activity indicator, not percentage progress.
- **Reset:** each form has its own Reset button. It clears selected files,
  ranges, errors, and results, and deletes that form's previous generated files
  from the server, if any. Merge resets to two empty upload rows; analysis
  clears its displayed report without deleting files. The other forms are
  unaffected. Reset is disabled while processing or cleaning up; if cleanup
  fails, an error is shown and the form is retained so you can retry.
- **Analyze:** a separate section below the conversion tools shows the uploaded
  filename, exact file size, page count, encryption status, document metadata,
  and per-page dimensions, rotation, and orientation. Select multiple PDFs at
  once to get a separate numbered report for each, in upload order. Author and
  other common properties are always listed, with **Not provided** for missing
  values and XMP metadata used as a fallback. Analysis has its own
  loading indicator and Reset button and does not create downloadable files.

## Requirements

- Python **3.10 or newer** (Python 3.14 is supported).
- **Microsoft Office desktop applications** installed and activated on Windows
  for document conversion, with the corresponding Office application available
  to the account running the app.
- A user-interactive Windows session for Office automation. Microsoft Office
  COM automation is not recommended for unattended server/service processes;
  image conversion does not require Office.
- A current web browser with JavaScript enabled.
- Disk space for generated PDFs and ZIPs; RAM appropriate to the documents.
- Internet access to install dependencies initially. The app itself does not
  need internet access.

## Quick start on Windows (PowerShell)

Open PowerShell in the project directory, where `app.py` and `requirements.txt`
are located.

```powershell
# Create an isolated environment (skip if .venv already exists).
py -m venv .venv

# Install dependencies into that environment.
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Start the local development server.
.\.venv\Scripts\python.exe -m flask --app app:create_app run --host 127.0.0.1 --port 5000
```

Open **http://127.0.0.1:5000** in your browser on the same computer.
**http://localhost:5000** is equivalent. Leave the terminal open while using the
application; press **Ctrl+C** to stop it.

You can also run `.\.venv\Scripts\python.exe app.py` for the same local address.
No virtual-environment activation is necessary when using the explicit Python
path, so PowerShell execution-policy changes are not needed.

### Use the application

To split a document, choose a source PDF, enter ranges such as `1-5, 6, 7, 8-23`,
and click **Split PDF**. After processing, click a filename to download that
sub-file, or **Download all files as ZIP**. A request for page 23 of a 20-page
document produces an error rather than silently truncating the range.

To merge documents, set the number of PDFs, click **Set upload rows**, and choose
each document in the intended order. Reorder rows if needed, then click
**Merge PDFs** and download the resulting file. The count field only changes
the rows when **Set upload rows** is clicked; the displayed rows define the
actual merge order.

### Convert images and documents

To create a PDF from images, select one or more supported images and click
**Convert Images to PDF**. The output contains one page per image, sorted by
filename in case-insensitive ascending order; the order in the file picker does
not affect it.

To convert an office document, select one supported Word, Excel, PowerPoint,
OpenDocument, RTF, CSV, HTML, or text file and click **Convert Document to PDF**.
Microsoft Word, Excel, and/or PowerPoint must be installed and activated on the
Windows computer running the app. Each format is converted by its corresponding
Office desktop application. A single document is converted per request. Office
automation runs in the app's user session and may not work when the app is run
as an unattended Windows service.

Do not refresh or close the page while processing. Downloads are links to
server-generated files; save them before they expire. Refreshing the page clears
the displayed result links and any displayed analysis.

For Split, Merge, and either conversion form, download anything you want to
keep before clicking **Reset** or submitting another job in the same form:
both remove that form's previous generated outputs and invalidate their
download links. Files already saved to your computer are not deleted.

### Analyze PDFs

1. Scroll to **Analyze PDFs**, below the conversion tools.
2. Choose one or more PDFs (use Ctrl/Cmd or Shift in the file picker) and click **Analyze PDFs**.
3. Wait for the upload and processing indicator to finish.
4. Read each file's separate document summary, metadata, and scrollable
   page-dimensions table. Unreadable files in a batch show individual errors
   without hiding reports for valid files.

Each report section is headed by its sequence number and filename, so even
files with identical names remain separate. Files are analyzed independently,
not merged. Selecting a new batch replaces the file picker's current selection;
clicking **Analyze PDFs** again replaces all previously displayed reports.
The reports appear after the batch finishes; they are not streamed individually
while processing.

| Result | Details |
|--------|---------|
| Filename | Original uploaded filename |
| File size | Exact byte count and size in MiB |
| Encryption | Whether the PDF is encrypted |
| Page count | Number of physical pages, not printed page labels |
| Metadata | Title, author, subject, keywords, creator application, PDF producer, creation and modification dates, plus any additional document information fields |
| Page dimensions | Width and height in points for each page; 72 points equal one inch |
| Orientation | Portrait, Landscape, or Square based on the reported dimensions |
| Rotation | Page rotation in degrees, normalized to 0-359 |

Dimensions use the page's MediaBox, scaled by UserUnit and adjusted for page
rotation; the visible cropped area may differ. Metadata is shown as stored in
the PDF. Common properties use the document information dictionary first,
falling back to XMP metadata when a field is missing or blank. Date values from
the information dictionary are shown as stored; XMP dates are parsed and shown
as date/time strings. Missing common properties explicitly show **Not provided**:
the application cannot infer an author or other details not embedded in the PDF.
Metadata may be inaccurate and is not independently verified.

#### Why an author or other property may be missing

An author name is not required in a PDF. Export tools may omit it, strip it for
privacy, or store it only in XMP rather than the standard information dictionary.
The Analyzer checks both sources and always displays common property labels.
**Not provided** means neither source supplies that value; it is not inferred
from the filename, page text, operating-system file owner, or upload account.
Encrypted documents cannot expose these properties through this Analyzer.

Encrypted PDFs show their filename, size, and encryption status, but page count,
metadata, and page details are unavailable without an unencrypted copy. No
password is requested and no decryption is attempted.

Analysis runs on the same server and uses the same upload limit as Split and
Merge; the limit applies to the total batch, not each file. It does not modify
the PDFs, create downloadable reports, or save analysis outputs. Click its
**Reset** button to clear all selected files and all report/error sections.
Running or resetting analysis does not affect results from other operations.
Analysis is a document summary, not OCR, text extraction, PDF repair, or a
malware/security scan.

### Reset an operation

1. Save any generated PDFs or ZIP you want to keep.
2. Click **Reset** beneath the operation you want to clear.
3. Wait for the cleanup indicator to finish before selecting new inputs.

Split Reset clears the source file and page ranges. Merge Reset clears all
selected files and restores two empty upload rows with a file count of `2`.
Both clear their own errors and results and remove their previous job's PDFs
and ZIP, if present, from server storage. Neither affects the other operation
or deletes original files on your computer.

Analyze Reset clears all its selected files, errors, and displayed reports only.
Analysis does not store a server-side output job, so there are no analysis
files to delete. It does not affect results from other operations.

Image and document conversion Reset clears the selected input, errors, and
download link, and deletes that conversion form's previous output job.

Reset is available even before a job has run or after an input error. It is
disabled while that form is uploading, processing, or cleaning up; it does not
cancel an active request. If cleanup fails, the form and result links remain
visible and an error explains that you should retry. Close or finish active
downloads before retrying, especially on Windows.

Reset only knows about the latest job tracked by that form in the current
page. After a page refresh or browser close, previously generated files remain
subject to the normal expiry and cleanup policy.

## Development

Run Flask's auto-reloader for local development only:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app run --debug
```

Never expose Flask debug mode to other users or untrusted networks.

### Project layout

| Path | Purpose |
|------|---------|
| `app.py` | Application factory, HTTP routes, validation responses, per-job deletion, download lifecycle, cleanup command |
| `pdf_tools.py` | PDF reading, summary analysis, range parsing, image/document conversion, page extraction, ordered page merging |
| `templates\index.html` | Accessible, server-rendered application shell |
| `static\app.js` | Upload rows, ordering, asynchronous form submission, loading states, download links, independent form resets |
| `static\style.css` | Responsive layout, focus states, spinner, reduced-motion support |
| `tests\test_app.py` | Standard-library unit and HTTP integration tests with generated PDF fixtures |
| `requirements.txt` | Runtime dependencies and compatible major-version bounds |
| `instance\outputs` | Default generated-output directory; created automatically and excluded from version control |

`create_app(test_config=None)` accepts a configuration dictionary for isolated
tests or embedding. PDF operations are synchronous within a server worker;
browser `fetch` requests keep the UI responsive. There is no task queue, polling
service, persistent user account, or resumable-job system.

### Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite generates PDFs in memory, uses temporary output directories, and
checks exact page selection and merge ordering by distinct page sizes. It also
covers ZIP contents, filenames, invalid ranges and uploads, encrypted and
zero-page inputs, atomic validation, output isolation, expiry, cleanup, upload
limits, and download-path handling. Reset coverage includes isolated job
deletion, repeated cleanup requests, invalid identifiers, and reported cleanup
failures. No sample user PDFs are required.
Analysis coverage includes standard and XMP metadata, information-dictionary
precedence, missing common properties, exact upload size, rotated and scaled
page dimensions, orientation, encrypted-file summaries, multi-file batches
with duplicate filenames and individual errors, invalid inputs, upload limits,
and isolation from existing output jobs. Conversion coverage checks image
filename ordering, page counts, invalid images and document uploads, and mocked
Microsoft Office automation.

### Dependencies

- **Flask:** HTTP application, templates, multipart uploads, download responses.
- **pypdf:** PDF parsing and page writing.
- **Pillow:** decoding and PDF generation from image uploads.
- **pywin32:** Windows COM integration for Office document conversion.
- **Microsoft Office:** installed desktop application required for document-to-PDF.
- **Waitress:** a Windows-compatible WSGI server for non-development use.

Compatible dependency ranges are declared in `requirements.txt`; they are not
an exact reproducibility lockfile. For a managed deployment, resolve and pin
approved versions in your deployment process, and keep PDF parsing dependencies
updated.

## Configuration

Set environment variables **before starting the server**:

| Variable | Default | Meaning |
|----------|---------|---------|
| `MAX_UPLOAD_MB` | `100` | Positive integer; total multipart request size, including all PDFs and form overhead, in MiB |
| `OUTPUT_TTL_SECONDS` | `3600` | Positive integer; time generated downloads remain valid after processing completes |
| `PDF_OUTPUT_DIR` | `instance\outputs` beside `app.py` | Directory for generated results; an absolute path is recommended |

```powershell
$env:MAX_UPLOAD_MB = "200"
$env:OUTPUT_TTL_SECONDS = "7200"
$env:PDF_OUTPUT_DIR = "C:\PDFWorkshopData\outputs"
.\.venv\Scripts\python.exe -m flask --app app:create_app run
```

The request limit applies to the **sum of all files**, not to each file.
Flask also applies its default multipart safeguards (1,000 form parts and
500,000 bytes of non-file form data). There is no separate application-level
fixed count of merge rows; practical limits depend on these safeguards, request
size, browser resources, available memory, and server capacity.

### Storage and cleanup

Input files are read from Werkzeug's upload streams, which may use OS temporary
files. The app does not deliberately retain original uploads. Intermediate
outputs use temporary directories that are removed when processing ends.
Successful PDFs and ZIPs are stored in randomly generated operation directories.
Uploads and outputs never use the supplied filename as a directory path.
Split filenames are sanitized for filesystem safety and their base names are
truncated to 120 characters; unsupported filename characters may be replaced or
removed, and a blank sanitized name becomes `document`.

Clicking **Reset**, or submitting another operation in the same form, requests
immediate deletion of that form's previous job using its `cleanup_url`.
Already-removed jobs are treated as successfully cleaned up. If deletion fails,
the browser reports the error and does not proceed with the reset or replacement
job. Outputs from other forms or browser tabs are not targeted.

Downloads stop working once the TTL elapses. Expired output directories are
removed before the next split/merge operation, or explicitly using:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app cleanup-outputs
```

Schedule this command in Windows Task Scheduler if you need cleanup during
idle periods. Run it from the project directory with the same environment
variables as the server. **Expiry does not by itself erase files at that exact
instant**; periodic cleanup is needed for a retention policy. Files from an
operation that is currently downloading may remain locked on Windows; consult
server logs if cleanup fails and rerun cleanup after downloads finish.

## Production deployment (Windows)

Use **Waitress**, the Windows-compatible production WSGI server included in
`requirements.txt`, rather than `python app.py` or Flask's development server.
Do not enable debug mode in production. Waitress handles serving the app, but
does not add HTTPS, authentication, or resource isolation; apply the protections
below before exposing the app to untrusted users.

### Prepare the host

1. Install Python 3.10 or newer and copy the project to the deployment directory.
2. Open PowerShell in that directory, create `.venv` if needed, and install
   dependencies with the commands below.
3. Choose an output directory that the server account can read, write, and
   delete from. Restrict access to that account and authorized administrators.
4. Configure the upload size and download retention for your environment.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:MAX_UPLOAD_MB = "100"
$env:OUTPUT_TTL_SECONDS = "3600"
$env:PDF_OUTPUT_DIR = "C:\PDFWorkshopData\outputs"
```

Skip environment creation if it already exists. Set these variables in the
same PowerShell session that starts Waitress, or configure them explicitly
for the service account when running as a service.

### Start on a specific port

Set `$Port` to the desired unused TCP port, for example `9000`. Valid port
numbers are `1` through `65535`; ensure your account can bind to the chosen port
and that it is allowed by the host's network policy.

```powershell
$Port = 9000
.\.venv\Scripts\waitress-serve.exe --host=127.0.0.1 --port=$Port --threads=4 --call app:create_app
```

Open **http://127.0.0.1:9000** on the server. Replace `9000` in the URL if you
choose another port. For a literal port argument instead of a PowerShell
variable, use `--port=9000`. The port is a **Waitress command-line setting**;
there is no application `PORT` environment variable.

Leave the terminal open while running this foreground command; **Ctrl+C**
stops the server. Changing the port requires stopping and restarting Waitress.
The `--threads=4` setting allows concurrent requests, but is not a memory or
CPU limit; choose capacity according to your documents and host resources.

### Allow trusted LAN access

To make the same port accessible from other computers, bind to all interfaces:

```powershell
$Port = 9000
.\.venv\Scripts\waitress-serve.exe --host=0.0.0.0 --port=$Port --threads=4 --call app:create_app
```

Allow inbound TCP on your chosen port in Windows Firewall only for the intended
network and clients. Do not open the port publicly without the protections below.
Find the server's LAN IPv4 address with `Get-NetIPAddress -AddressFamily IPv4`.
On another machine on that network, open `http://<server-ipv4-address>:9000`
(replace the placeholder with the actual address and use your chosen port).
`0.0.0.0` is a bind address, not a browser URL; `localhost` on another machine
refers to that other machine.

### HTTPS and internet-facing deployment

For an internet-facing deployment, put Waitress behind a properly configured
HTTPS reverse proxy and add authentication, authorization, rate limiting,
request timeouts, storage quotas, and process-level resource isolation.
Bind Waitress to `127.0.0.1` on the chosen backend port when the proxy runs on
the same machine, and keep that backend port inaccessible to external clients.
The proxy can listen on HTTPS port `443` and forward to
`http://127.0.0.1:9000`. Users then access your configured URL, such as
`https://pdf.example.com`, without the backend port in the browser URL.

Configure the proxy to forward uploads, downloads, and `DELETE /api/jobs/<job>`
requests. Ensure proxy and WSGI request limits match the desired upload size,
and allow enough time for PDF processing. Configure forwarded-header trust
only for your actual proxy, following Waitress and proxy documentation.

### Run persistently and maintain outputs

Run Waitress under an approved Windows service manager for unattended operation.
Configure the executable as the absolute path to `.venv\Scripts\waitress-serve.exe`,
the arguments as `--host=127.0.0.1 --port=9000 --threads=4 --call app:create_app`,
and the working directory as the project directory. Adjust the bind address
only if direct trusted LAN access is intended.

Use a dedicated non-administrator service account, set its environment variables,
enable automatic startup and restart on failure, and capture stdout/stderr in
your logging system. Environment variables set in an interactive PowerShell
session are not automatically inherited by a separately configured service.

Schedule the `cleanup-outputs` command from **Storage and cleanup** with the
same output directory and retention configuration. Monitor logs, free disk
space, and memory usage, and keep dependencies updated. Restart the service
after deploying code or configuration changes.

## Production deployment (Linux)

Waitress also runs on Linux, so no additional Python server dependency is
required. The following example targets **Ubuntu/Debian with systemd** and
Python 3.10 or newer. Adjust package-management and service commands for other
distributions. Commands and paths in this section use Linux syntax.

### Prepare the host and application

Install Python and virtual-environment support:

```bash
sudo apt-get update
sudo apt-get install python3 python3-venv
python3 --version
```

Copy the application source and `requirements.txt` to `/opt/pdf-workshop`
using your deployment process. Do not copy a Windows `.venv`; create a new
Linux environment. Keep application code and the virtual environment owned
by your deployment administrator, not writable by the runtime service account.

```bash
sudo useradd --system --user-group --home-dir /var/lib/pdf-workshop \
  --shell /usr/sbin/nologin pdf-workshop
sudo install -d -o pdf-workshop -g pdf-workshop -m 0700 \
  /var/lib/pdf-workshop /var/lib/pdf-workshop/outputs

cd /opt/pdf-workshop
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
```

Create the account only once. Ensure it has read/traverse access to the
application and virtual environment. Its generated files belong in
`/var/lib/pdf-workshop/outputs`, not in the application source directory.

### Choose the port and configuration

Create `/etc/pdf-workshop.env` with an administrator-owned text editor:

```ini
PORT=9000
MAX_UPLOAD_MB=100
OUTPUT_TTL_SECONDS=3600
PDF_OUTPUT_DIR=/var/lib/pdf-workshop/outputs
```

Restrict access to this configuration:

```bash
sudo chown root:root /etc/pdf-workshop.env
sudo chmod 0600 /etc/pdf-workshop.env
```

Choose an unused port between `1024` and `65535` for this non-root service.
Here, `PORT` is expanded by the systemd unit below into Waitress's `--port`
argument; it is **not** read by the Python application itself.

For a foreground smoke check before configuring systemd, run:

```bash
cd /opt/pdf-workshop
sudo -u pdf-workshop env \
  MAX_UPLOAD_MB=100 OUTPUT_TTL_SECONDS=3600 \
  PDF_OUTPUT_DIR=/var/lib/pdf-workshop/outputs \
  .venv/bin/waitress-serve --host=127.0.0.1 --port=9000 \
  --threads=4 --call app:create_app
```

From another terminal on that server, run `curl -I http://127.0.0.1:9000/`.
Stop the foreground instance with **Ctrl+C** before starting the service on
the same port. This foreground command uses the values shown explicitly;
it does not automatically load `/etc/pdf-workshop.env`.

### Install a persistent systemd service

Create `/etc/systemd/system/pdf-workshop.service`:

```ini
[Unit]
Description=PDF Workshop web application
After=network.target

[Service]
Type=simple
User=pdf-workshop
Group=pdf-workshop
WorkingDirectory=/opt/pdf-workshop
EnvironmentFile=/etc/pdf-workshop.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/pdf-workshop/.venv/bin/waitress-serve --host=127.0.0.1 --port=${PORT} --threads=4 --call app:create_app
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/pdf-workshop

[Install]
WantedBy=multi-user.target
```

Enable the service and inspect its status and logs:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pdf-workshop.service
sudo systemctl status pdf-workshop.service --no-pager
sudo journalctl -u pdf-workshop.service -n 100 --no-pager
curl -I http://127.0.0.1:9000/
```

Open **http://127.0.0.1:9000** in a browser on the server, or access it through
an HTTPS reverse proxy as described below. To change ports, edit `PORT` in
`/etc/pdf-workshop.env`, restart with
`sudo systemctl restart pdf-workshop.service`, and update the proxy's backend
address and any applicable firewall rules. Unit-file changes additionally
require `sudo systemctl daemon-reload`. Stop the app with
`sudo systemctl stop pdf-workshop.service`.

The unit intentionally restricts writes to the application data directory and
private temporary storage. If you change `PDF_OUTPUT_DIR`, create the new
directory with suitable ownership and update `ReadWritePaths` as well.

### Network access and HTTPS

For direct **trusted LAN access only**, change the service's `--host=127.0.0.1`
to `--host=0.0.0.0`, reload systemd, and restart the service. Allow TCP on your
chosen port only from the intended client subnet in your host/cloud firewall.
Browse to `http://<server-ip-address>:9000`; `0.0.0.0` is not a browser address.

For public access, keep the localhost binding and place an HTTPS reverse proxy
such as Nginx, Apache, or Caddy in front of Waitress. Forward your HTTPS site's
requests to `http://127.0.0.1:9000`, and expose only the intended proxy ports,
normally `443` and optionally `80` for redirects or certificate issuance.
Configure a valid certificate, authentication, rate limits, and appropriate
upload and processing timeouts. The proxy must support multipart POST uploads,
attachment downloads, and DELETE requests for Reset. The security and
resource-isolation requirements in the Windows deployment section apply here
too; a WSGI service alone does not make this application safe for hostile PDFs.

### Schedule output cleanup with a systemd timer

Create `/etc/systemd/system/pdf-workshop-cleanup.service`:

```ini
[Unit]
Description=Remove expired PDF Workshop outputs

[Service]
Type=oneshot
User=pdf-workshop
Group=pdf-workshop
WorkingDirectory=/opt/pdf-workshop
EnvironmentFile=/etc/pdf-workshop.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/pdf-workshop/.venv/bin/python -m flask --app app:create_app cleanup-outputs
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/pdf-workshop
```

Create `/etc/systemd/system/pdf-workshop-cleanup.timer`:

```ini
[Unit]
Description=Schedule PDF Workshop output cleanup

[Timer]
OnCalendar=*:0/15
Persistent=true
Unit=pdf-workshop-cleanup.service

[Install]
WantedBy=timers.target
```

Enable cleanup every 15 minutes, including during idle periods:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pdf-workshop-cleanup.timer
sudo systemctl list-timers pdf-workshop-cleanup.timer --no-pager

# Optional immediate cleanup and log inspection
sudo systemctl start pdf-workshop-cleanup.service
sudo journalctl -u pdf-workshop-cleanup.service -n 50 --no-pager
```

Downloads still expire at the configured TTL; physical deletion happens on a
cleanup run or subsequent PDF operation. The timer uses the same configuration
and service account as the web app. Monitor disk space and logs, and restart
the web service after deploying application or dependency updates.

## Privacy, security, and limitations

- This app has **no login or per-user access control**. Random operation URLs
  act as bearer links: anyone with the link can download the output until expiry.
  Treat URLs as sensitive. The default binding is local-only.
- Processing happens on the host server, not exclusively in the browser.
  No third-party upload service, external scripts, fonts, or analytics are used.
  Protect the output directory and OS temporary storage with appropriate
  permissions, encryption, and backup/retention policies.
- PDF parsing and writing consume RAM, CPU, and disk. Upload size limits do not
  bound decompressed PDF complexity or output size, especially with overlapping
  ranges. This app is intended for trusted users and ordinary documents, not
  hostile uploads. Use isolated worker processes and enforce resource limits
  before allowing untrusted traffic.
- Splitting and merging reject encrypted PDFs, including ones that open without
  a password. Analysis identifies encryption but does not inspect protected
  contents. Password entry, OCR, PDF/A validation, PDF repair, text extraction,
  and preview are not implemented. Summary analysis is not a security scan or
  a guarantee that a document is safe or structurally valid.
- The app copies pages; it does not preserve every document-level feature,
  such as bookmarks, attachments, form behavior, metadata, or digital signatures.
  Keep originals and review outputs before relying on them.
- Generated results are local to this server's filesystem. Multiple servers
  would need shared storage and a coordinated output lifecycle.
- Operational errors are logged by Flask/Waitress. Unexpected failures return a
  generic message instead of exposing internal exception details to the browser.

## HTTP interface

All API errors return JSON with an `error` string and a non-2xx status.

| Method | Route | Input / result |
|--------|-------|----------------|
| GET | `/` | Web interface |
| POST | `/api/split` | Multipart `file` (one PDF), `ranges` (text); JSON `files` array and `archive` object |
| POST | `/api/merge` | Repeated multipart `files` fields in order; JSON `file` object |
| POST | `/api/analyze` | Repeated multipart `file` fields; JSON `analyses` array in upload order, without an output job or cleanup URL |
| GET | `/downloads/<job>/<filename>` | Attachment download; 404 if absent, 410 if expired and not yet cleaned |
| DELETE | `/api/jobs/<job>` | Delete that job's outputs; 204 if deleted or already absent, 409 if cleanup fails |

Each result object contains `name` and `url`. PDF objects also include `pages`.
Successful split and merge responses also contain a top-level `cleanup_url`
for deleting their outputs. Like download URLs, this URL is a bearer capability;
anyone who has the job identifier can delete that job's generated files.
Common statuses are 400 for input errors and 413 for request limits. PDF results
are published only after all inputs have been validated and the operation has
finished.

Each `analyses` entry contains an `analysis` object, or `filename` and `error`
for a file that could not be analyzed. Multi-file requests return 200 with
per-file results even if some or all files are invalid; request-level errors
such as upload limits still return non-2xx statuses. For compatibility, a
single-file success also returns the top-level `analysis` object, and a
single-file input error returns 400.

The `analysis` object contains `filename`, `size_bytes`, `encrypted`,
`page_count`, `metadata`, `document_properties`, and `pages`. `metadata` contains
raw document information fields; `document_properties` contains normalized common
fields with XMP fallbacks and `null` for missing values. Each page has `number`, `width_points`,
`height_points`, `rotation` (degrees), and `orientation`. For encrypted files,
`page_count` is `null`, both metadata objects are empty, and `pages` is empty. Upload streams
use the same temporary-file handling as other operations, but analysis results
are returned directly as JSON rather than retained in the output directory.

## Troubleshooting

| Problem | Resolution |
|---------|------------|
| `py` is not found | Install Python and its launcher, or use your Python executable in place of `py` |
| Missing Flask/pypdf | Run the dependency-install command with the same `.venv` Python used to start the app |
| Port already in use | Development: use Flask `--port 5001`. Production: stop the affected Waitress instance or choose another unused port with `--port=9001`. Update the browser URL and any firewall/proxy settings accordingly |
| Upload too large | Reduce the total input size or adjust `MAX_UPLOAD_MB`; also check proxy/WSGI limits |
| Out-of-bounds range | Use physical PDF page positions, not printed labels or Roman-numeral page labels |
| Encrypted/unreadable PDF | Export an unencrypted, valid copy using a trusted PDF tool |
| Download expired/missing | Process the original files again; links do not regenerate outputs |
| Reset reports cleanup failed | Finish active downloads, check output-directory permissions and server logs, then click Reset again |
| Reset is disabled | Wait for that form's upload, PDF processing, or cleanup to finish; Reset does not cancel work in progress |
| LAN browser cannot connect | Check the bind address, actual server IP, firewall, and network access |
| Processing failed unexpectedly | Check terminal/service logs, disk permissions, available RAM, and free disk space |
