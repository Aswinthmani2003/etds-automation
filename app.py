"""
ETDS PDF Renamer — Web Dashboard
Amirtharaj Investment — Internal Tool

Run:   python app.py
Open:  http://localhost:5000
Team:  http://<your-ip>:5000
"""

import io
import re
import csv
import uuid
import threading
import time
import zipfile
import datetime as _dt
from pathlib import Path

import pymupdf as fitz
import zxingcpp
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import openpyxl
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

# ── Processing helpers ────────────────────────────────────────────────────────

def digits_of(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val == int(val):
        val = int(val)
    return re.sub(r"[^0-9]", "", str(val))


_DATE_FMTS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y")

def _fmt_date(val) -> str:
    """Convert any date/datetime/string value to DD/MM/YYYY string."""
    if isinstance(val, (_dt.datetime, _dt.date)):
        return val.strftime("%d/%m/%Y")
    if val is not None:
        s = str(val).strip()
        for fmt in _DATE_FMTS:
            try:
                return _dt.datetime.strptime(s, fmt).strftime("%d/%m/%Y")
            except ValueError:
                continue
    return ""

def _looks_like_date(val) -> bool:
    """Return True if val is a date object or a date-formatted string."""
    if isinstance(val, (_dt.datetime, _dt.date)):
        return True
    if val is not None and isinstance(val, str):
        s = val.strip()
        if len(s) >= 8:
            for fmt in _DATE_FMTS:
                try:
                    _dt.datetime.strptime(s, fmt)
                    return True
                except ValueError:
                    continue
    return False


def parse_excel(data: bytes, filename: str) -> dict:
    """
    Returns {barcode_20: {"token": token_15, "date": "DD/MM/YYYY"}}
    Auto-detects the barcode column (most 20-digit cells), token column
    (most 15-digit cells), and date column (most date/datetime cells).
    """
    ext = Path(filename).suffix.lower()
    rows = []

    if ext in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                rows.append(list(row))
        wb.close()
    elif ext == ".xls":
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        for ws in wb.sheets():
            for ri in range(ws.nrows):
                row = []
                for ci in range(ws.ncols):
                    if ws.cell_type(ri, ci) == xlrd.XL_CELL_DATE:
                        try:
                            row.append(xlrd.xldate_as_datetime(ws.cell_value(ri, ci), wb.datemode))
                        except Exception:
                            row.append(ws.cell_value(ri, ci))
                    else:
                        row.append(ws.cell_value(ri, ci))
                rows.append(row)
    elif ext == ".csv":
        text = data.decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
    else:
        raise ValueError(f"Unsupported format: {ext}")

    col_stats: dict[int, dict] = {}
    for row in rows:
        for ci, cell in enumerate(row):
            d = digits_of(cell)
            if ci not in col_stats:
                col_stats[ci] = {"t20": 0, "t15": 0, "tdate": 0}
            if len(d) == 20:
                col_stats[ci]["t20"] += 1
            if len(d) == 15:
                col_stats[ci]["t15"] += 1
            if _looks_like_date(cell):
                col_stats[ci]["tdate"] += 1

    if not col_stats:
        return {}

    token_col = max(col_stats, key=lambda c: col_stats[c]["t20"])
    target_col = max(
        (c for c in col_stats if c != token_col),
        key=lambda c: col_stats[c]["t15"],
        default=-1,
    )
    date_col = max(
        (c for c in col_stats if col_stats[c]["tdate"] > 0),
        key=lambda c: col_stats[c]["tdate"],
        default=-1,
    )

    token_map: dict[str, dict] = {}
    for row in rows:
        token = digits_of(row[token_col]) if 0 <= token_col < len(row) else ""
        if len(token) != 20:
            for cell in row:
                d = digits_of(cell)
                if len(d) == 20:
                    token = d
                    break
        if not token:
            continue
        target = digits_of(row[target_col]) if 0 <= target_col < len(row) else ""
        if len(target) != 15:
            for cell in row:
                d = digits_of(cell)
                if len(d) == 15:
                    target = d
                    break
        if not target:
            continue
        date_str = _fmt_date(row[date_col]) if 0 <= date_col < len(row) else ""
        if token not in token_map:
            token_map[token] = {"token": target, "date": date_str}

    return token_map


def _extract_20digit(text: str) -> str | None:
    """Find a 20-digit number in text, collapsing spaces OCR may have inserted."""
    # Remove spaces/newlines between consecutive digits (OCR artifact: "2607 1913..." → "26071913...")
    compact = text
    for _ in range(4):
        compact = re.sub(r'(?<=\d)[\s ]+(?=\d)', '', compact)
    m = re.search(r'\d{20}', compact)
    return m.group() if m else None


def _try_read_barcodes(img: Image.Image) -> str | None:
    """
    Try barcode decoding across multiple preprocessing variants and both
    binarizers.  Variants: original, gray, contrast×2, contrast×3,
    equalized, sharpened, inverted.
    """
    gray = img.convert("L")
    variants = [
        img,
        gray,
        ImageEnhance.Contrast(gray).enhance(2.0),
        ImageEnhance.Contrast(gray).enhance(3.0),
        ImageOps.equalize(gray),                        # histogram equalization — great for faded scans
        gray.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=3)),
        ImageOps.invert(gray),
    ]
    for binarizer in (zxingcpp.Binarizer.LocalAverage, zxingcpp.Binarizer.GlobalHistogram):
        for candidate in variants:
            try:
                for r in zxingcpp.read_barcodes(candidate, binarizer=binarizer):
                    d = digits_of(r.text)
                    if len(d) >= 15:
                        return d
            except Exception:
                continue
    return None


def _pil_from_pixmap(pix: fitz.Pixmap) -> Image.Image:
    """Convert a PyMuPDF Pixmap to PIL, normalising any colour space."""
    if pix.n == 4 or pix.n not in (1, 3):
        pix = fitz.Pixmap(fitz.csRGB, pix)
    mode = "RGB" if pix.n == 3 else "L"
    return Image.frombytes(mode, (pix.width, pix.height), pix.samples)


def _image_regions(img: Image.Image):
    """
    Yield the full image plus all useful sub-regions.

    Many ETDS scans are landscape forms scanned in portrait mode: the barcode
    sits as a VERTICAL STRIP on the left (or right) edge of the portrait image.
    We must crop that strip and rotate it 90° to give the barcode reader a
    normal horizontal barcode — because zxingcpp's internal try_rotate often
    misses thin bars at low JPEG resolutions.
    """
    w, h = img.size
    yield img

    # Horizontal crops (top / middle / bottom third)
    for y0, y1 in [(0, h // 3), (h // 3, 2 * h // 3), (2 * h // 3, h)]:
        yield img.crop((0, y0, w, y1))

    # Vertical strip crops + 90° explicit rotations + 2× upscale
    # ETDS forms are often landscape-scanned in portrait mode: barcode sits as a
    # thin vertical strip on the left/right edge.  At ~150 DPI JPEG the bars are
    # only 2-3 px wide — too thin to decode.  Rotating + 2× LANCZOS upscale
    # brings bars to 4-6 px wide, which zxingcpp can read reliably.
    for x0, x1 in [(0, w // 4), (0, w // 3), (3 * w // 4, w), (2 * w // 3, w)]:
        strip = img.crop((x0, 0, x1, h))
        yield strip
        for angle in (90, -90):
            rotated = strip.rotate(angle, expand=True)
            yield rotated
            rw, rh = rotated.size
            yield rotated.resize((rw * 2, rh * 2), Image.LANCZOS)  # 2× upscale for thin bars


def decode_barcode(pdf_bytes: bytes) -> str | None:
    """
    Extract a 20-digit barcode value from a PDF.
    Strategy (fastest-first):
      1. PDF text layer  — instant when number is printed as text
      2. Embedded images — barcode reader on native-resolution scan images,
                           with preprocessing + try_harder + region crops
      3. Rendered pages  — same on full-page renders at 300 / 200 / 150 DPI
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_num in range(min(3, doc.page_count)):
            page = doc.load_page(page_num)

            # Strategy 1: text extraction
            text = page.get_text()
            result = _extract_20digit(text)
            if result:
                return result

            # Strategy 2: embedded images at native resolution
            for img_info in page.get_images(full=True):
                xref = img_info[0]

                # 2a: via PyMuPDF Pixmap
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.width >= 100 and pix.height >= 100:
                        img = _pil_from_pixmap(pix)
                        for region in _image_regions(img):
                            result = _try_read_barcodes(region)
                            if result:
                                return result
                except Exception:
                    pass

                # 2b: via doc.extract_image → PIL (handles JPEG/JPEG2000 differently)
                try:
                    img_dict = doc.extract_image(xref)
                    if img_dict and img_dict.get("image"):
                        img = Image.open(io.BytesIO(img_dict["image"]))
                        for region in _image_regions(img):
                            result = _try_read_barcodes(region)
                            if result:
                                return result
                except Exception:
                    pass

            # Strategy 3: render full page at multiple DPIs
            for dpi in (300, 200, 150):
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
                img = _pil_from_pixmap(pix)
                for region in _image_regions(img):
                    result = _try_read_barcodes(region)
                    if result:
                        return result

    finally:
        doc.close()
    return None


# ── Job store (in-memory, auto-expires after 1 h) ─────────────────────────────

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _run_job(job_id: str, excel_data: bytes, excel_name: str, pdf_list: list[tuple[str, bytes]]):
    try:
        token_map = parse_excel(excel_data, excel_name)
        if not token_map:
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = (
                    "No barcode→token pairs found in Excel. "
                    "Verify the file has a 'Barcode Value' column (20-digit) and a 'Token Number' column (15-digit)."
                )
            return

        with _jobs_lock:
            _jobs[job_id]["excel_records"] = len(token_map)
            _jobs[job_id]["total"] = len(pdf_list)

        results = []
        zip_buf = io.BytesIO()

        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, (name, pdf_bytes) in enumerate(pdf_list):
                with _jobs_lock:
                    _jobs[job_id]["current"] = idx + 1
                    _jobs[job_id]["current_name"] = name

                try:
                    token = decode_barcode(pdf_bytes)
                except Exception as e:
                    results.append({"name": name, "status": "error", "receipt": "",
                                    "pdf_barcode": "", "excel_barcode": "", "date": "",
                                    "msg": str(e)})
                    continue

                if not token:
                    results.append({"name": name, "status": "no_barcode", "receipt": "",
                                    "pdf_barcode": "", "excel_barcode": "", "date": "",
                                    "msg": "No barcode found"})
                    continue

                # token is the 20-digit barcode value; look up → Token Number (15-digit)
                barcode_key = digits_of(token)
                entry = token_map.get(barcode_key)
                if not entry and len(barcode_key) > 20:
                    entry = token_map.get(barcode_key[-20:])
                if not entry:
                    results.append({"name": name, "status": "not_found", "receipt": "",
                                    "pdf_barcode": barcode_key, "excel_barcode": "", "date": "",
                                    "msg": f"Barcode {barcode_key} not in Excel"})
                    continue

                token_number = entry["token"]
                receipt_date = entry.get("date", "")
                zf.writestr(f"{token_number}.pdf", pdf_bytes)
                results.append({"name": name, "status": "ok", "receipt": token_number,
                                "pdf_barcode": barcode_key, "excel_barcode": barcode_key,
                                "date": receipt_date, "msg": ""})

        summary = {
            "ok":         sum(1 for r in results if r["status"] == "ok"),
            "no_barcode": sum(1 for r in results if r["status"] == "no_barcode"),
            "not_found":  sum(1 for r in results if r["status"] == "not_found"),
            "error":      sum(1 for r in results if r["status"] == "error"),
            "total":      len(results),
        }

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["results"] = results
            _jobs[job_id]["summary"] = summary
            _jobs[job_id]["zip_bytes"] = zip_buf.getvalue()

    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)

    # Auto-cleanup after 1 hour
    def _cleanup():
        time.sleep(3600)
        with _jobs_lock:
            _jobs.pop(job_id, None)
    threading.Thread(target=_cleanup, daemon=True).start()


# ── Routes ────────────────────────────────────────────────────────────────────

_LOGO = Path(__file__).parent / "logo.png"
_FAVICON = Path(__file__).parent / "favicon_icon.png"

@app.route("/logo.png")
def serve_logo():
    return send_file(str(_LOGO), mimetype="image/png")

@app.route("/favicon_icon.png")
def serve_favicon():
    return send_file(str(_FAVICON), mimetype="image/png")


@app.route("/")
def index():
    return HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/process", methods=["POST"])
def process():
    excel_file = request.files.get("excel")
    pdf_files  = request.files.getlist("pdfs")

    if not excel_file:
        return jsonify({"error": "No Excel file uploaded"}), 400
    if not pdf_files:
        return jsonify({"error": "No PDF files uploaded"}), 400

    excel_data = excel_file.read()
    excel_name = excel_file.filename
    pdf_list   = [(f.filename, f.read()) for f in pdf_files]

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "processing",
            "current": 0,
            "total": len(pdf_list),
            "current_name": "",
            "excel_records": 0,
            "results": [],
            "summary": {},
            "zip_bytes": b"",
            "error": None,
        }

    threading.Thread(target=_run_job, args=(job_id, excel_data, excel_name, pdf_list), daemon=True).start()
    return jsonify({"job_id": job_id, "total": len(pdf_list)})


@app.route("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({k: v for k, v in job.items() if k != "zip_bytes"})


@app.route("/download/<job_id>")
def download(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job["status"] != "done":
        return "Not ready or expired", 404
    return send_file(
        io.BytesIO(job["zip_bytes"]),
        download_name="renamed_etds.zip",
        as_attachment=True,
        mimetype="application/zip",
    )


@app.route("/debug", methods=["GET", "POST"])
def debug_pdf():
    """Upload one PDF → see exactly what the tool extracts from it."""
    if request.method == "GET":
        return (
            '<!doctype html><html><body style="font-family:monospace;padding:24px">'
            '<h2>PDF Debug</h2>'
            '<form method="post" enctype="multipart/form-data">'
            '<input type="file" name="pdf" accept=".pdf" required>'
            '<button type="submit" style="margin-left:8px">Analyse</button>'
            '</form></body></html>'
        )

    pdf_file = request.files.get("pdf")
    if not pdf_file:
        return "No PDF uploaded", 400

    pdf_bytes = pdf_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    rows = []

    try:
        for pno in range(doc.page_count):
            page = doc.load_page(pno)
            raw_text = page.get_text()
            text_result = _extract_20digit(raw_text)

            # Render page thumbnail at 100 DPI
            pix_thumb = page.get_pixmap(matrix=fitz.Matrix(100 / 72, 100 / 72))
            thumb_img = _pil_from_pixmap(pix_thumb)
            buf = io.BytesIO()
            thumb_img.save(buf, format="PNG")
            thumb_b64 = __import__("base64").b64encode(buf.getvalue()).decode()

            rows.append(f"<h3>Page {pno + 1}</h3>")
            rows.append(f'<img src="data:image/png;base64,{thumb_b64}" style="max-width:400px;border:1px solid #ccc">')
            rows.append(f"<p><b>Text layer:</b> {repr(raw_text[:300]) if raw_text.strip() else '<em>empty</em>'}</p>")
            rows.append(f"<p><b>20-digit from text:</b> {text_result or '<em>not found</em>'}</p>")

            embedded = page.get_images(full=True)
            rows.append(f"<p><b>Embedded images:</b> {len(embedded)}</p>")

            for ii, img_info in enumerate(embedded):
                xref = img_info[0]
                rows.append(f"<b>Image {ii + 1} (xref {xref})</b><br>")
                try:
                    pix = fitz.Pixmap(doc, xref)
                    rows.append(f"&nbsp;&nbsp;Pixmap: {pix.width}×{pix.height} n={pix.n}<br>")
                    if pix.width >= 100 and pix.height >= 100:
                        img = _pil_from_pixmap(pix)
                        found = _try_read_barcodes(img)
                        rows.append(f"&nbsp;&nbsp;zxingcpp full image: <b>{found or 'NOTHING'}</b><br>")
                        w, h = img.size
                        for label, box in [("top-third", (0, 0, w, h // 3)),
                                           ("mid-third",  (0, h // 3, w, 2 * h // 3)),
                                           ("bot-third",  (0, 2 * h // 3, w, h))]:
                            found_crop = _try_read_barcodes(img.crop(box))
                            rows.append(f"&nbsp;&nbsp;zxingcpp {label}: <b>{found_crop or 'NOTHING'}</b><br>")
                except Exception as ex:
                    rows.append(f"&nbsp;&nbsp;<em>Pixmap error: {ex}</em><br>")

                try:
                    img_dict = doc.extract_image(xref)
                    if img_dict:
                        rows.append(f"&nbsp;&nbsp;extract_image: ext={img_dict.get('ext')} "
                                    f"size={img_dict.get('width')}×{img_dict.get('height')} "
                                    f"cs={img_dict.get('colorspace')} xres={img_dict.get('xres')}<br>")
                        img2 = Image.open(io.BytesIO(img_dict["image"]))
                        found2 = _try_read_barcodes(img2)
                        rows.append(f"&nbsp;&nbsp;zxingcpp via PIL open: <b>{found2 or 'NOTHING'}</b><br>")
                        # Thumbnail of the embedded image
                        img2.thumbnail((300, 300))
                        buf2 = io.BytesIO()
                        img2.save(buf2, format="PNG")
                        b64_2 = __import__("base64").b64encode(buf2.getvalue()).decode()
                        rows.append(f'<img src="data:image/png;base64,{b64_2}" style="max-width:300px;border:1px solid #ccc;margin:4px"><br>')
                except Exception as ex2:
                    rows.append(f"&nbsp;&nbsp;<em>extract_image error: {ex2}</em><br>")

            # Strategy 3 render at 300 DPI
            pix3 = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))
            img3 = _pil_from_pixmap(pix3)
            found3 = _try_read_barcodes(img3)
            rows.append(f"<p><b>Rendered 300 DPI ({img3.width}×{img3.height}):</b> {found3 or '<em>NOTHING</em>'}</p>")

    finally:
        doc.close()

    html = (
        '<!doctype html><html><head><style>body{font-family:monospace;padding:24px;line-height:1.6}'
        'h2{color:#c00}h3{border-bottom:1px solid #ccc}</style></head><body>'
        f'<h2>Debug: {pdf_file.filename}</h2>'
        + "\n".join(rows)
        + '<p><a href="/debug">← Try another PDF</a></p></body></html>'
    )
    return html


# ── HTML dashboard ────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ETDS PDF Renamer — Amirtharaj Investment</title>
<style>
:root {
  --accent:      #E04B3E;
  --accent-dark: #C73A2E;
  --accent-soft: #FEF2F1;
  --card:        #FFFFFF;
  --surface:     #F8F4F4;
  --bg:          #F0EBEB;
  --border:      #EDE6E6;
  --border-med:  #D4C4C4;
  --text:        #18100F;
  --text-2:      #6B6070;
  --text-3:      #A09098;
  --green:       #0E7A57;
  --green-soft:  #F0FBF6;
  --green-bdr:   #B7DFD0;
  --amber:       #92400E;
  --amber-soft:  #FFFBEB;
  --amber-bdr:   #FDE68A;
  --red-soft:    #FEF2F1;
  --red-bdr:     #FECACA;
  --r:    16px;
  --r-sm: 10px;
  --r-xs: 6px;
  --sh:   0 1px 3px rgba(0,0,0,.07), 0 4px 16px rgba(0,0,0,.05);
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:var(--text);min-height:100vh;}

/* ── Header ── */
.hdr{background:var(--card);border-bottom:1px solid var(--border);padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:84px;position:sticky;top:0;z-index:100;box-shadow:0 1px 8px rgba(0,0,0,.06);}
.hdr-brand{display:flex;align-items:center;gap:16px;}
.hdr-logo-img{height:66px;width:auto;display:block;}
.hdr-sep{width:1px;height:36px;background:var(--border-med);margin:0 4px;}
.hdr-title{font-size:15px;font-weight:700;color:var(--text);}
.hdr-badge{font-size:10px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;padding:3px 10px;border:1.5px solid var(--accent);border-radius:99px;color:var(--accent);}

/* ── Layout ── */
.wrap{max-width:1000px;margin:0 auto;padding:36px 24px 60px;}
h1.page-title{font-size:24px;font-weight:800;letter-spacing:-.02em;margin-bottom:4px;}
.page-sub{font-size:14px;color:var(--text-2);margin-bottom:28px;}

/* ── Cards ── */
.card{background:var(--card);border-radius:var(--r);box-shadow:var(--sh);overflow:hidden;margin-bottom:20px;}
.card-hd{padding:16px 22px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.card-hd h2{font-size:14px;font-weight:700;}
.card-body{padding:22px;}

/* ── Upload grid ── */
.upload-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
@media(max-width:620px){.upload-grid{grid-template-columns:1fr;}}

.drop-card{background:var(--surface);border:2px dashed var(--border-med);border-radius:var(--r-sm);padding:28px 18px;text-align:center;cursor:pointer;transition:border-color .18s,background .18s;display:flex;flex-direction:column;align-items:center;gap:10px;user-select:none;position:relative;}
.drop-card:hover,.drop-card.drag{border-color:var(--accent);background:var(--accent-soft);}
.drop-card.loaded{border-style:solid;border-color:var(--green);background:var(--green-soft);}
.drop-icon{width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:4px;}
.drop-icon.xl{background:#E8F5E9;}
.drop-icon.pdf{background:#FEECEB;}
.drop-main{font-size:14px;font-weight:700;}
.drop-hint{font-size:12px;color:var(--text-3);margin-top:4px;}
.drop-meta{font-size:12.5px;color:var(--green);font-weight:600;margin-top:6px;}
.fmt-row{display:flex;gap:6px;justify-content:center;margin-top:8px;}
.fmt-chip{font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;background:var(--border);color:var(--text-2);}
input[type=file]{display:none;}

/* ── Action row ── */
.action-row{display:flex;align-items:center;gap:14px;margin-top:6px;}
.btn-process{display:inline-flex;align-items:center;gap:8px;padding:12px 28px;background:var(--accent);color:#fff;border:none;border-radius:var(--r-sm);font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;transition:background .15s,opacity .15s;}
.btn-process:hover{background:var(--accent-dark);}
.btn-process:disabled{opacity:.5;cursor:not-allowed;}
.btn-reset{padding:10px 18px;background:transparent;color:var(--text-2);border:1.5px solid var(--border-med);border-radius:var(--r-sm);font-size:13px;font-weight:600;font-family:inherit;cursor:pointer;transition:background .15s;}
.btn-reset:hover{background:var(--surface);}

/* ── Progress ── */
.progress-section{display:none;}
.progress-label{font-size:13px;color:var(--text-2);margin-bottom:8px;}
.progress-bar-wrap{background:var(--border);border-radius:99px;height:8px;overflow:hidden;}
.progress-bar-fill{height:100%;width:0%;background:linear-gradient(90deg,var(--accent-dark),var(--accent));border-radius:99px;transition:width .3s;}
.progress-file{font-size:11.5px;color:var(--text-3);margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

/* ── Results section ── */
.results-section{display:none;}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;}
@media(max-width:560px){.tiles{grid-template-columns:repeat(2,1fr);}}
.tile{background:var(--card);border:1px solid var(--border);border-radius:var(--r-sm);padding:14px 16px;text-align:center;}
.tile-num{font-size:28px;font-weight:800;line-height:1;}
.tile-lbl{font-size:11px;color:var(--text-3);margin-top:4px;text-transform:uppercase;letter-spacing:.06em;}
.tile.ok .tile-num{color:var(--green);}
.tile.warn .tile-num{color:var(--amber);}
.tile.bad .tile-num{color:var(--accent);}

/* ── Results table ── */
.tbl-wrap{overflow-x:auto;border-radius:var(--r-sm);border:1px solid var(--border);}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{background:var(--surface);padding:10px 14px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-3);border-bottom:1px solid var(--border);}
td{padding:9px 14px;border-bottom:1px solid var(--border);vertical-align:middle;}
tr:last-child td{border-bottom:none;}
tr:hover td{background:var(--surface);}
.st-ok{color:var(--green);font-weight:700;}
.st-warn{color:var(--amber);font-weight:700;}
.st-bad{color:var(--accent);font-weight:700;}
.receipt-num{font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;font-size:12px;letter-spacing:.04em;}
.barcode-val{font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;font-size:11px;letter-spacing:.03em;color:var(--text-2);}
.date-val{font-size:12px;white-space:nowrap;}
.note-txt{font-size:11.5px;color:var(--text-3);}

/* ── Download / actions ── */
.result-actions{display:flex;align-items:center;gap:12px;margin-top:18px;}
.btn-download{display:inline-flex;align-items:center;gap:8px;padding:12px 24px;background:var(--green);color:#fff;border:none;border-radius:var(--r-sm);font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;transition:background .15s;text-decoration:none;}
.btn-download:hover{background:#0A6647;}
.btn-new{padding:10px 18px;background:transparent;color:var(--text-2);border:1.5px solid var(--border-med);border-radius:var(--r-sm);font-size:13px;font-weight:600;font-family:inherit;cursor:pointer;transition:background .15s;}
.btn-new:hover{background:var(--surface);}

/* ── Error banner ── */
.err-banner{background:var(--red-soft);border:1px solid var(--red-bdr);border-radius:var(--r-sm);padding:12px 16px;color:var(--accent);font-size:13px;font-weight:600;display:none;}

/* ── Footer ── */
.footer{text-align:center;padding:24px;font-size:12px;color:var(--text-3);}
</style>
<link rel="icon" type="image/png" href="/favicon_icon.png">
</head>
<body>

<!-- Header -->
<header class="hdr">
  <div class="hdr-brand">
    <img class="hdr-logo-img" src="/logo.png" alt="Amirtharaj Investment">
    <div class="hdr-sep"></div>
    <div class="hdr-title">ETDS PDF Renamer</div>
  </div>
  <span class="hdr-badge">Internal Tool</span>
</header>

<!-- Main -->
<main class="wrap">
  <h1 class="page-title">Rename Scanned Receipts</h1>
  <p class="page-sub">Upload the ETDS Excel report and scanned PDFs — barcodes are decoded on the server and each PDF is renamed to its 15-digit receipt number.</p>

  <!-- Upload card -->
  <div class="card">
    <div class="card-hd">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      <h2>Upload Files</h2>
    </div>
    <div class="card-body">
      <div class="upload-grid">

        <!-- Excel drop -->
        <label class="drop-card" id="excelDrop" for="excelInput">
          <div class="drop-icon xl">
            <svg width="26" height="26" viewBox="0 0 34 34" fill="none">
              <rect x="3" y="2" width="20" height="28" rx="3" fill="#fff" stroke="#43A047" stroke-width="1.6"/>
              <path d="M17 2v8h9" stroke="#43A047" stroke-width="1.6" stroke-linecap="round"/>
              <rect x="17" y="2" width="9" height="8" rx="1" fill="#C8E6C9" stroke="#43A047" stroke-width="1.6"/>
              <path d="M8 18l3 5 3-5M8 18v5" stroke="#43A047" stroke-width="1.6" stroke-linecap="round"/>
              <path d="M19 18h5M19 21.5h4M19 25h5" stroke="#43A047" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
          </div>
          <div>
            <div class="drop-main">ETDS Excel Report</div>
            <div class="fmt-row"><span class="fmt-chip">.xls</span><span class="fmt-chip">.xlsx</span><span class="fmt-chip">.csv</span></div>
            <div class="drop-hint">Click to browse or drag &amp; drop</div>
          </div>
          <div class="drop-meta" id="excelMeta" style="display:none"></div>
        </label>
        <input type="file" id="excelInput">

        <!-- PDF drop -->
        <label class="drop-card" id="pdfDrop" for="pdfInput">
          <div class="drop-icon pdf">
            <svg width="26" height="26" viewBox="0 0 34 34" fill="none">
              <rect x="3" y="2" width="20" height="28" rx="3" fill="#fff" stroke="#E04B3E" stroke-width="1.6"/>
              <path d="M17 2v8h9" stroke="#E04B3E" stroke-width="1.6" stroke-linecap="round"/>
              <rect x="17" y="2" width="9" height="8" rx="1" fill="#FED7D4" stroke="#E04B3E" stroke-width="1.6"/>
              <path d="M8 17h2.5a2 2 0 010 4H8v4" stroke="#E04B3E" stroke-width="1.6" stroke-linecap="round"/>
              <path d="M19 17v8M19 17h2a2.5 2.5 0 010 5h-2" stroke="#E04B3E" stroke-width="1.6" stroke-linecap="round"/>
              <path d="M25 17h-.5A2.5 2.5 0 0022 19.5v3A2.5 2.5 0 0024.5 25H25" stroke="#E04B3E" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
          </div>
          <div>
            <div class="drop-main">Scanned PDFs</div>
            <div class="fmt-row"><span class="fmt-chip">.pdf</span><span class="fmt-chip">multi-select</span></div>
            <div class="drop-hint">Click to browse or drag &amp; drop</div>
          </div>
          <div class="drop-meta" id="pdfMeta" style="display:none"></div>
        </label>
        <input type="file" id="pdfInput" multiple>

      </div>

      <!-- Error banner -->
      <div class="err-banner" id="errBanner"></div>

      <!-- Action row -->
      <div class="action-row" style="margin-top:20px;">
        <button class="btn-process" id="processBtn" disabled>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          Process &amp; Rename
        </button>
        <button class="btn-reset" id="resetBtn" style="display:none">&#8635; Reset</button>
      </div>

      <!-- Progress -->
      <div class="progress-section" id="progressSection" style="margin-top:20px;">
        <div class="progress-label" id="progressLabel">Starting…</div>
        <div class="progress-bar-wrap"><div class="progress-bar-fill" id="progressFill"></div></div>
        <div class="progress-file" id="progressFile"></div>
      </div>
    </div>
  </div>

  <!-- Results card -->
  <div class="card results-section" id="resultsSection">
    <div class="card-hd">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
      <h2>Results</h2>
    </div>
    <div class="card-body">
      <div class="tiles">
        <div class="tile ok"><div class="tile-num" id="tileOk">—</div><div class="tile-lbl">Renamed</div></div>
        <div class="tile warn"><div class="tile-num" id="tileNoBC">—</div><div class="tile-lbl">No Barcode</div></div>
        <div class="tile warn"><div class="tile-num" id="tileNotFound">—</div><div class="tile-lbl">Not in Excel</div></div>
        <div class="tile bad"><div class="tile-num" id="tileErr">—</div><div class="tile-lbl">Errors</div></div>
      </div>

      <div class="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Original File</th>
              <th>Status</th>
              <th>Receipt Number</th>
              <th>Barcode (PDF)</th>
              <th>Barcode (Excel)</th>
              <th>Receipt Date</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody id="resultsBody"></tbody>
        </table>
      </div>

      <div class="result-actions">
        <a class="btn-download" id="downloadBtn" href="#" style="display:none">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download Renamed PDFs
        </a>
        <button class="btn-new" id="newBatchBtn">&#8635; New Batch</button>
      </div>
    </div>
  </div>
</main>

<footer class="footer">Amirtharaj Investment &mdash; ETDS Automation &mdash; Internal Tool</footer>

<script>
const $ = id => document.getElementById(id);

let excelFile = null;
let pdfFiles  = [];
let currentJobId = null;
let pollTimer = null;

// ── File wiring ───────────────────────────────────────────────────────────────

function wireInput(dropId, inputId, multi, onFiles) {
  const drop  = $(dropId);
  const input = $(inputId);
  input.addEventListener('change', () => { if (input.files.length) onFiles([...input.files]); input.value = ''; });
  drop.addEventListener('dragover',  e => { e.preventDefault(); drop.classList.add('drag'); });
  drop.addEventListener('dragleave', e => { e.preventDefault(); drop.classList.remove('drag'); });
  drop.addEventListener('drop', e => {
    e.preventDefault(); drop.classList.remove('drag');
    const files = [...e.dataTransfer.files].filter(f => true);
    if (files.length) onFiles(files);
  });
}

wireInput('excelDrop', 'excelInput', false, files => {
  excelFile = files[0];
  $('excelDrop').classList.add('loaded');
  const m = $('excelMeta');
  m.style.display = 'block';
  m.textContent = '✓ ' + excelFile.name;
  refreshBtn();
});

wireInput('pdfDrop', 'pdfInput', true, files => {
  const pdfs = files.filter(f => /\.pdf$/i.test(f.name));
  if (!pdfs.length) { showErr('No PDF files found in the selection.'); return; }
  pdfFiles = pdfs;
  $('pdfDrop').classList.add('loaded');
  const m = $('pdfMeta');
  m.style.display = 'block';
  m.textContent = '✓ ' + (pdfs.length === 1 ? pdfs[0].name : pdfs.length + ' PDFs selected');
  refreshBtn();
});

function refreshBtn() {
  $('processBtn').disabled = !(excelFile && pdfFiles.length);
}

function showErr(msg) {
  const b = $('errBanner');
  b.textContent = msg;
  b.style.display = 'block';
  setTimeout(() => { b.style.display = 'none'; }, 6000);
}

// ── Process ───────────────────────────────────────────────────────────────────

$('processBtn').addEventListener('click', async () => {
  if (!excelFile || !pdfFiles.length) return;

  $('errBanner').style.display = 'none';
  $('processBtn').disabled = true;
  $('resultsSection').style.display = 'none';
  $('resetBtn').style.display = 'inline-flex';

  const fd = new FormData();
  fd.append('excel', excelFile);
  pdfFiles.forEach(f => fd.append('pdfs', f));

  let jobId;
  try {
    const res = await fetch('/process', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { showErr(data.error); $('processBtn').disabled = false; return; }
    jobId = data.job_id;
    currentJobId = jobId;
  } catch (e) {
    showErr('Upload failed: ' + e.message);
    $('processBtn').disabled = false;
    return;
  }

  // Show progress
  $('progressSection').style.display = 'block';
  $('progressFill').style.width = '0%';
  $('progressLabel').textContent = 'Uploading complete — processing...';
  $('progressFile').textContent = '';

  // Poll for status
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch('/status/' + jobId);
      const job = await res.json();

      if (job.error) { clearInterval(pollTimer); showErr(job.error); $('progressSection').style.display = 'none'; $('processBtn').disabled = false; return; }

      const pct = job.total ? Math.round(job.current / job.total * 100) : 0;
      $('progressFill').style.width = pct + '%';
      $('progressLabel').textContent = job.current + ' / ' + job.total + ' PDFs processed';
      $('progressFile').textContent = job.current_name || '';

      if (job.status === 'done') {
        clearInterval(pollTimer);
        $('progressSection').style.display = 'none';
        renderResults(job, jobId);
      }
    } catch (e) { /* network hiccup, keep polling */ }
  }, 600);
});

// ── Render results ────────────────────────────────────────────────────────────

function renderResults(job, jobId) {
  const s = job.summary;
  $('tileOk').textContent       = s.ok;
  $('tileNoBC').textContent     = s.no_barcode;
  $('tileNotFound').textContent = s.not_found;
  $('tileErr').textContent      = s.error;

  const tbody = $('resultsBody');
  tbody.innerHTML = '';
  job.results.forEach((r, i) => {
    const tr = document.createElement('tr');
    let stClass = '', stIcon = '';
    if (r.status === 'ok')         { stClass = 'st-ok';   stIcon = '✓ Renamed'; }
    else if (r.status === 'no_barcode') { stClass = 'st-warn'; stIcon = '? No barcode'; }
    else if (r.status === 'not_found')  { stClass = 'st-warn'; stIcon = '? Not in Excel'; }
    else                                { stClass = 'st-bad';  stIcon = '✗ Error'; }
    tr.innerHTML =
      '<td>' + (i + 1) + '</td>' +
      '<td>' + esc(r.name) + '</td>' +
      '<td class="' + stClass + '">' + stIcon + '</td>' +
      '<td class="receipt-num">' + (r.receipt || '—') + '</td>' +
      '<td class="barcode-val">' + (r.pdf_barcode || '—') + '</td>' +
      '<td class="barcode-val">' + (r.excel_barcode || '—') + '</td>' +
      '<td class="date-val">' + (r.date || '—') + '</td>' +
      '<td class="note-txt">' + esc(r.msg) + '</td>';
    tbody.appendChild(tr);
  });

  const dlBtn = $('downloadBtn');
  if (s.ok > 0) {
    dlBtn.href = '/download/' + jobId;
    dlBtn.style.display = 'inline-flex';
  } else {
    dlBtn.style.display = 'none';
  }

  $('resultsSection').style.display = 'block';
  $('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── Reset ─────────────────────────────────────────────────────────────────────

function resetAll() {
  if (pollTimer) clearInterval(pollTimer);
  excelFile = null; pdfFiles = []; currentJobId = null;
  ['excelDrop','pdfDrop'].forEach(id => $(id).classList.remove('loaded','drag'));
  ['excelMeta','pdfMeta'].forEach(id => { $(id).style.display = 'none'; $(id).textContent = ''; });
  $('processBtn').disabled = true;
  $('resetBtn').style.display = 'none';
  $('progressSection').style.display = 'none';
  $('resultsSection').style.display = 'none';
  $('errBanner').style.display = 'none';
  $('resultsBody').innerHTML = '';
  $('downloadBtn').style.display = 'none';
}

$('resetBtn').addEventListener('click', resetAll);
$('newBatchBtn').addEventListener('click', resetAll);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import socket
    try:
        host_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        host_ip = "your-machine-ip"

    print()
    print("  ETDS PDF Renamer — Web Dashboard")
    print("  ===================================")
    print(f"  Local:  http://localhost:5000")
    print(f"  Team:   http://{host_ip}:5000")
    print()
    print("  Press Ctrl+C to stop the server.")
    print()
    app.run(host="0.0.0.0", port=5000, debug=False)
