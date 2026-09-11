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

Regle de securite absolue nº1 : la saisie du client fait foi
------------------------------------------------------------
Constat du 10/09 sur le dossier Ressourcerie : l'utilisateur avait declare
dans l'assistant une equipe nominative (Chloe Fontaine, 7 ans d'experience,
50 % de presence hebdomadaire) et le modele a materialise un organigramme
avec 11 ans et 51 %. Personne n'avait rien demande de tel : le modele avait
simplement "arrondi" des donnees factuelles. Dans un memoire technique remis
a un acheteur public, c'est une declaration inexacte sur les moyens humains,
c'est-a-dire un motif d'ecartement de l'offre -- et, si elle est decouverte
apres attribution, un faux.

Consequence : dès que l'utilisateur a declare quelque chose (equipe_cadres,
phasage_travaux + date_demarrage), CE SONT SES VALEURS QUI SONT ECRITES,
octet pour octet. Les propositions du modele ne servent qu'a completer ce
qui n'a pas ete declare, jamais a le corriger. Tout ecart constate est
signale a l'utilisateur dans le rapport plutot que d'etre applique en
silence.

Regle de securite absolue nº2 : aucun nom de personne invente
-------------------------------------------------------------
Un nom propre ne peut avoir qu'une seule origine : l'equipe declaree par le
client. Tout autre nom produit par le modele est remplace par "A pourvoir"
et le remplacement est signale. Un organigramme nominatif faux est un motif
d'ecartement du candidat ; un poste honnetement marque "a pourvoir" n'en est
pas un.

Regle de securite absolue nº3 : on n'ecrase jamais l'existant
--------------------------------------------------------------
On ne remplace JAMAIS un visuel existant. Si le projet a deja des taches ou des
noeuds -- saisis a la main ou issus d'une generation precedente -- on ne touche
a rien et on le dit dans le rapport. Une generation de section ne doit pas
pouvoir effacer le travail de mise en forme du conducteur de travaux.
"""
from __future__ import annotations

import logging
import unicodedata
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ProjectGanttTask, ProjectOrganigrammeNode

logger = logging.getLogger(__name__)

# Garde-fous : au-dela, c'est du bruit, pas un planning lisible par un jury.
MAX_GANTT_TASKS = 120  # 11/09 : planning detaille (phases + taches + sous-taches)
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


def _normalise(value: Any) -> str:
    """Cle de rapprochement insensible a la casse, aux accents et aux espaces :
    sert a reconnaitre qu'un poste propose par le modele designe bien un poste
    deja declare par le client ("Ingenieur QSE" vs "Ingénieur QSE & Environnement")."""
    decompose = unicodedata.normalize("NFKD", str(value or ""))
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(sans_accents.lower().split())


def _cadres_declares(declarations: Any) -> List[Dict[str, Any]]:
    """L'equipe d'encadrement telle que l'utilisateur l'a saisie dans l'assistant
    (ProjectDecision.form_data['equipe_cadres']). C'est la seule source legitime
    d'un nom de personne dans ce dossier."""
    cadres = (declarations or {}).get("equipe_cadres") if isinstance(declarations, dict) else None
    if not isinstance(cadres, list):
        return []
    retenus: List[Dict[str, Any]] = []
    for cadre in cadres:
        if not isinstance(cadre, dict):
            continue
        if not (_clean_text(cadre.get("nom")) or _clean_text(cadre.get("role"))):
            continue
        retenus.append(cadre)
        if len(retenus) >= MAX_ORGA_NODES:
            break
    return retenus


def _phasage_declare(declarations: Any) -> tuple[Optional[date], List[Dict[str, Any]]]:
    """Le phasage saisi dans l'assistant : date de demarrage + suite de phases
    avec leur duree en semaines. Renvoie (None, []) si rien d'exploitable, auquel
    cas seul le modele peut proposer un planning."""
    if not isinstance(declarations, dict):
        return None, []
    debut = _parse_date(declarations.get("date_demarrage"))
    brut = declarations.get("phasage_travaux")
    if not isinstance(brut, list):
        return debut, []
    phases: List[Dict[str, Any]] = []
    for item in brut:
        if not isinstance(item, dict):
            continue
        nom = _clean_text(item.get("phase") or item.get("nom") or item.get("name"))
        semaines = _clamp_int(item.get("duree_semaines"), 0, 520, 0)
        if not nom or semaines <= 0:
            continue
        phases.append({
            "phase": nom,
            "jalon": _clean_text(item.get("jalon")) or None,
            "semaines": semaines,
        })
        if len(phases) >= MAX_GANTT_TASKS:
            break
    return debut, phases


def _gantt_depuis_declaration(
    debut: date, phases: List[Dict[str, Any]], tenant_id: uuid.UUID, project_id: uuid.UUID
) -> List[ProjectGanttTask]:
    """Enchaine les phases declarees bout a bout depuis la date de demarrage
    saisie. Aucune interpretation : la duree ecrite est la duree appliquee."""
    taches: List[ProjectGanttTask] = []
    identifiants = [uuid.uuid4() for _ in phases]
    curseur = debut
    for rang, phase in enumerate(phases):
        fin = curseur + timedelta(weeks=phase["semaines"])
        taches.append(ProjectGanttTask(
            id=identifiants[rang],
            tenant_id=tenant_id,
            project_id=project_id,
            sequence=rang,
            name=phase["phase"],
            start_date=curseur,
            end_date=fin,
            progress=0,
            is_milestone=False,
            milestone_label=phase["jalon"],
            depends_on=[identifiants[rang - 1]] if rang else [],
        ))
        curseur = fin
    return taches


def _detail_sous_phases(
    brut: Any, phases: List[ProjectGanttTask], tenant_id: uuid.UUID, project_id: uuid.UUID,
    rejets: List[str],
) -> List[ProjectGanttTask]:
    """Rattache aux phases declarees les taches du modele qui citent une phase en
    "parent" (et leurs sous-taches). Dates ramenees dans la phase si besoin, et dit."""
    if not isinstance(brut, list):
        return []
    parents: Dict[str, ProjectGanttTask] = {_normalise(p.name): p for p in phases}
    crees: List[ProjectGanttTask] = []
    rang_par_parent: Dict[uuid.UUID, int] = {}
    # Deux passes : d'abord les taches rattachees a une phase, puis les sous-taches
    # rattachees a ces taches.
    for passe in (0, 1):
        for item in brut:
            if not isinstance(item, dict) or len(crees) >= MAX_GANTT_TASKS * 3:
                continue
            parent = parents.get(_normalise(item.get("parent") or item.get("phase")))
            nom = _clean_text(item.get("name") or item.get("nom"))
            if parent is None or not nom or _normalise(nom) in parents:
                continue
            est_sous_tache = parent.parent_id is not None
            if (passe == 0) == est_sous_tache:
                continue
            debut = _parse_date(item.get("start") or item.get("start_date"))
            fin = _parse_date(item.get("end") or item.get("end_date"))
            if debut is None or fin is None:
                rejets.append(f"« {nom} » : dates illisibles — tâche de détail non créée.")
                continue
            if fin < debut:
                debut, fin = fin, debut
            d2, f2 = max(debut, parent.start_date), min(fin, parent.end_date)
            if f2 < d2:
                d2, f2 = parent.start_date, parent.start_date
            if (d2, f2) != (debut, fin):
                rejets.append(f"« {nom} » : dates ramenées dans « {parent.name} ».")
            rang = rang_par_parent.get(parent.id, 0)
            rang_par_parent[parent.id] = rang + 1
            ligne = ProjectGanttTask(
                id=uuid.uuid4(), tenant_id=tenant_id, project_id=project_id, parent_id=parent.id,
                sequence=rang, name=nom, start_date=d2, end_date=f2, progress=0,
                is_milestone=False, milestone_label=None, depends_on=[],
                lot=_clean_text(item.get("lot"), 80) or None,
            )
            crees.append(ligne)
            parents.setdefault(_normalise(nom), ligne)
    return crees


def _ecarts_vs_declaration(propose: Dict[str, Any], cadre: Dict[str, Any]) -> List[str]:
    """Liste, en clair, ce que le modele a change par rapport a la declaration.
    Sert uniquement a informer : la valeur declaree est deja celle qui a ete
    ecrite."""
    intitule = _clean_text(cadre.get("nom")) or _clean_text(cadre.get("role")) or "Poste declare"
    ecarts: List[str] = []
    comparaisons = (
        ("experience_ans", "années d'expérience", 0, 60),
        ("presence_hebdo_pct", "% de présence hebdomadaire", 0, 100),
    )
    for cle, libelle, bas, haut in comparaisons:
        if propose.get(cle) is None or cadre.get(cle) is None:
            continue
        valeur_modele = _clamp_int(propose.get(cle), bas, haut, -1)
        valeur_client = _clamp_int(cadre.get(cle), bas, haut, -1)
        if valeur_modele >= 0 and valeur_client >= 0 and valeur_modele != valeur_client:
            ecarts.append(
                f"« {intitule} » : le modèle proposait {valeur_modele} {libelle} au lieu "
                f"des {valeur_client} que vous avez déclarés — votre valeur a été conservée."
            )
    qualif_modele = _clean_text(propose.get("qualif"))
    qualif_client = _clean_text(cadre.get("qualif"))
    if qualif_modele and qualif_client and _normalise(qualif_modele) != _normalise(qualif_client):
        ecarts.append(
            f"« {intitule} » : le modèle proposait la qualification « {qualif_modele} » "
            f"au lieu de « {qualif_client} » — votre valeur a été conservée."
        )
    return ecarts


async def _has_rows(db: AsyncSession, model, tenant_id: uuid.UUID, project_id: uuid.UUID) -> bool:
    res = await db.execute(
        select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id, model.project_id == project_id
        )
    )
    return bool(res.scalar() or 0)


def _build_gantt_tasks(
    spec: Dict[str, Any],
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    declarations: Any = None,
) -> tuple[List[ProjectGanttTask], List[str], str]:
    """Renvoie (taches, motifs d'écart, précision sur l'origine des données)."""
    rejets: List[str] = []

    # Priorite absolue au phasage saisi dans l'assistant : c'est un engagement
    # contractuel de delai, pas une suggestion. Le modele ne le reecrit pas.
    debut_declare, phases_declarees = _phasage_declare(declarations)
    if debut_declare and phases_declarees:
        taches = _gantt_depuis_declaration(debut_declare, phases_declarees, tenant_id, project_id)
        total_semaines = sum(p["semaines"] for p in phases_declarees)
        # 11/09 : le detail propose par le modele (taches rattachees a une phase via
        # "parent") est conserve A L'INTERIEUR des phases declarees -- les dates des
        # phases restent celles du client, seul le detail vient du modele.
        detail = _detail_sous_phases(spec.get("tasks"), taches, tenant_id, project_id, rejets)
        precision = (
            f" à partir du phasage que vous avez saisi dans l'assistant "
            f"({total_semaines} semaines à compter du {debut_declare.strftime('%d/%m/%Y')})"
            + (f", détaillé en {len(detail)} tâche(s) et sous-tâche(s) proposées par le modèle "
               f"à l'intérieur de vos phases" if detail else
               " — les dates proposées par le modèle n'ont pas été utilisées")
        )
        return taches + detail, rejets, precision

    brut = spec.get("tasks")
    if not isinstance(brut, list):
        return [], ["Le planning proposé ne contient pas de liste \"tasks\"."], ""

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
            "parent_name": _clean_text(item.get("parent") or item.get("phase")),
            "lot": _clean_text(item.get("lot"), 80) or None,
        })

    # Les identifiants sont tires d'abord pour resoudre les dependances par nom.
    par_nom: Dict[str, uuid.UUID] = {}
    for data in retenues:
        data["id"] = uuid.uuid4()
        par_nom.setdefault(data["name"].lower(), data["id"])

    taches: List[ProjectGanttTask] = []
    for rang, data in enumerate(retenues):
        parent_name = data.pop("parent_name")
        parent_id = par_nom.get(parent_name.lower()) if parent_name else None
        if parent_id == data["id"]:
            parent_id = None
        data["parent_id"] = parent_id
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
    return taches, rejets, ""


def _build_orga_nodes(
    spec: Dict[str, Any],
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    declarations: Any = None,
) -> tuple[List[ProjectOrganigrammeNode], List[str], str]:
    """Renvoie (postes, motifs d'écart, précision sur l'origine des données)."""
    rejets: List[str] = []
    cadres = _cadres_declares(declarations)
    brut = spec.get("nodes") if isinstance(spec, dict) else None
    propositions = [i for i in brut if isinstance(i, dict)] if isinstance(brut, list) else []

    if not cadres and not propositions:
        return [], ["L'organigramme proposé ne contient pas de liste \"nodes\"."], ""

    noeuds: List[ProjectOrganigrammeNode] = []
    par_role: Dict[str, Dict[str, Any]] = {}
    par_nom: Dict[str, Dict[str, Any]] = {}

    # 1. L'equipe declaree, recopiee sans la moindre retouche.
    for cadre in cadres:
        role = _clean_text(cadre.get("role")) or "Rôle à préciser"
        nom = _clean_text(cadre.get("nom")) or "À pourvoir"
        noeuds.append(ProjectOrganigrammeNode(
            tenant_id=tenant_id, project_id=project_id,
            nom=nom, role=role,
            experience_ans=_clamp_int(cadre.get("experience_ans"), 0, 60, 10),
            presence_hebdo_pct=_clamp_int(cadre.get("presence_hebdo_pct"), 0, 100, 100),
            qualif=_clean_text(cadre.get("qualif")) or None,
            sequence=len(noeuds),
        ))
        par_role.setdefault(_normalise(role), cadre)
        if _normalise(nom) and nom != "À pourvoir":
            par_nom.setdefault(_normalise(nom), cadre)
    precision = (
        f", dont les {len(cadres)} intervenant(s) que vous avez déclarés dans l'assistant, "
        f"repris tels quels (nom, expérience, présence, qualification)"
    ) if cadres else ""

    # 2. Les propositions du modele : uniquement pour completer, jamais pour corriger.
    for item in propositions:
        role = _clean_text(item.get("role"))
        nom_propose = _clean_text(item.get("nom") or item.get("name"))
        cle_role, cle_nom = _normalise(role), _normalise(nom_propose)

        cadre_correspondant = par_role.get(cle_role) or (par_nom.get(cle_nom) if cle_nom else None)
        if cadre_correspondant is not None:
            rejets.extend(_ecarts_vs_declaration(item, cadre_correspondant))
            continue

        if len(noeuds) >= MAX_ORGA_NODES:
            rejets.append(f"Organigramme tronqué à {MAX_ORGA_NODES} postes.")
            break
        if not role:
            rejets.append("Poste sans intitulé de fonction ignoré.")
            continue

        # Un nom propre ne peut venir que de l'equipe declaree. Tout autre nom est
        # une invention du modele : un organigramme nominatif faux ferait ecarter
        # l'offre, un poste "à pourvoir" non.
        nom_final = "À pourvoir"
        if cle_nom and cle_nom in par_nom:
            nom_final = nom_propose
        elif nom_propose:
            rejets.append(
                f"« {role} » : le modèle a proposé le nom « {nom_propose} », qui ne figure "
                f"dans aucune équipe déclarée — remplacé par « À pourvoir »."
            )

        noeuds.append(ProjectOrganigrammeNode(
            tenant_id=tenant_id, project_id=project_id,
            nom=nom_final, role=role,
            experience_ans=_clamp_int(item.get("experience_ans"), 0, 60, 10),
            presence_hebdo_pct=_clamp_int(item.get("presence_hebdo_pct"), 0, 100, 100),
            qualif=_clean_text(item.get("qualif")) or None,
            sequence=len(noeuds),
        ))
    return noeuds, rejets, precision


async def materialize_visual_specs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    visual_specs: Any,
    declarations: Any = None,
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
    # `declarations` = ProjectDecision.form_data. Ce que le client y a saisi fait
    # foi et n'est jamais reecrit par le modele (voir l'en-tete du module).

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
                taches, rejets, precision = _build_gantt_tasks(spec, tenant_id, project_id, declarations)
                rapport["rejected"].extend(rejets)
                if taches:
                    db.add_all(taches)
                    rapport["created"].append(f"Planning : {len(taches)} tâche(s) créée(s){precision}.")
                    logger.info(
                        "[VisualSpec] %d tache(s) Gantt creees pour le projet %s", len(taches), project_id
                    )
            elif type_spec in ("organigramme", "organigramme_chantier", "org_chart"):
                if await _has_rows(db, ProjectOrganigrammeNode, tenant_id, project_id):
                    rapport["skipped"].append(
                        "Organigramme : un organigramme existe déjà sur ce projet, il n'a pas été touché."
                    )
                    continue
                noeuds, rejets, precision = _build_orga_nodes(spec, tenant_id, project_id, declarations)
                rapport["rejected"].extend(rejets)
                if noeuds:
                    db.add_all(noeuds)
                    rapport["created"].append(f"Organigramme : {len(noeuds)} poste(s) créé(s){precision}.")
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
