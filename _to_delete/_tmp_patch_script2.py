import sys

def patch(path, replacements, label):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content
    for i, (old, new, expect) in enumerate(replacements):
        cnt = content.count(old)
        if cnt != expect:
            print(f"[{label}] FAIL at replacement #{i}: expected {expect} occurrences, found {cnt}")
            print("----- OLD (repr) -----")
            print(repr(old[:400]))
            sys.exit(1)
        content = content.replace(old, new)
    if content == original:
        print(f"[{label}] WARNING: no changes made")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[{label}] OK -- {len(replacements)} replacements applied")


PATH = "apps/api/app/services/llm_generator.py"
reps = []

# 3g. System prompt: add third citation style for tenant-added reference sites
reps.append((
    "   - Pour les éléments issus de la recherche web externe (normes techniques, guides professionnels, {env_reg}, données acheteur) : cite obligatoirement sous la forme explicite [Source web : Titre de la source — URL].\n",
    "   - Pour les éléments issus de la recherche web externe (normes techniques, guides professionnels, {env_reg}, données acheteur) : cite obligatoirement sous la forme explicite [Source web : Titre de la source — URL].\n"
    "   - Pour les éléments issus d'un site de référence explicitement ajouté par l'entreprise (ex. site de l'acheteur public visé) : cite obligatoirement sous la forme explicite [Site de référence client : Titre — URL]. Ces sources sont prioritaires pour maximiser la conformité au client visé.\n",
    1,
))

# 3a. CONTEXT_LIMITS: add client_sites budget
reps.append((
    'CONTEXT_LIMITS = {\n    "dce": 8000,\n    "assets": 6000,\n    "apprentissages": 4000,\n    "web": 4000,\n}',
    'CONTEXT_LIMITS = {\n    "dce": 8000,\n    "assets": 6000,\n    "apprentissages": 4000,\n    "web": 4000,\n    "client_sites": 3000,\n}',
    1,
))

# 3b-1. generate_memo_section signature: add rag_client_sites param
reps.append((
    "        rag_web_sources: Optional[List[Dict[str, Any]]] = None,\n"
    "        tenant_learnings: Optional[List[Dict[str, Any]]] = None,\n"
    "        regulatory_profile: Optional[Dict[str, Any]] = None,\n"
    "        tenant_system_prompt: Optional[str] = None,\n",
    "        rag_web_sources: Optional[List[Dict[str, Any]]] = None,\n"
    "        rag_client_sites: Optional[List[Dict[str, Any]]] = None,\n"
    "        tenant_learnings: Optional[List[Dict[str, Any]]] = None,\n"
    "        regulatory_profile: Optional[Dict[str, Any]] = None,\n"
    "        tenant_system_prompt: Optional[str] = None,\n",
    1,
))

# 3c-1. generate_memo_section body: define client_sites local var
reps.append((
    "        reg = regulatory_profile\n"
    "        web_sources = rag_web_sources or []\n"
    "        learnings_list = tenant_learnings or []\n"
    "        target_model = llm_model or self.default_model\n",
    "        reg = regulatory_profile\n"
    "        web_sources = rag_web_sources or []\n"
    "        client_sites = rag_client_sites or []\n"
    "        learnings_list = tenant_learnings or []\n"
    "        target_model = llm_model or self.default_model\n",
    1,
))

# 3c-3. Build client_sites_items / client_sites_context_text
reps.append((
    "        web_items = [\n"
    "            f\"--- Source Web ({w.get('title', 'Web')}) ---\\nURL: {w.get('url', '')}\\nExtrait: {w.get('snippet', '')}\"\n"
    "            for w in web_sources\n"
    "        ]\n"
    "        learnings_items = [\n"
    "            f\"- [Enseignement AO antérieur ({l.get('category', 'général')})] {l.get('title', '')} : {l.get('insight', '')} => Directive : {l.get('directive', '')}\"\n"
    "            for l in learnings_list\n"
    "        ]\n"
    "\n"
    "        dce_context_text = bounded_context_join(dce_items, CONTEXT_LIMITS[\"dce\"], \"DCE\")\n"
    "        assets_context_text = bounded_context_join(assets_items, CONTEXT_LIMITS[\"assets\"], \"Company Assets\")\n"
    "        web_context_text = bounded_context_join(web_items, CONTEXT_LIMITS[\"web\"], \"Web Sources\")\n"
    "        learnings_context_text = bounded_context_join(learnings_items, CONTEXT_LIMITS[\"apprentissages\"], \"Apprentissages\")\n",

    "        web_items = [\n"
    "            f\"--- Source Web ({w.get('title', 'Web')}) ---\\nURL: {w.get('url', '')}\\nExtrait: {w.get('snippet', '')}\"\n"
    "            for w in web_sources\n"
    "        ]\n"
    "        client_sites_items = [\n"
    "            f\"--- Site de Référence Client ({c.get('title', 'Site')}) ---\\nURL: {c.get('url', '')}\\nExtrait: {c.get('content', '')}\"\n"
    "            for c in client_sites\n"
    "        ]\n"
    "        learnings_items = [\n"
    "            f\"- [Enseignement AO antérieur ({l.get('category', 'général')})] {l.get('title', '')} : {l.get('insight', '')} => Directive : {l.get('directive', '')}\"\n"
    "            for l in learnings_list\n"
    "        ]\n"
    "\n"
    "        dce_context_text = bounded_context_join(dce_items, CONTEXT_LIMITS[\"dce\"], \"DCE\")\n"
    "        assets_context_text = bounded_context_join(assets_items, CONTEXT_LIMITS[\"assets\"], \"Company Assets\")\n"
    "        web_context_text = bounded_context_join(web_items, CONTEXT_LIMITS[\"web\"], \"Web Sources\")\n"
    "        client_sites_context_text = bounded_context_join(client_sites_items, CONTEXT_LIMITS[\"client_sites\"], \"Client Reference Sites\")\n"
    "        learnings_context_text = bounded_context_join(learnings_items, CONTEXT_LIMITS[\"apprentissages\"], \"Apprentissages\")\n",
    1,
))

# 3d. Prompt renumbering: insert new section 8 (client sites), shift consignes/langue to 9/10
reps.append((
    "7. SOURCES WEB TECHNIQUES & RÉGLEMENTAIRES (SERPER) :\n"
    "{web_context_text or \"Aucune recherche web externe nécessaire.\"}\n"
    "\n"
    "8. CONSIGNES PARTICULIÈRES (PRIORITAIRES — SURCHARGENT LES SECTIONS 1 À 7 CI-DESSUS EN CAS DE CONFLIT) :\n"
    "{custom_instructions or \"Aucune instruction supplémentaire.\"}\n"
    "\n"
    "9. LANGUE DE RÉDACTION OBLIGATOIRE (rappel) :\n",

    "7. SOURCES WEB TECHNIQUES & RÉGLEMENTAIRES (SERPER) :\n"
    "{web_context_text or \"Aucune recherche web externe nécessaire.\"}\n"
    "\n"
    "8. SITES DE RÉFÉRENCE AJOUTÉS PAR LE TENANT (PRIORITAIRES — ex. site de l'acheteur public visé par cet AO, fédération professionnelle...) :\n"
    "{client_sites_context_text or \"Aucun site de référence configuré par l'entreprise pour ce tenant.\"}\n"
    "IMPORTANT : si des extraits figurent ci-dessus, tu DOIS explicitement t'appuyer dessus pour maximiser la conformité au client/acheteur visé, et justifier chaque usage dans \"compliance_checklist\" avec la source \"[Site de référence client : Titre]\". Ne cite jamais un site de référence pour une information qu'il ne contient pas réellement.\n"
    "\n"
    "9. CONSIGNES PARTICULIÈRES (PRIORITAIRES — SURCHARGENT LES SECTIONS 1 À 8 CI-DESSUS EN CAS DE CONFLIT) :\n"
    "{custom_instructions or \"Aucune instruction supplémentaire.\"}\n"
    "\n"
    "10. LANGUE DE RÉDACTION OBLIGATOIRE (rappel) :\n",
    1,
))

# 3e. compliance_checklist source hint: mention client reference sites
reps.append((
    '"source": "[Source : DCE p.X] ou [Savoir-faire entreprise] ou [Source web : Titre] ou [Profil réglementaire pays]"',
    '"source": "[Source : DCE p.X] ou [Savoir-faire entreprise] ou [Source web : Titre] ou [Site de référence client : Titre] ou [Profil réglementaire pays]"',
    1,
))

# 3f. JSON schema: add client_sources_used field
reps.append((
    '  "web_sources_used": [\n'
    '    {{"title": "...", "url": "..."}}\n'
    '  ]\n'
    '}}\n'
    '\n'
    'IMPÉRATIF SUR "compliance_checklist"',

    '  "web_sources_used": [\n'
    '    {{"title": "...", "url": "..."}}\n'
    '  ],\n'
    '  "client_sources_used": [\n'
    '    {{"title": "...", "url": "..."}}\n'
    '  ]\n'
    '}}\n'
    '\n'
    'IMPÉRATIF SUR "compliance_checklist"',
    1,
))

# 3h. Fallback template engine invocation: pass client_sites through
reps.append((
    "        res = self._generate_specialized_btp_section(\n"
    "            section_key=section_key,\n"
    "            section_title=section_title,\n"
    "            decision_form=decision_form,\n"
    "            project_title=project_title,\n"
    "            rag_dce_chunks=rag_dce_chunks,\n"
    "            rag_company_assets=rag_company_assets,\n"
    "            rag_web_sources=web_sources,\n"
    "            tenant_learnings=learnings_list,\n",
    "        res = self._generate_specialized_btp_section(\n"
    "            section_key=section_key,\n"
    "            section_title=section_title,\n"
    "            decision_form=decision_form,\n"
    "            project_title=project_title,\n"
    "            rag_dce_chunks=rag_dce_chunks,\n"
    "            rag_company_assets=rag_company_assets,\n"
    "            rag_web_sources=web_sources,\n"
    "            rag_client_sites=client_sites,\n"
    "            tenant_learnings=learnings_list,\n",
    1,
))

# 3b-2. _generate_specialized_btp_section signature: add rag_client_sites param
reps.append((
    "        rag_web_sources: Optional[List[Dict[str, Any]]] = None,\n"
    "        tenant_learnings: Optional[List[Dict[str, Any]]] = None,\n"
    "        regulatory_profile: Optional[Dict[str, Any]] = None,\n"
    "        custom_instructions: Optional[str] = None,\n"
    "        language: str = \"fr\",\n"
    "        debug_error: Optional[str] = None,\n"
    "    ) -> Dict[str, Any]:",
    "        rag_web_sources: Optional[List[Dict[str, Any]]] = None,\n"
    "        rag_client_sites: Optional[List[Dict[str, Any]]] = None,\n"
    "        tenant_learnings: Optional[List[Dict[str, Any]]] = None,\n"
    "        regulatory_profile: Optional[Dict[str, Any]] = None,\n"
    "        custom_instructions: Optional[str] = None,\n"
    "        language: str = \"fr\",\n"
    "        debug_error: Optional[str] = None,\n"
    "    ) -> Dict[str, Any]:",
    1,
))

# 3c-2. _generate_specialized_btp_section body: define client_sites local var
reps.append((
    "        reg = regulatory_profile\n"
    "        dce_chunks = rag_dce_chunks or []\n"
    "        web_sources = rag_web_sources or []\n"
    "        learnings_list = tenant_learnings or []\n"
    "        delai = decision_form.get(\"delai_mois\", 6)\n",
    "        reg = regulatory_profile\n"
    "        dce_chunks = rag_dce_chunks or []\n"
    "        web_sources = rag_web_sources or []\n"
    "        client_sites = rag_client_sites or []\n"
    "        learnings_list = tenant_learnings or []\n"
    "        delai = decision_form.get(\"delai_mois\", 6)\n",
    1,
))

# 3i-1a. FB i18n: fr client_sites labels
reps.append((
    '"web_source_fallback_title": "Référence",',
    '"web_source_fallback_title": "Référence",\n                "client_sites_h3": "Sites de Référence Client",\n                "client_site_prefix": "Site de référence client :",',
    1,
))
# 3i-1b. FB i18n: en client_sites labels
reps.append((
    '"web_source_fallback_title": "Reference",',
    '"web_source_fallback_title": "Reference",\n                "client_sites_h3": "Client Reference Sites",\n                "client_site_prefix": "Client reference site:",',
    1,
))
# 3i-1c. FB i18n: ar client_sites labels
reps.append((
    '"web_source_fallback_title": "مرجع",',
    '"web_source_fallback_title": "مرجع",\n                "client_sites_h3": "مواقع مرجعية للعميل",\n                "client_site_prefix": "موقع مرجعي للعميل:",',
    1,
))

# 3i-2. Add client_sites_html block right after web_cites_html block
reps.append((
    "        # Web citation snippet\n"
    "        web_cites_html = \"\"\n"
    "        if web_sources:\n"
    "            web_cites_html = f\"<h3>{FB['external_sources_h3']}</h3><ul>\" + \"\".join([\n"
    "                f\"<li><strong>{FB['web_source_prefix']}</strong> {w.get('title', FB['web_source_fallback_title'])} — <a href='{w.get('url', '#')}'>{w.get('url', '')}</a></li>\"\n"
    "                for w in web_sources\n"
    "            ]) + \"</ul>\"\n",
    "        # Web citation snippet\n"
    "        web_cites_html = \"\"\n"
    "        if web_sources:\n"
    "            web_cites_html = f\"<h3>{FB['external_sources_h3']}</h3><ul>\" + \"\".join([\n"
    "                f\"<li><strong>{FB['web_source_prefix']}</strong> {w.get('title', FB['web_source_fallback_title'])} — <a href='{w.get('url', '#')}'>{w.get('url', '')}</a></li>\"\n"
    "                for w in web_sources\n"
    "            ]) + \"</ul>\"\n"
    "\n"
    "        # Client reference sites citation snippet (03/09) : sites explicitement ajoutes\n"
    "        # par le tenant (ex. site de l'acheteur public vise), prioritaires pour la conformite.\n"
    "        client_sites_html = \"\"\n"
    "        if client_sites:\n"
    "            client_sites_html = f\"<h3>{FB['client_sites_h3']}</h3><ul>\" + \"\".join([\n"
    "                f\"<li><strong>{FB['client_site_prefix']}</strong> {c.get('title', FB['web_source_fallback_title'])} — <a href='{c.get('url', '#')}'>{c.get('url', '')}</a></li>\"\n"
    "                for c in client_sites\n"
    "            ]) + \"</ul>\"\n",
    1,
))

# 3i-3. missing_data_alert: client_sites also counts as "we have something"
reps.append((
    '        if (custom_instructions and "introuvable" in custom_instructions.lower()) or (not dce_chunks and not web_sources and not rag_company_assets):',
    '        if (custom_instructions and "introuvable" in custom_instructions.lower()) or (not dce_chunks and not web_sources and not rag_company_assets and not client_sites):',
    1,
))

# 3i-4. Every section template: render client_sites_html right after web_cites_html
reps.append((
    "            {web_cites_html}",
    "            {web_cites_html}\n            {client_sites_html}",
    6,
))

# 3j. Fallback engine return dict: add client_sources_used
reps.append((
    '        return {\n'
    '            "title": section_title,\n'
    '            "content_html": html.strip(),\n'
    '            "compliance_score": score,\n'
    '            "compliance_notes": notes,\n'
    '            "visual_placeholders": ["gantt_chart", "organigramme_chantier"],\n'
    '            "web_sources_used": [{"title": w.get("title", ""), "url": w.get("url", "")} for w in web_sources],\n'
    '        }',
    '        return {\n'
    '            "title": section_title,\n'
    '            "content_html": html.strip(),\n'
    '            "compliance_score": score,\n'
    '            "compliance_notes": notes,\n'
    '            "visual_placeholders": ["gantt_chart", "organigramme_chantier"],\n'
    '            "web_sources_used": [{"title": w.get("title", ""), "url": w.get("url", "")} for w in web_sources],\n'
    '            "client_sources_used": [{"title": c.get("title", ""), "url": c.get("url", "")} for c in client_sites],\n'
    '        }',
    1,
))

patch(PATH, reps, "llm_generator.py")
print("ALL PATCHES APPLIED SUCCESSFULLY (script2)")
