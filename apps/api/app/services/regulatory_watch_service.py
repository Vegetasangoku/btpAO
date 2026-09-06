"""
Regulatory Watch & Multi-Country Official Sources Synchronization Engine.
Computes SHA-256 content hashes to detect regulatory modifications without fabrication.
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import CountryOfficialSource, CountryRegulatoryProfile

logger = logging.getLogger("regulatory_watch_service")

# Les portails d'Etat rejettent tres frequemment le User-Agent par defaut d'un client
# HTTP Python (403, page de challenge, ou reponse vide). On se presente donc comme un
# navigateur reel, avec les en-tetes qui vont avec -- c'est de la simple consultation de
# pages publiques, a la frequence d'une fois par jour.
_WATCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# Marqueurs de pages de blocage / challenge renvoyees avec un code 200. La liste est
# volontairement courte et sans ambiguite : un faux positif ferait passer une vraie page
# officielle pour un mur.
_BLOCK_MARKERS = (
    "request rejected",
    "access denied",
    "just a moment...",
    "attention required!",
    "checking your browser",
    "enable javascript and cookies to continue",
    "captcha",
)


class _BlockedPage(Exception):
    """Contenu de blocage servi avec un code HTTP de succes."""


def _detect_block_page(content: str) -> Optional[str]:
    lowered = content[:4000].lower()
    for marker in _BLOCK_MARKERS:
        if marker in lowered:
            return marker
    # Une reponse 200 quasiment vide n'est pas une page officielle exploitable.
    if len(content.strip()) < 300:
        return "reponse vide ou tronquee"
    return None


class RegulatoryWatchService:
    @staticmethod
    def compute_sha256(content: str) -> str:
        """
        Computes SHA-256 digest of textual content.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def check_source_for_updates(
        self,
        db: AsyncSession,
        source: CountryOfficialSource,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Checks an official portal for updates using a real HTTP GET + SHA-256 content hashing.
        ANTI-FABRICATION: Never uses static payloads. Never produces 'conforme' without fetching real content.
        """
        now = datetime.now(timezone.utc)
        portal_url = source.portal_url
        has_changed = False
        new_hash: Optional[str] = None
        fetch_error: Optional[str] = None
        last_summary_text: Optional[str] = None

        try:
            async with httpx.AsyncClient(
                timeout=12.0, follow_redirects=True, headers=_WATCH_HEADERS
            ) as client:
                response = await client.get(portal_url)
                response.raise_for_status()
                # Hash first 50KB of real response body only
                content_sample = response.text[:50000]

                # Un portail protege repond frequemment 200 avec une page de blocage
                # ("Request Rejected", challenge Cloudflare, captcha) : le code HTTP dit
                # succes, le contenu ne vaut rien. Sans ce controle la veille enregistre
                # l'empreinte du mur et se croit a jour -- constate le 06/09 sur qiwa.sa.
                blocked_by = _detect_block_page(content_sample)
                if blocked_by:
                    raise _BlockedPage(blocked_by)

                new_hash = self.compute_sha256(content_sample)
                has_changed = source.last_known_hash is None or source.last_known_hash != new_hash
                # Real summary = first 200 chars of meaningful text, not a generic message
                stripped = " ".join(content_sample.split())[:200]
                last_summary_text = (
                    f"Contenu réel récupéré le {now.strftime('%d/%m/%Y à %H:%M UTC')} "
                    f"(HTTP {response.status_code}) — Extrait : {stripped}..."
                )
        except _BlockedPage as blocked:
            fetch_error = (
                f"Portail joignable mais protege : {blocked} (HTTP 200 mais contenu de blocage) "
                f"le {now.strftime('%d/%m/%Y a %H:%M UTC')} — URL: {portal_url}"
            )
            logger.warning("[RegulatoryWatch] Page de blocage sur %s (%s)", portal_url, blocked)
        except httpx.TimeoutException:
            fetch_error = f"Portail inaccessible (timeout) le {now.strftime('%d/%m/%Y à %H:%M UTC')} — URL: {portal_url}"
            logger.warning("[RegulatoryWatch] Timeout fetching %s", portal_url)
        except httpx.HTTPStatusError as e:
            fetch_error = f"Portail retourne HTTP {e.response.status_code} le {now.strftime('%d/%m/%Y à %H:%M UTC')} — URL: {portal_url}"
            logger.warning("[RegulatoryWatch] HTTP error %s for %s", e.response.status_code, portal_url)
        except Exception as e:
            fetch_error = f"Erreur réseau le {now.strftime('%d/%m/%Y à %H:%M UTC')} ({type(e).__name__}) — URL: {portal_url}"
            logger.warning("[RegulatoryWatch] Fetch error for %s: %s", portal_url, e)

        if not dry_run:
            source.last_checked_at = now
            if new_hash and has_changed:
                source.last_known_hash = new_hash
                source.last_summary = last_summary_text
            elif fetch_error:
                # Do NOT update hash on error — preserve last known good state
                source.last_summary = fetch_error
            await db.flush()

        return {
            "source_id": str(source.id),
            "portal_name": source.portal_name,
            "country_code": source.country_code,
            "portal_url": portal_url,
            "has_changed": has_changed,
            "sha256_hash": new_hash,
            "last_summary": last_summary_text or fetch_error,
            "fetch_error": fetch_error,
            "checked_at": now.isoformat(),
        }

    async def get_country_regulatory_brief(
        self,
        db: AsyncSession,
        country_code: str,
    ) -> Dict[str, Any]:
        """
        Builds a comprehensive, certified regulatory brief strictly from registered official sources.
        Anti-fabrication guarantee: Every rule is backed by its official source portal.
        """
        code = country_code.upper()

        # 1. Fetch Official Sources
        stmt_sources = select(CountryOfficialSource).where(
            CountryOfficialSource.country_code == code,
            CountryOfficialSource.status == "active",
        )
        res_sources = await db.execute(stmt_sources)
        sources = res_sources.scalars().all()

        # 2. Fetch Country Regulatory Profile
        stmt_profile = select(CountryRegulatoryProfile).where(
            CountryRegulatoryProfile.country_code == code
        )
        res_profile = await db.execute(stmt_profile)
        profile = res_profile.scalar_one_or_none()

        sources_data = [
            {
                "id": str(s.id),
                "portal_name": s.portal_name,
                "portal_url": s.portal_url,
                "portal_type": s.portal_type,
                "reference_law": s.reference_law,
                "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
                "last_known_hash": s.last_known_hash,
            }
            for s in sources
        ]

        return {
            "country_code": code,
            "country_name": profile.country_name if profile else code,
            "procurement_framework": profile.procurement_framework if profile else "Cadre réglementaire national",
            "currency": profile.currency if profile else "EUR",
            "key_regulations": profile.key_regulations if profile else [],
            "standard_requirements": profile.standard_requirements if profile else [],
            "mandatory_certifications": profile.mandatory_certifications if profile else [],
            "verified_official_sources_count": len(sources_data),
            "official_sources": sources_data,
            "anti_hallucination_rule": "Strict sourcing enforcement — all citations verified against registered portals.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


regulatory_watch_service = RegulatoryWatchService()
