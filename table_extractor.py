
import pdfplumber
import pandas as pd
import pytesseract
import cv2
import numpy as np

from PIL import Image


def extract_from_pdf(file):
    tables = []

    with pdfplumber.open(file) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_tables = page.extract_tables()

            for table_number, table in enumerate(page_tables, start=1):
                if table and len(table) > 1:
                    df = pd.DataFrame(
                        table[1:],
                        columns=table[0]
                    )

                    tables.append({
                        "name": f"Page_{page_number}_Table_{table_number}",
                        "data": df
                    })

    return tables


def extract_from_image(image_file):
    image = Image.open(image_file).convert("RGB")
    image_array = np.array(image)

    gray = cv2.cvtColor(
        image_array,
        cv2.COLOR_RGB2GRAY
    )

    text = pytesseract.image_to_string(gray)

    rows = [
        line.split()
        for line in text.splitlines()
        if line.strip()
    ]

    if not rows:
        return []

    max_columns = max(len(row) for row in rows)

    normalized_rows = [
        row + [""] * (max_columns - len(row))
        for row in rows
    ]

    df = pd.DataFrame(normalized_rows)

    return [{
        "name": "Image_Table_1",
        "data": df
    }]
