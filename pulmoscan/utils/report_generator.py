# pulmoscan/utils/report_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
from datetime import datetime
from pathlib import Path
import io
import os
import uuid

# Register a fallback font (system dependent). If you have a nicer ttf in project, use that.
try:
    pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
    DEFAULT_FONT = "DejaVu"
except Exception:
    DEFAULT_FONT = "Helvetica"

PAGE_WIDTH, PAGE_HEIGHT = A4

# small helper to add a horizontal rule
class HR(Flowable):
    def __init__(self, width="100%", thickness=1, color=colors.gray):
        Flowable.__init__(self)
        self.width = width
        self.thickness = thickness
        self.color = color

    def wrap(self, availWidth, availHeight):
        if self.width == "100%":
            self.width = availWidth
        return self.width, self.thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


def _pil_image_to_temp(path_or_pil, max_width_mm=140):
    """
    Accept a PIL.Image or a path string; return an in-memory JPEG bytes buffer
    scaled to fit width (keeping aspect ratio).
    """
    if isinstance(path_or_pil, str) or isinstance(path_or_pil, Path):
        img = PILImage.open(str(path_or_pil)).convert("RGB")
    else:
        img = path_or_pil.convert("RGB")

    # convert max width in pixels using 72dpi (reportlab default 72 points/inch)
    max_width_px = int(max_width_mm * (72.0 / 25.4))  # mm->inches->points
    w, h = img.size
    if w > max_width_px:
        new_h = int((max_width_px / w) * h)
        img = img.resize((max_width_px, new_h), PILImage.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf


def generate_pdf_report(
    out_path: str,
    *,
    original_image_path: str = None,
    heatmap_image_path: str = None,
    report_id: str = None,
    patient_name: str = None,
    patient_id: str = None,
    prediction: str,
    raw_label: str,
    confidence_str: str,
    probability: float,
    severity_score: float = None,
    severity_category: str = None,
    precautionary_advice: dict = None,
    model_used: str = None,
    notes: str = None,
    timestamp: str = None
):
    """
    Generate a professionally formatted PDF report and save it to out_path.
    Returns the path written (out_path).
    """

    out_dir = Path(out_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if report_id is None:
        report_id = uuid.uuid4().hex[:12]

    if timestamp is None:
        timestamp = datetime.now().isoformat()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm
    )

    # Styles
    h_style = ParagraphStyle(
        "heading",
        fontName=DEFAULT_FONT,
        fontSize=18,
        leading=22,
        spaceAfter=6,
        textColor=colors.HexColor("#3a3a4d")
    )
    sub_h = ParagraphStyle(
        "subheading",
        fontName=DEFAULT_FONT,
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#555")
    )
    normal = ParagraphStyle(
        "normal",
        fontName=DEFAULT_FONT,
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#222")
    )
    small = ParagraphStyle(
        "small",
        fontName=DEFAULT_FONT,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#666")
    )

    elems = []

    # Header
    elems.append(Paragraph("PulmoScan AI — Chest X-Ray Analysis Report", h_style))
    meta_table_data = [
        ["Report ID:", report_id, "Generated:", timestamp],
    ]
    if patient_name or patient_id:
        meta_table_data.append(["Patient:", patient_name or "-", "Patient ID:", patient_id or "-"])
    if model_used:
        meta_table_data.append(["Model:", model_used, "", ""])

    meta_table = Table(meta_table_data, colWidths=[30 * mm, 70 * mm, 30 * mm, 50 * mm])
    meta_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#444")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
    ]))
    elems.append(meta_table)
    elems.append(Spacer(1, 6))

    elems.append(HR(thickness=1, color=colors.HexColor("#e6e6ee")))
    elems.append(Spacer(1, 8))

    # Results summary box (table)
    summary_data = [
        ["Prediction", prediction],
        ["Label", raw_label],
        ["Confidence", confidence_str],
        ["Probability", f"{probability:.4f}"],
    ]
    if severity_score is not None:
        summary_data.append(["Severity", f"{severity_category} ({severity_score:.3f})"])

    summary_tbl = Table(summary_data, colWidths=[40 * mm, 120 * mm], hAlign="LEFT")
    summary_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f7fb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7d7e3")),
        ("FONT", (0, 0), (-1, -1), DEFAULT_FONT, 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#ededf3")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(summary_tbl)
    elems.append(Spacer(1, 10))

    # Images side-by-side if present
    images_row = []
    imgs_present = 0
    max_width_mm = 75  # each image max width

    if original_image_path and Path(original_image_path).exists():
        buf = _pil_image_to_temp(original_image_path, max_width_mm=max_width_mm)
        img = Image(buf, width=None, height=None)
        images_row.append(img)
        imgs_present += 1

    if heatmap_image_path and Path(heatmap_image_path).exists():
        buf2 = _pil_image_to_temp(heatmap_image_path, max_width_mm=max_width_mm)
        img2 = Image(buf2, width=None, height=None)
        images_row.append(img2)
        imgs_present += 1

    if imgs_present:
        # arrange them in a small table to control alignment
        img_table = Table([images_row], colWidths=[(PAGE_WIDTH - 40 * mm) / imgs_present] * imgs_present)
        img_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        elems.append(img_table)
        elems.append(Spacer(1, 8))

    # Precautionary advice
    elems.append(Paragraph("Precautionary Advice", sub_h))
    if precautionary_advice:
        elems.append(Paragraph(precautionary_advice.get("recommendation", ""), normal))
        elems.append(Spacer(1, 6))
        precautions = precautionary_advice.get("precautions") or precautionary_advice.get("medicines") or []
        if precautions:
            list_items = "".join([f"• {p}<br/>" for p in precautions])
            elems.append(Paragraph(list_items, normal))
    else:
        elems.append(Paragraph("No precautionary information available.", normal))
    elems.append(Spacer(1, 12))

    # Notes
    if notes:
        elems.append(Paragraph("Notes", sub_h))
        elems.append(Paragraph(notes, normal))
        elems.append(Spacer(1, 8))

    # Footer disclaimer
    elems.append(HR(thickness=0.5, color=colors.HexColor("#e6e6ee")))
    elems.append(Spacer(1, 6))
    disclaimer = ("<b>Medical Disclaimer:</b> This AI-assisted tool is intended for educational and research purposes only. "
                  "It should not replace professional medical diagnosis or treatment. Always consult a qualified healthcare provider.")
    elems.append(Paragraph(disclaimer, small))

    # Build PDF
    doc.build(elems)

    return str(out_path)
