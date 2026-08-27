"""
Test suite ensuring ZERO fabrication when OCR / parsing fails.
Verifies:
1. When unparseable / corrupted bytes are sent to OCRService, it raises a clean RuntimeError.
2. It NEVER generates fake placeholder sentences like "Contenu extrait du document BTP...".
"""
import pytest
from app.services.ocr_service import OCRService


def test_ocr_raises_runtime_error_on_corrupt_pdf():
    ocr = OCRService()
    corrupt_bytes = b"CORRUPTED_NON_PDF_BINARY_DATA_12345"
    
    with pytest.raises(RuntimeError) as exc_info:
        ocr.extract_text_and_tables(corrupt_bytes, filename="damaged_cctp.pdf")
    
    err_str = str(exc_info.value)
    assert "Échec d'extraction OCR" in err_str or "illisible" in err_str
    # Anti-hallucination assertion: ensure no mock/dummy text is returned
    assert "gros oeuvre" not in err_str
    assert "délai 6 mois" not in err_str


def test_ocr_raises_runtime_error_on_empty_pdf():
    ocr = OCRService()
    # Empty bytes
    with pytest.raises(RuntimeError) as exc_info:
        ocr.extract_text_and_tables(b"", filename="empty.pdf")
    
    err_str = str(exc_info.value)
    assert "Échec d'extraction OCR" in err_str
