# AITransform PDF Table Extractor

Upload a PDF or an image that contains tables, preview what was extracted, and
download the result as an Excel workbook (one sheet per table) or as CSV.

**Live app:** `https://aitransform-table-extractor.streamlit.app/`

## Features
- Text-based PDFs with ruled (bordered) tables
- Text-based PDFs with borderless tables
- Scanned PDFs and images (PNG / JPG), including phone photos
- Several tables on one page, and tables that continue over several pages
- Preview of every table before download
- Excel export (one sheet per table) and CSV export (a zip when there is more than one table)

## Approach

The extractor picks a strategy per page.

| Input | Strategy |
|---|---|
| PDF page with ruling lines | `pdfplumber` line detection (`extract_tables`) |
| PDF page with text but no ruling lines | Word positions from `pdfplumber` are grouped into lines, then into cells (a large horizontal gap starts a new cell). Consecutive multi-cell lines form a table block. Column boundaries are the empty vertical strips between cells, measured on the body rows so that a left-aligned header over right-aligned numbers still lands in the right column. |
| Scanned PDF page (no text layer) | Page is rendered at 300 dpi with PyMuPDF and handled like an image. |
| Image / rendered scan | 1. Enlarge small images. 2. **Straighten**: rotate until horizontal lines are level, then shear until vertical lines are upright (handles tilt and mild perspective). 3. **Find the grid**: adaptive threshold, morphological opening to isolate horizontal and vertical lines, keep only the largest connected line structure (the table, not the paper edge), read row and column edges from line projections. 4. **OCR cell by cell** with Tesseract (`--psm 7`); light text on dark header cells is inverted first; blank cells are skipped; narrow one- or two-letter cells are re-read as a single character. 5. If no grid is found, fall back to OCR word positions and the same word-to-table logic used for borderless PDFs. |

The first row of every table is treated as the header.

## Data source

There is no public dataset in this project. I built my own test set of
**16 documents containing 22 tables**, and wrote a ground-truth CSV for every
table. `generate_test_data.py` creates them (fixed random seed, so the set is
reproducible). The content (names, companies, amounts) is made up, but the
layouts imitate real invoices, bank statements, result sheets and reports.
Scanned files and the photo get tilt, noise, dust, shadows, blur and JPEG
compression.

| # | Document | Category |
|---|---|---|
| 01 | Invoice with letterhead | Bordered PDF |
| 02 | Student result sheet (serif font, zebra rows) | Bordered PDF |
| 03 | Employee directory | Bordered PDF |
| 04 | Sales report (one rule under header) | Borderless PDF |
| 05 | Bank statement (monospace, empty cells) | Borderless PDF |
| 06 | Warehouse stock list | Borderless PDF |
| 07 | Attendance, 3 pages, header repeated | Multi-page PDF |
| 08 | Settlement log, header only on page 1 | Multi-page PDF |
| 09 | Two tables with text between | Multiple tables per page |
| 10 | Three small tables with headings | Multiple tables per page |
| 11 | Two-row header with merged cells | Merged cells |
| 12 | Scanned invoice, 0.7Â° tilt | Scanned PDF |
| 13 | Scanned marksheet, -1.1Â° tilt | Scanned PDF |
| 14 | Web dashboard screenshot | Image |
| 15 | Spreadsheet screenshot (JPEG) | Image |
| 16 | Phone photo of a bill | Phone photo |

## Setup

```bash
git clone <repo-url>
cd aiTransform_PDF_Table_Extractor
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

Tesseract OCR must be installed on the machine:
- **Windows:** UB Mannheim installer (https://github.com/UB-Mannheim/tesseract/wiki), then copy `.env.example` to `.env` and set `TESSERACT_CMD` to the path of `tesseract.exe`.
- **Linux / Streamlit Cloud:** `packages.txt` lists `tesseract-ocr`, nothing else to do.

Run the app:

```bash
python -m streamlit run app.py
```

No API keys or secrets are needed. `.env` is git-ignored; `.env.example` shows the only variable.

## Evaluation

```bash
python evaluate.py
```

For every ground-truth table the script finds the matching extracted table
(by reading order) and reports:
- **shape match**: rows x columns equal the ground truth
- **cell accuracy**: share of ground-truth cells that match exactly at the same position (whitespace trimmed; a missing cell counts as wrong)
- **char similarity**: average string similarity of the cells, giving partial credit to small OCR slips

Per-table results are in `test_documents/evaluation_results.csv`.

### Results

| Category | Tables | v1 (first version) | v2 (current) |
|---|---|---|---|
| Bordered PDF | 3 | 1.000 | 1.000 |
| Borderless PDF | 3 | 0.063 | 1.000 |
| Multi-page PDF | 5 | 0.639 | 1.000 |
| Multiple tables per page | 5 | 1.000 | 1.000 |
| Merged cells | 1 | 0.886 | 0.886 |
| Image (screenshot) | 2 | 0.259 | 1.000 |
| Phone photo | 1 | 0.000 | 1.000 |
| Scanned PDF | 2 | 0.000 | 0.943 |
| **Overall cell accuracy** | **22** | **0.581** | **0.990** |

v2 overall: char similarity 0.993, shape match 1.000.
v1 was a simple `pdfplumber` text strategy plus whole-image OCR that split
every line on spaces. v1 numbers are saved in `test_documents/evaluation_baseline.csv`.

**Read these numbers with care.** The test set was made by me and the extractor
was tuned on it, so v2 is optimistic. Real-world documents will score lower.

## Limitations
- The first row of each table is assumed to be the header. A table that continues on the next page without a header (doc 08) is extracted correctly, but its first data row becomes the column names in the preview.
- A vertically merged cell (e.g. "Region" spanning two header rows) ends up in the second header row, not the first.
- Images are assumed to hold **one** table. Several tables in one image are not separated.
- OCR needs ruling lines for best results. Scanned tables without lines use the weaker word-position fallback.
- OCR can confuse similar characters (e.g. a grade "C" read as "Cc"), and very low-resolution or heavily blurred photos will fail.
- Tables are matched to ground truth by reading order, so one missed table shifts the match for the following ones in the same file.
- Handwriting, rotated pages (90Â°), non-English scripts and nested tables are not supported.
- OCR runs cell by cell and is slow on large tables (several seconds per page).

## Project structure
```
app.py                  Streamlit UI (upload, preview, download)
table_extractor.py      extraction logic
evaluate.py             accuracy evaluation
generate_test_data.py   builds the test documents and ground truth
test_documents/         docs/, ground_truth/, manifest.csv, evaluation results
requirements.txt  packages.txt  .env.example
```

