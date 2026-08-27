"""
Word (.docx) and PDF Document Exporter Engine
Uses docxtpl with Jinja2 templating, InlineImage injection for Gantt & Organigrammes,
and LibreOffice CLI for headless PDF conversion.
"""
import io
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docxtpl import DocxTemplate, InlineImage
from app.core.storage import storage_service
from app.services.gantt_service import gantt_service
from app.services.diagram_service import diagram_service


class ExporterService:
    def build_memo_docx(
        self,
        tenant_id: str,
        project_id: str,
        project_data: Dict[str, Any],
        sections: List[Dict[str, Any]],
        decision_form: Dict[str, Any],
        template_bytes: Optional[bytes] = None,
        include_visuals: bool = True,
        required_section_titles: Optional[List[str]] = None,
        gantt_tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Compiles all validated sections, metadata, Gantt planning, and organigramme into a Word .docx document.
        Uses the client's Word template (with their header/logo/footer) when provided.
        """
        # 1. Create a base document — use client template if available
        missing_sections: List[str] = []
        if template_bytes:
            try:
                doc = docx.Document(io.BytesIO(template_bytes))
                missing_sections = self._detect_missing_required_sections(template_bytes, required_section_titles)
                # Clear existing body content but preserve headers/footers
                for element in list(doc.element.body):
                    if element.tag.endswith('}sectPr'):
                        continue  # preserve section properties (margins, headers)
                    doc.element.body.remove(element)
                self._replace_company_placeholders(doc, project_data.get('company_name') or 'Votre Entreprise')
            except Exception as e:
                print(f"[ExporterService] Template load error, using blank: {e}")
                doc = docx.Document()
        else:
            doc = docx.Document()

        # Page margins
        for section in doc.sections:
            section.top_margin = Inches(0.8)
            section.bottom_margin = Inches(0.8)
            section.left_margin = Inches(0.8)
            section.right_margin = Inches(0.8)

        # 2. Cover Page Header
        p_header = doc.add_paragraph()
        r_logo = p_header.add_run(f"{project_data.get('company_name') or 'Votre Entreprise'}\n")
        r_logo.bold = True
        r_logo.font.size = Pt(16)
        r_logo.font.color.rgb = RGBColor(2, 132, 199)

        # Title
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph("\n" * 2)
        
        r_title_badge = p_title.add_run("RÉPONSE À L'APPEL D'OFFRES\n")
        r_title_badge.font.size = Pt(13)
        r_title_badge.font.color.rgb = RGBColor(100, 116, 139)
        r_title_badge.bold = True

        r_main_title = p_title.add_run(f"MÉMOIRE TECHNIQUE JUSTIFICATIF\n{project_data.get('title', 'Projet BTP').upper()}\n")
        r_main_title.font.size = Pt(22)
        r_main_title.bold = True
        r_main_title.font.color.rgb = RGBColor(15, 23, 42)

        p_ref = doc.add_paragraph()
        p_ref.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_ref = p_ref.add_run(f"Réf. Consultation : {project_data.get('reference_code', 'AO-2026')}\nMaître d'Ouvrage : {project_data.get('client_name', 'Client')}\nLot : {project_data.get('lot_number', 'Lot 01')}\n")
        r_ref.font.size = Pt(12)
        r_ref.font.color.rgb = RGBColor(51, 65, 85)

        doc.add_paragraph("\n" * 2)

        # Executive Summary Box Table
        summary_table = doc.add_table(rows=4, cols=2)
        summary_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        summary_table.style = 'Light Shading Accent 1' if 'Light Shading Accent 1' in [s.name for s in doc.styles] else 'Table Grid'

        rows_data = [
            ("Délai global d'exécution garanti :", f"{decision_form.get('delai_mois', 6)} mois"),
            ("Budget prévisionnel des travaux :", f"{project_data.get('budget_estimate', 3500000.0):,.2f} € HT"),
            ("Matériel lourd principal :", decision_form.get('materiel_principal', 'Grue Potain 50m')),
            ("Taux de valorisation déchets BTP :", "88% en filières locales agréées (<15 km)"),
        ]

        for idx, (label, val) in enumerate(rows_data):
            row = summary_table.rows[idx]
            c1 = row.cells[0].paragraphs[0].add_run(label)
            c1.bold = True
            row.cells[1].paragraphs[0].add_run(val)

        doc.add_page_break()

        # 3. Table of Contents & Sections
        p_toc = doc.add_heading("Sommaire du Mémoire Technique", level=1)
        p_toc.paragraph_format.space_after = Pt(14)

        for s in sections:
            p_toc_item = doc.add_paragraph(style='List Bullet')
            r_toc = p_toc_item.add_run(f"{s.get('title', 'Section')}")
            r_toc.font.size = Pt(11)

        if missing_sections:
            warn_p = doc.add_paragraph()
            warn_run = warn_p.add_run(
                "⚠️ Sections requises par l'appel d'offres, absentes de la structure du template "
                "client d'origine (ajoutées automatiquement ci-dessous, à vérifier) :"
            )
            warn_run.bold = True
            warn_run.font.size = Pt(9.5)
            warn_run.font.color.rgb = RGBColor(180, 83, 9)
            for missing_title in missing_sections:
                li = doc.add_paragraph(style='List Bullet')
                li_run = li.add_run(missing_title)
                li_run.font.size = Pt(9.5)
                li_run.font.color.rgb = RGBColor(180, 83, 9)

        doc.add_paragraph("\n")

        # 4. Generate Visuals if requested
        gantt_path = None
        organigramme_path = None
        gantt_error = None
        organigramme_error = None

        if include_visuals:
            try:
                if gantt_tasks:
                    # Real, possibly user-edited tasks from the interactive Gantt (Batch 11)
                    # take priority over the legacy static phase list, so what the user sees
                    # and edits on screen is what actually gets embedded in the Word export.
                    gantt_res = gantt_service.generate_gantt_chart_png_from_tasks(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        project_title=project_data.get("title", "Chantier BTP"),
                        tasks=gantt_tasks,
                    )
                else:
                    gantt_res = gantt_service.generate_gantt_chart_png(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        project_title=project_data.get("title", "Chantier BTP"),
                        phases=decision_form.get("phasage_travaux", [])
                    )
                gantt_bytes = storage_service.download_file(tenant_id, gantt_res["s3_key"])
                temp_gantt = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_gantt.write(gantt_bytes)
                temp_gantt.close()
                gantt_path = temp_gantt.name
            except Exception as e:
                print(f"[ExporterService] Gantt generation error: {e}")
                gantt_error = "Le planning previsionnel (Gantt) n'a pas pu etre genere automatiquement pour cet export."

            try:
                diag_res = diagram_service.generate_organigramme_png(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    project_title=project_data.get("title", "Chantier BTP"),
                    cadres=decision_form.get("equipe_cadres", [])
                )
                diag_bytes = storage_service.download_file(tenant_id, diag_res["s3_key"])
                temp_diag = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_diag.write(diag_bytes)
                temp_diag.close()
                organigramme_path = temp_diag.name
            except Exception as e:
                print(f"[ExporterService] Organigramme generation error: {e}")
                organigramme_error = "L'organigramme d'encadrement n'a pas pu etre genere automatiquement pour cet export."

        # 5. Render Each Section Body
        for s in sections:
            sec_key = s.get("section_key", "")
            title = s.get("title", "Section")
            html_content = s.get("content_html", "")

            h = doc.add_heading(title, level=1)
            h.paragraph_format.space_before = Pt(18)
            h.paragraph_format.space_after = Pt(10)

            # Convert HTML text to clean paragraphs
            clean_paragraphs = self._html_to_docx_paragraphs(html_content)
            for p_text in clean_paragraphs:
                p_elem = doc.add_paragraph()
                p_elem.paragraph_format.line_spacing = 1.15
                p_elem.paragraph_format.space_after = Pt(6)
                
                # Check for bullet points
                if p_text.startswith("• ") or p_text.startswith("- "):
                    p_elem.style = 'List Bullet'
                    p_text = p_text[2:]
                
                run = p_elem.add_run(p_text)
                run.font.size = Pt(10.5)

            # Insert Visuals at appropriate sections
            if sec_key == "moyens_humains":
                if organigramme_path and os.path.exists(organigramme_path):
                    doc.add_paragraph("\nFigure 1 : Organigramme d'Encadrement Chantier").runs[0].italic = True
                    doc.add_picture(organigramme_path, width=Inches(6.5))
                    doc.add_paragraph("\n")
                elif organigramme_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"⚠️ Avertissement : Génération du graphique échouée — {organigramme_error}")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)

            elif sec_key == "methodologie_phasage" or sec_key == "planning_gantt":
                if gantt_path and os.path.exists(gantt_path):
                    doc.add_paragraph("\nFigure 2 : Planning Prévisionnel de Phasage (Gantt)").runs[0].italic = True
                    doc.add_picture(gantt_path, width=Inches(6.5))
                    doc.add_paragraph("\n")
                elif gantt_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"⚠️ Avertissement : Génération du graphique échouée — {gantt_error}")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)

        # 6. Save docx to buffer
        docx_buffer = io.BytesIO()
        doc.save(docx_buffer)
        docx_buffer.seek(0)
        docx_bytes = docx_buffer.read()

        # Clean up temporary visual files
        for p in [gantt_path, organigramme_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        # 7. Attempt to save to tenant storage (non-blocking)
        s3_docx_key = f"tenants/{tenant_id}/exports/{project_id}/memoire_technique_{project_id[:8]}.docx"
        try:
            storage_service.upload_file(
                tenant_id=tenant_id,
                subpath=f"exports/{project_id}/memoire_technique_{project_id[:8]}.docx",
                file_obj=docx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        except Exception as e:
            print(f"[ExporterService] Storage upload notice (file still available in-memory): {e}")

        return {
            "s3_docx_key": s3_docx_key,
            "docx_bytes": docx_bytes,
            "filename": f"Memoire_Technique_{project_data.get('reference_code', 'AO')}.docx",
        }

    def convert_docx_to_pdf(self, docx_bytes: bytes, tenant_id: str, project_id: str) -> Optional[str]:
        """
        Converts DOCX bytes to PDF using LibreOffice headless.
        Falls back gracefully if LibreOffice is not installed in the environment.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            in_file = os.path.join(tmp_dir, "input.docx")
            with open(in_file, "wb") as f:
                f.write(docx_bytes)

            try:
                cmd = ["libreoffice", "--headless", "--convert-to", "pdf", in_file, "--outdir", tmp_dir]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                
                out_pdf = os.path.join(tmp_dir, "input.pdf")
                if os.path.exists(out_pdf):
                    with open(out_pdf, "rb") as f:
                        pdf_bytes = f.read()

                    s3_pdf_key = storage_service.upload_file(
                        tenant_id=tenant_id,
                        subpath=f"exports/{project_id}/memoire_technique_{project_id[:8]}.pdf",
                        file_obj=pdf_bytes,
                        content_type="application/pdf"
                    )
                    return s3_pdf_key
            except Exception as e:
                print(f"[ExporterService] LibreOffice PDF conversion notice: {e}")

        return None

    # ─── Template Structural Fidelity (Batch 9) ────────────────────────────
    # AO-required sections missing from an uploaded client template are
    # detected (not silently dropped) and flagged as a visible suggestion; a
    # company-name placeholder left in the template's own header/footer is
    # replaced with the real tenant name instead of shipping whatever was
    # hardcoded in the client's original file.

    _PLACEHOLDER_PATTERNS = [
        re.compile(r'\{\{?\s*nom[_ ]du[_ ]client\s*\}?\}', re.IGNORECASE),
        re.compile(r'\{\{?\s*nom[_ ]entreprise\s*\}?\}', re.IGNORECASE),
        re.compile(r'\[\s*NOM[_ ]DU[_ ]CLIENT\s*\]', re.IGNORECASE),
        re.compile(r'\[\s*NOM[_ ]ENTREPRISE\s*\]', re.IGNORECASE),
    ]

    def _replace_placeholder_in_paragraphs(self, paragraphs, company_name: str) -> int:
        replaced = 0
        for p in paragraphs:
            for run in p.runs:
                new_text = run.text
                for pattern in self._PLACEHOLDER_PATTERNS:
                    new_text, n = pattern.subn(company_name, new_text)
                    replaced += n
                if new_text != run.text:
                    run.text = new_text
        return replaced

    def _replace_company_placeholders(self, doc, company_name: str) -> int:
        """
        Best-effort: replaces {nom_du_client}-style placeholder tokens found in the
        template's headers/footers with the real tenant company name. The generated
        body always replaces the template's own body content wholesale (see
        build_memo_docx below), so only headers/footers can still carry a hardcoded
        name from the client's original file -- this is the one place that needs it.
        Does not scan first-page/even-page header-footer variants (uncommon in
        practice); a token split across multiple Word-internal runs is not caught
        (documented limitation, non-blocking).
        """
        total = 0
        for section in doc.sections:
            for hf in (section.header, section.footer):
                try:
                    total += self._replace_placeholder_in_paragraphs(hf.paragraphs, company_name)
                    for table in hf.tables:
                        for row in table.rows:
                            for cell in row.cells:
                                total += self._replace_placeholder_in_paragraphs(cell.paragraphs, company_name)
                except Exception as e:
                    print(f"[ExporterService] Placeholder replacement notice: {e}")
        return total

    @staticmethod
    def _normalize_heading_text(text: str) -> str:
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r'^[0-9]+[\.\)]?\s*', '', text)
        text = re.sub(r'[^a-zA-Z\s]', ' ', text)
        return ' '.join(text.lower().split())

    @staticmethod
    def _word_set_similarity(norm_a: str, norm_b: str) -> float:
        """
        Jaccard similarity over normalized word sets. Deliberately NOT a raw
        character-level ratio (e.g. difflib.SequenceMatcher): short French BTP
        section titles share common domain words -- "Moyens Humains &
        Encadrement" vs "Moyens Matériels & Engins" overlap heavily at the
        character level (shared "Moyens", shared letters) despite being
        completely different sections. Comparing whole-word sets instead means
        only "Moyens" overlaps (1 of 5 unique words, ratio 0.2), correctly
        telling them apart, while still tolerating minor real-world phrasing
        differences (a template heading missing "& Encadrement" still matches
        at 0.67).
        """
        words_a, words_b = set(norm_a.split()), set(norm_b.split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    def _detect_missing_required_sections(
        self, template_bytes: Optional[bytes], required_titles: Optional[List[str]]
    ) -> List[str]:
        """
        Compares the heading-styled paragraph text found in the uploaded client
        template against the AO-required canonical section titles. Returns the
        canonical titles with no reasonably similar heading in the template, so
        build_memo_docx can flag them as a visible suggestion instead of silently
        inserting content the template's own author never anticipated. Returns []
        when there is no template (nothing to compare against) or no required
        titles were supplied -- never invents a "missing" list out of nothing.
        """
        if not template_bytes or not required_titles:
            return []
        try:
            tpl_doc = docx.Document(io.BytesIO(template_bytes))
        except Exception as e:
            print(f"[ExporterService] Template heading scan notice: {e}")
            return []

        heading_texts = []
        for p in tpl_doc.paragraphs:
            text = p.text.strip()
            if not text or len(text) > 120:
                continue
            style_name = p.style.name if p.style else ''
            is_heading_style = 'Heading' in style_name or 'Title' in style_name
            is_bold_run = any(r.bold for r in p.runs if r.bold)
            if is_heading_style or is_bold_run:
                heading_texts.append(self._normalize_heading_text(text))

        missing = []
        for title in required_titles:
            norm_title = self._normalize_heading_text(title)
            best_ratio = max(
                (self._word_set_similarity(norm_title, h) for h in heading_texts),
                default=0.0,
            )
            if best_ratio < 0.5:
                missing.append(title)
        return missing

    def _html_to_docx_paragraphs(self, html_text: str) -> List[str]:
        """
        Strips HTML tags while preserving paragraph breaks and bullet list structures.
        """
        text = html_text.replace("</li>", "\n")
        text = text.replace("<li>", "• ")
        text = text.replace("</h2>", "\n\n")
        text = text.replace("</h3>", "\n\n")
        text = text.replace("</p>", "\n\n")
        text = text.replace("<br>", "\n")
        text = text.replace("<br/>", "\n")
        
        # Remove remaining tags
        clean = re.sub(r'<[^>]+>', '', text)
        
        # Clean entities
        clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&gt;", ">").replace("&lt;", "<")
        
        paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
        return paragraphs


exporter_service = ExporterService()
