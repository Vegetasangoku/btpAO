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


# Types de moteurs pris en charge, exposes tels quels a l'administration.
SUPPORTED_SEARCH_TYPES = [
    {"type": "serper", "label": "Serper (Google)", "cost_per_query_usd": SERPER_COST_PER_QUERY_USD,
     "key_hint": "Cle API Serper (serper.dev)"},
    {"type": "brave", "label": "Brave Search", "cost_per_query_usd": BRAVE_COST_PER_QUERY_USD,
     "key_hint": "Jeton d'abonnement Brave Search API"},
]


def resolve_search_providers(conf: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Construit la liste effective des fournisseurs a partir de la configuration plateforme.

    Cles dechiffrees ici. Compatibilite ascendante assuree : une installation qui n'a que
    les anciens champs serper_api_key / brave_search_api_key, ou seulement des variables
    d'environnement, obtient la meme liste sans aucune migration.
    """
    from app.core.crypto_vault import decrypt_api_key

    raw = conf.get("web_search_providers")
    providers: List[Dict[str, Any]] = []

    if isinstance(raw, list) and raw:
        for i, p in enumerate(raw):
            key_enc = p.get("api_key") or ""
            try:
                key = decrypt_api_key(key_enc) if key_enc else ""
            except Exception:  # noqa: BLE001
                key = ""
            providers.append({
                "id": p.get("id") or p.get("type") or f"provider_{i}",
                "name": p.get("name") or p.get("type") or "Fournisseur",
                "type": p.get("type") or "serper",
                "api_key": key,
                "enabled": bool(p.get("enabled", True)),
                "priority": int(p.get("priority", i + 1)),
            })
        return providers

    # Repli : anciens champs, puis environnement.
    legacy = [
        ("serper", "Serper (Google)", conf.get("serper_api_key"), settings.SERPER_API_KEY),
        ("brave", "Brave Search", conf.get("brave_search_api_key"), settings.BRAVE_SEARCH_API_KEY),
    ]
    preferred = conf.get("web_search_provider") or settings.WEB_SEARCH_PROVIDER or "serper"
    for i, (ptype, label, enc, env_val) in enumerate(legacy):
        key = ""
        if enc:
            try:
                key = decrypt_api_key(enc) or ""
            except Exception:  # noqa: BLE001
                key = ""
        key = key or (env_val or "")
        providers.append({
            "id": ptype, "name": label, "type": ptype, "api_key": key,
            "enabled": bool(key), "priority": 1 if ptype == preferred else i + 2,
        })
    return providers


class WebSearchService:
    """
    Recherche web bornee a une whitelist de sites officiels.

    Les cles d'API sont configurables depuis l'administration (04/09) et non plus
    seulement par variable d'environnement : elles sont lues dans PlatformSettings
    (chiffrees au repos, meme coffre que les cles LLM), avec repli sur l'environnement.
    Un petit cache memoire evite un aller-retour base a chaque recherche.
    """

    _CACHE_TTL_SECONDS = 60

    def __init__(self):
        self.provider = settings.WEB_SEARCH_PROVIDER
        self._providers: List[Dict[str, Any]] = []
        self._resolved_at: float = 0.0

    async def _resolve_config(self) -> None:
        """
        Recharge la liste des fournisseurs de recherche depuis PlatformSettings.

        Format attendu (cle `web_search_providers`), une entree par fournisseur :
            {"id", "name", "type", "api_key" (chiffre), "enabled", "priority"}

        `type` designe l'adaptateur a utiliser (voir _ADAPTERS) : c'est ce qui rend la
        liste extensible sans redeploiement de schema -- ajouter un moteur revient a
        ecrire un adaptateur et a declarer une entree, pas a modifier la base.
        Compatibilite ascendante : si la liste est absente, on reconstruit deux entrees a
        partir des anciens champs serper_api_key / brave_search_api_key, ou de
        l'environnement. Aucune configuration existante n'est perdue.
        """
        import time as _time

        if self._providers and (_time.monotonic() - self._resolved_at) < self._CACHE_TTL_SECONDS:
            return

        conf: Dict[str, Any] = {}
        try:
            from sqlalchemy import select as _select
            from app.core.db import AsyncSessionLocal
            from app.models.entities import PlatformSettings

            # Session non filtree par le role tenant : la configuration plateforme est
            # globale, comme pour les taches inter-tenants.
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    _select(PlatformSettings).where(PlatformSettings.id == "global")
                )
                ps = res.scalar_one_or_none()
                conf = (ps.settings if ps and ps.settings else {}) or {}
        except Exception as exc:  # noqa: BLE001
            # La configuration en base est un confort : en cas d'echec on garde l'env.
            logger.warning("[WebSearch] Lecture de la configuration en base impossible : %s", exc)

        self._providers = resolve_search_providers(conf)
        self._resolved_at = _time.monotonic()

    @property
    def _resolved(self) -> Dict[str, Optional[str]]:
        """Compatibilite : expose les cles resolues par type, pour les proprietes ci-dessous."""
        out: Dict[str, Optional[str]] = {}
        for p in self._providers:
            out.setdefault(p.get("type"), p.get("api_key"))
        return out

    def invalidate_config_cache(self) -> None:
        """Appelee apres une sauvegarde en admin pour reprendre la nouvelle config aussitot."""
        self._providers = []
        self._resolved_at = 0.0

    @property
    def serper_api_key(self) -> Optional[str]:
        if self._resolved:
            return self._resolved.get("serper")
        return settings.SERPER_API_KEY

    @property
    def brave_api_key(self) -> Optional[str]:
        if self._resolved:
            return self._resolved.get("brave")
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
        # Recharge cles et fournisseur depuis l'administration (cache memoire 60 s).
        await self._resolve_config()
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
        # Cascade pilotee par la configuration (04/09) et non plus par deux cas codes en
        # dur : on parcourt les fournisseurs actifs dans l'ordre de priorite defini en
        # administration, et on s'arrete au premier qui rend des resultats. `prefer_provider`
        # (utilise par certains appelants) fait simplement passer ce type en tete.
        candidates = [p for p in self._providers if p.get("enabled") and p.get("api_key")]
        if prefer_provider:
            candidates.sort(key=lambda p: (p.get("type") != prefer_provider, p.get("priority", 99)))
        else:
            candidates.sort(key=lambda p: p.get("priority", 99))

        for prov in candidates:
            adapter = self._ADAPTERS.get(prov.get("type"))
            if not adapter:
                logger.warning(
                    "[WebSearch] Type de fournisseur inconnu '%s' (id=%s) -- ignore. "
                    "Ajouter un adaptateur dans _ADAPTERS pour le prendre en charge.",
                    prov.get("type"), prov.get("id"),
                )
                continue
            try:
                res = await adapter(self, effective_query, num_results, prov.get("api_key"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("[WebSearch] %s a echoue : %s", prov.get("id"), exc)
                continue
            if res:
                return self._filter_by_allowed_sites(res, allowed_sites)
            logger.info("[WebSearch] %s : 0 resultat, passage au fournisseur suivant.", prov.get("id"))

        logger.warning(
            "[WebSearch] Aucun fournisseur de recherche actif n'a rendu de resultat "
            "(%d configure(s)). Zero resultat renvoye plutot que des citations inventees.",
            len(candidates),
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

    async def _search_serper(self, query: str, num_results: int, api_key: Optional[str] = None) -> List[WebSearchResult]:
        key = api_key or self.serper_api_key
        if not key:
            return []
        try:
            headers = {
                "X-API-KEY": key,
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

    async def _search_brave(self, query: str, num_results: int, api_key: Optional[str] = None) -> List[WebSearchResult]:
        key = api_key or self.brave_api_key
        if not key:
            return []
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": key,
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

    # Registre type -> adaptateur. Ajouter un moteur = ecrire une methode _search_xxx
    # (signature : query, num_results, api_key) et l'inscrire ici. Rien d'autre a changer :
    # l'administration liste automatiquement les types disponibles.
    _ADAPTERS = {
        "serper": lambda self, q, n, k: self._search_serper(q, n, k),
        "brave": lambda self, q, n, k: self._search_brave(q, n, k),
    }

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
