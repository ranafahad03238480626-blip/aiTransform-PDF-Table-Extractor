"""
Generates the 16-document test set used to evaluate the table extractor,
together with a ground-truth CSV for every table.

Run:  python generate_test_data.py
Output:
    test_documents/docs/          the PDFs and images
    test_documents/ground_truth/  <doc>__t<N>.csv  (header row + data rows)
    test_documents/manifest.csv   doc, category, description

The content is made up (names, companies, amounts) but laid out the way real
invoices, bank statements, result sheets and reports look. Scanned files and
the phone photo get tilt, noise, blur, shadows and JPEG compression.
A fixed random seed keeps the test set reproducible.
"""
import csv
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

random.seed(42)
np.random.seed(42)

ROOT = "test_documents"
DOCS = os.path.join(ROOT, "docs")
GT = os.path.join(ROOT, "ground_truth")
os.makedirs(DOCS, exist_ok=True)
os.makedirs(GT, exist_ok=True)

MANIFEST = []
styles = getSampleStyleSheet()


# ----------------------------------------------------------------- helpers
def save_gt(doc, n, rows):
    path = os.path.join(GT, f"{doc}__t{n}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def register(doc, category, description):
    MANIFEST.append([doc, category, description])


def money(x):
    return f"{x:,.2f}"


def find_font(bold=False):
    names = (["LiberationSans-Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
             if bold else
             ["LiberationSans-Regular.ttf", "arial.ttf", "DejaVuSans.ttf"])
    dirs = ["/usr/share/fonts/truetype/liberation",
            "/usr/share/fonts/truetype/dejavu",
            "C:/Windows/Fonts", "/Library/Fonts"]
    for d in dirs:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None


def font(size, bold=False):
    p = find_font(bold)
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


FIRST = ["Ayesha", "Hamza", "Sana", "Bilal", "Fatima", "Usman", "Zainab",
         "Daniyal", "Hira", "Imran", "Maryam", "Talha", "Noor", "Saad",
         "Rabia", "Faisal", "Iqra", "Kamran", "Laiba", "Omar", "Sarah",
         "James", "Priya", "Daniel", "Emily", "Arjun", "Chloe", "Marcus"]
LAST = ["Khan", "Ahmed", "Malik", "Siddiqui", "Raza", "Butt", "Sheikh",
        "Qureshi", "Hussain", "Chaudhry", "Iqbal", "Farooq", "Mirza",
        "Patel", "Brown", "Walker", "Nguyen", "Fernandes", "Clarke"]


def person():
    return f"{random.choice(FIRST)} {random.choice(LAST)}"


def base_doc(path, footer=True):
    def on_page(canvas, doc):
        if footer:
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.grey)
            canvas.drawString(20 * mm, 10 * mm, "Confidential - for internal use")
            canvas.drawRightString(A4[0] - 20 * mm, 10 * mm,
                                   f"Page {doc.page}")
            canvas.restoreState()
    d = SimpleDocTemplate(path, pagesize=A4, leftMargin=20 * mm,
                          rightMargin=20 * mm, topMargin=18 * mm,
                          bottomMargin=18 * mm)
    return d, on_page


def heading(text, size=16, font_name="Helvetica-Bold", color=colors.black):
    return Paragraph(text, ParagraphStyle("h", fontName=font_name,
                                          fontSize=size, leading=size + 4,
                                          textColor=color, spaceAfter=4))


def body(text, size=9.5, font_name="Helvetica", align=0):
    return Paragraph(text, ParagraphStyle("b", fontName=font_name,
                                          fontSize=size, leading=size + 3,
                                          alignment=align))


def numeric_cols_right(ncols_numeric, total_cols, header_rows=1):
    return [("ALIGN", (c, header_rows), (c, -1), "RIGHT")
            for c in ncols_numeric if c < total_cols]


# --------------------------------------------------------- data generators
ITEMS = [("A4 Copy Paper (500 sheets)", 420), ("HP 305A Toner Cartridge", 7850),
         ("Stapler Heavy Duty", 650), ("Whiteboard Marker (pack of 12)", 540),
         ("Spiral Notebook 200pg", 180), ("USB-C Hub 7-in-1", 4200),
         ("Wireless Mouse", 1350), ("Desk Organizer", 890),
         ("Printer Ink 664 Black", 1900), ("File Folder (box of 25)", 760),
         ("Sticky Notes 3x3", 120), ("Ethernet Cable 5m", 450),
         ("Surge Protector 6-way", 1650), ("Laptop Stand Aluminium", 3300)]


def invoice_rows(n):
    rows = [["S.No", "Description", "Qty", "Unit Price", "Amount"]]
    picks = random.sample(ITEMS, n)
    total = 0
    for i, (d, p) in enumerate(picks, 1):
        q = random.randint(1, 24)
        total += q * p
        rows.append([str(i), d, str(q), money(p), money(q * p)])
    return rows, total


def results_rows(n):
    subjects = ["Math", "Physics", "Chemistry", "English", "Urdu", "CS"]
    rows = [["Roll No", "Student Name"] + subjects + ["Total", "Grade"]]
    for i in range(n):
        m = [random.randint(38, 98) for _ in subjects]
        t = sum(m)
        pct = t / (len(subjects) * 100)
        g = ("A+" if pct >= .85 else "A" if pct >= .75 else
             "B" if pct >= .65 else "C" if pct >= .55 else "D")
        rows.append([f"2026-{101 + i}", person()] + [str(x) for x in m]
                    + [str(t), g])
    return rows


def employees_rows(n):
    depts = ["Finance", "Engineering", "Marketing", "HR", "Operations",
             "Support"]
    roles = ["Analyst", "Manager", "Associate", "Lead", "Coordinator",
             "Specialist"]
    rows = [["ID", "Name", "Department", "Designation", "City", "Joined"]]
    for i in range(n):
        rows.append([f"E{1040 + i}", person(), random.choice(depts),
                     random.choice(roles),
                     random.choice(["Lahore", "Karachi", "Islamabad",
                                    "Multan", "Faisalabad"]),
                     f"{random.randint(2,28):02d}-{random.choice(['Jan','Mar','May','Jul','Sep','Nov'])}-{random.randint(2016,2025)}"])
    return rows


def sales_rows():
    rows = [["Product Line", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]]
    for p in ["Laptops", "Monitors", "Keyboards", "Headsets", "Webcams",
              "Docking Stations", "Printers"]:
        rows.append([p] + [f"{random.randint(120, 980):,}" for _ in range(6)])
    return rows


def bank_rows(n):
    rows = [["Date", "Description", "Debit", "Credit", "Balance"]]
    bal = random.randint(80000, 250000)
    descs = ["ATM Withdrawal", "Salary Credit", "Utility Bill - SNGPL",
             "POS Purchase - Imtiaz", "IBFT Transfer", "Foodpanda Order",
             "Mobile Top-up", "Cheque Deposit", "Online Shopping",
             "K-Electric Bill", "Rent Payment", "Fuel - PSO"]
    day = 1
    for _ in range(n):
        day += random.randint(0, 2)
        d = random.choice(descs)
        if d in ("Salary Credit", "Cheque Deposit", "IBFT Transfer") \
                and random.random() < .7:
            c = random.randint(5, 90) * 1000
            bal += c
            rows.append([f"{min(day, 28):02d}/03/2026", d, "", money(c),
                         money(bal)])
        else:
            dbt = random.randint(3, 400) * 50
            bal -= dbt
            rows.append([f"{min(day, 28):02d}/03/2026", d, money(dbt), "",
                         money(bal)])
    return rows


def inventory_rows(n):
    rows = [["SKU", "Item", "Warehouse", "On Hand", "Reorder Lvl", "Status"]]
    for i in range(n):
        item, _ = random.choice(ITEMS)
        oh = random.randint(0, 600)
        rl = random.choice([50, 100, 150, 200])
        rows.append([f"SKU-{4100 + i * 7}", item,
                     random.choice(["WH-Lahore", "WH-Karachi", "WH-ISB"]),
                     str(oh), str(rl), "Reorder" if oh < rl else "OK"])
    return rows


def attendance_rows(n, start=1):
    rows = []
    for i in range(n):
        late = random.choice([0, 0, 0, 1, 2, 3])
        absent = random.choice([0, 0, 0, 1, 2])
        rows.append([f"T-{200 + start + i}", person(),
                     str(22 - absent), str(absent), str(late),
                     f"{(22 - absent) / 22 * 100:.1f}%"])
    return rows


def transactions_rows(n):
    rows = []
    for _ in range(n):
        rows.append([f"TXN{random.randint(100000, 999999)}",
                     f"{random.randint(1, 28):02d}-Apr-2026",
                     random.choice(["Visa", "Mastercard", "JazzCash",
                                    "Easypaisa", "Bank Transfer"]),
                     money(random.randint(500, 95000) + random.choice(
                         [0, .5, .25, .75])),
                     random.choice(["Settled", "Settled", "Pending",
                                    "Failed"])])
    return rows


# --------------------------------------------------------- PDF table styles
def bordered_style(header_bg=colors.HexColor("#1F3A5F"),
                   zebra=False, font_name="Helvetica", size=9, nrows=0):
    st = [("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#555555")),
          ("BACKGROUND", (0, 0), (-1, 0), header_bg),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("FONTNAME", (0, 0), (-1, 0), font_name + "-Bold"
           if font_name != "Times-Roman" else "Times-Bold"),
          ("FONTNAME", (0, 1), (-1, -1), font_name),
          ("FONTSIZE", (0, 0), (-1, -1), size),
          ("TOPPADDING", (0, 0), (-1, -1), 5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if zebra:
        for r in range(2, nrows, 2):
            st.append(("BACKGROUND", (0, r), (-1, r),
                       colors.HexColor("#EEF2F7")))
    return st


def borderless_style(font_name="Helvetica", size=9, rule=True):
    st = [("FONTNAME", (0, 0), (-1, 0), font_name + "-Bold"
           if font_name != "Times-Roman" else "Times-Bold"),
          ("FONTNAME", (0, 1), (-1, -1), font_name),
          ("FONTSIZE", (0, 0), (-1, -1), size),
          ("TOPPADDING", (0, 0), (-1, -1), 4),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if rule:
        st.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black))
    return st


def tbl(rows, widths, style, repeat=0):
    t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=repeat)
    t.setStyle(TableStyle(style))
    return t


# ------------------------------------------------------------ 01-03 bordered
def d01():
    name = "01_invoice_bordered"
    rows, total = invoice_rows(8)
    save_gt(name, 1, rows)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    tax = round(total * 0.17, 2)
    story = [
        heading("Karachi Office Supplies Co.", 18, color=colors.HexColor("#1F3A5F")),
        body("Plot 14, Sector 7-A, Korangi Industrial Area, Karachi<br/>"
             "Phone: +92 21 3505 1142 | accounts@kosupplies.example"),
        Spacer(1, 10),
        heading("TAX INVOICE", 13),
        body("Invoice No: <b>INV-2026-0387</b> &nbsp;&nbsp; Date: <b>14 March 2026</b>"
             f"<br/>Bill To: <b>{person()}</b>, Al-Noor Traders, Lahore"),
        Spacer(1, 12),
        tbl(rows, [14, 78, 18, 30, 30],
            bordered_style() + numeric_cols_right([0, 2, 3, 4], 5)),
        Spacer(1, 10),
        body(f"Subtotal: {money(total)}<br/>GST (17%): {money(tax)}<br/>"
             f"<b>Grand Total: PKR {money(total + tax)}</b>", align=2),
        Spacer(1, 18),
        body("Payment due within 15 days. Cheques payable to Karachi Office "
             "Supplies Co."),
    ]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Bordered PDF", "Invoice with letterhead, totals outside the table")


def d02():
    name = "02_student_results_bordered"
    rows = results_rows(14)
    save_gt(name, 1, rows)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"), footer=False)
    story = [
        heading("Govt. Science College, Lahore", 17, "Times-Bold"),
        body("Annual Examination 2026 - Class XI (Pre-Engineering) - Section B",
             11, "Times-Roman"),
        Spacer(1, 12),
        tbl(rows, [20, 36, 12, 14, 17, 14, 12, 12, 12],
            bordered_style(colors.HexColor("#7A1F2B"), True, "Times-Roman", 8.5, len(rows))
            + [("ALIGN", (2, 1), (-1, -1), "CENTER")]),
        Spacer(1, 14),
        body("Passing marks: 33 per subject. Result prepared by the "
             "Examination Cell.", 9, "Times-Roman"),
    ]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Bordered PDF", "Result sheet, serif font, zebra rows")


def d03():
    name = "03_employee_directory_bordered"
    rows = employees_rows(18)
    save_gt(name, 1, rows)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    story = [
        heading("Employee Directory - Q2 2026", 15),
        body("Source: HR information system, exported 02 April 2026."),
        Spacer(1, 10),
        tbl(rows, [16, 40, 28, 32, 28, 26],
            bordered_style(colors.HexColor("#2E6B4F"), True, "Helvetica", 8.5, len(rows))),
    ]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Bordered PDF", "Directory with alternating row colours")


# ---------------------------------------------------------- 04-06 borderless
def d04():
    name = "04_sales_report_borderless"
    rows = sales_rows()
    save_gt(name, 1, rows)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    story = [
        heading("Units Sold by Product Line - H1 2026", 15),
        body("All figures in units. Region: North."),
        Spacer(1, 12),
        tbl(rows, [42, 20, 20, 20, 20, 20, 20],
            borderless_style() + numeric_cols_right(range(1, 7), 7)),
        Spacer(1, 14),
        body("Note: Webcam sales were affected by a supply delay in February."),
    ]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Borderless PDF", "Financial-report style, one rule under header")


def d05():
    name = "05_bank_statement_borderless"
    rows = bank_rows(16)
    save_gt(name, 1, rows)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    story = [
        heading("Meezan Current Account Statement", 15, "Courier-Bold"),
        body("Account: 0102-XXXX-4417 | Period: 01-Mar-2026 to 31-Mar-2026",
             9, "Courier"),
        Spacer(1, 12),
        tbl(rows, [26, 58, 26, 26, 30],
            borderless_style("Courier", 8.5, rule=False)
            + numeric_cols_right([2, 3, 4], 5)),
    ]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Borderless PDF", "Monospace statement, no lines, empty cells")


def d06():
    name = "06_inventory_borderless"
    rows = inventory_rows(15)
    save_gt(name, 1, rows)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    story = [
        heading("Warehouse Stock Position", 15),
        body("Snapshot taken 30 April 2026, 6:00 PM."),
        Spacer(1, 10),
        tbl(rows, [24, 62, 26, 18, 22, 18], borderless_style(size=8.5, rule=False)
            + numeric_cols_right([3, 4], 6)),
    ]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Borderless PDF", "Plain whitespace-aligned columns")


# ---------------------------------------------------------- 07-08 multi-page
def d07():
    name = "07_attendance_multipage"
    header = ["Staff ID", "Name", "Days Present", "Absent", "Late", "Attendance"]
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    story = [heading("Teaching Staff Attendance - May 2026", 15), Spacer(1, 8)]
    start = 1
    for page in range(1, 4):
        rows = [header] + attendance_rows(22, start)
        start += 22
        save_gt(name, page, rows)
        story.append(tbl(rows, [22, 52, 28, 20, 18, 28],
                         bordered_style(colors.HexColor("#444444"), False,
                                        "Helvetica", 9), repeat=1))
        if page < 3:
            story.append(PageBreak())
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Multi-page PDF", "3 pages, header repeated on each page")


def d08():
    name = "08_transactions_continued"
    header = ["Txn ID", "Date", "Channel", "Amount (PKR)", "Status"]
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    story = [heading("Payment Gateway Settlement Log - April 2026", 15),
             Spacer(1, 8)]
    for page in range(1, 3):
        data = transactions_rows(24)
        rows = ([header] if page == 1 else []) + data
        save_gt(name, page, rows)
        story.append(tbl(rows, [32, 30, 38, 36, 28],
                         borderless_style(size=9, rule=(page == 1))
                         + numeric_cols_right([3], 5, 1 if page == 1 else 0)))
        if page < 2:
            story.append(PageBreak())
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Multi-page PDF",
             "Header only on page 1, page 2 continues without header (hard case)")


# ---------------------------------------------------- 09-10 several per page
def d09():
    name = "09_two_tables_one_page"
    sales = [["Quarter", "Revenue", "Cost", "Profit"]]
    for q in ["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"]:
        r = random.randint(8_000, 15_000) * 1000
        c = int(r * random.uniform(.55, .78))
        sales.append([q, f"{r:,}", f"{c:,}", f"{r - c:,}"])
    exp = [["Expense Head", "Budget", "Actual"]]
    for e in ["Salaries", "Rent", "Marketing", "Travel", "Utilities"]:
        b = random.randint(2, 40) * 50_000
        exp.append([e, f"{b:,}", f"{int(b * random.uniform(.8, 1.15)):,}"])
    save_gt(name, 1, sales)
    save_gt(name, 2, exp)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    st = bordered_style(colors.HexColor("#3B3B98"))
    story = [
        heading("Management Summary - FY 2026", 15),
        body("The table below shows quarterly performance in PKR. Revenue grew "
             "steadily through the year, while costs rose slightly in the "
             "third quarter owing to higher logistics charges."),
        Spacer(1, 8),
        tbl(sales, [40, 45, 45, 40], st + numeric_cols_right([1, 2, 3], 4)),
        Spacer(1, 18),
        body("Operating expenses against budget are summarised next. Marketing "
             "and travel were the main areas of overspend."),
        Spacer(1, 8),
        tbl(exp, [60, 45, 45], st + numeric_cols_right([1, 2], 3)),
    ]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Multiple tables per page", "Two bordered tables with text between")


def d10():
    name = "10_three_tables_report"
    t1 = [["Class", "Boys", "Girls"]] + [[f"Grade {g}", str(random.randint(18, 40)),
                                          str(random.randint(15, 38))] for g in range(6, 11)]
    t2 = [["Teacher", "Subject", "Periods/Week"]] + [
        [person(), s, str(random.randint(14, 30))]
        for s in ["Mathematics", "Science", "English", "History"]]
    t3 = [["Month", "Fee Collected"]] + [[m, f"{random.randint(180, 420) * 1000:,}"]
                                         for m in ["January", "February", "March"]]
    for i, t in enumerate([t1, t2, t3], 1):
        save_gt(name, i, t)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    st = bordered_style(colors.HexColor("#555555"), False, "Times-Roman", 10)
    story = [heading("School Annual Report 2025-26 (Extract)", 16, "Times-Bold"),
             body("1. Enrolment", 11, "Times-Bold"),
             tbl(t1, [40, 30, 30], st), Spacer(1, 14),
             body("2. Faculty Workload", 11, "Times-Bold"),
             tbl(t2, [50, 45, 35], st), Spacer(1, 14),
             body("3. Fee Collection", 11, "Times-Bold"),
             tbl(t3, [45, 45], st)]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Multiple tables per page", "Three small tables with section headings")


# -------------------------------------------------------------- 11 merged
def d11():
    name = "11_merged_header_cells"
    regions = ["Punjab", "Sindh", "KPK", "Balochistan", "Islamabad"]
    rows = [["Region", "Q1 2026", "", "Q2 2026", ""],
            ["", "Units", "Revenue", "Units", "Revenue"]]
    for r in regions:
        u1, u2 = random.randint(300, 1500), random.randint(300, 1500)
        rows.append([r, f"{u1:,}", f"{u1 * 1250:,}", f"{u2:,}", f"{u2 * 1250:,}"])
    save_gt(name, 1, rows)
    d, op = base_doc(os.path.join(DOCS, name + ".pdf"))
    st = bordered_style(colors.HexColor("#1F3A5F")) + [
        ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (2, 0)), ("SPAN", (3, 0), (4, 0)),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#1F3A5F")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.white),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 1), "CENTER"),
        ("ALIGN", (1, 2), (-1, -1), "RIGHT")]
    story = [heading("Regional Sales Summary", 15), Spacer(1, 10),
             tbl(rows, [38, 28, 38, 28, 38], st)]
    d.build(story, onFirstPage=op, onLaterPages=op)
    register(name, "Merged cells", "Two-row header with merged (spanning) cells")


# ------------------------------------------------------- image rendering
def draw_table_image(rows, size=22, pad=14, header_fill=(31, 58, 95),
                     header_text=(255, 255, 255), grid=(90, 90, 90),
                     zebra=None, right_cols=(), title=None, subtitle=None,
                     margin=60, min_width=0):
    f, fb = font(size), font(size, True)
    ft = font(size + 10, True)
    fs = font(size - 3)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    ncol = max(len(r) for r in rows)
    widths = []
    for c in range(ncol):
        w = 0
        for ri, r in enumerate(rows):
            ff = fb if ri == 0 else f
            w = max(w, tmp.textlength(r[c], font=ff))
        widths.append(int(w + 2 * pad))
    row_h = size + 2 * pad - 4
    tw = sum(widths)
    head_h = 0
    if title:
        head_h += 55
    if subtitle:
        head_h += 34
    W = max(tw + 2 * margin, min_width)
    H = head_h + row_h * len(rows) + 2 * margin
    img = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    y = margin
    if title:
        dr.text((margin, y), title, font=ft, fill=(20, 20, 20))
        y += 55
    if subtitle:
        dr.text((margin, y), subtitle, font=fs, fill=(90, 90, 90))
        y += 34
    top = y
    for ri, r in enumerate(rows):
        yy = top + ri * row_h
        if ri == 0:
            dr.rectangle([margin, yy, margin + tw, yy + row_h], fill=header_fill)
        elif zebra and ri % 2 == 0:
            dr.rectangle([margin, yy, margin + tw, yy + row_h], fill=zebra)
        x = margin
        for ci, cell in enumerate(r):
            ff = fb if ri == 0 else f
            col = header_text if ri == 0 else (25, 25, 25)
            if ci in right_cols and ri > 0:
                tx = x + widths[ci] - pad - dr.textlength(cell, font=ff)
            else:
                tx = x + pad
            dr.text((tx, yy + (row_h - size) // 2 - 2), cell, font=ff, fill=col)
            x += widths[ci]
    if grid:
        x = margin
        for w in [0] + widths:
            x += w
            dr.line([x, top, x, top + row_h * len(rows)], fill=grid, width=2)
        dr.line([margin, top, margin, top + row_h * len(rows)], fill=grid, width=2)
        for ri in range(len(rows) + 1):
            yy = top + ri * row_h
            dr.line([margin, yy, margin + tw, yy], fill=grid, width=2)
    return img


def paper_noise(img, strength=10, dust=60, tint=(250, 247, 238)):
    arr = np.array(img.convert("RGB")).astype(np.float32)
    arr = arr * (np.array(tint, dtype=np.float32) / 255.0)
    arr += np.random.normal(0, strength, arr.shape[:2])[..., None]
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for _ in range(dust):
        x, y = random.randint(0, out.width - 1), random.randint(0, out.height - 1)
        r = random.choice([1, 1, 2])
        g = random.randint(90, 170)
        d.ellipse([x, y, x + r, y + r], fill=(g, g, g))
    return out


def edge_shadow(img, side="left", strength=70):
    w, h = img.size
    ramp = np.linspace(strength, 0, int(w * 0.07))
    arr = np.array(img).astype(np.float32)
    n = len(ramp)
    if side == "left":
        arr[:, :n, :] -= ramp[None, :, None]
    else:
        arr[:, w - n:, :] -= ramp[::-1][None, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# --------------------------------------------------------- 12-13 scanned PDF
def a4_page_with(table_img, title_lines, dpi=200, tilt=0.8, shadow="left"):
    W, H = int(8.27 * dpi), int(11.69 * dpi)
    page = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(page)
    y = 150
    for i, (txt, sz, bold) in enumerate(title_lines):
        d.text((110, y), txt, font=font(sz, bold), fill=(15, 15, 15))
        y += sz + 14
    y += 30
    ratio = min(1.0, (W - 220) / table_img.width)
    if ratio < 1:
        table_img = table_img.resize((W - 220, int(table_img.height * ratio)),
                                     Image.LANCZOS)
    page.paste(table_img, (110, y))
    page = paper_noise(page, 8, 90)
    page = page.rotate(tilt, resample=Image.BICUBIC, fillcolor=(236, 234, 228))
    page = edge_shadow(page, shadow, 60)
    return page.filter(ImageFilter.GaussianBlur(0.7)).convert("L")


def d12():
    name = "12_scanned_invoice"
    rows, total = invoice_rows(7)
    save_gt(name, 1, rows)
    img = draw_table_image(rows, size=24, pad=14, header_fill=(70, 70, 70),
                           right_cols=(0, 2, 3, 4), margin=6)
    page = a4_page_with(img, [("Lahore Hardware & Electric Store", 44, True),
                              ("Ph: 042-3578 2290   NTN: 3341827-5", 26, False),
                              ("Invoice # 2218      Date: 02/04/2026", 28, False)],
                        tilt=0.7)
    page.save(os.path.join(DOCS, name + ".pdf"), "PDF", resolution=200,
              quality=70)
    register(name, "Scanned PDF", "Image-only PDF, tilt 0.7 deg, noise, dust, edge shadow")


def d13():
    name = "13_scanned_marksheet"
    rows = results_rows(9)
    rows = [[c for c in r[:2] + r[2:5] + r[-2:]] for r in rows]  # fewer cols
    save_gt(name, 1, rows)
    img = draw_table_image(rows, size=24, pad=13, header_fill=(60, 60, 60),
                           zebra=(238, 238, 238), right_cols=(), margin=6)
    page = a4_page_with(img, [("Allama Iqbal Public School", 46, True),
                              ("Mid-Term Marksheet - Class 10", 30, False)],
                        tilt=-1.1, shadow="right")
    page.save(os.path.join(DOCS, name + ".pdf"), "PDF", resolution=200,
              quality=65)
    register(name, "Scanned PDF", "Image-only PDF, tilt -1.1 deg, grey zebra rows")


# ------------------------------------------------------------ 14-16 images
def d14():
    name = "14_table_screenshot"
    rows = [["Order ID", "Customer", "City", "Items", "Total (PKR)"]]
    for i in range(9):
        rows.append([f"#{50210 + i * 3}", person(),
                     random.choice(["Lahore", "Karachi", "Islamabad", "Quetta"]),
                     str(random.randint(1, 9)), f"{random.randint(15, 240) * 100:,}"])
    save_gt(name, 1, rows)
    img = draw_table_image(rows, size=20, pad=12, header_fill=(244, 245, 247),
                           header_text=(30, 30, 30), grid=(205, 208, 214),
                           right_cols=(3, 4), margin=24)
    img.save(os.path.join(DOCS, name + ".png"))
    register(name, "Image (screenshot)", "Clean web-dashboard style screenshot, light grid")


def d15():
    name = "15_spreadsheet_screenshot"
    rows = [["Month", "Website Visits", "Signups", "Conversion", "Ad Spend"]]
    for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]:
        v = random.randint(8_000, 30_000)
        s = int(v * random.uniform(.02, .06))
        rows.append([m, f"{v:,}", f"{s:,}", f"{s / v * 100:.1f}%",
                     f"{random.randint(40, 180) * 1000:,}"])
    save_gt(name, 1, rows)
    img = draw_table_image(rows, size=19, pad=11, header_fill=(33, 115, 70),
                           grid=(190, 190, 190), zebra=None,
                           right_cols=(1, 2, 3, 4), margin=20)
    img.save(os.path.join(DOCS, name + ".jpg"), quality=82)
    register(name, "Image (screenshot)", "Spreadsheet-style screenshot saved as JPEG")


def d16():
    name = "16_phone_photo_receipt_table"
    rows = [["Item", "Qty", "Rate", "Amount"]]
    for it in random.sample(["Basmati Rice 5kg", "Cooking Oil 3L", "Sugar 2kg",
                             "Tea Leaves 950g", "Milk Pack 1L", "Eggs (dozen)",
                             "Flour 10kg"], 6):
        q = random.randint(1, 4)
        r = random.randint(120, 2400)
        rows.append([it, str(q), f"{r:,}", f"{q * r:,}"])
    save_gt(name, 1, rows)
    tab = draw_table_image(rows, size=30, pad=16, header_fill=(215, 215, 215),
                           header_text=(20, 20, 20), grid=(70, 70, 70),
                           right_cols=(1, 2, 3), margin=40,
                           title="Al-Fatah Mart - Bill", subtitle="Counter 3  |  18/04/2026")
    tab = paper_noise(tab, 6, 40, tint=(252, 250, 244))
    # desk background + perspective + shadow + blur, like a phone photo
    W, H = tab.width + 500, tab.height + 450
    bg = Image.new("RGB", (W, H), (96, 78, 62))
    bgarr = np.array(bg).astype(np.float32)
    bgarr += np.random.normal(0, 9, bgarr.shape[:2])[..., None]
    bg = Image.fromarray(np.clip(bgarr, 0, 255).astype(np.uint8))
    tab = tab.rotate(3.2, expand=True, resample=Image.BICUBIC,
                     fillcolor=(96, 78, 62))
    bg.paste(tab, ((W - tab.width) // 2, (H - tab.height) // 2))
    arr = np.array(bg).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    light = 1.08 - 0.42 * (xx / W) - 0.10 * (yy / H)   # uneven lighting
    arr *= light[..., None]
    bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    bg = bg.transform(bg.size, Image.PERSPECTIVE,
                      (1, 0.03, 0, 0.02, 1, 0, 0.00004, 0.00002),
                      resample=Image.BICUBIC, fillcolor=(80, 64, 50))
    bg = bg.filter(ImageFilter.GaussianBlur(1.1))
    bg.save(os.path.join(DOCS, name + ".jpg"), quality=55)
    register(name, "Phone photo", "Tilted, perspective-skewed, uneven light, blurred, JPEG q55")


def main():
    for fn in [d01, d02, d03, d04, d05, d06, d07, d08, d09, d10, d11,
               d12, d13, d14, d15, d16]:
        fn()
    with open(os.path.join(ROOT, "manifest.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["document", "category", "description"])
        w.writerows(MANIFEST)
    print(f"Generated {len(MANIFEST)} documents in {DOCS}")


if __name__ == "__main__":
    main()
