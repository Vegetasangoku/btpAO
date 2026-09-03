"""
Test suite pour le triage de coût OCR (03/09) : pdfplumber d'abord (gratuit) sur
TOUT le document, Azure Document Intelligence seulement pour les pages à faible
rendement textuel -- et seulement si une clé Azure est configurée. Sans ce test,
une régression accidentelle (ex: appel Azure systématique réintroduit) ne serait
détectée qu'à la facture Azure du client, pas avant.
"""
import io

import pytest
from app.services.ocr_service import OCRService, LOW_TEXT_YIELD_CHARS_PER_PAGE


def _make_pdf_bytes(pages_text):
    """Construit un PDF minimal en mémoire avec une page par chaîne de `pages_text`."""
    pypdf = pytest.importorskip("pypdf")
    from reportlab.pdfgen import canvas  # type: ignore
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for text in pages_text:
        if text:
            c.drawString(72, 720, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_no_azure_call_when_no_endpoint_configured():
    """Sans clé Azure configurée, le document natif est traité intégralement en
    local (pages_azure == 0), quel que soit son contenu -- comportement déjà
    garanti par ocr_service avant ce correctif, doit rester vrai après."""
    ocr = OCRService()
    ocr.endpoint = None
    ocr.api_key = None

    pdf_bytes = _make_pdf_bytes(["Article 3.2 - Moyens humains et matériels du chantier " * 5])
    result = ocr.extract_text_and_tables(pdf_bytes, "cctp_natif.pdf")

    assert result["ocr_stats"]["pages_azure"] == 0
    assert result["provider"] == "local_pdf_parser"
    assert "Moyens humains" in result["full_text"]


def test_azure_never_called_for_fully_native_pdf_even_if_configured(monkeypatch):
    """Coeur du correctif de coût (03/09) : un document 100% natif ne doit JAMAIS
    déclencher d'appel Azure, même si une clé est configurée -- c'est ce qui fait
    tomber le coût OCR à zéro sur l'immense majorité des CCTP/RC français."""
    ocr = OCRService()
    ocr.endpoint = "https://fake-resource.cognitiveservices.azure.com/"
    ocr.api_key = "fake-key"

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Azure Document Intelligence ne doit jamais être appelé pour un PDF 100% natif.")

    monkeypatch.setattr(ocr, "_parse_with_azure", _fail_if_called)

    pdf_bytes = _make_pdf_bytes(["Contenu numérique natif suffisamment long pour dépasser le seuil de rendement. " * 3] * 3)
    result = ocr.extract_text_and_tables(pdf_bytes, "cctp_natif_3p.pdf")

    assert result["ocr_stats"]["pages_azure"] == 0
    assert result["ocr_stats"]["pages_total"] == 3


def test_weak_pages_escalated_to_azure_only(monkeypatch):
    """Un document mixte (pages natives + pages quasi vides, probable scan) ne doit
    escalader vers Azure QUE les pages faibles -- jamais le document entier."""
    ocr = OCRService()
    ocr.endpoint = "https://fake-resource.cognitiveservices.azure.com/"
    ocr.api_key = "fake-key"

    calls = []

    def _fake_parse_weak_pages(pdf_bytes, page_numbers):
        calls.append(list(page_numbers))
        return [{"page_number": pn, "text": f"Texte Azure reconstruit page {pn}", "tables": []} for pn in page_numbers]

    monkeypatch.setattr(ocr, "_parse_weak_pages_with_azure", _fake_parse_weak_pages)

    # 3 pages : 2 avec du texte natif suffisant, 1 quasi vide (scan probable)
    pdf_bytes = _make_pdf_bytes([
        "Article 1 - Contenu numérique natif suffisant pour ce test de non-escalade. " * 3,
        "",
        "Article 3 - Autre contenu numérique natif suffisant pour ce test également. " * 3,
    ])
    result = ocr.extract_text_and_tables(pdf_bytes, "cctp_mixte.pdf")

    assert calls, "Azure aurait dû être appelé pour la page faible"
    assert calls[0] == [2], f"Seule la page 2 (faible rendement) doit être escaladée, reçu: {calls[0]}"
    assert result["ocr_stats"]["pages_azure"] == 1
    assert result["ocr_stats"]["pages_total"] == 3
    assert "Texte Azure reconstruit page 2" in result["full_text"]
