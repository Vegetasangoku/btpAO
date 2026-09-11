"""
Lecture du CONTENU des pages officielles trouvees par la recherche web (11/09).

Constat : l'assistant et la redaction ne recevaient que l'extrait de 2-3 lignes
renvoye par le moteur de recherche. Sur le Qatar, les bonnes pages Ashghal
(préqualification, dossiers d'appel d'offres) etaient trouvees, mais la reponse
restait « aucune information » faute de contenu. On lit donc la page elle-meme --
HTML, PDF ou Word, les formulaires officiels etant presque toujours des PDF -- et
on n'en garde que les passages qui parlent de la question.

Garde-fous :
  - lecture en parallele, 12 s maximum par page, 3 Mo maximum ;
  - le domaine est verifie par l'appelant (liste blanche des sources officielles) ;
  - un echec de lecture n'empeche jamais la reponse : on retombe sur l'extrait.
"""
import asyncio
import io
import logging
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

import httpx

logger = logging.getLogger(__name__)

MAX_OCTETS = 3_000_000
_ENTETES = {
    "User-Agent": "Mozilla/5.0 (compatible; btpAO-SourcesOfficielles/1.0)",
    "Accept": "text/html,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8,ar;q=0.6",
}
_VIDES = {"les", "des", "une", "pour", "sur", "avec", "dans", "que", "qui", "est", "sont", "the", "and", "for",
          "with", "what", "which", "are", "quels", "quelles", "quel", "quelle", "faut", "doit", "aux", "par"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _texte_html(html: str) -> tuple[str, str]:
    from app.services.company_bootstrap_service import HTMLTextCleaner
    p = HTMLTextCleaner()
    p.feed(html)
    return p.get_title(), p.get_text()


def _texte_pdf(data: bytes) -> str:
    try:
        import pdfplumber
        morceaux = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:25]:
                morceaux.append(page.extract_text() or "")
        return "\n".join(morceaux)
    except Exception:
        try:
            from pypdf import PdfReader
            r = PdfReader(io.BytesIO(data))
            return "\n".join((pg.extract_text() or "") for pg in r.pages[:25])
        except Exception as exc:
            logger.info("[PageReader] PDF illisible : %s", exc)
            return ""


def _texte_docx(data: bytes) -> str:
    try:
        import docx
        d = docx.Document(io.BytesIO(data))
        lignes = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                lignes.append(" | ".join(c.text for c in row.cells))
        return "\n".join(lignes)
    except Exception:
        return ""


def passages_pertinents(texte: str, question: str, budget: int = 2500) -> str:
    """Garde les phrases qui contiennent les mots de la question (et leur voisinage),
    dans l'ordre du document. Sans correspondance : le debut de la page."""
    texte = re.sub(r"[ \t]+", " ", texte or "").strip()
    if len(texte) <= budget:
        return texte
    mots = {m for m in re.findall(r"[a-z0-9]{4,}", _norm(question)) if m not in _VIDES}
    phrases = re.split(r"(?<=[\.\!\?;:])\s+|\n+", texte)
    scores = []
    for i, ph in enumerate(phrases):
        n = _norm(ph)
        s = sum(1 for m in mots if m in n)
        if s:
            scores.append((s, i))
    if not scores:
        return texte[:budget]
    retenues = set()
    for _, i in sorted(scores, reverse=True):
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(phrases):
                retenues.add(j)
        if sum(len(phrases[k]) for k in retenues) > budget:
            break
    extrait = " … ".join(phrases[k].strip() for k in sorted(retenues) if phrases[k].strip())
    return extrait[:budget]


async def lire_page(url: str, question: str = "", budget: int = 2500) -> Dict[str, Any]:
    """Renvoie {url, titre, type, texte, erreur}. Ne leve jamais."""
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, verify=False, headers=_ENTETES) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return {"url": url, "erreur": f"code {resp.status_code}"}
        data = resp.content[:MAX_OCTETS]
        ctype = (resp.headers.get("content-type") or "").lower()
        chemin = url.lower().split("?")[0]
        titre = ""
        if "pdf" in ctype or chemin.endswith(".pdf"):
            genre, texte = "pdf", _texte_pdf(data)
        elif "wordprocessingml" in ctype or chemin.endswith(".docx"):
            genre, texte = "docx", _texte_docx(data)
        else:
            genre = "html"
            titre, texte = _texte_html(resp.text)
        if len(texte.strip()) < 60:
            return {"url": url, "type": genre, "erreur": "contenu vide ou non lisible (page dynamique ou document scanné)"}
        return {"url": url, "titre": titre, "type": genre, "texte": passages_pertinents(texte, question, budget)}
    except httpx.TimeoutException:
        return {"url": url, "erreur": "délai dépassé"}
    except Exception as exc:
        return {"url": url, "erreur": type(exc).__name__}


async def lire_pages(urls: Iterable[str], question: str = "", budget_par_page: int = 2500, maximum: int = 4) -> List[Dict[str, Any]]:
    uniques: List[str] = []
    for u in urls:
        if u and u not in uniques:
            uniques.append(u)
    uniques = uniques[:maximum]
    if not uniques:
        return []
    return list(await asyncio.gather(*(lire_page(u, question, budget_par_page) for u in uniques)))
