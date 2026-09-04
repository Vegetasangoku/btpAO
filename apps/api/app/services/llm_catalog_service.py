"""
Catalogue de modèles LLM certifié LiteLLM & Synchronisation Dynamique.

Le catalogue alimente l'administration et le journal de consommation (llm_usage_logs) :
1. Source primaire : Base de données officielle interne de LiteLLM (litellm.model_cost)
   - Contient tous les identifiants officiels testables et exécutables sans hypothèse ni invention
   - Prix officiels exacts convertis au million de tokens (prompt / completion)
   - Fenêtres de contexte maximales certifiées
   - Résistant à 100% aux pannes réseau (disponible localement en toute circonstance)
2. Source secondaire : API publique OpenRouter en complément si connectivité disponible
3. Synchronisation nocturne automatique quotidienne via Celery Beat (4h00) ou à la demande
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import httpx
import litellm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import LlmCatalogModel
from app.services.llm_reference_catalog import REFERENCE_AS_OF, REFERENCE_MODELS

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
SUPPORTED_PROVIDERS = {"anthropic", "openai", "mistral", "gemini", "deepseek"}


def _to_per_million(raw_price_per_token: Any) -> Optional[Decimal]:
    """Convertit un prix unitaire par token en USD pour 1M tokens."""
    if raw_price_per_token is None:
        return None
    try:
        return Decimal(str(raw_price_per_token)) * Decimal(1_000_000)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _extract_provider_slug(external_id: str) -> str:
    return external_id.split("/", 1)[0] if "/" in external_id else external_id


def _parse_expiration_date(raw: Any) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    raw_str = str(raw).strip()
    for parser in (
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
        lambda s: datetime.strptime(s, "%Y-%m-%d"),
    ):
        try:
            parsed = parser(raw_str)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _get_curated_litellm_models() -> List[Dict[str, Any]]:
    """Extrait tous les modèles textuels pertinents depuis la base de données certifiée de LiteLLM."""
    results = []
    for k, v in litellm.model_cost.items():
        if not isinstance(v, dict):
            continue
        prov = v.get("litellm_provider")
        if prov not in SUPPORTED_PROVIDERS:
            continue

        # Exclusion des passerelles cloud tierces (Azure/Bedrock/Vertex) pour garder les modèles directs purs
        if any(k.startswith(pfx) for pfx in ["azure/", "bedrock/", "vertex_ai/", "sagemaker/", "groq/", "together_ai/"]):
            continue
        # Exclusion des identifiants ARN AWS et des formats internes de passerelle.
        # Ne peut pas se baser sur la présence d'un point : les noms de modèles courants
        # en contiennent (« gpt-5.6-sol », « mistral-medium-3.5-26.04 »).
        if k.startswith("arn:") or "::" in k:
            continue
        # Exclusion des modèles non-LLM (audio, vision pure, transcription, embeddings)
        if any(bad in k.lower() for bad in ["audio", "realtime", "transcribe", "diarize", "embedding", "dall-e", "tts", "whisper"]):
            continue

        inp = v.get("input_cost_per_token")
        out = v.get("output_cost_per_token")
        if inp is None or out is None:
            continue

        ext_id = k if "/" in k else f"{prov}/{k}"
        clean_name = k.split("/")[-1].replace("-", " ").title()

        results.append({
            "external_id": ext_id,
            "display_name": f"{clean_name}",
            "provider_slug": prov,
            "context_length": v.get("max_input_tokens") or v.get("max_tokens"),
            "pricing_prompt_per_million": _to_per_million(inp),
            "pricing_completion_per_million": _to_per_million(out),
            "raw_metadata": v,
        })
    return results


async def sync_catalog(db: AsyncSession) -> Dict[str, Any]:
    """
    Synchronise le catalogue de modèles :
    1. Ingestion de tous les modèles certifiés LiteLLM (toujours à jour et disponibles localement).
    2. Enrichissement optionnel via OpenRouter si réseau actif.
    3. Mise à jour de is_active pour refléter la disponibilité réelle des modèles.
    """
    now = datetime.now(timezone.utc)
    seen_external_ids: set = set()

    existing_res = await db.execute(select(LlmCatalogModel))
    existing_by_id = {row.external_id: row for row in existing_res.scalars().all()}

    created_count = 0
    updated_count = 0

    # 1. Traitement des modèles LiteLLM natifs
    litellm_models = _get_curated_litellm_models()
    for entry in litellm_models:
        ext_id = entry["external_id"]
        seen_external_ids.add(ext_id)

        row = existing_by_id.get(ext_id)
        if row is None:
            row = LlmCatalogModel(external_id=ext_id, first_seen_at=now)
            db.add(row)
            existing_by_id[ext_id] = row
            created_count += 1
        else:
            updated_count += 1

        row.canonical_slug = ext_id
        row.display_name = entry["display_name"]
        row.provider_slug = entry["provider_slug"]
        row.context_length = entry["context_length"]
        row.pricing_prompt_per_million = entry["pricing_prompt_per_million"]
        row.pricing_completion_per_million = entry["pricing_completion_per_million"]
        row.raw_metadata = entry["raw_metadata"]
        row.is_active = True
        row.last_seen_at = now
        row.updated_at = now

    # 2. Enrichissement complémentaire en direct via OpenRouter (si joignable)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(OPENROUTER_MODELS_URL)
            if resp.status_code == 200:
                payload = resp.json()
                openrouter_entries = payload.get("data") or []
                for entry in openrouter_entries:
                    ext_id = entry.get("id")
                    if not ext_id or not str(ext_id).strip():
                        continue
                    ext_id = str(ext_id).strip()
                    prov_slug = _extract_provider_slug(ext_id)
                    if prov_slug not in SUPPORTED_PROVIDERS:
                        continue

                    seen_external_ids.add(ext_id)
                    pricing = entry.get("pricing") or {}
                    top_provider = entry.get("top_provider") or {}

                    row = existing_by_id.get(ext_id)
                    if row is None:
                        row = LlmCatalogModel(external_id=ext_id, first_seen_at=now)
                        db.add(row)
                        existing_by_id[ext_id] = row
                        created_count += 1
                    else:
                        updated_count += 1

                    row.canonical_slug = entry.get("canonical_slug") or ext_id
                    row.display_name = entry.get("name") or row.display_name
                    row.provider_slug = prov_slug
                    row.context_length = entry.get("context_length") or top_provider.get("context_length") or row.context_length
                    if pricing.get("prompt") is not None:
                        row.pricing_prompt_per_million = _to_per_million(pricing.get("prompt"))
                    if pricing.get("completion") is not None:
                        row.pricing_completion_per_million = _to_per_million(pricing.get("completion"))
                    row.expiration_date = _parse_expiration_date(entry.get("expiration_date")) or row.expiration_date
                    row.is_active = True
                    row.last_seen_at = now
                    row.updated_at = now
    except Exception as e:
        logger.info(f"[LlmCatalogService] Synchro complémentaire OpenRouter ignorée (LiteLLM actif): {e}")

    # 3. Socle de référence relevé sur les pages tarifaires officielles — priorité
    # maximale : il corrige les tarifs périmés de la base LiteLLM embarquée et garantit
    # que les modèles réellement commercialisés sont présents même hors ligne.
    reference_count = 0
    for entry in REFERENCE_MODELS:
        ext_id = entry["external_id"]
        seen_external_ids.add(ext_id)
        row = existing_by_id.get(ext_id)
        if row is None:
            row = LlmCatalogModel(external_id=ext_id, first_seen_at=now)
            db.add(row)
            existing_by_id[ext_id] = row
            created_count += 1
        row.canonical_slug = ext_id
        row.display_name = entry["display_name"]
        row.provider_slug = entry["provider_slug"]
        if entry.get("context_length"):
            row.context_length = entry["context_length"]
        row.pricing_prompt_per_million = Decimal(str(entry["pricing_prompt_per_million"]))
        row.pricing_completion_per_million = Decimal(str(entry["pricing_completion_per_million"]))
        row.raw_metadata = {
            "source": "reference_catalog",
            "as_of": REFERENCE_AS_OF,
            "free_tier": entry.get("free_tier", False),
            "note": entry.get("note"),
        }
        row.is_active = True
        row.last_seen_at = now
        row.updated_at = now
        reference_count += 1

    # 4. Désactivation des modèles absents
    deactivated_count = 0
    for external_id, row in existing_by_id.items():
        if external_id not in seen_external_ids and row.is_active:
            row.is_active = False
            row.updated_at = now
            deactivated_count += 1

    return {
        "synced_at": now.isoformat(),
        "reference_as_of": REFERENCE_AS_OF,
        "reference_applied": reference_count,
        "total_seen": len(seen_external_ids),
        "created": created_count,
        "updated": updated_count,
        "deactivated": deactivated_count,
    }


async def list_catalog(db: AsyncSession, include_inactive: bool = True) -> List[Dict[str, Any]]:
    stmt = select(LlmCatalogModel)
    if not include_inactive:
        stmt = stmt.where(LlmCatalogModel.is_active.is_(True))
    stmt = stmt.order_by(LlmCatalogModel.provider_slug, LlmCatalogModel.display_name)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return [
        {
            "id": str(r.id),
            "external_id": r.external_id,
            "display_name": r.display_name,
            "provider_slug": r.provider_slug,
            "context_length": r.context_length,
            "pricing_prompt_per_million": float(r.pricing_prompt_per_million) if r.pricing_prompt_per_million is not None else None,
            "pricing_completion_per_million": float(r.pricing_completion_per_million) if r.pricing_completion_per_million is not None else None,
            "is_moderated": r.is_moderated,
            "expiration_date": r.expiration_date.isoformat() if r.expiration_date else None,
            "is_active": r.is_active,
            "source": (r.raw_metadata or {}).get("source") if isinstance(r.raw_metadata, dict) else None,
            "free_tier": bool((r.raw_metadata or {}).get("free_tier")) if isinstance(r.raw_metadata, dict) else False,
            "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
            "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
        }
        for r in rows
    ]
