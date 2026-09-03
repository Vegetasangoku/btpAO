"""
OCR & Document Parsing Service
Integrates Azure Document Intelligence with graceful fallback to pdfplumber / pypdf.

Triage cout (03/09) : la quasi-totalite des CCTP/RC/CCAP de marches publics francais
sont des PDF numeriques natifs (texte selectionnable), pas des scans. Avant ce
correctif, tout document etait envoye INTEGRALEMENT a Azure Document Intelligence des
qu'une cle etait configuree -- meme un dossier de 500 pages 100% natif -- ce qui facture
Azure page par page pour du contenu que pdfplumber (gratuit, local) sait deja lire
parfaitement. Le pipeline devient desormais : pdfplumber d'abord sur TOUT le document
(gratuit), puis seules les pages a faible rendement textuel (probablement scannees /
images) sont extraites dans un mini-PDF et envoyees a Azure. Sur un dossier natif a
100%, le cout Azure tombe a zero. `ocr_stats` (pages_total/pages_local/pages_azure) est
retourne pour que l'appelant (app/workers/tasks.py) puisse journaliser le cout OCR reel
via app/services/ocr_cost_service.py.
"""
import io
import os
import re
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

# En-dessous de ce nombre de caracteres utiles extraits par pdfplumber, une page est
# consideree comme probablement scannee/image et eligible a l'escalade Azure. Valeur
# empirique : une page de CCTP/RC meme tres courte (ex. page de garde, tableau synthetique)
# depasse largement ce seuil des qu'elle contient du texte numerique reel.
LOW_TEXT_YIELD_CHARS_PER_PAGE = 40

# Nombre max de pages "faibles" envoyees a Azure en une seule fois (securite mémoire/
# latence sur des documents massivement scannes) -- au-dela, le reste reste en texte
# local partiel plutot que de bloquer indefiniment sur un seul document.
MAX_AZURE_ESCALATION_PAGES = 400


class OCRService:
    def __init__(self):
        self.endpoint = settings.AZURE_DOC_INTELLIGENCE_ENDPOINT
        self.api_key = settings.AZURE_DOC_INTELLIGENCE_KEY

    def extract_text_and_tables(self, pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extracts structured text, tables, and page metadata from PDF file.

        Triage local -> Azure (03/09) : pdfplumber/pypdf lit TOUJOURS le document en
        premier (gratuit). Seules les pages dont le rendement textuel est trop faible
        (probable scan/image) sont ensuite re-analysees par Azure Document Intelligence,
        si configure. Retourne "ocr_stats" (pages_total/pages_local/pages_azure) pour
        journalisation du cout reel par l'appelant.
        """
        local_result = self._parse_with_pdfplumber(pdf_bytes, filename)
        local_pages: List[Dict[str, Any]] = local_result.get("pages", [])

        weak_page_numbers = [
            p.get("page_number")
            for p in local_pages
            if len((p.get("text") or "").strip()) < LOW_TEXT_YIELD_CHARS_PER_PAGE
        ]
        weak_page_numbers = [pn for pn in weak_page_numbers if pn is not None][:MAX_AZURE_ESCALATION_PAGES]

        pages_azure_used = 0
        provider = "local_pdf_parser"

        if weak_page_numbers and self.endpoint and self.api_key:
            try:
                azure_pages = self._parse_weak_pages_with_azure(pdf_bytes, weak_page_numbers)
                page_index_by_number = {p.get("page_number"): idx for idx, p in enumerate(local_pages)}
                for pg in azure_pages:
                    idx = page_index_by_number.get(pg["page_number"])
                    if idx is not None and pg.get("text"):
                        local_pages[idx]["text"] = pg["text"]
                        if pg.get("tables"):
                            local_pages[idx]["tables"] = pg["tables"]
                        pages_azure_used += 1
                if pages_azure_used:
                    provider = "hybrid_local_azure"
            except Exception as e:
                print(f"[OCRService] Azure Document Intelligence escalation notice (kept local text for weak pages): {e}")

        full_text = "\n\n".join(p.get("text", "") for p in local_pages).strip()
        if not full_text:
            raise RuntimeError(
                f"Échec d'extraction OCR : aucun contenu textuel n'a pu être extrait du document '{filename}'."
            )

        return {
            "provider": provider,
            "full_text": full_text,
            "pages": local_pages,
            "ocr_stats": {
                "pages_total": len(local_pages),
                "pages_azure": pages_azure_used,
                "pages_local": max(len(local_pages) - pages_azure_used, 0),
            },
        }

    def _parse_weak_pages_with_azure(self, pdf_bytes: bytes, page_numbers: List[int]) -> List[Dict[str, Any]]:
        """
        Extrait UNIQUEMENT les pages listees (1-indexees) dans un mini-PDF via pypdf,
        puis envoie ce mini-PDF (et non le document complet) a Azure Document
        Intelligence -- c'est ce qui rend le triage rentable : le cout Azure est
        proportionnel aux seules pages reellement suspectees d'etre scannees.
        """
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        writer = pypdf.PdfWriter()
        ordered_page_numbers: List[int] = []
        for pn in page_numbers:
            idx = pn - 1
            if 0 <= idx < len(reader.pages):
                writer.add_page(reader.pages[idx])
                ordered_page_numbers.append(pn)

        if not ordered_page_numbers:
            return []

        mini_buf = io.BytesIO()
        writer.write(mini_buf)
        mini_pdf_bytes = mini_buf.getvalue()

        azure_result = self._parse_with_azure(mini_pdf_bytes)
        azure_pages_raw = azure_result.get("pages", [])

        remapped: List[Dict[str, Any]] = []
        for i, pg in enumerate(azure_pages_raw):
            if i < len(ordered_page_numbers):
                remapped.append({
                    "page_number": ordered_page_numbers[i],
                    "text": pg.get("text", ""),
                    "tables": pg.get("tables", []),
                })
        return remapped

    def _parse_with_azure(self, pdf_bytes: bytes) -> Dict[str, Any]:
        url = f"{self.endpoint.rstrip('/')}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2023-07-31"
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/pdf"
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, content=pdf_bytes)
            response.raise_for_status()
            operation_url = response.headers.get("Operation-Location")

            # Poll for results
            if not operation_url:
                raise ValueError("No Operation-Location returned by Azure Document Intelligence")

            for _ in range(30):
                import time
                time.sleep(1)
                poll_resp = client.get(operation_url, headers={"Ocp-Apim-Subscription-Key": self.api_key})
                result = poll_resp.json()
                if result.get("status") == "succeeded":
                    analyze_result = result.get("analyzeResult", {})
                    pages_data = []
                    for page in analyze_result.get("pages", []):
                        page_num = page.get("pageNumber", 1)
                        lines = [line.get("content", "") for line in page.get("lines", [])]
                        pages_data.append({
                            "page_number": page_num,
                            "text": "\n".join(lines),
                            "tables": []
                        })
                    return {
                        "provider": "azure_doc_intelligence",
                        "full_text": analyze_result.get("content", ""),
                        "pages": pages_data,
                    }
                elif result.get("status") == "failed":
                    raise RuntimeError("Azure OCR analysis failed")

        raise TimeoutError("Azure OCR polling timed out")

    def _parse_with_pdfplumber(self, pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
        pages_data = []
        full_text_list = []

        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    tables = page.extract_tables() or []
                    pages_data.append({
                        "page_number": idx,
                        "text": text,
                        "tables": tables,
                    })
                    full_text_list.append(text)
        except Exception as e_pdfplumber:
            # Secondary fallback with pypdf
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                for idx, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    pages_data.append({
                        "page_number": idx,
                        "text": text,
                        "tables": [],
                    })
                    full_text_list.append(text)
            except Exception as e_pypdf:
                raise RuntimeError(
                    f"Échec d'extraction OCR : le document '{filename}' est illisible ou corrompu "
                    f"(pdfplumber: {e_pdfplumber}, pypdf: {e_pypdf})"
                )

        full_text = "\n\n".join(full_text_list).strip()
        if not full_text and not pages_data:
            raise RuntimeError(
                f"Échec d'extraction OCR : aucun contenu textuel n'a pu être extrait du document '{filename}'."
            )

        return {
            "provider": "local_pdf_parser",
            "full_text": full_text,
            "pages": pages_data,
        }


ocr_service = OCRService()
