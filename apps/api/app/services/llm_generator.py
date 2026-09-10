"""
LLM Generation Engine for Technical BTP Memos (Mémoires Techniques BTP)
Orchestrates Claude 3.5 Sonnet / Mistral via LiteLLM with strict BTP domain prompt engineering,
internal & web source citations, and anti-hallucination flagging.
Strictly localized per tenant country regulatory profile (Zero hardcoded French norms).
"""
import json
import re
import time
from typing import Any, Dict, List, Optional
import litellm
from app.core.config import settings

# 29/08 (2e confirmation redemarrage) : `litellm.drop_params = True` est desormais pose de
# facon centrale dans app.core.config (importe avant tout par main.py ET celery_app.py) --
# voir le commentaire la-bas pour le bug reel que ceci corrige (UnsupportedParamsError sur
# temperature pour certains modeles, ex. claude-opus-5, repli silencieux vers le moteur de
# gabarits). Rien a faire ici, `settings` importe juste au-dessus suffit a l'activer.


# ---------------------------------------------------------------------------
# 06/09 - Bug "conformement au cadre reglementaire applicable (None)"
#
# dict.get(cle, defaut) ne renvoie le defaut que si la CLE est absente. Or les
# profils pays existent en base avec toutes leurs colonnes a NULL tant que
# personne ne les a remplies : la cle est donc presente, sa valeur vaut None,
# et c'est la chaine "None" qui partait dans le prompt ET dans le HTML livre
# au client ("... cadre reglementaire applicable (None)").
#
# Consequence directe sur la qualite : le modele recevait cinq lignes "None"
# en guise de cadre reglementaire. Soit il les ignorait, soit -- pire -- il
# comblait le vide en inventant des normes. Les deux cassent le principe de
# reponse sans invention.
#
# On ne remplace donc PAS un champ vide par une formule generique (ce serait
# deja une invention deguisee) : on dit explicitement au modele que le point
# n'est pas documente et qu'il lui est interdit de citer une norme dessus.
# ---------------------------------------------------------------------------
REG_NON_DOCUMENTE = (
    "NON DOCUMENTÉ dans le profil pays — n'invente et ne cite aucune norme, "
    "aucun texte ni aucun sigle sur ce point"
)


def reg_value(regulatory_profile: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
    """Lit un champ du profil pays en traitant NULL et chaine vide comme absents."""
    raw = (regulatory_profile or {}).get(key)
    if raw is None:
        return default
    if isinstance(raw, str) and not raw.strip():
        return default
    if isinstance(raw, (list, tuple, dict)) and len(raw) == 0:
        return default
    return raw


def reg_documented(regulatory_profile: Optional[Dict[str, Any]], *keys: str) -> List[str]:
    """Renvoie la liste des champs pays reellement renseignes (pour tracabilite)."""
    return [k for k in keys if reg_value(regulatory_profile, k) is not None]


def build_btp_system_prompt(
    regulatory_profile: Dict[str, Any],
    tenant_system_prompt: Optional[str] = None,
    language: str = "fr",
) -> str:
    """
    Dynamically constructs the BTP system prompt tailored to the tenant's country regulatory profile.
    Incorporates the tenant's custom system prompt (saved in tenant branding_config) if specified.
    Eliminates all hardcoded country-specific norms.
    """
    if not regulatory_profile:
        raise ValueError("regulatory_profile est requis pour construire le prompt système — aucun défaut silencieux autorisé")

    country_name = reg_value(regulatory_profile, "country_name", "National")
    standards_ref = reg_value(regulatory_profile, "technical_standards_reference", REG_NON_DOCUMENTE)
    env_reg = reg_value(regulatory_profile, "environmental_regulation", REG_NON_DOCUMENTE)
    proc_regime = reg_value(regulatory_profile, "public_procurement_regime", REG_NON_DOCUMENTE)
    safety_reg = reg_value(regulatory_profile, "safety_plan_regime", REG_NON_DOCUMENTE)
    waste_reg = reg_value(regulatory_profile, "waste_tracking_regime", REG_NON_DOCUMENTE)
    recognized_quals = reg_value(regulatory_profile, "recognized_qualifications", []) or []
    quals_str = ", ".join(recognized_quals) if recognized_quals else REG_NON_DOCUMENTE

    base_prompt = f"""Tu es un Ingénieur Principal Méthodes & Études de Prix BTP et un Rédacteur expert de Mémoires Techniques pour les Appels d'Offres de marchés publics et privés en {country_name}.

CADRE RÉGLEMENTAIRE ET NORMATIF DU PAYS ({country_name.upper()}) :
- Normes et référentiels techniques applicables : {standards_ref}
- Réglementation environnementale et RSE : {env_reg}
- Régime de la commande publique : {proc_regime}
- Sécurité et prévention santé : {safety_reg}
- Filières et traçabilité des déchets : {waste_reg}
- Qualifications professionnelles reconnues : {quals_str}

DIRECTIVES DE RÉDACTION STRICTES :
1. TON ET STYLE : Rédige de manière technique, factuelle, chiffrée, méthodique et engageante.
2. ZÉRO JARGON MARKETING FLOU : Bannis les expressions vagues. Utilise des engagements quantifiés et des normes précises ({standards_ref}, {env_reg}, {safety_reg}, charte chantier à faibles nuisances).
3. DOUBLE SYSTÈME DE CITATION DES SOURCES :
   - Pour les éléments issus des pièces de marché du projet : cite explicitement sous la forme [Source : CCTP Lot X, Page Y] ou [Source : Règlement de Consultation - Art. Z].
   - Pour les éléments issus du savoir-faire ou du parc matériel de l'entreprise : cite sous la forme [Source : Entreprise - Savoir-Faire] ou [Source : Entreprise - Qualifications & Références].
   - Pour les éléments issus de la recherche web externe (normes techniques, guides professionnels, {env_reg}, données acheteur) : cite obligatoirement sous la forme explicite [Source web : Titre de la source — URL].
   - Pour les éléments issus d'un site de référence explicitement ajouté par l'entreprise (ex. site de l'acheteur public visé) : cite obligatoirement sous la forme explicite [Site de référence client : Titre — URL]. Ces sources sont prioritaires pour maximiser la conformité au client visé.
4. RÈGLE STRICTE ANTI-HALLUCINATION / TRANSPARENCE :
   - Si une exigence particulière du DCE ou une consigne ne trouve de réponse ni dans les documents internes de l'entreprise ni dans les sources web fiables fournies, NE RIEN INVENTER.
   - Insère immédiatement un marqueur explicite sous la forme : [Donnée non trouvée / Manquante : Préciser le choix technique ou la référence manquante].
5. FORMAT DE SORTIE :
   - Le contenu doit être structuré avec des balises HTML riches (<h2>, <h3>, <p>, <ul>, <ol>, <li>, <strong>, <table>, <tr>, <th>, <td>).
   - Fournis également une note de conformité (compliance_score /100) et une justification des points forts vis-à-vis des critères du RC.
"""

    # Langue de sortie (30/08) : le prompt ci-dessus est intégralement rédigé en
    # français, y compris pour un tenant ayant choisi anglais/arabe (Project.output_language).
    # Ce bloc est délibérément répété (voir aussi la fin du user_prompt dans
    # generate_memo_section) et placé en dernier, juste avant le prompt personnalisé du
    # tenant, pour maximiser sa prise en compte par le LLM (effet de récence).
    _LANGUAGE_NAMES = {"fr": "français", "en": "English", "ar": "Arabic (العربية الفصحى)"}
    _lang_key = language if language in _LANGUAGE_NAMES else "fr"
    if _lang_key != "fr":
        lang_label = _LANGUAGE_NAMES[_lang_key]
        base_prompt += f"""
LANGUE DE RÉDACTION OBLIGATOIRE — PRIORITAIRE SUR TOUTES LES INSTRUCTIONS CI-DESSUS :
Bien que ces instructions soient rédigées en français, tu dois produire l'INTÉGRALITÉ de
ta réponse (tous les titres, tout le texte, toutes les listes, le champ "title", le champ
"content_html" et le champ "compliance_notes") exclusivement en {lang_label}. N'inclus
aucune phrase en français, y compris dans les libellés de citation (traduis "[Source : ...]"
en "[Source: ...]" en anglais, ou l'équivalent arabe). Seules les références réglementaires
qui n'ont pas d'équivalent officiel traduit peuvent rester dans leur langue d'origine, entre
parenthèses. Cette directive prévaut sur la langue des documents sources fournis (DCE,
savoir-faire entreprise), qui peuvent rester en français : traduis leur sens, pas leurs mots.
MANDATORY OUTPUT LANGUAGE: Write your entire response in {lang_label}, regardless of the
language of this system prompt or of any source material provided to you.
"""

    if tenant_system_prompt and tenant_system_prompt.strip():
        base_prompt += f"""
DIRECTIVES ET POSITIONNEMENT SPÉCIFIQUES DE L'ENTREPRISE (PROMPT SYSTÈME PERSONNALISÉ) :
{tenant_system_prompt.strip()}
"""

    return base_prompt


# Budgets de contexte, en CARACTERES. Releves le 10/09 : ils avaient ete calibres
# a l'epoque ou la sortie etait plafonnee a 2500 tokens, et rognaient donc la matiere
# meme du memoire -- en particulier les anciens memoires de l'entreprise, qui sont
# precisement ce qui permet de reproduire son style. ~57 000 caracteres au total,
# soit de l'ordre de 16 000 tokens d'entree : largement dans la fenetre de tous les
# modeles vises, pour un cout d'entree qui reste tres inferieur au cout de sortie.
CONTEXT_LIMITS = {
    "dce": 20000,
    "anciens_memoires": 20000,
    "assets": 12000,
    "apprentissages": 6000,
    "web": 6000,
    "client_sites": 5000,
}

# Categories de company_assets qui constituent le corpus de STYLE : ce sont d'anciens
# memoires ou fiches de reference deja remis par l'entreprise, pas des fiches produit.
CATEGORIES_ANCIENS_MEMOIRES = ("memoire_reference", "memoire", "dossier_reference", "reference_chantier")


# ---------------------------------------------------------------------------
# 10/09 - CAUSE RACINE DE "presque vide, chaque paragraphe pas clair".
#
# L'appel etait plafonne a max_tokens=2500. Or on demande au modele, dans UN
# SEUL objet JSON avec echappement, la totalite de :
#   - content_html : le corps redige de la section (le livrable),
#   - compliance_checklist : une entree par critere du RC + par exigence pays,
#   - compliance_notes, web_sources_used, client_sources_used.
# L'echappement JSON de HTML (\" partout) gonfle encore le cout en tokens.
#
# Resultat systematique : le modele atteint le plafond en plein milieu d'une
# chaine, la reponse est coupee, json.loads leve
#   "Unterminated string starting at: line 3 column 19 (char 66)"
# et TOUT est jete au profit du moteur de gabarits degrade. On paie donc
# l'enorme prompt d'entree (DCE + savoir-faire + web) pour ne rien recuperer.
#
# Trois correctifs complementaires ci-dessous :
#   1. un plafond de sortie realiste, reglable par variable d'environnement ;
#   2. la detection explicite de la troncature (finish_reason == "length") ;
#   3. un sauvetage du JSON partiel plutot que la perte seche.
# ---------------------------------------------------------------------------

# Plafond de sortie. 2500 etait le bug ; 12000 laisse la place a une section
# redigee ET a une grille de conformite complete. Reglable sans redeploiement.
DEFAULT_MAX_OUTPUT_TOKENS = 12000

# Delai maximal d'un appel au fournisseur, en secondes.
LLM_CALL_TIMEOUT_SECONDS = 180


def resolve_max_output_tokens() -> int:
    raw = getattr(settings, "LLM_MAX_OUTPUT_TOKENS", None)
    try:
        value = int(raw) if raw else DEFAULT_MAX_OUTPUT_TOKENS
    except (TypeError, ValueError):
        value = DEFAULT_MAX_OUTPUT_TOKENS
    # Garde-fous : jamais sous 4000 (on retomberait dans le bug), jamais
    # au-dessus de 32000 (aucun fournisseur courant ne l'accepte en sortie).
    return max(4000, min(value, 32000))


def _finish_reason(response) -> str:
    try:
        return (getattr(response.choices[0], "finish_reason", "") or "").lower()
    except Exception:
        return ""


def _strip_code_fence(raw: str) -> str:
    """Certains modeles renvoient le JSON dans un bloc ```json ... ``` malgre
    response_format. On enleve la cloture avant de parser."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


_JSON_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<punct>[{}\[\],:])
    | (?P<string>"(?:[^"\\]|\\.)*")
    | (?P<literal>-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|true|false|null)
    """,
    re.VERBOSE,
)


def _repair_truncated_json(text: str) -> Optional[str]:
    """Reconstruit un JSON coupe en plein vol, en coupant au dernier point sur.

    Principe : on retokenise le texte en suivant l'automate JSON (objet attend
    une cle, puis deux-points, puis une valeur, puis une virgule...). A chaque
    fois qu'une VALEUR complete vient d'etre lue, on memorise la position ainsi
    que la pile de conteneurs ouverts : c'est un endroit ou l'on peut couper et
    refermer proprement. Quand la tokenisation bute (chaine non terminee, texte
    coupe net), on revient au dernier point sur et on referme la pile.

    Cette precaution evite deux pieges d'une reparation naive :
      - couper sur une CLE sans valeur ({"a":1,"b} est invalide) ;
      - couper juste apres un crochet ouvrant ({"a":[ ).
    Dans les deux cas on recule jusqu'a la derniere valeur complete.

    Renvoie None si le texte est deja valide (rien a reparer) ou si rien n'est
    recuperable -- jamais un JSON approximatif qui casserait plus loin.
    """
    if not text:
        return None

    stack: List[str] = []          # caracteres de fermeture attendus
    expect = "value"               # value | key | colon | comma_or_end
    safe_cut: Optional[int] = None
    safe_stack: List[str] = []
    pos = 0
    length = len(text)
    truncated = False

    def mark_value_done(end_pos: int) -> None:
        nonlocal safe_cut, safe_stack, expect
        expect = "comma_or_end"
        safe_cut = end_pos
        safe_stack = list(stack)

    while pos < length:
        m = _JSON_TOKEN_RE.match(text, pos)
        if not m:
            truncated = True       # chaine non terminee ou caractere illegal
            break
        pos = m.end()
        if m.lastgroup == "ws":
            continue
        if m.lastgroup == "string":
            if expect in ("key", "key_or_end"):
                expect = "colon"
            elif expect in ("value", "value_or_end"):
                mark_value_done(m.end())
            else:
                return None        # structure inattendue : on ne bricole pas
            continue
        if m.lastgroup == "literal":
            if expect not in ("value", "value_or_end"):
                return None
            mark_value_done(m.end())
            continue
        tok = m.group("punct")
        if tok == "{":
            if expect not in ("value", "value_or_end"):
                return None
            stack.append("}")
            expect = "key_or_end"
        elif tok == "[":
            if expect not in ("value", "value_or_end"):
                return None
            stack.append("]")
            expect = "value_or_end"
        elif tok in "}]":
            if not stack or stack[-1] != tok:
                return None
            stack.pop()
            mark_value_done(m.end())
        elif tok == ":":
            if expect != "colon":
                return None
            expect = "value"
        elif tok == ",":
            if expect != "comma_or_end":
                return None
            expect = "key" if (stack and stack[-1] == "}") else "value"

    if not truncated and not stack and expect == "comma_or_end":
        return None                # deja valide : l'erreur vient d'ailleurs
    if safe_cut is None or not safe_stack:
        return None                # rien de complet n'a ete lu
    return text[:safe_cut] + "".join(reversed(safe_stack))


def parse_llm_json(raw_content: str, finish_reason: str = "") -> Dict[str, Any]:
    """Parse la reponse du modele, en recuperant le maximum si elle est coupee.

    Leve une ValueError explicite (et non une JSONDecodeError opaque) quand
    rien n'est recuperable, pour que le motif affiche au client dise la verite.
    """
    text = _strip_code_fence(raw_content)
    if not text:
        raise ValueError("Le modèle n'a renvoyé aucun contenu.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        repaired = _repair_truncated_json(text)
        if repaired:
            try:
                data = json.loads(repaired)
                data["_truncated"] = True
                data["_truncation_reason"] = (
                    "réponse coupée par le plafond de sortie du modèle"
                    if finish_reason == "length"
                    else "réponse JSON incomplète renvoyée par le modèle"
                )
                print(
                    "[LLMGenerator] Reponse tronquee (finish_reason=%r) : JSON reconstruit, "
                    "%d caracteres recuperes." % (finish_reason, len(repaired))
                )
                return data
            except json.JSONDecodeError:
                pass
        hint = ""
        if finish_reason == "length":
            hint = (
                " Le modèle a atteint son plafond de tokens de sortie "
                "(augmenter LLM_MAX_OUTPUT_TOKENS ou réduire le contexte)."
            )
        raise ValueError(f"Réponse JSON illisible du modèle : {exc}.{hint}")


def bounded_context_join(items: List[str], max_chars: int, section_name: str) -> str:
    """
    Joint les éléments de contexte avec vérification et log explicite de troncature.
    Ne tronque jamais silencieusement.
    """
    joined = "\n\n".join([it for it in items if it and it.strip()])
    if len(joined) > max_chars:
        print(
            f"[CONTEXT BUDGET WARNING] Dépassement sur la section '{section_name}' : "
            f"{len(joined)} caractères (plafond : {max_chars}). Troncature explicite appliquée."
        )
        return (
            joined[:max_chars]
            + f"\n\n[... Troncature explicite : limite de {max_chars} caractères atteinte pour la section {section_name} ...]"
        )
    return joined


class LLMGeneratorService:
    def __init__(self):
        self.default_model = settings.DEFAULT_LLM_MODEL
        self.fallback_model = settings.FALLBACK_LLM_MODEL

    async def generate_memo_section(
        self,
        project_title: str,
        reference_code: str,
        section_key: str,
        section_title: str,
        decision_form: Dict[str, Any],
        dce_criteria: List[Dict[str, Any]],
        rag_dce_chunks: List[Dict[str, Any]],
        rag_company_assets: List[Dict[str, Any]],
        rag_web_sources: Optional[List[Dict[str, Any]]] = None,
        rag_client_sites: Optional[List[Dict[str, Any]]] = None,
        tenant_learnings: Optional[List[Dict[str, Any]]] = None,
        regulatory_profile: Optional[Dict[str, Any]] = None,
        tenant_system_prompt: Optional[str] = None,
        language: str = "fr",
        custom_instructions: Optional[str] = None,
        llm_model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        fallback_model: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        fallback_api_base: Optional[str] = None,
        # Chaine de replis ordonnee (10/09). Si elle est fournie, elle remplace le
        # triplet fallback_model/api_key/api_base ci-dessus, conserve pour les
        # appelants existants et les tests.
        fallback_chain: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:

        """
        Generates a high-value BTP technical memo section using RAG context + chantier decisions + web enrichment + tenant experience learnings + country regulatory profile + tenant custom system prompt.
        Strictly requires a valid regulatory_profile (No silent fallback).
        Uses tenant-specified or platform-default LLM model.
        """
        if regulatory_profile is None:
            raise ValueError("regulatory_profile est requis — aucun défaut silencieux autorisé")

        reg = regulatory_profile
        web_sources = rag_web_sources or []
        client_sites = rag_client_sites or []
        learnings_list = tenant_learnings or []
        target_model = llm_model or self.default_model

        print(f"[LLMGenerator] Executing memo generation using LLM model: '{target_model}'")



        # Build prompt context with strict section character budgets and explicit logging
        dce_items = [
            f"--- Extrait DCE ({c.get('section_title', 'Pièce')}, p.{c.get('page_number', 1)}) ---\n{c.get('content', '')}"
            for c in rag_dce_chunks
        ]
        # 10/09 : les anciens memoires de l'entreprise etaient noyes dans le meme bloc
        # que les fiches materiel et les certificats, sous l'intitule "savoir-faire".
        # Le modele n'avait donc aucune raison de comprendre qu'il devait en REPRODUIRE
        # LE STYLE -- alors que c'est la demande centrale du produit : "tout ce que
        # faisait le client dans les anciens sera fait au meme style". On les isole.
        def _est_ancien_memoire(a: Dict[str, Any]) -> bool:
            return str(a.get("category") or "").strip().lower() in CATEGORIES_ANCIENS_MEMOIRES

        anciens_memoires = [a for a in rag_company_assets if _est_ancien_memoire(a)]
        autres_assets = [a for a in rag_company_assets if not _est_ancien_memoire(a)]

        anciens_items = [
            f"--- Ancien dossier remis par l'entreprise : {a.get('title', 'Sans titre')} ---\n{a.get('description', a.get('content', ''))}"
            for a in anciens_memoires
        ]
        assets_items = [
            f"--- Savoir-faire Entreprise ({a.get('category', 'Asset')}) : {a.get('title', '')} ---\n{a.get('description', a.get('content', ''))}"
            for a in autres_assets
        ]
        web_items = [
            f"--- Source Web ({w.get('title', 'Web')}) ---\nURL: {w.get('url', '')}\nExtrait: {w.get('snippet', '')}"
            for w in web_sources
        ]
        client_sites_items = [
            f"--- Site de Référence Client ({c.get('title', 'Site')}) ---\nURL: {c.get('url', '')}\nExtrait: {c.get('content', '')}"
            for c in client_sites
        ]
        learnings_items = [
            f"- [Enseignement AO antérieur ({l.get('category', 'général')})] {l.get('title', '')} : {l.get('insight', '')} => Directive : {l.get('directive', '')}"
            for l in learnings_list
        ]

        dce_context_text = bounded_context_join(dce_items, CONTEXT_LIMITS["dce"], "DCE")
        anciens_context_text = bounded_context_join(anciens_items, CONTEXT_LIMITS["anciens_memoires"], "Anciens mémoires")
        assets_context_text = bounded_context_join(assets_items, CONTEXT_LIMITS["assets"], "Company Assets")
        web_context_text = bounded_context_join(web_items, CONTEXT_LIMITS["web"], "Web Sources")
        client_sites_context_text = bounded_context_join(client_sites_items, CONTEXT_LIMITS["client_sites"], "Client Reference Sites")
        learnings_context_text = bounded_context_join(learnings_items, CONTEXT_LIMITS["apprentissages"], "Apprentissages")

        user_prompt = f"""
PROJET : {project_title} (Réf : {reference_code})
SECTION À RÉDIGER : {section_title} (Clé : {section_key})

1. CADRE RÉGLEMENTAIRE DU PAYS DU MARCHÉ ({reg_value(reg, 'country_name', 'National')}) :
- Normes techniques applicables : {reg_value(reg, 'technical_standards_reference', REG_NON_DOCUMENTE)}
- Réglementation environnementale : {reg_value(reg, 'environmental_regulation', REG_NON_DOCUMENTE)}
- Régime de la commande publique : {reg_value(reg, 'public_procurement_regime', REG_NON_DOCUMENTE)}
- Traçabilité des déchets : {reg_value(reg, 'waste_tracking_regime', REG_NON_DOCUMENTE)}
- Plan de sécurité chantier : {reg_value(reg, 'safety_plan_regime', REG_NON_DOCUMENTE)}

2. DONNÉES DU FORMULAIRE CONDUCTEUR DE TRAVAUX :
{json.dumps(decision_form, ensure_ascii=False, indent=2)}

3. CRITÈRES DE NOTATION DU RÈGLEMENT DE CONSULTATION (RC) :
{json.dumps(dce_criteria, ensure_ascii=False, indent=2)}

4. EXTRAITS PERTINENTS DU DCE (CCTP, RC) :
{dce_context_text or "Aucun extrait DCE spécifique fourni."}

5. ANCIENS DOSSIERS REMIS PAR CETTE ENTREPRISE — RÉFÉRENCE DE STYLE ET DE FOND :
{anciens_context_text or "Aucun ancien mémoire n'a été chargé pour cette entreprise."}
DIRECTIVE : ces textes ont déjà été remis à des acheteurs publics par cette entreprise.
Reprends-en la structure de raisonnement, le vocabulaire métier, les intitulés de poste,
les unités et le niveau de détail chiffré. Le jury doit reconnaître la même plume. Tu peux
proposer une amélioration (un tableau là où il y avait un paragraphe, un engagement
chiffré là où il était vague), mais jamais un texte générique qui pourrait appartenir à
n'importe quelle entreprise. En revanche, ne recopie JAMAIS un chiffre, une référence de
chantier ou un nom propre d'un ancien dossier dans celui-ci : ils concernent un autre
marché. Ces textes servent de modèle de forme, pas de réservoir de faits.

5 bis. SAVOIR-FAIRE, CERTIFICATS ET MOYENS DE L'ENTREPRISE :
{assets_context_text or "Aucune fiche savoir-faire chargée pour cette entreprise."}

6. RETOUR D'EXPÉRIENCE DU CLIENT (ENSEIGNEMENTS ACCUMULÉS DU TENANT) :
{learnings_context_text or "Aucun retour d'expérience antérieur enregistré pour ce tenant."}

7. SOURCES WEB TECHNIQUES & RÉGLEMENTAIRES (SERPER) :
{web_context_text or "Aucune recherche web externe nécessaire."}

8. SITES DE RÉFÉRENCE AJOUTÉS PAR LE TENANT (PRIORITAIRES — ex. site de l'acheteur public visé par cet AO, fédération professionnelle...) :
{client_sites_context_text or "Aucun site de référence configuré par l'entreprise pour ce tenant."}
IMPORTANT : si des extraits figurent ci-dessus, tu DOIS explicitement t'appuyer dessus pour maximiser la conformité au client/acheteur visé, et justifier chaque usage dans "compliance_checklist" avec la source "[Site de référence client : Titre]". Ne cite jamais un site de référence pour une information qu'il ne contient pas réellement.

9. CONSIGNES PARTICULIÈRES (PRIORITAIRES — SURCHARGENT LES SECTIONS 1 À 8 CI-DESSUS EN CAS DE CONFLIT) :
{custom_instructions or "Aucune instruction supplémentaire."}

10. LANGUE DE RÉDACTION OBLIGATOIRE (rappel) :
{"Rédige l'intégralité de cette section en " + {"en": "anglais (English)", "ar": "arabe (العربية الفصحى)"}.get(language, "français") + ", y compris les titres et les libellés de citation, quelle que soit la langue des extraits sources ci-dessus." if language in ("en", "ar") else "Français (comportement standard)."}


INSTRUCTIONS DE SORTIE :
Réponds UNIQUEMENT par un objet JSON strict : pas une ligne de texte avant, pas une après,
aucun bloc markdown. Structure attendue :
{{
  "title": "{section_title}",
  "content_html": "<h3>Sous-titre</h3><p>...</p><table>...</table>",
  "compliance_score": 0,
  "compliance_notes": "Ce qui est couvert, ce qui ne l'est pas, et pourquoi.",
  "compliance_checklist": [
    {{"criterion": "Intitulé exact du critère RC ou de l'exigence réglementaire concernée", "status": "met", "source": "[Source : CCTP p.X] ou [Savoir-faire entreprise] ou [Source web : Titre] ou [Site de référence client : Titre] ou [Profil réglementaire pays]", "justification": "Une phrase précise citant le passage exact qui couvre ce point."}}
  ],
  "gaps": [
    {{"missing": "Ce qui manquait dans le contexte fourni", "impact": "Ce que cela empêche d'affirmer dans cette section", "how_to_fix": "Le document ou la donnée à fournir pour lever le point"}}
  ],
  "visual_specs": [],
  "web_sources_used": [{{"title": "...", "url": "..."}}],
  "client_sources_used": [{{"title": "...", "url": "..."}}]
}}

A. EXIGENCES DE FOND SUR "content_html" — c'est LE livrable, un jury le note :
A1. VOLUME : entre 900 et 1500 mots. En dessous de 900 mots la section est refusée :
    une demi-page de généralités ne vaut aucun point dans une notation d'appel d'offres.
A2. STRUCTURE : 3 à 6 sous-parties introduites par <h3>. Des paragraphes <p> de 4 à
    8 lignes. Les listes <ul> uniquement pour de vraies énumérations (moyens, étapes,
    documents) — jamais pour découper une idée qui devrait être rédigée.
A3. AU MOINS UN TABLEAU <table> réellement informatif dès que la section s'y prête
    (moyens humains, moyens matériels, phasage, cadences, contrôles, points d'arrêt,
    correspondance exigence -> réponse). Un tableau de 2 lignes vides ne compte pas.
A4. CHIFFRER SYSTÉMATIQUEMENT : effectifs, cadences, délais, tonnages, fréquences de
    contrôle, références de normes. Un engagement non chiffré n'engage à rien.
A5. PHRASES INTERDITES — n'écris jamais des formules creuses de ce type :
    "nous mettons un point d'honneur à", "acteur incontournable", "solution sur mesure",
    "nous nous engageons à respecter les normes en vigueur", "notre savoir-faire reconnu".
    Chaque phrase doit apporter un fait, un chiffre, une méthode ou une preuve.
A6. CITATIONS : chaque affirmation factuelle porte sa source, au format défini plus haut.
    Une phrase sans source doit être une phrase de méthode, jamais une affirmation
    sur le marché, sur l'entreprise ou sur la réglementation.
A7. STYLE DE L'ENTREPRISE : la section 5 contient ses anciens dossiers, la 5 bis son
    savoir-faire, la 6 ses enseignements capitalisés. Le mémoire doit se lire comme la
    suite de ses dossiers précédents — même vocabulaire, mêmes intitulés de poste, mêmes
    unités, même niveau de détail chiffré — et jamais comme un texte interchangeable.
A8. ZÉRO INVENTION : jamais un nom de personne, une référence de chantier, un chiffre
    d'affaires, une certification ou un numéro de norme qui ne figure pas dans le contexte
    fourni. S'il manque une donnée, écris explicitement l'hypothèse ou le champ à
    compléter (par exemple "effectif à confirmer par le conducteur de travaux") et
    reporte le point dans "gaps".

B. "gaps" — DIS CE QUI T'A MANQUÉ. C'est une exigence produit : l'utilisateur doit savoir
   si une section faible vient du modèle ou d'un document absent. Une entrée par manque
   réel (règlement de consultation absent, aucun critère de notation fourni, aucun ancien
   dossier de l'entreprise, planning non communiqué, effectifs inconnus...). Liste vide
   uniquement si le contexte fourni permettait réellement de tout traiter.

C. "visual_specs" — LES SCHÉMAS SONT CRÉÉS AUTOMATIQUEMENT À PARTIR DE CE CHAMP, et
   restent modifiables par l'utilisateur dans l'application. Ne décris donc pas un schéma
   en texte : produis ses données. Deux types sont acceptés, uniquement quand la section
   les justifie et quand le contexte fournit de quoi les remplir :
   - Planning :
     {{"type": "gantt", "title": "Planning prévisionnel des travaux",
       "tasks": [{{"name": "Installation de chantier", "start": "2026-03-02",
                  "end": "2026-03-20", "progress": 0, "is_milestone": false,
                  "depends_on": []}}]}}
     Dates réelles au format AAAA-MM-JJ, déduites du délai d'exécution du marché.
     "depends_on" cite le "name" exact des tâches précédentes.
   - Organigramme de chantier :
     {{"type": "organigramme", "title": "Organigramme d'encadrement",
       "nodes": [{{"nom": "À pourvoir", "role": "Conducteur de travaux",
                  "experience_ans": 15, "presence_hebdo_pct": 50,
                  "qualif": "Ingénieur TP"}}]}}
     L'ordre de la liste EST la hiérarchie : le premier nœud est la tête d'encadrement,
     puis on descend. N'invente JAMAIS un nom de personne : écris "À pourvoir" sauf si le
     nom figure réellement dans le contexte fourni.
   Renvoie [] si la section ne justifie aucun schéma — un planning inventé est pire
   qu'une absence de planning.

D. IMPÉRATIF SUR "compliance_checklist" : la conformité doit être vérifiable point par
   point, jamais un score auto-déclaré. Crée une entrée pour CHAQUE critère de notation du
   RC (section 3) ET pour chaque exigence réglementaire pays citée en section 1, avec
   "status" parmi "met", "partial" ou "missing". Si la section 3 est vide, appuie-toi sur
   les exigences explicites du CCTP (section 4) et signale l'absence de RC dans "gaps".
   N'invente JAMAIS une source : sans preuve interne (DCE / savoir-faire) ou web, le
   statut est "missing" et tu le dis, plutôt que d'affirmer une conformité non prouvée.
"""

        # 1. Try LiteLLM call with dynamic country system prompt and tenant customization
        system_prompt = build_btp_system_prompt(reg, tenant_system_prompt=tenant_system_prompt, language=language)

        # 10/09 - TRANSPARENCE SUR CE QUI EST ENVOYE (donc sur ce qui est facture).
        # "Ca consomme beaucoup de tokens pour un resultat mediocre" etait un reproche
        # impossible a instruire : personne ne savait ce que pesait reellement le
        # prompt, ni quel bloc de contexte le remplissait. On mesure, on remonte, et
        # l'utilisateur peut arbitrer plutot que subir.
        contexte_stats = {
            "dce_chars": len(dce_context_text),
            "anciens_memoires_chars": len(anciens_context_text),
            "savoir_faire_chars": len(assets_context_text),
            "apprentissages_chars": len(learnings_context_text),
            "web_chars": len(web_context_text),
            "sites_client_chars": len(client_sites_context_text),
            "consignes_chars": len(system_prompt) + len(user_prompt)
            - len(dce_context_text) - len(anciens_context_text) - len(assets_context_text)
            - len(learnings_context_text) - len(web_context_text) - len(client_sites_context_text),
            "total_chars": len(system_prompt) + len(user_prompt),
        }
        print(
            "[LLMGenerator] Prompt envoye : %d caracteres au total "
            "(DCE %d, anciens memoires %d, savoir-faire %d, web %d, sites client %d)."
            % (
                contexte_stats["total_chars"], contexte_stats["dce_chars"],
                contexte_stats["anciens_memoires_chars"], contexte_stats["savoir_faire_chars"],
                contexte_stats["web_chars"], contexte_stats["sites_client_chars"],
            )
        )

        # Correctif (29/08) : has_api_key vérifiait settings.ANTHROPIC_API_KEY/MISTRAL_API_KEY/
        # OPENAI_API_KEY mais kwargs["api_key"] n'était réellement posé QUE si le paramètre
        # api_key (résolu via PlatformSettings, l'UI admin -- souvent vide en pratique tant que
        # l'admin n'a rien collé) était non-vide. litellm.completion() partait alors SANS clé
        # explicite et comptait sur os.environ, qui ne contient PAS ces clés (pydantic-settings
        # lit .env sans jamais populate os.environ ici). Conséquence : repli silencieux et
        # systématique vers le moteur de gabarits ci-dessous, jamais un vrai appel LLM.
        def _extract_usage(resp) -> Optional[Dict[str, Any]]:
            """Extrait usage.prompt_tokens/completion_tokens/total_tokens de la reponse
            LiteLLM en dict JSON-safe (30/08, suivi de consommation). Ne leve jamais
            d'exception -- retourne None si absent/format inattendu."""
            try:
                u = getattr(resp, "usage", None)
                if u is None:
                    return None
                return {
                    "prompt_tokens": getattr(u, "prompt_tokens", None),
                    "completion_tokens": getattr(u, "completion_tokens", None),
                    "total_tokens": getattr(u, "total_tokens", None),
                }
            except Exception:
                return None

        def _apply_compliance_checklist(parsed_result: Dict[str, Any]) -> Dict[str, Any]:
            """03/09 (nuit, exigence client) : la conformité doit être vérifiable, pas une
            simple note auto-déclarée par le modèle. Si le modèle a produit une
            "compliance_checklist" (voir prompt ci-dessus), recalcule compliance_score à
            partir d'elle (% de critères réellement couverts, pas un chiffre inventé) et
            l'affiche dans le contenu, avec source + justification par point. Ne modifie
            rien si le modèle n'a pas produit de checklist exploitable (rétro-compatible,
            jamais bloquant pour la génération)."""
            checklist = parsed_result.get("compliance_checklist")
            if not isinstance(checklist, list) or not checklist:
                return parsed_result
            # 10/09 : exiger AUSSI un statut non vide. Une entree reduite a
            # {"criterion": "..."} -- typiquement la derniere ligne d'une reponse
            # coupee et reconstruite -- n'est pas une evaluation : la compter comme
            # "manquant" ferait chuter le score de conformite pour une raison
            # technique, et afficherait au client une ligne "non couvert" fausse.
            valid_items = [
                c for c in checklist
                if isinstance(c, dict) and c.get("criterion") and str(c.get("status") or "").strip()
            ]
            if not valid_items:
                return parsed_result

            met_statuses = ("met", "conforme", "ok", "oui", "yes", "couvert")
            partial_statuses = ("partial", "partiel", "partiellement")
            met_count = sum(1 for c in valid_items if str(c.get("status", "")).strip().lower() in met_statuses)
            partial_count = sum(1 for c in valid_items if str(c.get("status", "")).strip().lower() in partial_statuses)
            parsed_result["compliance_score"] = round(100 * (met_count + 0.5 * partial_count) / len(valid_items), 1)

            def _status_label(raw_status: str) -> str:
                s = raw_status.strip().lower()
                if s in met_statuses:
                    return "✓ Couvert"
                if s in partial_statuses:
                    return "◐ Partiel"
                return "✗ Manquant"

            rows_html = "".join(
                f"<tr><td>{c.get('criterion', '')}</td>"
                f"<td>{_status_label(str(c.get('status', '')))}</td>"
                f"<td>{c.get('source', '') or '—'}</td>"
                f"<td>{c.get('justification', '') or ''}</td></tr>"
                for c in valid_items
            )
            checklist_html = (
                "<h3>Grille de conformité DCE</h3>"
                "<table style=\"width:100%; border-collapse: collapse;\" border=\"1\">"
                "<thead><tr><th>Critère</th><th>Statut</th><th>Source</th><th>Justification</th></tr></thead>"
                f"<tbody>{rows_html}</tbody></table>"
            )
            parsed_result["content_html"] = f"{parsed_result.get('content_html', '')}\n{checklist_html}"
            return parsed_result

        def _flag_truncation(parsed_result: Dict[str, Any]) -> Dict[str, Any]:
            """Signale visiblement une section reconstruite depuis une reponse coupee.

            Le sauvetage du JSON partiel evite de tout perdre, mais le texte recupere
            s'arrete au milieu. Le livrer sans le dire serait pire que l'echec : le
            client relirait une section amputee en la croyant complete. On l'affiche
            donc en tete de section, et on empeche le score de conformite de passer
            pour un resultat definitif."""
            if not parsed_result.get("_truncated"):
                return parsed_result
            motif = parsed_result.get("_truncation_reason") or "réponse incomplète du modèle"
            banniere = (
                '<div style="border-left:4px solid #d97706;background:#fffbeb;'
                'padding:12px 16px;margin:0 0 16px;border-radius:4px;">'
                '<strong>Section incomplète — à régénérer.</strong> '
                f'La réponse du modèle a été interrompue ({motif}). '
                'Le texte ci-dessous s\'arrête donc en cours de rédaction et la grille '
                'de conformité est partielle. Relancez la génération de cette section.'
                "</div>"
            )
            parsed_result["content_html"] = banniere + (parsed_result.get("content_html") or "")
            notes = parsed_result.get("compliance_notes") or ""
            parsed_result["compliance_notes"] = (
                f"[Génération interrompue : {motif} — conformité non concluante] {notes}".strip()
            )
            return parsed_result

        def _fallback_env_api_key(model_str: str) -> Optional[str]:
            """Repli .env apparié au bon fournisseur (jamais une clé Mistral pour un modèle
            anthropic/claude-*, etc.), utilisé seulement si aucune clé admin n'est configurée.
            03/09 (nuit) : l'ancien repli final ("renvoie la 1ère clé env non-vide trouvée,
            n'importe laquelle") pouvait faire passer une clé Anthropic à un modèle Gemini ou
            DeepSeek (aucun des 3 préfixes ci-dessous ne matche) -- échec d'authentification
            garanti plutôt qu'une absence de clé correctement détectée. Aucun repli pour un
            fournisseur non reconnu : None, jamais une clé prise au hasard."""
            if "anthropic" in model_str or "claude" in model_str:
                return settings.ANTHROPIC_API_KEY or None
            if "mistral" in model_str:
                return settings.MISTRAL_API_KEY or None
            if "openai" in model_str or "gpt" in model_str:
                return settings.OPENAI_API_KEY or None
            return None

        def _is_transient_llm_error(exc: Exception) -> bool:
            """Nouvel essai uniquement pour les erreurs manifestement transitoires (surcharge/
            quota momentané du fournisseur) -- jamais pour une clé invalide, un modèle inconnu
            ou une erreur de requête, qui échoueraient de la même façon à chaque tentative."""
            transient_types = tuple(
                t for t in (
                    getattr(litellm, "RateLimitError", None),
                    getattr(litellm, "ServiceUnavailableError", None),
                    getattr(litellm, "Timeout", None),
                    getattr(litellm, "APIConnectionError", None),
                ) if isinstance(t, type)
            )
            if transient_types and isinstance(exc, transient_types):
                return True
            msg = str(exc).lower()
            return any(s in msg for s in ("503", "429", "unavailable", "overloaded", "rate limit", "high demand"))

        def _completion_with_retry(call_kwargs: Dict[str, Any], max_attempts: int = 3, delay_seconds: float = 4.0):
            """Jusqu'à `max_attempts` tentatives -- une surcharge momentanée (503 Gemini
            "high demand", 429...) ne doit pas condamner la génération au moteur de gabarits
            dégradé quand un simple nouvel essai quelques secondes plus tard aurait suffi
            (cause réelle observée le 03/09 : gemini-3.8-flash renvoie 503 UNAVAILABLE en
            pointe de charge chez Google, sans aucun rapport avec la config du tenant)."""
            last_exc: Optional[Exception] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return litellm.completion(**call_kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_attempts and _is_transient_llm_error(exc):
                        print(f"[LLMGenerator] Tentative {attempt}/{max_attempts} échouée (motif transitoire) pour '{call_kwargs.get('model')}': {exc} — nouvel essai dans {delay_seconds:.0f}s.")
                        time.sleep(delay_seconds)
                        continue
                    raise
            raise last_exc

        effective_api_key = api_key or _fallback_env_api_key(target_model)
        has_api_key = bool(effective_api_key)
        # 03/09 (nuit) : capture le VRAI motif d'echec LLM pour l'afficher dans le contenu
        # de secours au lieu du message generique "ne dispose pas encore d'un gabarit dedie"
        # qui ne disait rien de la cause reelle -- impossible jusqu'ici de savoir si c'etait
        # la cle, le modele ou autre chose sans aller lire les logs du conteneur worker.
        _llm_error_detail: Optional[str] = None
        # Consommation de la derniere reponse recue, meme si son contenu s'est revele
        # inexploitable : le fournisseur a bien facture ces tokens.
        _last_usage: Optional[Dict[str, Any]] = None
        if not has_api_key:
            _llm_error_detail = f"Aucune clé API disponible pour le modèle '{target_model}'."
        if has_api_key:
            try:
                kwargs: Dict[str, Any] = {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                    "max_tokens": resolve_max_output_tokens(),
                    # 10/09 : aucun timeout n'etait pose. Un fournisseur qui ne repond
                    # jamais (connexion ouverte mais silencieuse) bloquait definitivement
                    # un slot du worker, et la section restait sur "processing" pour
                    # toujours -- sans erreur, sans trace, sans possibilite de relancer.
                    # 180 s couvre largement une redaction de 12 000 tokens de sortie.
                    "timeout": LLM_CALL_TIMEOUT_SECONDS,
                }
                # Transmis seulement s'il est configure. litellm.drop_params etant
                # actif (voir app.core.config), un modele qui ne connait pas ce
                # parametre l'ignore proprement au lieu d'echouer.
                effort = (getattr(settings, "LLM_REASONING_EFFORT", "") or "").strip().lower()
                if effort in ("minimal", "low", "medium", "high"):
                    kwargs["reasoning_effort"] = effort
                kwargs["api_key"] = effective_api_key
                if api_base:
                    kwargs["api_base"] = api_base

                response = _completion_with_retry(kwargs)
                _last_usage = _extract_usage(response)
                raw_content = response.choices[0].message.content
                parsed = parse_llm_json(raw_content, _finish_reason(response))
                parsed["model_used"] = target_model
                parsed["fallback_used"] = False
                parsed["usage"] = _extract_usage(response)
                parsed = _apply_compliance_checklist(parsed)
                parsed = _flag_truncation(parsed)
                parsed["context_stats"] = contexte_stats
                return parsed
            except Exception as e:
                _llm_error_detail = f"{target_model} : {e}"
                print(f"[LLMGenerator] LiteLLM call notice with model '{target_model}': {e}, attempting fallback if available.")

                # CHAINE DE REPLIS (10/09), et non plus un unique essai.
                #
                # L'ancienne version tentait UN seul fournisseur de secours. Or la
                # cause d'echec la plus frequente est un quota : elle frappe tout le
                # fournisseur, pas la requete. Concretement : modele principal coupe
                # par le plafond de sortie, repli sur le palier gratuit Gemini
                # (20 requetes/jour) deja epuise -> 429 -> moteur de gabarits, alors
                # qu'un troisieme fournisseur parfaitement utilisable etait configure.
                # On essaie donc chaque repli disponible, dans l'ordre choisi par
                # l'administrateur, et on n'abandonne qu'apres les avoir tous vus.
                candidats: List[Dict[str, Any]] = [
                    c for c in (fallback_chain or [])
                    if isinstance(c, dict) and c.get("model_string") and c.get("api_key")
                ]
                if not candidats and fallback_model and fallback_api_key:
                    candidats = [{
                        "model_string": fallback_model,
                        "api_key": fallback_api_key,
                        "api_base": fallback_api_base,
                    }]

                motifs: List[str] = [f"{target_model} : {e}"]
                for candidat in candidats:
                    modele_repli = candidat["model_string"]
                    try:
                        print(f"[LLMGenerator] Tentative de repli sur '{modele_repli}' après échec de '{target_model}'.")
                        fb_kwargs: Dict[str, Any] = dict(kwargs)
                        fb_kwargs["model"] = modele_repli
                        fb_kwargs["api_key"] = candidat["api_key"]
                        if candidat.get("api_base"):
                            fb_kwargs["api_base"] = candidat["api_base"]
                        elif "api_base" in fb_kwargs:
                            del fb_kwargs["api_base"]

                        fb_response = _completion_with_retry(fb_kwargs)
                        _last_usage = _extract_usage(fb_response) or _last_usage
                        fb_raw_content = fb_response.choices[0].message.content
                        fb_parsed = parse_llm_json(fb_raw_content, _finish_reason(fb_response))
                        fb_parsed["model_used"] = modele_repli
                        fb_parsed["fallback_used"] = True
                        fb_parsed["primary_model_failed"] = target_model
                        fb_parsed["usage"] = _extract_usage(fb_response)
                        fb_parsed = _apply_compliance_checklist(fb_parsed)
                        fb_parsed = _flag_truncation(fb_parsed)
                        fb_parsed["context_stats"] = contexte_stats
                        return fb_parsed
                    except Exception as e2:
                        motifs.append(f"repli {modele_repli} : {e2}")
                        print(f"[LLMGenerator] Repli '{modele_repli}' également en échec: {e2}")

                _llm_error_detail = " | ".join(motifs)
                if len(candidats) > 1:
                    print(f"[LLMGenerator] Les {len(candidats)} replis ont échoué -- moteur de gabarits.")


        # 2. Resilient BTP Domain Template Engine with Citations, Learnings & Anti-Hallucination
        res = self._generate_specialized_btp_section(
            section_key=section_key,
            section_title=section_title,
            decision_form=decision_form,
            project_title=project_title,
            rag_dce_chunks=rag_dce_chunks,
            rag_company_assets=rag_company_assets,
            rag_web_sources=web_sources,
            rag_client_sites=client_sites,
            tenant_learnings=learnings_list,
            regulatory_profile=reg,
            custom_instructions=custom_instructions,
            language=language,
            debug_error=_llm_error_detail,
        )
        res["model_used"] = target_model
        res["context_stats"] = contexte_stats

        # 10/09 - HONNETETE DU SCORE DE CONFORMITE.
        #
        # Le moteur de gabarits affichait des scores de 97 a 99 % sur des textes
        # qui ne sont que des canevas : aucune exigence du marche n'a ete lue,
        # aucun critere verifie. C'est la source directe du "tu annonces 85 % et
        # il n'y a rien dedans" : le chiffre venait d'une constante ecrite dans le
        # code, pas d'une evaluation. Un gabarit ne prouve aucune conformite, donc
        # il n'a pas de score -- et on le dit.
        if _llm_error_detail:
            res["compliance_score"] = 0.0
            res["compliance_notes"] = (
                "Aucune rédaction par l'IA n'a abouti : le texte affiché est un canevas, "
                "pas une réponse au marché. Aucune conformité n'a donc pu être vérifiée. "
                f"Cause réelle : {_llm_error_detail}"
            )
            res["degraded"] = True
            # Les tokens consommes par la tentative echouee sont bien reels : ils
            # doivent apparaitre dans le suivi de consommation, sinon le cout du
            # jour est sous-estime precisement les jours ou tout echoue.
            if _last_usage:
                res["usage"] = _last_usage
        return res


    def _generate_specialized_btp_section(
        self,
        section_key: str,
        section_title: str,
        decision_form: Dict[str, Any],
        project_title: str = "",
        rag_dce_chunks: Optional[List[Dict[str, Any]]] = None,
        rag_company_assets: Optional[List[Dict[str, Any]]] = None,
        rag_web_sources: Optional[List[Dict[str, Any]]] = None,
        rag_client_sites: Optional[List[Dict[str, Any]]] = None,
        tenant_learnings: Optional[List[Dict[str, Any]]] = None,
        regulatory_profile: Optional[Dict[str, Any]] = None,
        custom_instructions: Optional[str] = None,
        language: str = "fr",
        debug_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Produces realistic, highly-technical BTP sections tailored from the decision form parameters,
        with explicit internal citations, web citations, accumulated tenant experience learnings,
        and localized country regulatory standards.
        Strictly requires a valid regulatory_profile (No silent fallback).
        """
        if regulatory_profile is None:
            raise ValueError("regulatory_profile est requis — aucun défaut silencieux autorisé")

        reg = regulatory_profile
        dce_chunks = rag_dce_chunks or []
        web_sources = rag_web_sources or []
        client_sites = rag_client_sites or []
        learnings_list = tenant_learnings or []
        delai = decision_form.get("delai_mois", 6)
        materiel = decision_form.get("materiel_principal", "Grue à tour Potain 50m, 2 pelles 22t")
        dechets = decision_form.get("gestion_dechets", "Tri sélectif 5 flux avec 88% de valorisation")
        cadres = decision_form.get("equipe_cadres", [])
        securite = decision_form.get("mesures_securite", f"Respect strict du {reg_value(reg, 'safety_plan_regime', 'plan de sécurité chantier applicable')}")
        rse = decision_form.get("demarche_rse_environnement", f"Conformité {reg_value(reg, 'environmental_regulation', 'à la réglementation environnementale applicable')} et béton bas carbone")

        phases = decision_form.get("phasage_travaux", [])

        # Internationalisation du moteur de gabarits de secours (30/08) : ce moteur ne
        # s'exécute que si l'appel LLM réel (Claude/Mistral/OpenAI) ET son repli ont tous
        # deux échoué -- traduire les ~35 chaînes fixes réparties sur les 7 gabarits de
        # section aurait un rapport risque/valeur défavorable (beaucoup de texte HTML à
        # retranscrire à la main, sans pouvoir exécuter/tester ce code dans cet
        # environnement). Choix assumé : traduire les éléments structurels PARTAGÉS par
        # toutes les sections (citations, sources web, enseignements, alerte de donnée
        # manquante) et ajouter un avertissement honnête et traduit quand la langue
        # demandée n'est pas le français, plutôt que de laisser croire à une traduction
        # complète qui n'existe pas. Le contenu issu du formulaire de décision (matériel,
        # déchets, sécurité...) reste dans la langue saisie par l'utilisateur.
        _FB_I18N = {
            "fr": {
                "source_page": lambda t, p: f"[Source : DCE {t}, Page {p}]",
                "external_sources_h3": "Sources Réglementaires & Techniques Externes",
                "web_source_prefix": "Source web :",
                "web_source_fallback_title": "Référence",
                "client_sites_h3": "Sites de Référence Client",
                "client_site_prefix": "Site de référence client :",
                "learnings_h3": "Retour d'Expérience & Enseignements Capitalisés du Tenant",
                "learning_prefix": lambda cat: f"[Retour d'Expérience Entreprise — {cat}] :",
                "learning_fallback_cat": "Général",
                "missing_data": "<strong>[Donnée non trouvée / Manquante :</strong> Les données relatives à cette exigence spécifique ne figurent ni dans le corpus client (RAG) ni dans les sources web officielles autorisées. Préciser le choix ou l'information requise.]",
                "fallback_notice": "",
            },
            "en": {
                "source_page": lambda t, p: f"[Source: DCE {t}, Page {p}]",
                "external_sources_h3": "External Regulatory & Technical Sources",
                "web_source_prefix": "Web source:",
                "web_source_fallback_title": "Reference",
                "client_sites_h3": "Client Reference Sites",
                "client_site_prefix": "Client reference site:",
                "learnings_h3": "Company Experience Feedback & Capitalized Learnings",
                "learning_prefix": lambda cat: f"[Company Experience Feedback — {cat}]:",
                "learning_fallback_cat": "General",
                "missing_data": "<strong>[Data not found / Missing:</strong> No data addressing this specific requirement was found in the client corpus (RAG) or in the authorized official web sources. Please specify the required choice or information.]",
                "fallback_notice": "<p style='color:#92400e;background:#fffbeb;padding:8px;border-left:4px solid #f59e0b;'><strong>[Notice — backup engine]:</strong> The primary AI service was unavailable, so this section was generated by the offline backup engine. Headings and labels are in English, but free-text content copied directly from your project's decision form (equipment, waste plan, safety measures...) stays in the language it was entered in. Retry generation once the AI service is back for a fully English, AI-written version of this section.</p>",
            },
            "ar": {
                "source_page": lambda t, p: f"[المصدر: وثائق الاستشارة {t}، صفحة {p}]",
                "external_sources_h3": "المصادر التنظيمية والتقنية الخارجية",
                "web_source_prefix": "مصدر ويب:",
                "web_source_fallback_title": "مرجع",
                "client_sites_h3": "مواقع مرجعية للعميل",
                "client_site_prefix": "موقع مرجعي للعميل:",
                "learnings_h3": "الخبرات المكتسبة وملاحظات الشركة",
                "learning_prefix": lambda cat: f"[ملاحظات خبرة الشركة — {cat}]:",
                "learning_fallback_cat": "عام",
                "missing_data": "<strong>[بيانات غير متوفرة / مفقودة:</strong> لا تتوفر بيانات بخصوص هذا المتطلب المحدد لا في مستندات العميل (RAG) ولا في المصادر الرسمية على الويب. يرجى تحديد الخيار أو المعلومة المطلوبة.]",
                "fallback_notice": "<p dir='rtl' style='color:#92400e;background:#fffbeb;padding:8px;border-right:4px solid #f59e0b;'><strong>[تنبيه — محرك احتياطي]:</strong> كانت خدمة الذكاء الاصطناعي الرئيسية غير متوفرة، لذلك تم توليد هذا القسم بواسطة المحرك الاحتياطي. العناوين والتسميات باللغة العربية، لكن النصوص الحرة المأخوذة مباشرة من استمارة القرار (المعدات، إدارة النفايات، تدابير السلامة...) تبقى بلغتها الأصلية. أعد المحاولة بعد عودة خدمة الذكاء الاصطناعي للحصول على نسخة كاملة بالعربية.</p>",
            },
        }
        FB = _FB_I18N.get(language, _FB_I18N["fr"])

        # Internal citation snippet
        internal_cite = ""
        if dce_chunks:
            c = dce_chunks[0]
            internal_cite = f"<p><em>{FB['source_page'](c.get('section_title', 'CCTP'), c.get('page_number', 1))}</em></p>"
        if FB["fallback_notice"]:
            internal_cite += FB["fallback_notice"]

        # Web citation snippet
        web_cites_html = ""
        if web_sources:
            web_cites_html = f"<h3>{FB['external_sources_h3']}</h3><ul>" + "".join([
                f"<li><strong>{FB['web_source_prefix']}</strong> {w.get('title', FB['web_source_fallback_title'])} — <a href='{w.get('url', '#')}'>{w.get('url', '')}</a></li>"
                for w in web_sources
            ]) + "</ul>"

        # Client reference sites citation snippet (03/09) : sites explicitement ajoutes
        # par le tenant (ex. site de l'acheteur public vise), prioritaires pour la conformite.
        client_sites_html = ""
        if client_sites:
            client_sites_html = f"<h3>{FB['client_sites_h3']}</h3><ul>" + "".join([
                f"<li><strong>{FB['client_site_prefix']}</strong> {c.get('title', FB['web_source_fallback_title'])} — <a href='{c.get('url', '#')}'>{c.get('url', '')}</a></li>"
                for c in client_sites
            ]) + "</ul>"

        # Tenant continuous learnings snippet
        learnings_html = ""
        if learnings_list:
            learnings_html = f"<h3>{FB['learnings_h3']}</h3><ul>" + "".join([
                f"<li><strong>{FB['learning_prefix'](l.get('category', FB['learning_fallback_cat']))}</strong> {l.get('directive', l.get('insight', ''))}</li>"
                for l in learnings_list
            ]) + "</ul>"

        # Missing data / Anti-hallucination check
        missing_data_alert = ""
        if (custom_instructions and "introuvable" in custom_instructions.lower()) or (not dce_chunks and not web_sources and not rag_company_assets and not client_sites):
            missing_data_alert = f"<p style='color: #b91c1c; background: #fef2f2; padding: 8px; border-left: 4px solid #ef4444;'>{FB['missing_data']}</p>"

        if section_key == "moyens_humains":
            cadres_html = "".join([
                f"<li><strong>{c.get('nom', 'Cadre')} ({c.get('role', 'Conducteur')}) :</strong> {c.get('experience_ans', 10)} ans d'expérience - Qualification : {c.get('qualif', 'Ingénieur BTP')}. Présence effective sur site : <strong>{c.get('presence_hebdo_pct', 100)}%</strong>.</li>"
                for c in cadres
            ])
            html = f"""
            <h2>1. Organisation Humaine & Encadrement du Chantier</h2>
            <p>Pour assurer la conduite exemplaire du projet <strong>{project_title}</strong> et garantir le respect du délai contractuel de <strong>{delai} mois</strong>, notre entreprise déploie une équipe d'encadrement dédiée :</p>
            <ul>{cadres_html or "<li>Conducteur de travaux principal diplômé ESTP 15 ans d'expérience [Source : Entreprise - Savoir-Faire].</li>"}</ul>
            {internal_cite}
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            {client_sites_html}
            """
            score = 98.5
            notes = "Encadrement expérimenté avec ratios de présence validés."

        elif section_key == "moyens_materiels":
            html = f"""
            <h2>2. Moyens Matériels et Plan d'Installation de Chantier (PIC)</h2>
            <p>La logistique du chantier repose sur des équipements modernes :</p>
            <p><strong>Parc matériel principal mobilisé :</strong> {materiel}. [Source : Entreprise - Parc Matériel]</p>
            {internal_cite}
            <h3>2.1 Dimensionnement de la Grue à Tour et Levage</h3>
            <p>Implantation optimisée garantissant le survol sécurisé de l'emprise du projet sans zone d'interférence.</p>
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            {client_sites_html}
            """
            score = 96.0
            notes = "Fiches techniques matériels intégrées avec citations."

        elif section_key == "methodologie_phasage" or section_key == "planning_phasage":
            phases_html = "".join([
                f"<li><strong>{p.get('phase', p.get('nom', 'Phase'))} ({p.get('duree_semaines', delai * 4)} semaines) :</strong> Jalon : <em>{p.get('jalon', p.get('description', 'Travaux'))}</em>.</li>"
                for p in phases
            ])
            html = f"""
            <h2>3. Méthodologie d'Exécution et Phasage des Travaux</h2>
            <p>La méthodologie constructive garantit la livraison dans le délai global de <strong>{delai} mois</strong>.</p>
            {internal_cite}
            <h3>3.1 Découpage en phases chronologiques</h3>
            <ol>{phases_html or "<li>Installation de chantier et terrassements (4 semaines).</li><li>Gros oeuvre infrastructure et superstructure (16 semaines).</li>"}</ol>
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            {client_sites_html}
            """
            score = 97.0
            notes = "Chemin critique validé avec citations techniques."

        elif section_key in ("qse_environnement", "rse_environnement"):
            html = f"""
            <h2>{section_title}</h2>
            <p>Notre démarche s'inscrit dans les plus hauts standards de la construction durable :</p>
            <p><strong>Engagements environnementaux :</strong> {rse}. [Source : Entreprise - Charte RSE]</p>
            {internal_cite}
            <p><strong>Plan de gestion et valorisation des déchets :</strong> {dechets}.</p>
            <h3>Traçabilité des déchets et filières agréées</h3>
            <p>Chaque rotation de benne fait l'objet d'un suivi strict sous le régime : <strong>{reg_value(reg, 'waste_tracking_regime', 'bordereau de suivi des déchets applicable')}</strong>.</p>
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            {client_sites_html}
            """
            score = 99.0
            notes = "Taux de valorisation 88%, béton bas carbone et sources web intégrées."

        elif section_key == "securite_ppsps":
            html = f"""
            <h2>{section_title}</h2>
            <p>La politique Zéro Accident constitue l'engagement fondamental de notre encadrement sous le régime : <strong>{reg_value(reg, 'safety_plan_regime', 'plan de sécurité chantier applicable')}</strong>.</p>
            <p><strong>Mesures de sécurité opérationnelles :</strong> {securite}.</p>
            {internal_cite}
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            {client_sites_html}
            """

            score = 98.0
            notes = "Procédure de sécurité complète avec PAQ et causeries hebdomadaires."

        else:
            # Gabarit générique mais honnête pour toute clé sans template dédié
            # (presentation_entreprise, references_similaires, qualite_controle,
            # sous_traitance, ou toute clé future). N'invente JAMAIS un contenu hors-sujet :
            # utilise le vrai section_title au lieu d'un intitulé codé en dur. Ce chemin ne
            # s'exécute que si l'appel LLM réel (Claude/Mistral/OpenAI) a échoué au-dessus.
            html = f"""
            <h2>{section_title}</h2>
            <p>Cette section est rédigée pour le projet <strong>{project_title}</strong>, conformément au cadre réglementaire applicable ({reg_value(reg, 'technical_standards_reference', 'normes en vigueur')}).</p>
            {internal_cite}
            {missing_data_alert or (
                "<p style='color: #b91c1c; background: #fef2f2; padding: 8px; border-left: 4px solid #ef4444;'>"
                "<strong>[Échec de génération IA — cause réelle :</strong> "
                f"{debug_error or 'inconnue (aucune clé/modèle tenté)'}"
                " — relancer la génération peut réussir si la cause est transitoire.]</p>"
            )}
            {learnings_html}
            {web_cites_html}
            {client_sites_html}
            """
            score = 75.0
            notes = "Contenu généré par le moteur de secours générique — relecture et complément manuel recommandés."

        return {
            "title": section_title,
            "content_html": html.strip(),
            "compliance_score": score,
            "compliance_notes": notes,
            "visual_placeholders": ["gantt_chart", "organigramme_chantier"],
            "web_sources_used": [{"title": w.get("title", ""), "url": w.get("url", "")} for w in web_sources],
            "client_sources_used": [{"title": c.get("title", ""), "url": c.get("url", "")} for c in client_sites],
        }


llm_generator_service = LLMGeneratorService()
