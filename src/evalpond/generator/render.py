"""Document model plus text and PDF renderers. Every page is watermarked as synthetic."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportlab import rl_config

rl_config.invariant = 1  # deterministic PDF bytes for a given input

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

WATERMARK = "SYNTHETIC - NOT A REAL DOCUMENT"
SYNTH_FLAG = "evalpond-synthetic: true"


@dataclass
class Block:
    kind: str  # "kv" or "table"
    heading: str = ""
    rows: list = field(default_factory=list)  # kv: [(label, value)]; table: [header] + rows


@dataclass
class Doc:
    title: str
    subtitle: str = ""
    blocks: list[Block] = field(default_factory=list)


@dataclass
class Style:
    font: str = "Helvetica"
    size: int = 9
    kv_columns: int = 1
    table_style: str = "grid"  # grid | zebra | lines
    accent: str = "#2b4c7e"
    title_align: int = 0  # 0 left, 1 center
    compact: bool = False


def to_text(doc: Doc) -> str:
    """Plain-text layer, like OCR output. Same content as the PDF."""
    out = [f"*** {WATERMARK} ***", doc.title.upper()]
    if doc.subtitle:
        out.append(doc.subtitle)
    out.append("")
    for b in doc.blocks:
        if b.heading:
            out.append(b.heading.upper())
        if b.kind == "kv":
            for label, value in b.rows:
                out.append(f"{label}: {value}")
        else:
            header, *rows = b.rows
            widths = [max(len(str(r[i])) for r in b.rows) for i in range(len(header))]
            for r in [header, *rows]:
                out.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)).rstrip())
        out.append("")
    out.append(f"*** {WATERMARK} ***")
    return "\n".join(out) + "\n"


def _watermark(canvas, doc_):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 38)
    canvas.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.16))
    canvas.translate(letter[0] / 2, letter[1] / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, "SYNTHETIC")
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawCentredString(0, -30, WATERMARK)
    canvas.restoreState()
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.Color(0.7, 0.1, 0.1))
    canvas.drawCentredString(letter[0] / 2, 22, f"{WATERMARK}  |  generated test data")
    canvas.restoreState()


def to_pdf(doc: Doc, style: Style, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    accent = colors.HexColor(style.accent)
    base = ParagraphStyle("b", fontName=style.font, fontSize=style.size, leading=style.size + 3)
    h1 = ParagraphStyle("h1", parent=base, fontName=style.font + "-Bold", fontSize=style.size + 7,
                        leading=style.size + 12, textColor=accent, alignment=style.title_align, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=base, fontName=style.font + "-Bold", fontSize=style.size + 1,
                        textColor=accent, spaceBefore=4, spaceAfter=2)
    pdf = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=44, rightMargin=44, topMargin=40,
                            bottomMargin=44, title=f"{doc.title} (SYNTHETIC)",
                            subject=SYNTH_FLAG, keywords=SYNTH_FLAG, author="evalpond generator")
    flow = [Paragraph(doc.title, h1)]
    if doc.subtitle:
        flow.append(Paragraph(doc.subtitle, base))
    flow.append(Spacer(1, 6 if style.compact else 10))
    for b in doc.blocks:
        if b.heading:
            flow.append(Paragraph(b.heading, h2))
        if b.kind == "kv":
            rows = [[Paragraph(f"<b>{lab}</b>", base), Paragraph(str(val), base)] for lab, val in b.rows]
            if style.kv_columns == 2:
                half = (len(rows) + 1) // 2
                left, right = rows[:half], rows[half:]
                while len(right) < len(left):
                    right.append(["", ""])
                rows = [l + r for l, r in zip(left, right)]
                t = Table(rows, colWidths=[90, 140, 90, 140])
            else:
                t = Table(rows, colWidths=[150, 360])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
        else:
            data = [[Paragraph(str(c), base) for c in r] for r in b.rows]
            t = Table(data, repeatRows=1)
            cmds = [("FONTSIZE", (0, 0), (-1, -1), style.size), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf4"))]
            if style.table_style == "grid":
                cmds.append(("GRID", (0, 0), (-1, -1), 0.4, colors.grey))
            elif style.table_style == "zebra":
                for i in range(1, len(data), 2):
                    cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f5")))
            else:
                cmds.append(("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey))
            t.setStyle(TableStyle(cmds))
        flow += [t, Spacer(1, 6 if style.compact else 9)]
    pdf.build(flow, onFirstPage=_watermark, onLaterPages=_watermark)
