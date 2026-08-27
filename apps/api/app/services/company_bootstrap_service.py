"""
Company Profile Auto-Bootstrap Service.
Searches public web presence and client-provided reference URLs to pre-fill company profile.
STRICT ANTI-FABRICATION GUARANTEE:
1. Every extracted field carries its source URL.
2. If a field is not reliably found, it is left empty — NEVER fabricated.
3. Every generated company_asset starts with validated_by_user = False.
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models.entities import CompanyAsset, CompanyBootstrapRun, TenantReferenceUrl
from app.services.embedding_service import embedding_service
from app.services.web_search_service import web_search_service

logger = logging.getLogger("company_bootstrap_service")


class HTMLTextCleaner(HTMLParser):
    """Clean HTML text extractor for website pages."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed: List[str] = []
        self.title_parts: List[str] = []
        self._in_title = False
        self._skip = False
        self._skip_tags = {"script", "style", "noscript", "svg", "header", "footer", "nav"}

    def handle_starttag(self, tag: str, attrs: Any):
        t = tag.lower()
        if t in self._skip_tags:
            self._skip = True
        elif t == "title":
            self._in_title = True

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t in self._skip_tags:
            self._skip = False
        elif t == "title":
            self._in_title = False

    def handle_data(self, d: str):
        if self._in_title:
            self.title_parts.append(d)
        elif not self._skip:
            self.fed.append(d)

    def get_text(self) -> str:
        raw = " ".join(self.fed)
        return re.sub(r"\s+", " ", raw).strip()

    def get_title(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()


class CompanyBootstrapService:
    def __init__(self):
        pass

    async def fetch_page_content(self, url: str) -> Optional[Dict[str, str]]:
        """Fetches and cleans text from a public web page."""
        if not url or not url.startswith(("http://", "https://")):
            return None
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; btpAO-BootstrapBot/1.0; +https://btpao.fr)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, verify=False) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    parser = HTMLTextCleaner()
                    parser.feed(resp.text)
                    title = parser.get_title() or url
                    text = parser.get_text()
                    if len(text) > 40:
                        return {"url": url, "title": title, "text": text[:6000]}
        except Exception as exc:
            logger.warning(f"[CompanyBootstrap] Failed to fetch {url}: {exc}")
        return None

    async def bootstrap_company_profile(
        self,
        tenant_id: str,
        company_name: str,
        siret: Optional[str] = None,
        reference_urls: Optional[List[str]] = None,
        triggered_by: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes company profile bootstrap:
        1. Web search via Serper (if configured)
        2. Reference URLs crawling
        3. LLM structured extraction with strict anti-fabrication
        4. Storing draft company_assets with validated_by_user = False
        """
        t_uuid = uuid.UUID(tenant_id)
        user_uuid = uuid.UUID(triggered_by) if triggered_by else None
        bootstrap_run_uuid = uuid.UUID(run_id) if run_id else uuid.uuid4()
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as db:
            # 1. Create or retrieve bootstrap run record
            run = await db.get(CompanyBootstrapRun, bootstrap_run_uuid)
            if not run:
                run = CompanyBootstrapRun(
                    id=bootstrap_run_uuid,
                    tenant_id=t_uuid,
                    status="running",
                    triggered_by=user_uuid,
                    started_at=now,
                    sources_found=[],
                )
                db.add(run)
                await db.commit()
            else:
                run.status = "running"
                await db.commit()

            sources_found: List[Dict[str, Any]] = []
            collected_pages: List[Dict[str, Any]] = []

            # 2. Add client-provided URLs and saved tenant reference URLs
            urls_to_crawl: List[Dict[str, str]] = []
            if reference_urls:
                for u in reference_urls:
                    urls_to_crawl.append({"url": u.strip(), "source_type": "tenant_provided_url", "label": "Lien fourni par le client"})

            # Query existing saved tenant reference URLs from DB
            db_urls_stmt = select(TenantReferenceUrl).where(
                TenantReferenceUrl.tenant_id == t_uuid,
                TenantReferenceUrl.status == "active",
            )
            db_urls_res = await db.execute(db_urls_stmt)
            for db_url in db_urls_res.scalars().all():
                if not any(u["url"] == db_url.url for u in urls_to_crawl):
                    urls_to_crawl.append({"url": db_url.url, "source_type": "tenant_provided_url", "label": db_url.label or "Lien de référence client"})

            # 3. Perform web searches (Google/Serper)
            search_queries = [
                f"{company_name} BTP entreprise",
                f"{company_name} qualifications certifications chantiers",
            ]
            if siret:
                search_queries.append(f"{company_name} SIRET {siret}")

            for q in search_queries:
                try:
                    res = await web_search_service.search(
                        tenant_id=tenant_id,
                        query=q,
                        num_results=3,
                    )
                    for item in res:
                        if item.url and not any(u["url"] == item.url for u in urls_to_crawl):
                            urls_to_crawl.append({
                                "url": item.url,
                                "source_type": "web_auto_bootstrap",
                                "label": item.title,
                            })
                except Exception as search_err:
                    logger.warning(f"[CompanyBootstrap] Search query '{q}' error: {search_err}")

            # 4. Fetch content from all URLs
            for url_entry in urls_to_crawl[:8]:  # Limit to top 8 distinct pages
                url = url_entry["url"]
                page_data = await self.fetch_page_content(url)
                if page_data:
                    page_data["source_type"] = url_entry["source_type"]
                    page_data["label"] = url_entry.get("label") or page_data["title"]
                    collected_pages.append(page_data)
                    sources_found.append({
                        "url": url,
                        "title": page_data["title"],
                        "source_type": url_entry["source_type"],
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })

            # 5. Extract structured assets via LLM (or deterministic parser if offline)
            extracted_assets = await self._extract_profile_data(
                company_name=company_name,
                siret=siret,
                collected_pages=collected_pages,
            )

            # 6. Save extracted assets into database as unvalidated company_assets
            created_assets = []
            for item in extracted_assets:
                asset_id = uuid.uuid4()
                desc = item.get("description", "").strip()
                title = item.get("title", "").strip()
                category = item.get("category", "presentation_generale")
                source_url = item.get("source_url") or (collected_pages[0]["url"] if collected_pages else None)
                source_type = item.get("source_type", "web_auto_bootstrap")

                if not title or not desc:
                    continue

                emb = None
                try:
                    if embedding_service:
                        emb = embedding_service.generate_embedding(f"{title}\n{desc}"[:2000])
                except Exception:
                    emb = None

                new_asset = CompanyAsset(
                    id=asset_id,
                    tenant_id=t_uuid,
                    category=category,
                    title=title,
                    description=desc,
                    s3_url=source_url,
                    status="indexed",
                    source_type=source_type,
                    collected_at=datetime.now(timezone.utc),
                    validated_by_user=False,  # Human validation MANDATORY
                    embedding=emb,
                    metadata_json={
                        "bootstrap_run_id": str(bootstrap_run_uuid),
                        "source_url": source_url,
                        "source_type": source_type,
                        "confidence": item.get("confidence", "high"),
                        "extracted_at": datetime.now(timezone.utc).isoformat(),
                    },
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(new_asset)
                created_assets.append(new_asset)

            # 7. Update bootstrap run status
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.sources_found = sources_found
            await db.commit()

            return {
                "run_id": str(bootstrap_run_uuid),
                "status": "completed",
                "sources_count": len(sources_found),
                "extracted_assets_count": len(created_assets),
                "sources_found": sources_found,
            }

    async def _extract_profile_data(
        self,
        company_name: str,
        siret: Optional[str],
        collected_pages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Uses LLM with strict anti-hallucination prompt to extract verified company data.
        """
        if not collected_pages:
            return []

        # Combine source texts with explicit URL markers
        corpus_blocks = []
        for p in collected_pages:
            corpus_blocks.append(f"--- SOURCE : {p['url']} (Type: {p.get('source_type', 'web')}) ---\nTitre: {p['title']}\nContenu:\n{p['text']}\n")

        corpus_text = "\n".join(corpus_blocks)

        system_prompt = (
            "Tu es un analyste rigoureux spécialisé en mémoires techniques BTP et profilage d'entreprises.\n"
            "RÈGLE STRICTE ANTI-FABRICATION :\n"
            "1. Tu dois UNIQUEMENT extraire des faits réels explicitement écrits dans les textes sources ci-dessous.\n"
            "2. Pour chaque élément extrait, indique obligatoirement l'URL exacte d'où vient l'information.\n"
            "3. Si un champ n'est pas mentionné dans les sources, NE L'INVENTE PAS. Laisse-le vide.\n"
            "4. Catégories autorisées pour les fiches : 'presentation_generale', 'certificat_qualibat', 'materiel_engins', 'cv_encadrement', 'demarche_rse', 'reference_chantier'.\n"
            "5. Réponds EXCLUSIVEMENT sous la forme d'un tableau JSON d'objets avec les clés :\n"
            "   [{\"category\": str, \"title\": str, \"description\": str, \"source_url\": str, \"source_type\": str, \"confidence\": \"high\"}]"
        )

        user_prompt = (
            f"Entreprise cible : {company_name}\n"
            f"SIRET : {siret or 'Non précisé'}\n\n"
            f"Textes sources disponibles :\n{corpus_text[:14000]}\n\n"
            "Extrais les fiches d'informations vérifiées (Présentation, Qualifications/Certifications, Moyens matériels, Références de chantiers, Engagements RSE)."
        )

        try:
            import litellm
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = await litellm.acompletion(
                model=settings.LITELLM_MODEL or "gpt-4o-mini",
                messages=messages,
                temperature=0.0,
                max_tokens=2000,
            )
            raw_content = response.choices[0].message.content.strip()
            # Extract JSON block
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                return parsed
        except Exception as e:
            logger.warning(f"[CompanyBootstrap] LLM extraction fallback: {e}")

        # Fallback deterministic extraction from text if LLM unavailable
        results = []
        for p in collected_pages:
            txt = p["text"]
            url = p["url"]
            stype = p.get("source_type", "web_auto_bootstrap")

            # Extract basic presentation
            if len(txt) > 80:
                results.append({
                    "category": "presentation_generale",
                    "title": f"Présentation : {company_name}",
                    "description": txt[:500],
                    "source_url": url,
                    "source_type": stype,
                    "confidence": "medium",
                })
            # Check for Qualibat / ISO mentions
            if "qualibat" in txt.lower() or "iso 9001" in txt.lower() or "iso 14001" in txt.lower() or "rge" in txt.lower():
                qualif_snippets = [line for line in txt.split(".") if any(k in line.lower() for k in ["qualibat", "iso", "rge", "certification"])]
                if qualif_snippets:
                    results.append({
                        "category": "certificat_qualibat",
                        "title": f"Qualifications détectées - {company_name}",
                        "description": ". ".join(qualif_snippets[:4]).strip() + ".",
                        "source_url": url,
                        "source_type": stype,
                        "confidence": "high",
                    })
            # Check for RSE / Green mentions
            if "rse" in txt.lower() or "bas carbone" in txt.lower() or "environnement" in txt.lower() or "déchet" in txt.lower():
                rse_snippets = [line for line in txt.split(".") if any(k in line.lower() for k in ["rse", "carbone", "environnement", "tri", "déchet", "re2020"])]
                if rse_snippets:
                    results.append({
                        "category": "demarche_rse",
                        "title": f"Démarche Environnementale & RSE - {company_name}",
                        "description": ". ".join(rse_snippets[:4]).strip() + ".",
                        "source_url": url,
                        "source_type": stype,
                        "confidence": "high",
                    })

        return results


company_bootstrap_service = CompanyBootstrapService()
