"""
Semantic Document Chunker for BTP Tender Documents (RC, CCTP, CCAP)
"""
import re
from typing import Any, Dict, List


class ChunkingService:
    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Splits extracted pages into semantic chunks while maintaining page number,
        article titles, and contextual metadata.
        """
        chunks = []
        chunk_index = 0

        for page in pages:
            page_num = page.get("page_number", 1)
            text = page.get("text", "").strip()
            if not text:
                continue

            # Identify BTP headers (e.g., "Article 3.2 -", "Chapitre 1 :", "1.1 Moyens")
            paragraphs = re.split(r'\n{2,}', text)
            current_section_title = f"Page {page_num}"

            current_chunk_text = ""
            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    continue

                # Check if paragraph looks like a section header
                if len(p_clean) < 120 and any(p_clean.lower().startswith(kw) for kw in ["article", "chapitre", "lot", "section", "critère", "1.", "2.", "3.", "4.", "5."]):
                    current_section_title = p_clean

                if len(current_chunk_text) + len(p_clean) < self.chunk_size:
                    current_chunk_text += ("\n\n" + p_clean if current_chunk_text else p_clean)
                else:
                    if current_chunk_text:
                        chunks.append({
                            "chunk_index": chunk_index,
                            "page_number": page_num,
                            "section_title": current_section_title,
                            "content": current_chunk_text,
                            "metadata_json": {
                                "page": page_num,
                                "char_count": len(current_chunk_text),
                                "section": current_section_title,
                            }
                        })
                        chunk_index += 1
                    current_chunk_text = p_clean

            if current_chunk_text:
                chunks.append({
                    "chunk_index": chunk_index,
                    "page_number": page_num,
                    "section_title": current_section_title,
                    "content": current_chunk_text,
                    "metadata_json": {
                        "page": page_num,
                        "char_count": len(current_chunk_text),
                        "section": current_section_title,
                    }
                })
                chunk_index += 1

        return chunks


chunking_service = ChunkingService()
