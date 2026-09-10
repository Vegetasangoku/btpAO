"""
Déduction de la charte graphique d'une entreprise à partir de ses propres dossiers
(10/09).

Demande client : « les chartes ne se génèrent pas automatiquement [...] on se base sur
la charte du client, soit template déposé soit derniers dossiers ». Jusqu'ici la charte
était un formulaire à remplir à la main dans l'administration : couleur, police,
en-tête, pied de page. Résultat observé en base : des valeurs par défaut
(company_name = "test", primary_color = #0284c7) qui n'ont rien à voir avec le client,
et un mémoire exporté aux couleurs de personne.

Ce service lit les .docx que l'entreprise a déjà déposés (anciens mémoires, fiches de
référence, gabarit d'export) et en extrait une PROPOSITION de charte. Il n'écrit jamais
dans la configuration du tenant : la proposition est présentée à l'utilisateur, qui
valide ou corrige. C'est la même règle que pour les profils réglementaires — on ne
remplace jamais une donnée client par une déduction non validée.

Chaque champ proposé porte le fichier dont il vient, pour que l'utilisateur puisse
juger sur pièce plutôt que sur parole.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Couleurs a ne jamais proposer comme couleur de marque : noir, blanc, "automatique"
# et les gris tres proches. Une charte n'est pas "noir sur blanc" -- si on ne trouve
# que ca, on le dit au lieu d'inventer une couleur.
_COULEURS_IGNOREES = {"auto", "000000", "ffffff", "fff", "000"}

_MOTIFS_CERTIFS = re.compile(
    r"\b(QUALIBAT(?:\s*\d{4})?|ISO\s*9001(?::\d{4})?|ISO\s*14001(?::\d{4})?|ISO\s*45001"
    r"|MASE|RGE|QUALIFELEC|QUALIFIBRE|CERTIBAT|OPQIBI|NF\s*HABITAT)\b",
    re.IGNORECASE,
)
_MOTIF_SIRET = re.compile(r"\bSIRET\s*:?\s*((?:\d[\s.]?){14})", re.IGNORECASE)
_MOTIF_SIREN = re.compile(r"\bSIREN\s*:?\s*((?:\d[\s.]?){9})", re.IGNORECASE)

# Raison sociale : on s'arrete a la forme juridique, c'est le repere le plus fiable
# dans un en-tete de memoire technique francais.
_MOTIF_RAISON_SOCIALE = re.compile(
    r"^\s*(.{2,70}?\b(?:SAS|SASU|SARL|EURL|SA|SNC|SCOP|SCIC|SCI|GIE|EI|EIRL))\b",
    re.IGNORECASE,
)

# Couleurs par defaut des themes Word. Les proposer comme "charte de l'entreprise"
# serait trompeur : ce sont celles de n'importe quel document cree sous Word sans
# modele maison. On les propose quand meme (elles sont bien dans le document) mais
# en le disant clairement, pour que l'utilisateur ne prenne pas un bleu Microsoft
# pour le bleu de son logo.
_COULEURS_WORD_PAR_DEFAUT = {
    "2E74B5", "1F4E79", "4472C4", "5B9BD5", "ED7D31", "A5A5A5", "FFC000",
    "44546A", "0563C1", "954F72", "70AD47", "255E91",
}


def _texte_brut(xml: str) -> str:
    """Texte lisible d'une partie OOXML, sans dépendance à python-docx."""
    sans_balises = re.sub(r"<[^>]+>", " ", xml)
    sans_entites = (
        sans_balises.replace("&apos;", "'").replace("&amp;", "&")
        .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    )
    return re.sub(r"[ \t ]+", " ", sans_entites).strip()


def _luminance(hexa: str) -> float:
    r, v, b = (int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * v + 0.0722 * b


def _saturation(hexa: str) -> float:
    canaux = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    haut, bas = max(canaux), min(canaux)
    return 0.0 if haut == 0 else (haut - bas) / haut


def _couleurs_utilisables(compteur: Counter) -> List[Tuple[str, int]]:
    retenues = []
    for hexa, n in compteur.most_common():
        h = hexa.lower()
        if h in _COULEURS_IGNOREES or len(h) != 6:
            continue
        try:
            lum = _luminance(h)
        except ValueError:
            continue
        if lum > 0.94 or lum < 0.04:      # quasi blanc ou quasi noir
            continue
        retenues.append((h.upper(), n))
    return retenues


def extraire_charte_docx(contenu: bytes, nom_fichier: str = "") -> Dict[str, Any]:
    """Extrait les signaux de charte d'un unique .docx. Ne lève jamais."""
    resultat: Dict[str, Any] = {
        "fichier": nom_fichier,
        "couleurs": Counter(),
        "polices": Counter(),
        "entete": None,
        "pied": None,
        "premieres_lignes": [],
        "logo_present": False,
        "logo_octets": None,
        "logo_nom": None,
    }
    try:
        z = zipfile.ZipFile(io.BytesIO(contenu))
    except Exception as exc:
        logger.warning("[Charte] %s illisible (pas un .docx ?) : %s", nom_fichier, exc)
        return resultat

    noms = z.namelist()

    def lire(nom: str) -> str:
        try:
            return z.read(nom).decode("utf-8", "ignore")
        except Exception:
            return ""

    # 1. Couleurs du thème (accent1..6) : c'est la source la plus fiable quand le
    #    document a été fait à partir d'un modèle d'entreprise.
    if "word/theme/theme1.xml" in noms:
        theme = lire("word/theme/theme1.xml")
        for nom_role, val in re.findall(
            r"<a:(accent[1-6]|dk2|lt2)>.*?val=\"([0-9A-Fa-f]{6})\"", theme, re.S
        ):
            # accent1 pèse le plus lourd : c'est la couleur de marque par convention.
            poids = 40 if nom_role == "accent1" else 12
            resultat["couleurs"][val.lower()] += poids
        for police in re.findall(r"<a:latin typeface=\"([^\"]+)\"", theme):
            if police and not police.startswith("+"):
                resultat["polices"][police] += 20

    # 2. Couleurs et polices réellement utilisées dans le corps et les styles.
    for partie in ("word/document.xml", "word/styles.xml"):
        if partie not in noms:
            continue
        xml = lire(partie)
        for val in re.findall(r"w:color w:val=\"([0-9A-Fa-f]{6})\"", xml):
            resultat["couleurs"][val.lower()] += 1
        for val in re.findall(r"w:fill=\"([0-9A-Fa-f]{6})\"", xml):
            resultat["couleurs"][val.lower()] += 2
        for police in re.findall(r"w:ascii=\"([^\"]+)\"", xml):
            resultat["polices"][police] += 1

    # 3. En-tête et pied de page : souvent la signature de l'entreprise.
    for nom in noms:
        if re.match(r"word/header\d*\.xml$", nom) and not resultat["entete"]:
            t = _texte_brut(lire(nom))
            if t:
                resultat["entete"] = t[:200]
        if re.match(r"word/footer\d*\.xml$", nom) and not resultat["pied"]:
            t = _texte_brut(lire(nom))
            if t:
                resultat["pied"] = t[:200]

    # 4. Premières lignes du document : raison sociale, SIRET, certifications.
    if "word/document.xml" in noms:
        corps = _texte_brut(lire("word/document.xml"))
        resultat["premieres_lignes"] = [s.strip() for s in corps[:500].split("  ") if s.strip()][:8]
        resultat["texte_entete_doc"] = corps[:500]

    # 5. Logo : la plus grosse image embarquée.
    images = [(n, z.getinfo(n).file_size) for n in noms if n.startswith("word/media/")]
    if images:
        nom_img, _ = max(images, key=lambda x: x[1])
        try:
            resultat["logo_octets"] = z.read(nom_img)
            resultat["logo_nom"] = nom_img.rsplit("/", 1)[-1]
            resultat["logo_present"] = True
        except Exception:
            pass

    return resultat


def consolider_proposition(extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrège plusieurs documents en une proposition de charte unique.

    Chaque champ porte sa provenance (le fichier d'où il vient). Un champ pour lequel
    aucun signal fiable n'a été trouvé est renvoyé à None avec un motif — jamais
    comblé par une valeur plausible.
    """
    couleurs = Counter()
    polices = Counter()
    provenance: Dict[str, Any] = {}
    entete = pied = None
    source_entete = source_pied = None
    lignes_identite: List[Tuple[str, str]] = []
    logo = None

    for ext in extractions:
        couleurs.update(ext.get("couleurs") or {})
        polices.update(ext.get("polices") or {})
        if not entete and ext.get("entete"):
            entete, source_entete = ext["entete"], ext.get("fichier")
        if not pied and ext.get("pied"):
            pied, source_pied = ext["pied"], ext.get("fichier")
        if ext.get("texte_entete_doc"):
            lignes_identite.append((ext["texte_entete_doc"], ext.get("fichier") or ""))
        if logo is None and ext.get("logo_present"):
            logo = ext

    utilisables = _couleurs_utilisables(couleurs)
    # Couleur principale : la plus fréquente qui soit réellement colorée.
    principale = next((c for c, _ in utilisables if _saturation(c.lower()) > 0.15), None)
    # Couleur secondaire : la plus foncée des autres (texte, titres).
    autres = [c for c, _ in utilisables if c != principale]
    secondaire = min(autres, key=lambda c: _luminance(c.lower())) if autres else None

    proposition: Dict[str, Any] = {}
    motifs_absence: Dict[str, str] = {}

    if principale:
        proposition["primary_color"] = f"#{principale}"
        if principale in _COULEURS_WORD_PAR_DEFAUT:
            provenance["primary_color"] = (
                "Couleur la plus présente dans les documents déposés — mais c'est une "
                "couleur par défaut de Word, pas nécessairement votre charte. "
                "À confirmer avec votre logo."
            )
            proposition["primary_color_a_confirmer"] = True
        else:
            provenance["primary_color"] = "Couleur la plus présente dans les documents déposés"
    else:
        motifs_absence["primary_color"] = (
            "Aucune couleur de marque trouvée : les documents déposés sont en noir, blanc "
            "et gris. À saisir à la main."
        )
    if secondaire:
        proposition["secondary_color"] = f"#{secondaire}"
        provenance["secondary_color"] = "Couleur foncée dominante (titres et texte)"

    police = next((p for p, _ in polices.most_common() if not p.startswith("+")), None)
    if police:
        proposition["font_family"] = police
        provenance["font_family"] = "Police dominante des documents déposés"
    else:
        motifs_absence["font_family"] = "Aucune police explicite : le document utilise celle du thème par défaut."

    if entete:
        proposition["header_text"] = entete
        provenance["header_text"] = f"En-tête de {source_entete}"
    if pied:
        proposition["footer_text"] = pied
        provenance["footer_text"] = f"Pied de page de {source_pied}"

    # Identité : raison sociale, SIRET, certifications, lues telles quelles.
    for texte, fichier in lignes_identite:
        if "company_name" not in proposition:
            debut = texte.strip()
            trouve = None
            m_rs = _MOTIF_RAISON_SOCIALE.match(debut)
            if m_rs:
                trouve = m_rs.group(1).strip()
            else:
                # Repli : tout ce qui precede la mention SIRET, souvent accolee au nom.
                avant_siret = re.split(r"\bSIRET\b", debut, maxsplit=1, flags=re.IGNORECASE)[0].strip()
                candidat = avant_siret.split("  ")[0].strip(" -—|")
                if 3 <= len(candidat) <= 80 and candidat.count(" ") <= 8:
                    trouve = candidat
            if trouve:
                proposition["company_name"] = trouve
                provenance["company_name"] = f"En-tête de {fichier}"
        if "siret" not in proposition:
            m = _MOTIF_SIRET.search(texte) or _MOTIF_SIREN.search(texte)
            if m:
                proposition["siret"] = re.sub(r"\D", "", m.group(1))
                provenance["siret"] = f"Mention SIRET/SIREN lue dans {fichier}"
        certifs = sorted({c.upper().replace("  ", " ") for c in _MOTIFS_CERTIFS.findall(texte)})
        if certifs and "certifications" not in proposition:
            proposition["certifications"] = certifs
            provenance["certifications"] = f"Mentions relevées dans {fichier}"

    if not proposition.get("company_name"):
        motifs_absence["company_name"] = "Raison sociale non identifiable en tête des documents déposés."

    return {
        "proposition": proposition,
        "provenance": provenance,
        "champs_non_trouves": motifs_absence,
        "logo": {
            "present": bool(logo),
            "nom": logo.get("logo_nom") if logo else None,
            "octets": logo.get("logo_octets") if logo else None,
            "fichier_source": logo.get("fichier") if logo else None,
        },
        "documents_analyses": [e.get("fichier") for e in extractions],
    }
