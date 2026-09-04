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
            print(repr(old[:300]))
            sys.exit(1)
        content = content.replace(old, new)
    if content == original:
        print(f"[{label}] WARNING: no changes made")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[{label}] OK -- {len(replacements)} replacements applied")


BASE = "apps/api/app"

# ---------- 1. entities.py : add content_title/content_excerpt columns ----------
patch(f"{BASE}/models/entities.py", [
    (
        "    status = Column(Text, nullable=False, default=\"active\")  # 'active', 'broken', 'fetching'\n\n\nclass TenantSettings(Base):",
        "    status = Column(Text, nullable=False, default=\"active\")  # 'active', 'broken', 'fetching'\n    content_title = Column(Text, nullable=True)\n    content_excerpt = Column(Text, nullable=True)\n\n\nclass TenantSettings(Base):",
        1,
    ),
], "entities.py")

# ---------- 2. schemas.py : expose content_title in TenantReferenceUrlOut ----------
patch(f"{BASE}/models/schemas.py", [
    (
        "class TenantReferenceUrlOut(BaseModel):\n    id: str\n    tenant_id: str\n    url: str\n    label: Optional[str] = None\n    added_by: Optional[str] = None\n    added_at: datetime\n    last_fetched_at: Optional[datetime] = None\n    status: str = \"active\"",
        "class TenantReferenceUrlOut(BaseModel):\n    id: str\n    tenant_id: str\n    url: str\n    label: Optional[str] = None\n    added_by: Optional[str] = None\n    added_at: datetime\n    last_fetched_at: Optional[datetime] = None\n    status: str = \"active\"\n    content_title: Optional[str] = None",
        1,
    ),
], "schemas.py")

# ---------- 3. company_bootstrap.py ----------
cb_import_old = "from sqlalchemy import select"
cb_import_new = "from sqlalchemy import func, select"

cb_cap_old = """COMPANY_CHAT_WEB_SEARCH_MONTHLY_CAP = 50


class CompanyAskPayload(BaseModel):"""
cb_cap_new = """COMPANY_CHAT_WEB_SEARCH_MONTHLY_CAP = 50

# Garde-fou anti-derive de cout (03/09, demande client explicite) : nombre max de sites de
# reference qu'un tenant peut configurer AU TOTAL (tous statuts confondus). Ces sites sont
# desormais injectes comme source RAG a CHAQUE generation de section (voir tasks.py), donc
# leur nombre borne directement un cout recurrent -- contrairement au quota ci-dessus qui ne
# borne que l'assistant de chat ponctuel. Volontairement bas : un tenant type n'a besoin que
# du site de l'acheteur public vise + 1-2 sources professionnelles de reference.
MAX_TENANT_REFERENCE_URLS = 3


class CompanyAskPayload(BaseModel):"""

cb_list_old = """    return [
        TenantReferenceUrlOut(
            id=str(u.id),
            tenant_id=str(u.tenant_id),
            url=u.url,
            label=u.label,
            added_by=str(u.added_by) if u.added_by else None,
            added_at=u.added_at,
            last_fetched_at=u.last_fetched_at,
            status=u.status,
        )
        for u in urls
    ]"""
cb_list_new = """    return [
        TenantReferenceUrlOut(
            id=str(u.id),
            tenant_id=str(u.tenant_id),
            url=u.url,
            label=u.label,
            added_by=str(u.added_by) if u.added_by else None,
            added_at=u.added_at,
            last_fetched_at=u.last_fetched_at,
            status=u.status,
            content_title=u.content_title,
        )
        for u in urls
    ]"""

cb_add_old = """    url = payload.url.strip()
    if not url.startswith((\"http://\", \"https://\")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=\"URL invalide. Veuillez fournir une URL commençant par http:// ou https://.\",
        )

    ref_url = TenantReferenceUrl(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        url=url,
        label=payload.label.strip() if payload.label else None,
        added_by=user_uuid,
        added_at=datetime.now(timezone.utc),
        status=\"active\",
    )
    db.add(ref_url)
    await db.commit()

    return TenantReferenceUrlOut(
        id=str(ref_url.id),
        tenant_id=str(ref_url.tenant_id),
        url=ref_url.url,
        label=ref_url.label,
        added_by=str(ref_url.added_by) if ref_url.added_by else None,
        added_at=ref_url.added_at,
        last_fetched_at=ref_url.last_fetched_at,
        status=ref_url.status,
    )"""
cb_add_new = """    url = payload.url.strip()
    if not url.startswith((\"http://\", \"https://\")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=\"URL invalide. Veuillez fournir une URL commençant par http:// ou https://.\",
        )

    count_stmt = select(func.count()).select_from(TenantReferenceUrl).where(
        TenantReferenceUrl.tenant_id == t_uuid,
    )
    existing_count = (await db.execute(count_stmt)).scalar_one()
    if existing_count >= MAX_TENANT_REFERENCE_URLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f\"Limite de {MAX_TENANT_REFERENCE_URLS} sites de référence atteinte. \"
                \"Supprimez-en un avant d'en ajouter un nouveau (garde-fou de coût : chaque \"
                \"site est relu à chaque génération de section).\"
            ),
        )

    ref_url = TenantReferenceUrl(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        url=url,
        label=payload.label.strip() if payload.label else None,
        added_by=user_uuid,
        added_at=datetime.now(timezone.utc),
        status=\"active\",
    )

    # Recuperation immediate du contenu (03/09) : sans ce fetch, une URL fraichement ajoutee
    # restait invisible de la generation jusqu'a un clic manuel sur \"Actualiser\" -- jamais
    # fait en pratique. Echec de fetch = statut \"broken\" mais l'URL reste enregistree
    # (l'utilisateur peut reessayer via \"Actualiser\" une fois le site accessible).
    from app.services.company_bootstrap_service import company_bootstrap_service
    try:
        page_data = await company_bootstrap_service.fetch_page_content(url)
    except Exception as fetch_exc:
        logger.warning(\"[company_bootstrap.py] fetch_page_content failed on add for %s: %s\", url, fetch_exc)
        page_data = None

    if page_data:
        ref_url.content_title = page_data.get(\"title\")
        ref_url.content_excerpt = page_data.get(\"text\")
        ref_url.last_fetched_at = datetime.now(timezone.utc)
        ref_url.status = \"active\"
    else:
        ref_url.status = \"broken\"

    db.add(ref_url)
    await db.commit()

    return TenantReferenceUrlOut(
        id=str(ref_url.id),
        tenant_id=str(ref_url.tenant_id),
        url=ref_url.url,
        label=ref_url.label,
        added_by=str(ref_url.added_by) if ref_url.added_by else None,
        added_at=ref_url.added_at,
        last_fetched_at=ref_url.last_fetched_at,
        status=ref_url.status,
        content_title=ref_url.content_title,
    )"""

cb_refresh_old = """    from app.services.company_bootstrap_service import company_bootstrap_service
    page_data = await company_bootstrap_service.fetch_page_content(ref_url.url)

    if page_data:
        ref_url.last_fetched_at = datetime.now(timezone.utc)
        ref_url.status = \"active\"
        await db.commit()
        return {\"success\": True, \"message\": f\"URL '{ref_url.url}' actualisée avec succès.\", \"title\": page_data[\"title\"]}
    else:
        ref_url.status = \"broken\"
        await db.commit()
        return {\"success\": False, \"message\": f\"Impossible de joindre l'URL '{ref_url.url}'.\", \"status\": \"broken\"}"""
cb_refresh_new = """    from app.services.company_bootstrap_service import company_bootstrap_service
    page_data = await company_bootstrap_service.fetch_page_content(ref_url.url)

    if page_data:
        ref_url.last_fetched_at = datetime.now(timezone.utc)
        ref_url.status = \"active\"
        ref_url.content_title = page_data.get(\"title\")
        ref_url.content_excerpt = page_data.get(\"text\")
        await db.commit()
        return {\"success\": True, \"message\": f\"URL '{ref_url.url}' actualisée avec succès.\", \"title\": page_data[\"title\"]}
    else:
        ref_url.status = \"broken\"
        await db.commit()
        return {\"success\": False, \"message\": f\"Impossible de joindre l'URL '{ref_url.url}'.\", \"status\": \"broken\"}"""

patch(f"{BASE}/api/company_bootstrap.py", [
    (cb_import_old, cb_import_new, 1),
    (cb_cap_old, cb_cap_new, 1),
    (cb_list_old, cb_list_new, 1),
    (cb_add_old, cb_add_new, 1),
    (cb_refresh_old, cb_refresh_new, 1),
], "company_bootstrap.py")

# ---------- 4. tasks.py ----------
tk_import_old = "from app.models.entities import DCECriterionEntity, DCEDocument, DCEEmbedding, ExportJob, ExportTemplate, GeneratedSection, KnowledgeVector, LlmCatalogModel, LlmUsageLog, Project, ProjectDecision, ProjectGanttTask, CompanyAsset, Tenant, SharePointConnection, SharePointSyncItem"
tk_import_new = "from app.models.entities import DCECriterionEntity, DCEDocument, DCEEmbedding, ExportJob, ExportTemplate, GeneratedSection, KnowledgeVector, LlmCatalogModel, LlmUsageLog, Project, ProjectDecision, ProjectGanttTask, CompanyAsset, Tenant, SharePointConnection, SharePointSyncItem, TenantReferenceUrl"

tk_step_old = """                    web_sources_payload = [
                        {\"title\": r.title, \"url\": r.url, \"snippet\": r.snippet}
                        for r in web_results
                    ]

                # 8. Retrieve Tenant Custom System Prompt and Model Tier"""
tk_step_new = """                    web_sources_payload = [
                        {\"title\": r.title, \"url\": r.url, \"snippet\": r.snippet}
                        for r in web_results
                    ]

                # 7bis. Sites de reference ajoutes par le tenant (ex. site de l'acheteur
                # public vise, federation professionnelle...) -- INDEPENDANT du repli web
                # ci-dessus : contrairement a la recherche Serper, ce sont des sources que le
                # tenant a explicitement demande d'utiliser a CHAQUE generation pour coller
                # au plus pres du client vise (garde-fou de cout : MAX_TENANT_REFERENCE_URLS
                # sites au total -- voir company_bootstrap.py -- contenu de chacun re-borne a
                # CONTEXT_LIMITS[\"client_sites\"] caracteres au moment du prompt, voir
                # llm_generator.py).
                client_sites_stmt = select(TenantReferenceUrl).where(
                    TenantReferenceUrl.tenant_id == tenant_uuid,
                    TenantReferenceUrl.status == \"active\",
                    TenantReferenceUrl.content_excerpt.isnot(None),
                ).order_by(TenantReferenceUrl.added_at.desc())
                client_sites_res = await db.execute(client_sites_stmt)
                client_sites_payload = [
                    {
                        \"title\": u.content_title or u.label or u.url,
                        \"url\": u.url,
                        \"content\": u.content_excerpt,
                    }
                    for u in client_sites_res.scalars().all()
                ]

                # 8. Retrieve Tenant Custom System Prompt and Model Tier"""

tk_call_old = """                    rag_web_sources=web_sources_payload,
                    tenant_learnings=tenant_learnings_payload,"""
tk_call_new = """                    rag_web_sources=web_sources_payload,
                    rag_client_sites=client_sites_payload,
                    tenant_learnings=tenant_learnings_payload,"""

patch(f"{BASE}/workers/tasks.py", [
    (tk_import_old, tk_import_new, 1),
    (tk_step_old, tk_step_new, 1),
    (tk_call_old, tk_call_new, 1),
], "tasks.py")

print("ALL PATCHES APPLIED SUCCESSFULLY")
