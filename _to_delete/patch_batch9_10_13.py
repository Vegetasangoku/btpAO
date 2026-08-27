#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 9 — Docx export template-structure fidelity:
  1. exporter_service.py gains 3 new methods: placeholder-token replacement
     ({nom_du_client}/[NOM_DU_CLIENT]-style tokens in the template's own
     header/footer replaced with the real tenant company_name, never a
     hardcoded/previous-client name), missing-required-section detection
     (fuzzy-matches the template's own heading paragraphs against the 9
     canonical SECTION_DEFINITIONS titles via word-set Jaccard similarity,
     chosen over a raw character-level ratio because short French BTP
     section titles share domain words that make character overlap
     misleading -- see _word_set_similarity's docstring), and a
     visible warning block injected into the Sommaire for any AO-required
     section absent from the template's own structure.
  2. Both real callers of build_memo_docx (export.py's stream_project_docx,
     tasks.py's build_export_doc_task) now pass required_section_titles=
     sourced from the single canonical SECTION_DEFINITIONS dict.
  3. The Gantt/organigramme failure placeholder is retagged to lead with the
     mega-spec's exact literal string "⚠️ Avertissement : Génération du
     graphique échouée" (was "[Figure non disponible : ...]").

Batch 10 — Priorisation RAG absolue: tasks.py's generate_section_task
  currently calls web_search_service.search(...) unconditionally on EVERY
  section generation, regardless of whether the tenant's own historical
  corpus (validated company assets + capitalized learnings) already has
  content. This burns web-search quota/cost and dilutes a well-covered
  section with less-authoritative external sources even when the internal
  corpus already answers it -- the opposite of "priorité RAG absolue". Now
  gated: web search only runs when company_assets AND tenant_learnings_payload
  are BOTH empty (i.e. it is a genuine fallback for a corpus with nothing to
  say, never a blanket enrichment). DCE chunks are deliberately excluded from
  this gate -- they are the CURRENT tender's own documents, not "corpus
  historique", and stay independent of this decision. Whitelist enforcement
  itself (CountryOfficialSource, zero-source-country = zero-search) is
  untouched -- it was already correctly implemented.

Batch 13 — Chat module exclusivity: the mega-spec says the chat module lives
  EXCLUSIVELY on the Corpus Client page. DCEChatSidebar is currently mounted
  in 3 places: apps/web/.../dashboard/company/page.tsx ("Mon Entreprise" --
  hosts the tenant's own knowledge/savoir-faire + reference-sites tabs, i.e.
  the Corpus Client page), apps/web/.../dashboard/workspace/page.tsx (the
  main AO dossier workspace), and apps/web/.../projects/[id]/editor/page.tsx
  (a second, standalone editor route). Removed from the latter two (toggle
  button, state, sidebar mount, now-unused imports); left untouched on the
  company page.

Exact-match-count-of-1 verified live against the running files immediately
before writing this script (protects against drift from the other AI's
concurrent edits). Aborts per-file with zero writes on any mismatch.
"""
import sys


def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for item in replacements:
        if len(item) == 4:
            label, old, new, expected_count = item
        else:
            label, old, new = item
            expected_count = 1
        count = content.count(old)
        if count != expected_count:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected {expected_count}). No changes written.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_batch9_10_13.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
EXPORTER_PY = f"{REPO_ROOT}/apps/api/app/services/exporter_service.py"
EXPORT_API_PY = f"{REPO_ROOT}/apps/api/app/api/export.py"
TASKS_PY = f"{REPO_ROOT}/apps/api/app/workers/tasks.py"
WORKSPACE_TSX = f"{REPO_ROOT}/apps/web/src/app/dashboard/workspace/page.tsx"
EDITOR_TSX = f"{REPO_ROOT}/apps/web/src/app/projects/[id]/editor/page.tsx"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. exporter_service.py
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(EXPORTER_PY, [
    (
        "add unicodedata import",
        "import io\nimport os\nimport re\nimport subprocess\nimport tempfile\n",
        "import io\nimport os\nimport re\nimport subprocess\nimport tempfile\nimport unicodedata\n",
    ),
    (
        "build_memo_docx signature gains required_section_titles",
        '''    def build_memo_docx(
        self,
        tenant_id: str,
        project_id: str,
        project_data: Dict[str, Any],
        sections: List[Dict[str, Any]],
        decision_form: Dict[str, Any],
        template_bytes: Optional[bytes] = None,
        include_visuals: bool = True,
    ) -> Dict[str, Any]:''',
        '''    def build_memo_docx(
        self,
        tenant_id: str,
        project_id: str,
        project_data: Dict[str, Any],
        sections: List[Dict[str, Any]],
        decision_form: Dict[str, Any],
        template_bytes: Optional[bytes] = None,
        include_visuals: bool = True,
        required_section_titles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:''',
    ),
    (
        "detect missing sections + replace placeholders on template load",
        '''        # 1. Create a base document — use client template if available
        if template_bytes:
            try:
                doc = docx.Document(io.BytesIO(template_bytes))
                # Clear existing body content but preserve headers/footers
                for element in list(doc.element.body):
                    if element.tag.endswith('}sectPr'):
                        continue  # preserve section properties (margins, headers)
                    doc.element.body.remove(element)
            except Exception as e:
                print(f"[ExporterService] Template load error, using blank: {e}")
                doc = docx.Document()
        else:
            doc = docx.Document()''',
        '''        # 1. Create a base document — use client template if available
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
            doc = docx.Document()''',
    ),
    (
        "inject missing-sections warning after TOC",
        '''        for s in sections:
            p_toc_item = doc.add_paragraph(style='List Bullet')
            r_toc = p_toc_item.add_run(f"{s.get('title', 'Section')}")
            r_toc.font.size = Pt(11)

        doc.add_paragraph("\\n")''',
        '''        for s in sections:
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

        doc.add_paragraph("\\n")''',
    ),
    (
        "literal chart-failure banner: organigramme",
        '''                elif organigramme_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"[Figure non disponible : {organigramme_error}]")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)''',
        '''                elif organigramme_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"⚠️ Avertissement : Génération du graphique échouée — {organigramme_error}")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)''',
    ),
    (
        "literal chart-failure banner: gantt",
        '''                elif gantt_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"[Figure non disponible : {gantt_error}]")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)''',
        '''                elif gantt_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"⚠️ Avertissement : Génération du graphique échouée — {gantt_error}")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)''',
    ),
    (
        "insert new template-fidelity methods before _html_to_docx_paragraphs",
        '''    def _html_to_docx_paragraphs(self, html_text: str) -> List[str]:''',
        '''    # ─── Template Structural Fidelity (Batch 9) ────────────────────────────
    # AO-required sections missing from an uploaded client template are
    # detected (not silently dropped) and flagged as a visible suggestion; a
    # company-name placeholder left in the template's own header/footer is
    # replaced with the real tenant name instead of shipping whatever was
    # hardcoded in the client's original file.

    _PLACEHOLDER_PATTERNS = [
        re.compile(r'\\{\\{?\\s*nom[_ ]du[_ ]client\\s*\\}?\\}', re.IGNORECASE),
        re.compile(r'\\{\\{?\\s*nom[_ ]entreprise\\s*\\}?\\}', re.IGNORECASE),
        re.compile(r'\\[\\s*NOM[_ ]DU[_ ]CLIENT\\s*\\]', re.IGNORECASE),
        re.compile(r'\\[\\s*NOM[_ ]ENTREPRISE\\s*\\]', re.IGNORECASE),
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
        text = re.sub(r'^[0-9]+[\\.\\)]?\\s*', '', text)
        text = re.sub(r'[^a-zA-Z\\s]', ' ', text)
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

    def _html_to_docx_paragraphs(self, html_text: str) -> List[str]:''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 2. export.py — stream_project_docx: pass required_section_titles
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(EXPORT_API_PY, [
    (
        "stream_project_docx: pass required_section_titles",
        '''    docx_res = exporter_service.build_memo_docx(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        project_data=project_dict,
        sections=sections,
        decision_form=decision_form,
        template_bytes=template_bytes,
        include_visuals=False,
    )''',
        '''    from app.api.generate import SECTION_DEFINITIONS
    required_section_titles = sorted({v["title"] for k, v in SECTION_DEFINITIONS.items() if k != "qse_environnement"})
    docx_res = exporter_service.build_memo_docx(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        project_data=project_dict,
        sections=sections,
        decision_form=decision_form,
        template_bytes=template_bytes,
        include_visuals=False,
        required_section_titles=required_section_titles,
    )''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 3. tasks.py — build_export_doc_task: pass required_section_titles (Batch 9)
#    AND generate_section_task: gate web search behind RAG-sufficiency (Batch 10)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TASKS_PY, [
    (
        "build_export_doc_task: pass required_section_titles",
        '''                docx_res = exporter_service.build_memo_docx(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    project_data=project_dict,
                    sections=sections,
                    decision_form=decision_form,
                    template_bytes=template_bytes,
                    include_visuals=include_visuals,
                )''',
        '''                from app.api.generate import SECTION_DEFINITIONS
                required_section_titles = sorted({v["title"] for k, v in SECTION_DEFINITIONS.items() if k != "qse_environnement"})
                docx_res = exporter_service.build_memo_docx(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    project_data=project_dict,
                    sections=sections,
                    decision_form=decision_form,
                    template_bytes=template_bytes,
                    include_visuals=include_visuals,
                    required_section_titles=required_section_titles,
                )''',
    ),
    (
        "generate_section_task: gate web search behind RAG corpus sufficiency",
        '''                # 7. Targeted Web Search Enrichment (Serper API) strictly scoped to tenant request
                # AND strictement restreinte a la whitelist reglementaire Super Admin du pays du
                # tenant : jamais un site hors whitelist, jamais un repli vers l'internet ouvert.
                # Zero source configuree pour ce pays = zero recherche (pas un repli non restreint).
                from app.services.web_search_service import web_search_service
                from app.models.entities import CountryOfficialSource
                from urllib.parse import urlparse
                whitelist_res = await db.execute(
                    select(CountryOfficialSource).where(
                        CountryOfficialSource.country_code == reg_profile.country_code,
                        CountryOfficialSource.status == "active",
                    )
                )
                whitelist_domains = sorted({
                    urlparse(s.portal_url).netloc for s in whitelist_res.scalars().all() if s.portal_url
                })
                search_query = f"{project.title} {section_key} BTP normes {reg_profile.technical_standards_reference[:25]}"
                if custom_instructions:
                    search_query += f" {custom_instructions[:60]}"
                web_results = await web_search_service.search(
                    tenant_id=tenant_id,
                    query=search_query,
                    num_results=3,
                    project_id=project_id,
                    allowed_sites=whitelist_domains,
                )
                web_sources_payload = [
                    {"title": r.title, "url": r.url, "snippet": r.snippet}
                    for r in web_results
                ]''',
        '''                # 7. Targeted Web Search Enrichment (Serper API) strictly scoped to tenant request
                # AND strictement restreinte a la whitelist reglementaire Super Admin du pays du
                # tenant : jamais un site hors whitelist, jamais un repli vers l'internet ouvert.
                # Zero source configuree pour ce pays = zero recherche (pas un repli non restreint).
                # PRIORITE RAG ABSOLUE (cahier des charges) : la recherche web est un VRAI repli,
                # jamais un enrichissement systematique -- si le corpus historique du tenant
                # (savoir-faire valide + enseignements capitalises) contient deja de la matiere,
                # la recherche web est sautee entierement (zero appel provider, zero cout, zero
                # dilution du corpus interne par une source externe moins autorisee). Les extraits
                # DCE (dce_chunks) restent hors de cette condition : ce sont les pieces du marche
                # EN COURS, pas le "corpus historique" du tenant, donc toujours independants ici.
                if company_assets or tenant_learnings_payload:
                    logger.info(
                        "[GenerateSectionTask] Corpus client suffisant (%d savoir-faire, %d enseignements) "
                        "-- recherche web sautee (priorite RAG absolue).",
                        len(company_assets), len(tenant_learnings_payload),
                    )
                    web_sources_payload = []
                else:
                    from app.services.web_search_service import web_search_service
                    from app.models.entities import CountryOfficialSource
                    from urllib.parse import urlparse
                    whitelist_res = await db.execute(
                        select(CountryOfficialSource).where(
                            CountryOfficialSource.country_code == reg_profile.country_code,
                            CountryOfficialSource.status == "active",
                        )
                    )
                    whitelist_domains = sorted({
                        urlparse(s.portal_url).netloc for s in whitelist_res.scalars().all() if s.portal_url
                    })
                    search_query = f"{project.title} {section_key} BTP normes {reg_profile.technical_standards_reference[:25]}"
                    if custom_instructions:
                        search_query += f" {custom_instructions[:60]}"
                    web_results = await web_search_service.search(
                        tenant_id=tenant_id,
                        query=search_query,
                        num_results=3,
                        project_id=project_id,
                        allowed_sites=whitelist_domains,
                    )
                    web_sources_payload = [
                        {"title": r.title, "url": r.url, "snippet": r.snippet}
                        for r in web_results
                    ]''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 4. workspace/page.tsx — remove chat (Batch 13)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(WORKSPACE_TSX, [
    (
        "remove DCEChatSidebar import",
        "import { DCEChatSidebar } from '@/components/chat/dce-chat-sidebar';\n",
        "",
    ),
    (
        "remove showChatSidebar state",
        "  const [showChatSidebar, setShowChatSidebar] = useState(false);\n",
        "",
    ),
    (
        "remove Assistant DCE & Normes toggle button",
        '''            <button
              onClick={() => setShowChatSidebar(true)}
              className="flex items-center gap-2 px-4 py-3 rounded-2xl bg-slate-800 hover:bg-slate-700 text-sky-400 hover:text-sky-300 border border-slate-700 text-xs font-bold transition-all shadow-lg"
            >
              <MessageSquare className="w-4 h-4 text-sky-400" />
              <span>Assistant DCE & Normes</span>
            </button>

''',
        "",
    ),
    (
        "remove DCEChatSidebar mount",
        '''      {/* CHAT SIDEBAR WITH REAL DCE CONTEXT */}
      <DCEChatSidebar
        projectId={project.id}
        projectTitle={project.title}
        isOpen={showChatSidebar}
        onClose={() => setShowChatSidebar(false)}
      />

''',
        "",
    ),
    (
        "remove now-unused MessageSquare icon import",
        "  MessageSquare,\n",
        "",
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 5. projects/[id]/editor/page.tsx — remove chat (Batch 13)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(EDITOR_TSX, [
    (
        "remove DCEChatSidebar import",
        "import { DCEChatSidebar } from '@/components/chat/dce-chat-sidebar';\n",
        "",
    ),
    (
        "remove chatOpen state",
        "  const [chatOpen, setChatOpen] = useState(false);\n",
        "",
    ),
    (
        "remove Assistant Q&A toggle button",
        '''            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 text-xs font-semibold hover:bg-slate-700 transition-all"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Assistant Q&A
            </button>

''',
        "",
    ),
    (
        "remove DCEChatSidebar mount",
        '''      <DCEChatSidebar
        projectId={projectId}
        projectTitle={project?.title || ''}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />
''',
        "",
    ),
    (
        "remove now-unused MessageSquare icon import",
        "  MessageSquare,\n",
        "",
    ),
]))

if not all(results):
    print("\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\nALL BATCH-9/10/13 PATCHES APPLIED SUCCESSFULLY.")
