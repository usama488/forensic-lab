"""Court-style PDF reports: case report with chain of custody, and DNA statistical report."""
from __future__ import annotations

import datetime as dt
import io
import json

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY, GOLD = colors.HexColor("#0B1F3A"), colors.HexColor("#C9A227")
SS = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=SS["Heading1"], fontSize=16, textColor=NAVY, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=SS["Heading2"], fontSize=11.5, textColor=NAVY, spaceBefore=8, spaceAfter=4)
B = ParagraphStyle("b", parent=SS["BodyText"], fontSize=9, leading=12)
S = ParagraphStyle("s", parent=B, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#555555"))
C = ParagraphStyle("c", parent=B, fontSize=7.5, leading=9)
CH = ParagraphStyle("ch", parent=C, textColor=colors.white, fontName="Helvetica-Bold")


def _tab(df_or_rows, widths):
    rows = df_or_rows if isinstance(df_or_rows, list) else [list(df_or_rows.columns)] + df_or_rows.astype(str).values.tolist()
    rows = [[Paragraph(str(h), CH) for h in rows[0]]] + [[Paragraph(str(c), C) for c in r] for r in rows[1:]]
    t = Table(rows, colWidths=widths, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#BBBBBB")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i in range(2, len(rows), 2):
        st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F2F5F9")))
    t.setStyle(TableStyle(st))
    return t


def _doc(title):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=15 * mm, title=title)

    def footer(c, d):
        c.saveState()
        c.setStrokeColor(GOLD)
        c.line(14 * mm, 12 * mm, A4[0] - 14 * mm, 12 * mm)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawString(14 * mm, 8 * mm, f"{title} · generated {dt.datetime.now():%Y-%m-%d %H:%M} · page {d.page}")
        c.restoreState()
    return buf, doc, footer


def case_report(case: dict, ev: pd.DataFrame, custody: dict, chain_ok: dict, results: pd.DataFrame, lab: str) -> bytes:
    buf, doc, footer = _doc(f"Case report {case['case_id']}")
    el = [Paragraph(lab, H1), Paragraph(f"<b>Case report — {case['case_id']}</b>", B), Spacer(1, 4)]
    info = [["Title", case["title"], "Status", case["status"]], ["Agency", case["agency"], "Priority", case["priority"]],
            ["Offence", case["offence"], "Section", case["section"]], ["Opened", case["opened"], "Due", case.get("due") or ""],
            ["Investigator", case["investigator"], "Analyst", case["analyst"]]]
    t = Table(info, colWidths=[28 * mm, 66 * mm, 24 * mm, 64 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), .25, colors.grey),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F5F9")), ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F2F5F9"))]))
    el += [t, Paragraph("Circumstances", H2), Paragraph(case.get("description") or "-", B), Paragraph("Evidence register", H2)]
    el.append(_tab(ev[["item_id", "description", "type", "collected_by", "collected_at", "status"]], [34 * mm, 44 * mm, 32 * mm, 26 * mm, 22 * mm, 24 * mm]))
    el.append(Paragraph("Results", H2))
    if len(results):
        el.append(_tab(results[["ts", "item_id", "section", "summary", "analyst"]], [24 * mm, 32 * mm, 26 * mm, 76 * mm, 24 * mm]))
    else:
        el.append(Paragraph("No results recorded yet.", B))
    el.append(Paragraph("Chain of custody", H2))
    for item, cdf in custody.items():
        ok = chain_ok[item]
        el.append(Paragraph(f"<b>{item}</b> — integrity check: " + ("<font color='#1E7B45'>INTACT (all SHA-256 links verified)</font>" if ok
                            else "<font color='#B42318'>BROKEN - log altered after entry</font>"), B))
        el.append(_tab(cdf[["ts", "action", "from_person", "to_person", "location", "notes"]].assign(hash=cdf.entry_hash.str[:12]),
                       [26 * mm, 26 * mm, 26 * mm, 26 * mm, 26 * mm, 30 * mm, 22 * mm]))
        el.append(Spacer(1, 4))
    el.append(Paragraph("Each custody entry stores the SHA-256 hash of its contents plus the previous entry's hash, so any later edit "
                        "breaks the chain and is detected.", S))
    el.append(Spacer(1, 14))
    el.append(Paragraph("Reporting scientist: ______________________ &nbsp;&nbsp; Reviewer: ______________________ &nbsp;&nbsp; Date: ____________", B))
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def dna_report(title: str, case_ref: str, pop: str, method: str, theta: float, table: pd.DataFrame, statement: str, extra: dict, lab: str) -> bytes:
    buf, doc, footer = _doc(f"DNA report {case_ref}")
    el = [Paragraph(lab, H1), Paragraph(f"<b>{title}</b> — case reference {case_ref}", B), Spacer(1, 4),
          Paragraph("Conclusion", H2), Paragraph(statement, B), Paragraph("Statistical parameters", H2),
          Paragraph(f"Population database: <b>{pop}</b> (norSTR v2023, Department of Forensic Sciences, Oslo University Hospital). "
                    f"Method: <b>{method}</b>, θ (F<sub>ST</sub>) = {theta}. Minimum allele frequency applied to rare alleles.", B)]
    for k, v in extra.items():
        el.append(Paragraph(f"<b>{k}:</b> {v}", B))
    el.append(Paragraph("Locus-by-locus results", H2))
    cols = list(table.columns)
    w = 182 / len(cols)
    el.append(_tab(table.round(6) if hasattr(table, "round") else table, [w * mm] * len(cols)))
    el.append(Paragraph("Interpretation", H2))
    el.append(Paragraph("A likelihood ratio expresses how much more probable the DNA results are under one proposition than under the "
                        "alternative. It is <b>not</b> the probability that the person is the source or the father (avoid the "
                        "'prosecutor's fallacy'). Verbal equivalents follow the ENFSI guideline for evaluative reporting.", B))
    el.append(Paragraph("Educational software: results are not admissible evidence. Casework requires validated kits, laboratory "
                        "accreditation and an authorised reporting scientist.", S))
    el.append(Spacer(1, 12))
    el.append(Paragraph("Reporting scientist: ______________________ &nbsp;&nbsp; Date: ____________", B))
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
