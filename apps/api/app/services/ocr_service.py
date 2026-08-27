"""
OCR & Document Parsing Service
Integrates Azure Document Intelligence with graceful fallback to pdfplumber / pypdf.
"""
import io
import os
import re
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings


class OCRService:
    def __init__(self):
        self.endpoint = settings.AZURE_DOC_INTELLIGENCE_ENDPOINT
        self.api_key = settings.AZURE_DOC_INTELLIGENCE_KEY

    def extract_text_and_tables(self, pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extracts structured text, tables, and page metadata from PDF file.
        Uses Azure Document Intelligence if configured, otherwise falls back to pdfplumber.
        """
        # 1. Try Azure Document Intelligence if credentials are provided
        if self.endpoint and self.api_key:
            try:
                return self._parse_with_azure(pdf_bytes)
            except Exception as e:
                print(f"[OCRService] Azure Document Intelligence failed, falling back to local: {e}")

        # 2. Local fallback using pdfplumber / pypdf
        return self._parse_with_pdfplumber(pdf_bytes, filename)

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
        if not full_text:
            raise RuntimeError(
                f"Échec d'extraction OCR : aucun contenu textuel n'a pu être extrait du document '{filename}'."
            )

        return {
            "provider": "local_pdf_parser",
            "full_text": full_text,
            "pages": pages_data,
        }



ocr_service = OCRService()
