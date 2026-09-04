"""
Real LLM-based extraction of DCE (Dossier de Consultation des Entreprises) notation
criteria from the actual OCR'd text of an uploaded Règlement de Consultation (RC).

Avant ce fichier (01/09), l'endpoint d'upload insérait TOUJOURS les 4 mêmes critères
codés en dur (Moyens humains 25% / Méthodologie 35% / RSE 25% / Qualité-Sécurité 15%),
quel que soit le contenu réel du document déposé -- une extraction fictive, pas un
"gabarit de secours". Ce service remplace cette insertion synchrone par un vrai appel
LLM sur le texte OCR réel (déclenché depuis parse_dce_task, une fois l'OCR terminé --
au moment de l'upload synchrone, le texte n'existe pas encore).

Le gabarit à 4 critères est conservé, mais seulement comme repli explicite et
transparent (aucune clé LLM configurée, échec de l'appel, ou réponse LLM inexploitable)
-- jamais comme comportement par défaut silencieux.
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DCECriterionEntity
from app.services.billing_service import billing_service
from app.services.model_routing_service import model_routing_service

logger = logging.getLogger(__name__)

# Repli explicite si l'extraction LLM réelle est indisponible ou échoue -- jamais
# renvoyé silencieusement comme si c'était une lecture du document.
FALLBACK_CRITERIA: List[Dict[str, Any]] = [
    (
        "1. Moyens humains & Organisation du chantier", 25.0,
        "Pertinence de l'organigramme dédié et qualifications des cadres.",
        ["Organigramme nominatif", "CVs signés"], ["Attestations de formation SST"],
    ),
    (
        "2. Méthodologie d'exécution, Matériels & Phasage", 35.0,
        "Procédés d'exécution, moyens matériels et respect du planning.",
        ["Planning Gantt", "Fiches techniques matériel"], ["Plan de phasage"],
    ),
    (
        "3. Démarche Environnementale (RSE) & Déchets", 25.0,
        "Gestion environnementale du chantier et valorisation des déchets.",
        ["Bordereaux de suivi des déchets (BSD)"], ["Fiches FDES"],
    ),
    (
        "4. Qualité (PAQ) & Sécurité (PPSPS)", 15.0,
        "Contrôles qualité et dispositif de sécurité chantier.",
        ["Fiches d'autocontrôle", "PPSPS"], ["Plan d'Assurance Qualité type"],
    ),
]

MAX_TEXT_CHARS = 18000  # budget de prompt raisonnable pour un RC (généralement plus court qu'un CCTP)


def _fallback_rows(tenant_id: uuid.UUID, project_id: uuid.UUID, source: str) -> List[DCECriterionEntity]:
    rows = []
    for title, weight, desc, exp, ev in FALLBACK_CRITERIA:
        rows.append(
            DCECriterionEntity(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                project_id=project_id,
                criterion_title=title,
                weight_percentage=weight,
                description=desc,
                key_expectations=exp,
                required_evidence=ev,
                mandatory="true",
            )
        )
    logger.warning(
        "[CriteriaExtraction] Repli sur le gabarit à 4 critères (raison : %s) -- "
        "PAS une extraction du document réel.", source,
    )
    return rows


async def extract_criteria_from_text(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    raw_text: str,
    filename: str,
) -> List[DCECriterionEntity]:
    """
    Extrait les vrais critères de notation depuis le texte OCR du RC via un appel LLM
    réel (task_type="extraction_gonogo" -- le même identifiant de tâche exposé sur
    l'onglet admin "Routage IA par Tâche & Client"). Retombe explicitement sur un
    gabarit générique si aucune clé n'est configurée ou si l'appel échoue.
    Ne lève jamais d'exception -- retourne toujours une liste de lignes prêtes à
    persister (db.add_all), jamais persistées ici (l'appelant gère la transaction).
    """
    text = (raw_text or "").strip()
    if not text:
        return _fallback_rows(tenant_id, project_id, "document sans texte OCR exploitable")

    # 02/09 : plafond de cout LLM mensuel reel -- ce point d'appel ne doit jamais lever
    # d'exception (contrat documente ci-dessus), donc degrade vers le gabarit de repli
    # plutot que de bloquer la tache de fond appelante en cas de plafond atteint.
    cap_exceeded, _cap, _spend = await billing_service.is_cost_cap_exceeded(tenant_id, db)
    if cap_exceeded:
        return _fallback_rows(tenant_id, project_id, "plafond de cout LLM mensuel atteint")

    try:
        resolved = await model_routing_service.resolve_model_for_tenant(
            db=db, tenant_id=tenant_id, task_type="extraction_gonogo",
        )
        model_string = resolved["model_string"]
        credentials = await model_routing_service.get_credentials_for_model(db=db, model_string=model_string)
        api_key = credentials.get("api_key")
        if not api_key:
            return _fallback_rows(tenant_id, project_id, "aucune clé LLM configurée pour extraction_gonogo")

        system_prompt = (
            "Tu es un expert en analyse d'appels d'offres publics BTP (bâtiment/travaux publics). "
            "Tu extrais les CRITÈRES DE NOTATION réels d'un Règlement de Consultation (RC), tels "
            "qu'ils apparaissent explicitement dans le texte fourni -- jamais inventés. Si le texte "
            "ne contient pas de grille de notation identifiable, retourne une liste vide plutôt que "
            "de fabriquer des critères plausibles."
        )
        user_prompt = f"""Extrait la grille de critères de notation de l'offre (souvent une pondération
en %, ex: "Valeur technique 60%, Prix 40%") depuis cet extrait de Règlement de Consultation
(fichier: {filename}). Pour chaque critère (et sous-critère s'il existe), donne : titre exact,
pondération en % (nombre), description courte, attentes clés (liste courte), pièces justificatives
demandées si mentionnées (liste courte). Les pondérations doivent sommer à environ 100 si un
barème complet est identifiable.

TEXTE DU DOCUMENT (peut être tronqué) :
{text[:MAX_TEXT_CHARS]}

Réponds en JSON strict avec cette structure exacte :
{{"criteria": [{{"title": "...", "weight_percentage": 60.0, "description": "...",
"key_expectations": ["..."], "required_evidence": ["..."], "mandatory": true}}]}}
Si aucun barème n'est identifiable dans le texte, réponds {{"criteria": []}}.
"""
        kwargs: Dict[str, Any] = {
            "model": model_string,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 2000,
            "api_key": api_key,
        }
        if credentials.get("api_base"):
            kwargs["api_base"] = credentials["api_base"]

        response = litellm.completion(**kwargs)

        # 02/09 : journal de consommation LLM -- absent jusqu'ici sur ce point d'appel.
        _usage = getattr(response, "usage", None)
        await billing_service.log_llm_usage(
            db=db,
            tenant_id=tenant_id,
            project_id=project_id,
            provider_id=credentials.get("provider_id"),
            model_string=model_string,
            prompt_tokens=getattr(_usage, "prompt_tokens", None) if _usage else None,
            completion_tokens=getattr(_usage, "completion_tokens", None) if _usage else None,
            total_tokens=getattr(_usage, "total_tokens", None) if _usage else None,
        )

        parsed = json.loads(response.choices[0].message.content)
        items = parsed.get("criteria") or []
        if not isinstance(items, list) or not items:
            return _fallback_rows(tenant_id, project_id, "réponse LLM sans critère exploitable")

        rows: List[DCECriterionEntity] = []
        for item in items:
            try:
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                weight = float(item.get("weight_percentage") or 0.0)
                rows.append(
                    DCECriterionEntity(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        project_id=project_id,
                        criterion_title=title,
                        weight_percentage=round(weight, 2),
                        description=str(item.get("description") or "") or None,
                        key_expectations=item.get("key_expectations") or [],
                        required_evidence=item.get("required_evidence") or [],
                        mandatory="true" if item.get("mandatory", True) else "false",
                    )
                )
            except Exception as row_exc:
                logger.warning("[CriteriaExtraction] Ligne de critère LLM ignorée (format inattendu) : %s", row_exc)

        if not rows:
            return _fallback_rows(tenant_id, project_id, "aucune ligne LLM valide après parsing")

        logger.info(
            "[CriteriaExtraction] %d critère(s) réellement extrait(s) du document '%s' via '%s'.",
            len(rows), filename, model_string,
        )
        return rows

    except Exception as e:
        logger.warning("[CriteriaExtraction] Échec extraction LLM réelle (%s) -- repli gabarit.", e)
        return _fallback_rows(tenant_id, project_id, f"exception : {e}")
