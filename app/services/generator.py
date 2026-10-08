"""Build one PDF certificate with ReportLab.

Single predefined template, landscape A4. Raises on failure so the
caller (processor) can mark that row failed without stopping the job.
"""
import logging
import os
import tempfile
from pathlib import Path

from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Font names used inside the PDF. Fall back to Helvetica if files are missing.
NAME_FONT = "Helvetica"
BODY_FONT = "Helvetica"
TITLE_FONT = "Helvetica-Bold"
_DEV_FONT = "NotoSansDevanagari"


def _register_fonts() -> None:
    """Register bundled TTFs once; stay silent-safe if a file is absent."""
    global NAME_FONT, BODY_FONT, TITLE_FONT
    try:
        regular = FONT_DIR / "NotoSans-Regular.ttf"
        bold = FONT_DIR / "NotoSans-Bold.ttf"
        dev = FONT_DIR / "NotoSansDevanagari-Regular.ttf"
        if regular.exists():
            pdfmetrics.registerFont(TTFont("NotoSans", str(regular)))
            NAME_FONT = "NotoSans"
            BODY_FONT = "NotoSans"
        if bold.exists():
            pdfmetrics.registerFont(TTFont("NotoSans-Bold", str(bold)))
            TITLE_FONT = "NotoSans-Bold"
        if dev.exists():
            pdfmetrics.registerFont(TTFont(_DEV_FONT, str(dev)))
    except Exception:
        logger.warning("font registration failed, using Helvetica", exc_info=True)
        NAME_FONT = "Helvetica"
        BODY_FONT = "Helvetica"
        TITLE_FONT = "Helvetica-Bold"


_register_fonts()


def _name_font_for(name: str) -> str:
    # Devanagari names need the Devanagari font; everything else uses NotoSans.
    if any("\u0900" <= ch <= "\u097f" for ch in name):
        try:
            pdfmetrics.getFont(_DEV_FONT)
            return _DEV_FONT
        except KeyError:
            pass
    return NAME_FONT


def generate_certificate(
    recipient_name: str,
    title: str,
    issued_date: str,
    issuer: str | None,
    output_path: str | Path,
) -> str:
    """Create one PDF at output_path (atomic write). Returns the final path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    width, height = landscape(A4)
    name_font = _name_font_for(recipient_name)

    # Write to a temp file first, then rename: a crash never leaves a
    # half-written PDF that looks like a success.
    fd, tmp_name = tempfile.mkstemp(suffix=".tmp", dir=str(output_path.parent))
    os.close(fd)
    try:
        c = canvas.Canvas(tmp_name, pagesize=landscape(A4))

        # Double border.
        c.setStrokeColorRGB(0.13, 0.23, 0.38)
        c.setLineWidth(3)
        c.rect(20, 20, width - 40, height - 40)
        c.setLineWidth(1)
        c.rect(30, 30, width - 60, height - 60)

        # Heading.
        c.setFont(TITLE_FONT, 28)
        c.drawCentredString(width / 2, height - 110, "Certificate of Completion")
        c.setFont(BODY_FONT, 14)
        c.drawCentredString(width / 2, height - 140, "This is to certify that")

        # Recipient name, shrinking until it fits.
        size = 36
        max_width = width - 160
        while size > 12 and pdfmetrics.stringWidth(recipient_name, name_font, size) > max_width:
            size -= 2
        c.setFont(name_font, size)
        c.drawCentredString(width / 2, height - 190, recipient_name)

        c.setFont(BODY_FONT, 14)
        c.drawCentredString(width / 2, height - 220, "has successfully completed")
        c.setFont(TITLE_FONT, 20)
        c.drawCentredString(width / 2, height - 255, title)

        # Footer: date left, issuer right with a signature line.
        c.setFont(BODY_FONT, 12)
        c.drawString(60, 60, f"Issued: {issued_date}")
        if issuer:
            c.drawRightString(width - 60, 60, issuer)
            c.line(width - 210, 75, width - 60, 75)

        c.showPage()
        c.save()
    except Exception:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise

    os.replace(tmp_name, output_path)
    return str(output_path)
