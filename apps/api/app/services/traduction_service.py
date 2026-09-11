"""
Traduction des sections deja redigees (11/09).

Changer la langue du mémoire ne traduisait que la mise en page (titres, page de
garde) : le texte restait dans la langue où il avait été écrit. On traduit ici
section par section, en conservant le HTML et la version d'origine.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

NOMS = {"fr": "français", "en": "anglais", "ar": "arabe"}
_MOTS_FR = (" les ", " des ", " pour ", " est ", " une ", " dans ", " sur ", " avec ", " du ")
_MOTS_EN = (" the ", " and ", " for ", " with ", " is ", " of ", " on ", " our ", " to ")


def langue_du_texte(html: str) -> Optional[str]:
    """Langue dominante d'un texte rédigé (fr / en / ar), None si trop court."""
    t = " " + re.sub(r"<[^>]+>", " ", html or "").lower() + " "
    t = f" {' '.join(t.split())} "
    if len(t) < 200:
        return None
    arabes = sum(1 for c in t if "؀" <= c <= "ۿ")
    lettres = sum(1 for c in t if c.isalpha()) or 1
    if arabes / lettres > 0.3:
        return "ar"
    fr = sum(t.count(m) for m in _MOTS_FR)
    en = sum(t.count(m) for m in _MOTS_EN)
    return "fr" if fr >= en else "en"


async def traduire_html(db: AsyncSession, tenant_uuid, html: str, cible: str,
                        titre: str = "") -> Dict[str, Any]:
    """Traduit un contenu HTML. Renvoie {ok, html, titre, motif}."""
    cible = (cible or "fr").lower()[:2]
    if cible not in NOMS:
        return {"ok": False, "motif": f"langue inconnue : {cible}"}
    if not (html or "").strip():
        return {"ok": False, "motif": "section vide"}

    import litellm
    from app.services.model_routing_service import model_routing_service

    try:
        res = await model_routing_service.resolve_model_for_tenant(
            db=db, tenant_id=tenant_uuid, task_type="redaction_memoire")
        cred = await model_routing_service.get_credentials_for_model(db=db, model_string=res["model_string"])
        if not cred.get("api_key"):
            return {"ok": False, "motif": "aucune clé de modèle configurée"}
        consigne = (
            f"Traduis en {NOMS[cible]} le mémoire technique BTP ci-dessous.\n"
            "Règles strictes : garde EXACTEMENT les mêmes balises HTML et le même ordre ; "
            "ne résume pas, ne rajoute rien, n'enlève rien ; garde les chiffres, unités, "
            "dates, noms propres, références de normes et de documents tels quels ; "
            "traduis aussi le titre.\n"
            'Réponds en JSON strict : {"titre": "...", "html": "..."}\n\n'
            f"TITRE : {titre}\n\nHTML :\n{html}"
        )
        kw = {
            "model": res["model_string"],
            "api_key": cred["api_key"],
            "max_tokens": 8000,
            "temperature": 0.1,
            "timeout": 180,
            "messages": [{"role": "user", "content": consigne}],
        }
        if cred.get("api_base"):
            kw["api_base"] = cred["api_base"]
        r = await litellm.acompletion(**kw)
        brut = (r.choices[0].message.content or "").strip()
        brut = re.sub(r"^```(?:json)?\s*|\s*```$", "", brut)
        m = re.search(r"\{.*\}", brut, re.S)
        data = json.loads(m.group(0) if m else brut)
        traduit = (data.get("html") or "").strip()
        if not traduit:
            return {"ok": False, "motif": "réponse du modèle sans contenu"}
        return {"ok": True, "html": traduit, "titre": (data.get("titre") or titre or "").strip() or titre}
    except Exception as exc:
        logger.warning("[Traduction] échec : %s", exc)
        return {"ok": False, "motif": str(exc)[:300]}
