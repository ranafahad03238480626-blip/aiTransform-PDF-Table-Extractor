"""
Runs the extractor on every document in test_documents/docs and compares each
extracted table with its ground-truth CSV.

Run:  python evaluate.py
Output: test_documents/evaluation_results.csv  (one row per ground-truth table)
        plus a summary printed to the console.

Metrics (per table)
  shape_match      extracted rows x columns equal the ground truth
  cell_accuracy    share of ground-truth cells that match exactly at the same
                   (row, column) position, after trimming and collapsing spaces.
                   Missing cells count as wrong.
  char_similarity  average difflib similarity of the cells (0-1). It gives
                   partial credit to OCR slips such as "1,350.00" -> "1.350.00".

Tables are matched to ground truth in reading order (page by page, top to
bottom). A table that was not found scores 0 and is marked "missed".
"""
import csv
import difflib
import io
import os
import re

import pandas as pd

from table_extractor import extract_from_image, extract_from_pdf

ROOT = "test_documents"
DOCS = os.path.join(ROOT, "docs")
GT = os.path.join(ROOT, "ground_truth")
OUT = os.path.join(ROOT, "evaluation_results.csv")


def norm(x):
    return re.sub(r"\s+", " ", str(x if x is not None else "")).strip()


def df_to_grid(df):
    """Header row + data rows, so header detection does not matter."""
    return [[norm(c) for c in df.columns]] + [[norm(v) for v in row]
                                              for row in df.values.tolist()]


def load_gt(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [[norm(c) for c in row] for row in csv.reader(f)]


def compare(gt, pred):
    gr, gc = len(gt), max(len(r) for r in gt)
    pr = len(pred)
    pc = max((len(r) for r in pred), default=0)
    total = sum(len(r) for r in gt)
    hit, sim = 0, 0.0
    for i, row in enumerate(gt):
        for j, cell in enumerate(row):
            got = pred[i][j] if i < pr and j < len(pred[i]) else ""
            if got == cell:
                hit += 1
                sim += 1.0
            else:
                sim += difflib.SequenceMatcher(None, cell, got).ratio()
    return {
        "expected_shape": f"{gr}x{gc}",
        "extracted_shape": f"{pr}x{pc}",
        "shape_match": (gr, gc) == (pr, pc),
        "cell_accuracy": round(hit / total, 4),
        "char_similarity": round(sim / total, 4),
    }


def main():
    manifest = {}
    with open(os.path.join(ROOT, "manifest.csv"), newline="",
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            manifest[r["document"]] = r["category"]

    rows = []
    for fname in sorted(os.listdir(DOCS)):
        stem, ext = os.path.splitext(fname)
        gt_files = sorted(g for g in os.listdir(GT) if g.startswith(stem + "__t"))
        if not gt_files:
            continue
        with open(os.path.join(DOCS, fname), "rb") as f:
            buf = io.BytesIO(f.read())
        try:
            tables = (extract_from_pdf(buf) if ext.lower() == ".pdf"
                      else extract_from_image(buf))
            error = ""
        except Exception as e:  # keep going, record the failure
            tables, error = [], f"{type(e).__name__}: {e}"

        for k, g in enumerate(gt_files):
            gt = load_gt(os.path.join(GT, g))
            base = {"document": fname, "category": manifest.get(stem, ""),
                    "table": g.split("__")[1].replace(".csv", "")}
            if k < len(tables):
                res = compare(gt, df_to_grid(tables[k]["data"]))
                res["status"] = "ok"
            else:
                res = {"expected_shape": f"{len(gt)}x{max(len(r) for r in gt)}",
                       "extracted_shape": "-", "shape_match": False,
                       "cell_accuracy": 0.0, "char_similarity": 0.0,
                       "status": "error: " + error if error else "missed"}
            res["tables_expected_in_doc"] = len(gt_files)
            res["tables_found_in_doc"] = len(tables)
            rows.append({**base, **res})

    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)

    print(df[["document", "table", "expected_shape", "extracted_shape",
              "cell_accuracy", "char_similarity", "status"]].to_string(index=False))
    print("\n=== Summary by category ===")
    summ = df.groupby("category").agg(
        tables=("table", "count"),
        shape_match=("shape_match", "mean"),
        cell_accuracy=("cell_accuracy", "mean"),
        char_similarity=("char_similarity", "mean")).round(3)
    print(summ.to_string())
    print(f"\nDocuments: {df['document'].nunique()}  Tables: {len(df)}")
    print(f"Overall cell accuracy:   {df['cell_accuracy'].mean():.3f}")
    print(f"Overall char similarity: {df['char_similarity'].mean():.3f}")
    print(f"Shape match:             {df['shape_match'].mean():.3f}")
    print(f"\nSaved: {OUT}")


if __name__ == "__main__":
    main()
