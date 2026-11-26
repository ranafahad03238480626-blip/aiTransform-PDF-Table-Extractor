"""
Table extraction from text PDFs, scanned PDFs and images.

Pipeline
  PDF page with ruled tables   -> pdfplumber line detection
  PDF page, borderless tables  -> word positions -> rows / columns (words_to_tables)
  Scanned page or image        -> deskew -> detect ruling lines -> OCR cell by cell
                                  (falls back to OCR word positions if no grid)
"""
import io
import os

import cv2
try:
    import pymupdf as fitz
except ImportError:  # older PyMuPDF
    import fitz
import numpy as np
import pandas as pd
import pdfplumber
import pytesseract
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
_cmd = os.getenv("TESSERACT_CMD")
if _cmd:
    pytesseract.pytesseract.tesseract_cmd = _cmd


# ------------------------------------------------------------------ helpers
def make_unique_columns(cols):
    """Fix empty or duplicate header names."""
    seen, out = {}, []
    for i, c in enumerate(cols):
        name = str(c).strip() if c not in (None, "") else f"col_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        out.append(name)
    return out


def rows_to_df(rows):
    """List of rows -> DataFrame (first row is the header)."""
    if len(rows) < 2:
        return None
    width = max(len(r) for r in rows)
    rows = [list(r) + [""] * (width - len(r)) for r in rows]
    df = pd.DataFrame(rows[1:], columns=make_unique_columns(rows[0]))
    return df.fillna("")


def _good_table(table):
    return bool(table) and len(table) >= 2 and max(len(r) for r in table) >= 2


def _runs(mask):
    """Start/end indices of consecutive True values."""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


# ------------------------------------------- words -> table (no ruling lines)
def words_to_tables(words, min_rows=3):
    """
    words: dicts with text, left, top, w, h (same unit: PDF points or pixels).
    Groups words into lines, lines into cells (big gap = new cell), finds blocks
    of consecutive multi-cell lines and splits each block into columns using the
    empty vertical strips between them. Works for right-aligned numbers too.
    """
    if not words:
        return []
    med_h = float(np.median([w["h"] for w in words]))

    # 1) lines
    words = sorted(words, key=lambda w: w["top"])
    lines = []
    for w in words:
        cy = w["top"] + w["h"] / 2
        if lines and abs(cy - lines[-1]["cy"]) < med_h * 0.55:
            lines[-1]["words"].append(w)
            ys = [x["top"] + x["h"] / 2 for x in lines[-1]["words"]]
            lines[-1]["cy"] = float(np.mean(ys))
        else:
            lines.append({"cy": cy, "words": [w]})

    # 2) cells inside each line
    gap = med_h * 1.3
    for ln in lines:
        cells = []
        for w in sorted(ln["words"], key=lambda w: w["left"]):
            right = w["left"] + w["w"]
            if cells and w["left"] - cells[-1]["right"] < gap:
                cells[-1]["text"] += " " + w["text"]
                cells[-1]["right"] = right
            else:
                cells.append({"text": w["text"], "left": w["left"],
                              "right": right})
        ln["cells"] = cells

    # 3) blocks of consecutive tabular lines (>= 2 cells, no big vertical jump)
    blocks, cur = [], []
    for ln in lines:
        if len(ln["cells"]) >= 2:
            if cur and ln["cy"] - cur[-1]["cy"] > med_h * 3.4:
                blocks.append(cur)
                cur = []
            cur.append(ln)
        else:
            if cur:
                blocks.append(cur)
                cur = []
    if cur:
        blocks.append(cur)

    tables = []
    for block in blocks:
        if len(block) < min_rows:
            continue
        # 4) columns = runs of x covered by any cell. They are measured on the
        #    body rows only, because headers are often left-aligned over
        #    right-aligned numbers and would not overlap the values.
        close = int(med_h * 0.5)  # bridge tiny gaps inside one column

        def col_runs(lines_):
            xmax = int(max(c["right"] for ln in lines_ for c in ln["cells"])) + 2
            cover = np.zeros(xmax + 1, dtype=bool)
            for ln in lines_:
                for c in ln["cells"]:
                    cover[int(c["left"]):int(c["right"]) + 1] = True
            out = []
            for r in _runs(cover):
                if out and r[0] - out[-1][1] <= close:
                    out[-1] = (out[-1][0], r[1])
                else:
                    out.append(r)
            return out

        merged = col_runs(block[1:])
        header_cells = block[0]["cells"]
        by_index = len(header_cells) == len(merged)
        if not by_index:
            merged = col_runs(block)
        if len(merged) < 2:
            continue

        def nearest(mid):
            return min(range(len(merged)),
                       key=lambda i: 0 if merged[i][0] <= mid <= merged[i][1]
                       else min(abs(mid - merged[i][0]), abs(mid - merged[i][1])))

        rows = []
        for k, ln in enumerate(block):
            row = [""] * len(merged)
            for ci, c in enumerate(ln["cells"]):
                if k == 0 and by_index:
                    idx = ci
                else:
                    idx = nearest((c["left"] + c["right"]) / 2)
                row[idx] = (row[idx] + " " + c["text"]).strip()
            rows.append(row)
        keep = [j for j in range(len(merged)) if any(r[j] for r in rows)]
        rows = [[r[j] for j in keep] for r in rows]
        tables.append(rows)
    return tables


# ------------------------------------------------------------- image / OCR
def _line_angles(gray):
    """Median angle of near-horizontal lines and median slope (dx/dy) of
    near-vertical lines, measured on a downscaled copy."""
    h, w = gray.shape
    s = 1000 / max(w, 1)
    small = cv2.resize(gray, None, fx=s, fy=s) if s < 1 else gray.copy()
    bw = cv2.adaptiveThreshold(small, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 31, 10)
    lines = cv2.HoughLinesP(bw, 1, np.pi / 1440, threshold=80,
                            minLineLength=min(small.shape) * 0.12, maxLineGap=8)
    hor, ver = [], []
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            dx, dy = x2 - x1, y2 - y1
            if abs(dx) >= abs(dy):
                a = np.degrees(np.arctan2(dy, dx))
                if abs(a) < 12:
                    hor.append(a)
            else:
                sl = dx / dy
                if abs(sl) < 0.2:
                    ver.append(sl)
    ang = float(np.median(hor)) if len(hor) >= 3 else 0.0
    slope = float(np.median(ver)) if len(ver) >= 3 else 0.0
    return ang, slope


def deskew(gray):
    """Straighten a scan or photo: rotate until the horizontal lines are level,
    then shear until the vertical lines are upright (handles mild perspective)."""
    h, w = gray.shape
    ang, _ = _line_angles(gray)
    if abs(ang) >= 0.15:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
        gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    _, slope = _line_angles(gray)
    if abs(slope) >= 0.004:
        M = np.float32([[1, -slope, slope * h / 2], [0, 1, 0]])
        gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    return gray


def find_grid(gray):
    """Return (row_edges, col_edges) from ruling lines, or None."""
    h, w = gray.shape
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 41, 8)
    m = max(4, int(min(h, w) * 0.015))      # ignore page-edge artefacts
    bw[:m, :] = 0
    bw[-m:, :] = 0
    bw[:, :m] = 0
    bw[:, -m:] = 0
    k = max(25, int(min(h, w) * 0.03))
    hor = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
    ver = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, k)))

    # keep only the biggest connected line structure (the table), so paper
    # edges, shadows and stray rules are ignored
    both = cv2.dilate(cv2.bitwise_or(hor, ver), np.ones((5, 5), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(both, connectivity=8)
    if n < 2:
        return None
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = (labels == best).astype(np.uint8) * 255
    hor = cv2.bitwise_and(hor, keep)
    ver = cv2.bitwise_and(ver, keep)

    hp = hor.sum(axis=1) / 255.0
    if hp.max() < w * 0.1:
        return None
    hl = _runs(hp > hp.max() * 0.4)
    ys = [int((a + b) / 2) for a, b in hl]
    if len(ys) < 3:
        return None
    # table's horizontal extent comes from the long horizontal lines
    xs_cov = hor[:, :].sum(axis=0) > 0
    x0, x1 = np.where(xs_cov)[0][[0, -1]]
    y0, y1 = ys[0], ys[-1]

    vp = ver[y0:y1 + 1, :].sum(axis=0) / 255.0
    if vp.max() < (y1 - y0) * 0.5:
        return None
    vl = _runs(vp > vp.max() * 0.5)
    xs = [int((a + b) / 2) for a, b in vl if x0 - 15 <= (a + b) / 2 <= x1 + 15]
    if len(xs) < 3:
        return None

    def dedupe(v, mn):
        out = [v[0]]
        for e in v[1:]:
            if e - out[-1] >= mn:
                out.append(e)
        return out
    ys, xs = dedupe(ys, 12), dedupe(xs, 12)
    if len(ys) < 3 or len(xs) < 3:
        return None
    return ys, xs


def ocr_cell(gray, y0, y1, x0, x1):
    ins = 5
    crop = gray[y0 + ins:y1 - ins, x0 + ins:x1 - ins]
    if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
        return ""
    crop = cv2.normalize(crop, None, 0, 255, cv2.NORM_MINMAX)
    _, bw = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if (bw < 128).mean() > 0.5:                # light text on a dark cell
        bw = 255 - bw
    if (bw < 128).mean() < 0.004:              # blank cell
        return ""
    if bw.shape[0] < 60:
        f = 60 / bw.shape[0]
        bw = cv2.resize(bw, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    bw = cv2.copyMakeBorder(bw, 14, 14, 14, 14, cv2.BORDER_CONSTANT, value=255)
    txt = " ".join(pytesseract.image_to_string(bw, config="--psm 7")
                   .replace("|", " ").split())
    # a narrow cell with one or two letters is a grade/code: re-read it as a
    # single character, which avoids "C" -> "Cc" or a stray dot
    narrow = (x1 - x0) < 1.6 * (y1 - y0)
    letters = "".join(ch for ch in txt if ch.isalnum())
    if narrow and letters.isalpha() and len(letters) <= 2:
        one = pytesseract.image_to_string(bw, config="--psm 10").strip()
        if one:
            txt = one
    return txt


def ocr_words(gray):
    """OCR the whole image and return positioned words (fallback, no grid)."""
    h, w = gray.shape
    if w < 1500:
        f = 1500 / w
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    d = pytesseract.image_to_data(bw, output_type=pytesseract.Output.DICT, config="--psm 6")
    out = []
    for i, t in enumerate(d["text"]):
        if t.strip() and float(d["conf"][i]) > 30:
            out.append({"text": t.strip(), "left": d["left"][i], "top": d["top"][i],
                        "w": d["width"][i], "h": d["height"][i]})
    return out


def ocr_tables(gray):
    """Gray image -> list of tables (each a list of rows)."""
    h, w = gray.shape
    if w < 1600:                                # small screenshots: enlarge
        f = 1600 / w
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    gray = deskew(gray)
    grid = find_grid(gray)
    if grid:
        ys, xs = grid
        rows = []
        for r in range(len(ys) - 1):
            row = [ocr_cell(gray, ys[r], ys[r + 1], xs[c], xs[c + 1])
                   for c in range(len(xs) - 1)]
            if any(row):
                rows.append(row)
        if len(rows) >= 2:
            return [rows]
    return words_to_tables(ocr_words(gray), min_rows=2)


# --------------------------------------------------------- public functions
def extract_from_image(image_file):
    image = Image.open(image_file).convert("RGB")
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    result = []
    for n, rows in enumerate(ocr_tables(gray), start=1):
        df = rows_to_df(rows)
        if df is not None:
            result.append({"name": f"Image_Table_{n}", "data": df})
    return result


def extract_from_pdf(file):
    pdf_bytes = file.getvalue() if hasattr(file, "getvalue") else open(file, "rb").read()
    tables = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_number, page in enumerate(pdf.pages, start=1):
            # 1) tables drawn with ruling lines
            found = [t for t in page.extract_tables() if _good_table(t)]

            has_text = len((page.extract_text() or "").strip()) > 20
            # 2) borderless tables: use word positions
            if not found and has_text:
                words = [{"text": w["text"], "left": w["x0"], "top": w["top"],
                          "w": w["x1"] - w["x0"], "h": w["bottom"] - w["top"]}
                         for w in page.extract_words(x_tolerance=1.5)]
                found = words_to_tables(words)

            # 3) scanned page: render, then OCR
            if not found and not has_text:
                pix = doc[page_number - 1].get_pixmap(dpi=300, alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
                found = ocr_tables(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))

            for table_number, table in enumerate(found, start=1):
                df = rows_to_df(table)
                if df is not None:
                    tables.append({"name": f"Page_{page_number}_Table_{table_number}",
                                   "data": df})
    return tables
