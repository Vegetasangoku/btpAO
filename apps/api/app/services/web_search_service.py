"""
Web Search Service with Multi-Tenant Scoping, Multi-Provider Support (Brave Search / Serper),
Cost Tracking, Source Citations & GDPR / Data Privacy Compliance.
NEVER generates fabricated search results outside of automated test mode.
"""
import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger("web_search_service")

# Query cost estimates in USD
SERPER_COST_PER_QUERY_USD = 0.001
BRAVE_COST_PER_QUERY_USD = 0.003


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source_type: str = "web"
    position: int = 1
    provider: str = "serper"


class WebSearchService:
    def __init__(self):
        self.provider = settings.WEB_SEARCH_PROVIDER

    @property
    def serper_api_key(self) -> Optional[str]:
        return settings.SERPER_API_KEY

    @property
    def brave_api_key(self) -> Optional[str]:
        return settings.BRAVE_SEARCH_API_KEY

    async def search(
        self,
        tenant_id: str,
        query: str,
        num_results: int = 4,
        project_id: Optional[str] = None,
        prefer_provider: Optional[str] = None,
        allowed_sites: Optional[List[str]] = None,
    ) -> List[WebSearchResult]:
        """
        Executes a targeted web search strictly scoped to the tenant's request.
        Supports automatic provider failover (Brave Search <-> Serper).
        Adheres to GDPR data minimization for company and public procurement lookups.

        allowed_sites: when provided (non-empty), the search is STRICTLY restricted to these
        domains -- via a `site:` filter added to the provider query AND a hard post-filter on
        returned URLs (defense in depth: a provider ignoring/mishandling `site:` must never
        leak an off-allowlist result to the caller). An explicit empty list means "tenant has
        configured zero reference sites" and short-circuits to zero results without ever
        calling a provider -- this must never be mistaken for "unrestricted". Passing None
        (the default) preserves the original unrestricted behavior for existing callers
        (project DCE assistant, section generation, company bootstrap scan).
        """
        logger.info(
            f"[WebSearch] Tenant {tenant_id} | Project {project_id} | Query: '{query}' | "
            f"Provider Config: {self.provider} (prefer: {prefer_provider}) | "
            f"Allowed sites: {allowed_sites if allowed_sites is not None else 'unrestricted'}"
        )

        if allowed_sites is not None and len(allowed_sites) == 0:
            logger.info("[WebSearch] allowed_sites explicitly empty -- skipping search entirely (no provider call).")
            return []

        is_test_env = settings.APP_ENV in ("test", "testing")
        if is_test_env:
            return self._filter_by_allowed_sites(self._generate_mock_results(query, num_results), allowed_sites)

        effective_query = query
        if allowed_sites:
            site_filter = " OR ".join(f"site:{d}" for d in allowed_sites)
            effective_query = f"{query} ({site_filter})"

        # Provider determination
        active_provider = prefer_provider or self.provider

        # 1. Try Brave Search if requested/configured
        if active_provider == "brave" or (active_provider == "auto" and self.brave_api_key):
            brave_res = await self._search_brave(effective_query, num_results)
            if brave_res:
                return self._filter_by_allowed_sites(brave_res, allowed_sites)
            logger.info("[WebSearch] Brave search returned 0 results or failed, attempting Serper fallback.")

        # 2. Try Serper (Google Search API)
        if self.serper_api_key:
            serper_res = await self._search_serper(effective_query, num_results)
            if serper_res:
                return self._filter_by_allowed_sites(serper_res, allowed_sites)

        # 3. If primary was Serper and failed, try Brave as fallback
        if self.brave_api_key and active_provider != "brave":
            brave_res = await self._search_brave(effective_query, num_results)
            if brave_res:
                return self._filter_by_allowed_sites(brave_res, allowed_sites)

        logger.warning(
            f"[WebSearch] No active search provider API keys configured or queries failed. "
            f"Returning 0 results to prevent fake citations."
        )
        return []

    @staticmethod
    def _filter_by_allowed_sites(
        results: List[WebSearchResult], allowed_sites: Optional[List[str]]
    ) -> List[WebSearchResult]:
        """Defense-in-depth post-filter: drops any result whose URL domain isn't in
        allowed_sites, in case a provider ignored the `site:` filter. No-op (returns results
        unchanged) when allowed_sites is None, i.e. unrestricted mode."""
        if not allowed_sites:
            return results
        from urllib.parse import urlparse
        allowed_set = set(allowed_sites)
        kept = []
        for r in results:
            domain = urlparse(r.url).netloc
            if any(domain == d or domain.endswith(f".{d}") for d in allowed_set):
                kept.append(r)
        return kept

    async def _search_serper(self, query: str, num_results: int) -> List[WebSearchResult]:
        if not self.serper_api_key:
            return []
        try:
            headers = {
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "q": query,
                "gl": "fr",
                "hl": "fr",
                "num": num_results,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://google.serper.dev/search", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for idx, item in enumerate(data.get("organic", [])[:num_results], start=1):
                        results.append(
                            WebSearchResult(
                                title=item.get("title", "Source Web"),
                                url=item.get("link", ""),
                                snippet=item.get("snippet", ""),
                                position=idx,
                                provider="serper",
                            )
                        )
                    return results
        except Exception as e:
            logger.error(f"[WebSearch] Serper API error: {e}")
        return []

    async def _search_brave(self, query: str, num_results: int) -> List[WebSearchResult]:
        if not self.brave_api_key:
            return []
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.brave_api_key,
            }
            params = {
                "q": query,
                "count": num_results,
                "country": "FR",
                "search_lang": "fr",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://api.search.brave.com/res/v1/web/search", params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    web_items = data.get("web", {}).get("results", [])
                    for idx, item in enumerate(web_items[:num_results], start=1):
                        results.append(
                            WebSearchResult(
                                title=item.get("title", "Source Web"),
                                url=item.get("url", ""),
                                snippet=item.get("description", ""),
                                position=idx,
                                provider="brave",
                            )
                        )
                    return results
        except Exception as e:
            logger.error(f"[WebSearch] Brave Search API error: {e}")
        return []

    def _generate_mock_results(self, query: str, num_results: int) -> List[WebSearchResult]:
        """
        Deterministic mock results used EXCLUSIVELY in test/testing environments.
        """
        q_lower = query.lower()

        if "re2020" in q_lower or "carbone" in q_lower or "cem iii" in q_lower:
            return [
                WebSearchResult(
                    title="Réglementation Environnementale RE2020 - Seuils Carbone Gros Œuvre",
                    url="https://www.ecologie.gouv.fr/reglementation-environnementale-re2020",
                    snippet="La RE2020 impose pour les bâtiments collectifs un seuil carbone max Ic_construction à respecter, favorisant l'usage de bétons bas carbone CEM III/A ou CEM III/B avec FDES vérifiées INIES.",
                    position=1,
                    provider="test_fixture",
                ),
                WebSearchResult(
                    title="Bases INIES - Fiches FDES Bétons Prêts à l'Emploi à faible empreinte",
                    url="https://www.inies.fr/donnees-environnementales-fdes-beton",
                    snippet="Données environnementales vérifiées CSTB : les bétons à liant de laitier moulu réduisent l'empreinte CO2 de 45% par rapport au CEM I standard.",
                    position=2,
                    provider="test_fixture",
                ),
            ][:num_results]

        if "dtu" in q_lower or "norme" in q_lower or "fondation" in q_lower:
            return [
                WebSearchResult(
                    title="NF DTU 13.3 - Dallages : Conception, calcul et exécution",
                    url="https://www.afnor.org/normes/nf-dtu-13-3-dallages-beton",
                    snippet="Norme NF DTU 13.3 : Prescriptions techniques pour le dallage industriel et tertiaire. Épaisseur minimale 15cm, armature minimale treillis soudé ST25C et joints de retrait sciés tous les 25m².",
                    position=1,
                    provider="test_fixture",
                ),
                WebSearchResult(
                    title="CSTB - Guide d'application des Eurocodes 2 et 7 en géotechnique",
                    url="https://evaluation.cstb.fr/fr/eurocodes-fondations-profondes",
                    snippet="Règles de justification des fondations profondes et semelles superficielles selon NF EN 1997-1 et son annexe nationale.",
                    position=2,
                    provider="test_fixture",
                ),
            ][:num_results]

        if "déchet" in q_lower or "5 flux" in q_lower or "bsd" in q_lower:
            return [
                WebSearchResult(
                    title="Décret 7 flux BTP et Traçabilité Trackdéchets",
                    url="https://trackdechets.beta.gouv.fr/reglementation-btp-bsd",
                    snippet="Obligation de tri à la source des 7 flux de déchets de chantier (gravats, bois, métaux, plastique, plâtre, verre, papier) et émission obligatoire du Bordereau de Suivi de Déchets (BSD) électronique.",
                    position=1,
                    provider="test_fixture",
                )
            ][:num_results]

        return [
            WebSearchResult(
                title=f"Référence Technique BTP : {query}",
                url=f"https://www.batirama.com/guides-techniques/{query.replace(' ', '-').lower()}",
                snippet=f"Guide de mise en œuvre et préconisations de chantier pour {query} conformément aux règles professionnelles.",
                position=1,
                provider="test_fixture",
            )
        ][:num_results]


web_search_service = WebSearchService()
