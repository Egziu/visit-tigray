"""Unicode PDF fonts shared by reports and competition certificates."""
from pathlib import Path

from fpdf import FPDF

from app.core.errors import AppError

FONT_PATHS = (
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
ETHIOPIC_FONT = "/usr/share/fonts/truetype/noto/NotoSansEthiopic-Regular.ttf"


def set_body_font(doc: FPDF, size: int) -> None:
    font = next((path for path in FONT_PATHS if Path(path).is_file()), None)
    if font is None:
        raise AppError(503, "pdf_font_unavailable", "PDF export requires an installed Unicode font.")
    doc.add_font("Body", "", font)
    doc.set_font("Body", size=size)
    if Path(ETHIOPIC_FONT).is_file():
        doc.add_font("Ethiopic", "", ETHIOPIC_FONT)
        doc.set_fallback_fonts(["Ethiopic"])
