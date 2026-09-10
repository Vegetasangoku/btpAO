"""
Materialisation des schemas proposes par le modele (10/09).

Probleme resolu
---------------
Le modele renvoyait jusqu'ici un champ "visual_placeholders" du type
["gantt_chart", "organigramme_chantier"] : une simple liste de noms. Elle etait
stockee telle quelle dans generated_sections.visual_placeholders et... rien ne
la consommait. Cote utilisateur cela se traduisait par "les graphiques ne se
generent pas automatiquement" : le mémoire annoncait un planning et un
organigramme que personne ne fabriquait.

Ce service prend le nouveau champ "visual_specs" -- qui contient les DONNEES du
schema et plus seulement son nom -- et cree les lignes dans les deux tables deja
editables par l'utilisateur (project_gantt_tasks, project_organigramme_nodes).
Le client retrouve donc le planning et l'organigramme dans les editeurs
existants, et peut tout modifier : c'est exactement la demande "pouvoir tout
modifier dans l'outil".

Regle de securite absolue
-------------------------
On ne remplace JAMAIS un visuel existant. Si le projet a deja des taches ou des
noeuds -- saisis a la main ou issus d'une generation precedente -- on ne touche
a rien et on le dit dans le rapport. Une generation de section ne doit pas
pouvoir effacer le travail de mise en forme du conducteur de travaux.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ProjectGanttTask, ProjectOrganigrammeNode

logger = logging.getLogger(__name__)

# Garde-fous : au-dela, c'est du bruit, pas un planning lisible par un jury.
MAX_GANTT_TASKS = 40
MAX_ORGA_NODES = 25

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _parse_date(value: Any) -> Optional[date]:
    """Accepte les formats que les modeles produisent en pratique. Renvoie None
    plutot que de deviner : une date fausse dans un planning est pire qu'une
    tache ecartee et signalee."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(float(str(value).strip().rstrip("%")))
    except (TypeError, ValueError):
        return default
    return max(low, min(number, high))


def _clean_text(value: Any, max_len: int = 300) -> str:
    return " ".join(str(value or "").split())[:max_len]


async def _has_rows(db: AsyncSession, model, tenant_id: uuid.UUID, project_id: uuid.UUID) -> bool:
    res = await db.execute(
        select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id, model.project_id == project_id
        )
    )
    return bool(res.scalar() or 0)


def _build_gantt_tasks(
    spec: Dict[str, Any], tenant_id: uuid.UUID, project_id: uuid.UUID
) -> tuple[List[ProjectGanttTask], List[str]]:
    rejets: List[str] = []
    brut = spec.get("tasks")
    if not isinstance(brut, list):
        return [], ["Le planning proposé ne contient pas de liste \"tasks\"."]

    retenues: List[Dict[str, Any]] = []
    for item in brut:
        if len(retenues) >= MAX_GANTT_TASKS:
            rejets.append(f"Planning tronqué à {MAX_GANTT_TASKS} tâches.")
            break
        if not isinstance(item, dict):
            continue
        nom = _clean_text(item.get("name") or item.get("nom"))
        if not nom:
            rejets.append("Tâche sans intitulé ignorée.")
            continue
        debut = _parse_date(item.get("start") or item.get("start_date"))
        fin = _parse_date(item.get("end") or item.get("end_date"))
        if debut is None or fin is None:
            rejets.append(f"« {nom} » : date de début ou de fin illisible — tâche non créée.")
            continue
        if fin < debut:
            rejets.append(f"« {nom} » : fin antérieure au début — tâche non créée.")
            continue
        depends_raw = item.get("depends_on") or item.get("dependencies") or []
        if isinstance(depends_raw, str):
            depends_raw = [depends_raw]
        retenues.append({
            "name": nom,
            "start_date": debut,
            "end_date": fin,
            "progress": _clamp_int(item.get("progress"), 0, 100, 0),
            "is_milestone": bool(item.get("is_milestone")) or debut == fin,
            "milestone_label": _clean_text(item.get("milestone_label")) or None,
            "depends_on_names": [_clean_text(d) for d in depends_raw if _clean_text(d)],
        })

    # Les identifiants sont tires d'abord pour resoudre les dependances par nom.
    par_nom: Dict[str, uuid.UUID] = {}
    for data in retenues:
        data["id"] = uuid.uuid4()
        par_nom.setdefault(data["name"].lower(), data["id"])

    taches: List[ProjectGanttTask] = []
    for rang, data in enumerate(retenues):
        liens: List[uuid.UUID] = []
        for nom_dep in data.pop("depends_on_names"):
            cible = par_nom.get(nom_dep.lower())
            if cible and cible != data["id"]:
                liens.append(cible)
            elif not cible:
                rejets.append(
                    f"« {data['name']} » : dépendance « {nom_dep} » introuvable — lien ignoré."
                )
        taches.append(ProjectGanttTask(
            tenant_id=tenant_id, project_id=project_id, sequence=rang,
            depends_on=liens, **data
        ))
    return taches, rejets


def _build_orga_nodes(
    spec: Dict[str, Any], tenant_id: uuid.UUID, project_id: uuid.UUID
) -> tuple[List[ProjectOrganigrammeNode], List[str]]:
    rejets: List[str] = []
    brut = spec.get("nodes")
    if not isinstance(brut, list):
        return [], ["L'organigramme proposé ne contient pas de liste \"nodes\"."]

    noeuds: List[ProjectOrganigrammeNode] = []
    for item in brut:
        if len(noeuds) >= MAX_ORGA_NODES:
            rejets.append(f"Organigramme tronqué à {MAX_ORGA_NODES} postes.")
            break
        if not isinstance(item, dict):
            continue
        role = _clean_text(item.get("role"))
        if not role:
            rejets.append("Poste sans intitulé de fonction ignoré.")
            continue
        # "À pourvoir" est le defaut voulu : le modele a interdiction d'inventer
        # un nom de personne, et un organigramme nominatif faux serait un motif
        # d'ecartement du candidat.
        nom = _clean_text(item.get("nom") or item.get("name")) or "À pourvoir"
        noeuds.append(ProjectOrganigrammeNode(
            tenant_id=tenant_id, project_id=project_id,
            nom=nom, role=role,
            experience_ans=_clamp_int(item.get("experience_ans"), 0, 60, 10),
            presence_hebdo_pct=_clamp_int(item.get("presence_hebdo_pct"), 0, 100, 100),
            qualif=_clean_text(item.get("qualif")) or None,
            sequence=len(noeuds),
        ))
    return noeuds, rejets


async def materialize_visual_specs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    visual_specs: Any,
) -> Dict[str, Any]:
    """Cree les visuels manquants a partir des specs du modele.

    Ne commit pas : l'appelant reste maitre de la transaction. Ne leve jamais --
    un schema mal forme ne doit pas faire echouer la redaction de la section,
    qui est le livrable principal.

    Renvoie un rapport destine a etre affiche : ce qui a ete cree, ce qui a ete
    laisse en place, et ce qui a ete ecarte avec le motif.
    """
    rapport: Dict[str, Any] = {"created": [], "skipped": [], "rejected": []}
    if not isinstance(visual_specs, list) or not visual_specs:
        return rapport

    for spec in visual_specs:
        if not isinstance(spec, dict):
            continue
        type_spec = str(spec.get("type") or "").strip().lower()
        try:
            if type_spec in ("gantt", "gantt_chart", "planning"):
                if await _has_rows(db, ProjectGanttTask, tenant_id, project_id):
                    rapport["skipped"].append(
                        "Planning : un planning existe déjà sur ce projet, il n'a pas été touché."
                    )
                    continue
                taches, rejets = _build_gantt_tasks(spec, tenant_id, project_id)
                rapport["rejected"].extend(rejets)
                if taches:
                    db.add_all(taches)
                    rapport["created"].append(f"Planning : {len(taches)} tâche(s) créée(s).")
                    logger.info(
                        "[VisualSpec] %d tache(s) Gantt creees pour le projet %s", len(taches), project_id
                    )
            elif type_spec in ("organigramme", "organigramme_chantier", "org_chart"):
                if await _has_rows(db, ProjectOrganigrammeNode, tenant_id, project_id):
                    rapport["skipped"].append(
                        "Organigramme : un organigramme existe déjà sur ce projet, il n'a pas été touché."
                    )
                    continue
                noeuds, rejets = _build_orga_nodes(spec, tenant_id, project_id)
                rapport["rejected"].extend(rejets)
                if noeuds:
                    db.add_all(noeuds)
                    rapport["created"].append(f"Organigramme : {len(noeuds)} poste(s) créé(s).")
                    logger.info(
                        "[VisualSpec] %d noeud(s) organigramme crees pour le projet %s", len(noeuds), project_id
                    )
            elif type_spec:
                rapport["rejected"].append(
                    f"Type de schéma « {type_spec} » non pris en charge — ignoré."
                )
        except Exception as exc:  # jamais bloquant pour la section redigee
            logger.warning("[VisualSpec] Spec '%s' ignoree : %s", type_spec, exc)
            rapport["rejected"].append(f"Schéma « {type_spec} » ignoré : {exc}")

    return rapport
