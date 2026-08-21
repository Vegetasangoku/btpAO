"""
Web Search Service with Multi-Tenant Scoping, Cost Tracking & Source Citations.
Supports Serper (Google Search API).
NEVER generates fabricated search results outside of automated test mode.
"""
import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger("web_search_service")

# Serper cost per query
SERPER_COST_PER_QUERY_USD = 0.001


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source_type: str = "web"
    position: int = 1


class WebSearchService:
    def __init__(self):
        self.provider = settings.WEB_SEARCH_PROVIDER

    @property
    def api_key(self) -> Optional[str]:
        return settings.SERPER_API_KEY

    async def search(
        self,
        tenant_id: str,
        query: str,
        num_results: int = 4,
        project_id: Optional[str] = None,
    ) -> List[WebSearchResult]:
        """
        Executes a targeted web search strictly scoped to the tenant's request.
        Logs the query and cost estimate for tenant quota tracking.
        Outside of test environment, NEVER returns mock or fabricated results.
        """
        # Multi-tenant logging & cost tracking
        logger.info(
            f"[WebSearch] Tenant {tenant_id} | Project {project_id} | Query: '{query}' | "
            f"Provider: {self.provider} | Estimated Cost: ${SERPER_COST_PER_QUERY_USD:.4f}"
        )

        is_test_env = settings.APP_ENV in ("test", "testing")

        # 1. Non-test environment (development, staging, production)
        if not is_test_env:
            if not self.api_key:
                logger.warning(
                    f"[WebSearch] Serper API key (SERPER_API_KEY) is missing in {settings.APP_ENV} environment. "
                    f"Returning 0 web results to prevent fake/hallucinated citations."
                )
                return []

            try:
                headers = {
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "q": query,
                    "gl": "fr",
                    "hl": "fr",
                    "num": num_results,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://google.serper.dev/search",
                        json=payload,
                        headers=headers,
                    )
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
                                )
                            )
                        return results
                    else:
                        logger.error(
                            f"[WebSearch] Serper returned HTTP {resp.status_code}: {resp.text}. "
                            f"Returning 0 results to prevent hallucination."
                        )
                        return []
            except Exception as e:
                logger.error(
                    f"[WebSearch] Serper API request error: {e}. Returning 0 results to prevent hallucination."
                )
                return []

        # 2. Automated Test Mode ONLY: Return deterministic test fixtures
        return self._generate_mock_results(query, num_results)

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
                ),
                WebSearchResult(
                    title="Bases INIES - Fiches FDES Bétons Prêts à l'Emploi à faible empreinte",
                    url="https://www.inies.fr/donnees-environnementales-fdes-beton",
                    snippet="Données environnementales vérifiées CSTB : les bétons à liant de laitier moulu réduisent l'empreinte CO2 de 45% par rapport au CEM I standard.",
                    position=2,
                ),
            ][:num_results]

        if "dtu" in q_lower or "norme" in q_lower or "fondation" in q_lower:
            return [
                WebSearchResult(
                    title="NF DTU 13.3 - Dallages : Conception, calcul et exécution",
                    url="https://www.afnor.org/normes/nf-dtu-13-3-dallages-beton",
                    snippet="Norme NF DTU 13.3 : Prescriptions techniques pour le dallage industriel et tertiaire. Épaisseur minimale 15cm, armature minimale treillis soudé ST25C et joints de retrait sciés tous les 25m².",
                    position=1,
                ),
                WebSearchResult(
                    title="CSTB - Guide d'application des Eurocodes 2 et 7 en géotechnique",
                    url="https://evaluation.cstb.fr/fr/eurocodes-fondations-profondes",
                    snippet="Règles de justification des fondations profondes et semelles superficielles selon NF EN 1997-1 et son annexe nationale.",
                    position=2,
                ),
            ][:num_results]

        if "déchet" in q_lower or "5 flux" in q_lower or "bsd" in q_lower:
            return [
                WebSearchResult(
                    title="Décret 7 flux BTP et Traçabilité Trackdéchets",
                    url="https://trackdechets.beta.gouv.fr/reglementation-btp-bsd",
                    snippet="Obligation de tri à la source des 7 flux de déchets de chantier (gravats, bois, métaux, plastique, plâtre, verre, papier) et émission obligatoire du Bordereau de Suivi de Déchets (BSD) électronique.",
                    position=1,
                )
            ][:num_results]

        # Generic technical search fallback for tests
        return [
            WebSearchResult(
                title=f"Référence Technique BTP : {query}",
                url=f"https://www.batirama.com/guides-techniques/{query.replace(' ', '-').lower()}",
                snippet=f"Guide de mise en œuvre et préconisations de chantier pour {query} conformément aux règles professionnelles.",
                position=1,
            )
        ][:num_results]


web_search_service = WebSearchService()
