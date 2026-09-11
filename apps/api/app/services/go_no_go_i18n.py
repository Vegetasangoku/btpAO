"""
Affichage du Go/No-Go dans la langue de l'interface (11/09).

Le moteur (go_no_go_service) ne produisait que du francais, et une conclusion
« suspendue » ne disait ni pourquoi, ni quoi faire. Ici, a partir des codes
stockes sur chaque facteur, on rend :
  - le titre, le constat et le conseil de chaque facteur (FR / EN / AR) ;
  - la conclusion (etat : go / no_go / suspendue / reserves) et son resume ;
  - les RAISONS de cette conclusion ;
  - les ACTIONS a mener, chacune avec le lien de la page ou la mener.
"""
from typing import Any, Dict, List, Optional

COUVERTURE_MINIMALE_POUR_UN_GO = 75.0

TITRES = {
    "mandatory_criteria": {"fr": "Critères de l'acheteur (RC)", "en": "Buyer's criteria (RC)", "ar": "معايير المشتري (نظام المناقصة)"},
    "qualifications": {"fr": "Qualifications & assurances", "en": "Qualifications & insurance", "ar": "المؤهلات والتأمينات"},
    "deadline_workload": {"fr": "Délai de réponse & charge", "en": "Response time & workload", "ar": "مهلة الرد وعبء العمل"},
    "historical_win_rate": {"fr": "Historique de réussite", "en": "Past success rate", "ar": "سجل النجاح السابق"},
}

# code -> langue -> (constat, conseil, libelle de l'action)
F = {
    "crit_absents": {
        "fr": ("Aucun critère de notation de l'acheteur : le règlement de consultation (RC) n'est pas déposé ou n'a pas été lu.",
               "Sans le RC, impossible de savoir sur quoi l'offre sera notée ni s'il y a une exigence éliminatoire.",
               "Déposer le règlement de consultation"),
        "en": ("No buyer scoring criteria: the tender regulations (RC) are not uploaded or could not be read.",
               "Without the RC, there is no way to know how the bid will be scored or whether a requirement is eliminatory.",
               "Upload the tender regulations"),
        "ar": ("لا توجد معايير تقييم من المشتري: نظام المناقصة (RC) غير مرفوع أو تعذرت قراءته.",
               "بدون نظام المناقصة يستحيل معرفة أسس تقييم العرض أو وجود شرط إقصائي.",
               "رفع نظام المناقصة")},
    "crit_ok": {
        "fr": ("{n} critère(s) lus dans le RC, dont {m} obligatoire(s).", "Répondre à chacun, en priorité aux obligatoires.", None),
        "en": ("{n} criterion/criteria read from the RC, {m} of them mandatory.", "Address each one, mandatory ones first.", None),
        "ar": ("{n} معيار مقروء من نظام المناقصة، منها {m} إلزامي.", "أجب عن كل معيار، والإلزامية أولًا.", None)},
    "qualif_absentes": {
        "fr": ("Aucune qualification ni assurance enregistrée dans « Mon entreprise » ({quals}, décennale…).",
               "L'acheteur les demande presque toujours : sans elles, la candidature peut être écartée.",
               "Ajouter vos attestations"),
        "en": ("No qualification or insurance saved in “My company” ({quals}, ten-year liability…).",
               "Buyers almost always require them: without them the bid may be rejected.",
               "Add your certificates"),
        "ar": ("لا توجد مؤهلات أو تأمينات مسجلة في «ملف الشركة» ({quals}، التأمين العشري…).",
               "يطلبها المشتري دائمًا تقريبًا: بدونها قد يُستبعد العرض.",
               "إضافة الشهادات")},
    "qualif_expirees": {
        "fr": ("Attestation(s) expirée(s) : {liste}.", "Une attestation périmée rend l'offre irrecevable.", "Mettre à jour les attestations"),
        "en": ("Expired certificate(s): {liste}.", "An expired certificate makes the bid inadmissible.", "Update the certificates"),
        "ar": ("شهادات منتهية الصلاحية: {liste}.", "الشهادة المنتهية تجعل العرض غير مقبول.", "تحديث الشهادات")},
    "qualif_manquantes": {
        "fr": ("Le RC exige des qualifications absentes de votre dossier : {liste}.",
               "Répondre en groupement avec une entreprise qualifiée, ou sous-traiter le lot concerné.", "Compléter vos qualifications"),
        "en": ("The RC requires qualifications missing from your file: {liste}.",
               "Bid jointly with a qualified company, or subcontract the relevant lot.", "Complete your qualifications"),
        "ar": ("يشترط نظام المناقصة مؤهلات غير موجودة في ملفك: {liste}.",
               "تقدّم ضمن تجمع مع شركة مؤهلة أو تعاقد من الباطن على الحصة المعنية.", "استكمال المؤهلات")},
    "qualif_ok": {
        "fr": ("{n} qualification(s), assurance(s) et référence(s) valides enregistrées.", None, None),
        "en": ("{n} valid qualification(s), insurance(s) and reference(s) saved.", None, None),
        "ar": ("{n} مؤهل وتأمين ومرجع صالح مسجل.", None, None)},
    "delai_absent": {
        "fr": ("La date limite de remise n'est pas renseignée ({charge} dossier(s) en cours).",
               "Sans date limite, impossible de dire si le délai est tenable.", "Saisir la date limite"),
        "en": ("The submission deadline is not filled in ({charge} bid(s) in progress).",
               "Without a deadline, there is no way to tell whether the timeline is feasible.", "Enter the deadline"),
        "ar": ("لم يُحدَّد الموعد النهائي للتقديم ({charge} ملف جارٍ).",
               "بدون موعد نهائي يستحيل الحكم على إمكانية الالتزام بالمهلة.", "إدخال الموعد النهائي")},
    "delai_intenable": {
        "fr": ("Plus que {j} jour(s) avant la remise, avec {charge} dossier(s) en parallèle.",
               "Risque élevé de rendre une offre incomplète.", None),
        "en": ("Only {j} day(s) left before submission, with {charge} bid(s) in parallel.",
               "High risk of submitting an incomplete bid.", None),
        "ar": ("لم يتبقَّ سوى {j} يوم قبل التقديم، مع {charge} ملف بالتوازي.",
               "خطر كبير لتقديم عرض غير مكتمل.", None)},
    "delai_tendu": {
        "fr": ("Délai tendu : {j} jour(s) restants, {charge} dossier(s) en cours.", "Lancer la rédaction dès maintenant.", None),
        "en": ("Tight deadline: {j} day(s) left, {charge} bid(s) in progress.", "Start writing now.", None),
        "ar": ("مهلة ضيقة: {j} يوم متبقٍ، {charge} ملف جارٍ.", "ابدأ التحرير فورًا.", None)},
    "delai_ok": {
        "fr": ("Délai confortable : {j} jour(s) restants pour {charge} dossier(s) actif(s).", None, None),
        "en": ("Comfortable deadline: {j} day(s) left for {charge} active bid(s).", None, None),
        "ar": ("مهلة مريحة: {j} يوم متبقٍ لـ{charge} ملف نشط.", None, None)},
    "histo_absent": {
        "fr": ("Pas assez d'appels d'offres passés dont l'issue est connue ({n} gagné(s) ou perdu(s) enregistré(s), il en faut 2).",
               "Indiquez « gagné » ou « perdu » sur vos anciens dossiers : l'application saura si ce type de marché vous réussit.",
               "Indiquer l'issue de vos anciens dossiers"),
        "en": ("Not enough past tenders with a known outcome ({n} won or lost recorded, 2 needed).",
               "Mark your past bids as “won” or “lost”: the app will learn whether this kind of tender suits you.",
               "Record the outcome of past bids"),
        "ar": ("لا توجد مناقصات سابقة كافية معروفة النتيجة ({n} مسجلة بين رابحة وخاسرة، والمطلوب 2).",
               "حدّد «ربح» أو «خسارة» على ملفاتك السابقة ليعرف التطبيق مدى نجاحك في هذا النوع من المناقصات.",
               "تسجيل نتيجة الملفات السابقة")},
    "histo_ok": {
        "fr": ("{taux} % de réussite sur {n} marché(s) passés ({g} gagné(s)).", None, None),
        "en": ("{taux}% success rate over {n} past tender(s) ({g} won).", None, None),
        "ar": ("نسبة نجاح {taux}% في {n} مناقصة سابقة ({g} رابحة).", None, None)},
    "histo_faible": {
        "fr": ("Taux de réussite modéré : {taux} % sur {n} marché(s).", "Soigner particulièrement la méthodologie pour se démarquer.", None),
        "en": ("Moderate success rate: {taux}% over {n} tender(s).", "Put extra care into the methodology to stand out.", None),
        "ar": ("نسبة نجاح متوسطة: {taux}% في {n} مناقصة.", "اعتنِ بالمنهجية بشكل خاص للتميز.", None)},
}

TEXTES = {
    "fr": {
        "go": "GO : {verifies}.",
        "go_vide": "GO : aucun point bloquant.",
        "no_go": "NO-GO : {n} point(s) bloquant(s).",
        "suspendue": "Conclusion suspendue : le score ({score}/100) ne repose que sur {k} facteur(s) sur {total}. Il en faut au moins {min} pour conclure.",
        "reserves": "Candidature possible, sous réserve des points signalés ci-dessous.",
        "raison_manque": "{titre} — {constat}",
        "raison_bloquant": "Point bloquant — {titre} : {constat}",
        "raison_faible": "{titre} : {constat}",
    },
    "en": {
        "go": "GO: {verifies}.",
        "go_vide": "GO: no blocking issue.",
        "no_go": "NO-GO: {n} blocking issue(s).",
        "suspendue": "Conclusion on hold: the score ({score}/100) rests on only {k} factor(s) out of {total}. At least {min} are needed to conclude.",
        "reserves": "Bidding is possible, subject to the points below.",
        "raison_manque": "{titre} — {constat}",
        "raison_bloquant": "Blocking — {titre}: {constat}",
        "raison_faible": "{titre}: {constat}",
    },
    "ar": {
        "go": "موافقة: {verifies}.",
        "go_vide": "موافقة: لا توجد نقطة مانعة.",
        "no_go": "رفض: {n} نقطة مانعة.",
        "suspendue": "الاستنتاج معلّق: النتيجة ({score}/100) تستند إلى {k} عامل فقط من {total}. يلزم {min} على الأقل للاستنتاج.",
        "reserves": "التقدم ممكن مع مراعاة النقاط أدناه.",
        "raison_manque": "{titre} — {constat}",
        "raison_bloquant": "نقطة مانعة — {titre}: {constat}",
        "raison_faible": "{titre}: {constat}",
    },
}


def _lang(l: Optional[str]) -> str:
    l = (l or "fr").lower()[:2]
    return l if l in ("fr", "en", "ar") else "fr"


def _lien(code: str, category: str, pid: str) -> Optional[str]:
    base = f"/projects/{pid}"
    if code == "crit_absents":
        return f"{base}/dce"
    if code in ("qualif_absentes", "qualif_expirees", "qualif_manquantes"):
        return "/dashboard/company"
    if code == "delai_absent":
        return f"{base}#infos"
    if code == "histo_absent":
        return "/dashboard/projects"
    return None


def localiser_facteur(f: Dict[str, Any], L: str, pid: str) -> Dict[str, Any]:
    f = dict(f)
    cat = f.get("category") or ""
    if cat in TITRES:
        f["title"] = TITRES[cat][L]
    code = f.get("code")
    if code in F:
        constat, conseil, action = F[code][L]
        params = f.get("params") or {}
        try:
            f["detail"] = constat.format(**params)
            f["recommendation"] = conseil.format(**params) if conseil else None
        except (KeyError, IndexError, ValueError):
            pass
        f["action"] = action
        f["lien"] = _lien(code, cat, pid) if action else None
    return f


def localiser_analyse(analysis: Any, langue: Optional[str]) -> Dict[str, Any]:
    """Construit le dictionnaire GoNoGoAnalysisOut dans la langue demandee."""
    L = _lang(langue)
    T = TEXTES[L]
    pid = str(analysis.project_id)
    facteurs = [localiser_facteur(f, L, pid) for f in (analysis.factors or [])]
    total = len(facteurs) or 1
    manquants = [f for f in facteurs if f.get("status") == "missing_data"]
    bloquants = [f for f in facteurs if f.get("status") == "blocking"]
    faibles = [f for f in facteurs if f.get("status") == "warning"]
    k = total - len(manquants)
    couverture = 100.0 * k / total
    score = float(analysis.score)
    rec = (analysis.recommendation or "").upper().replace("-", "_")
    minimum = int(-(-COUVERTURE_MINIMALE_POUR_UN_GO * total // 100))

    if bloquants or rec == "NO_GO":
        etat = "no_go"
        resume = T["no_go"].format(n=len(bloquants) or len(analysis.blocking_issues or []))
    elif rec == "GO":
        etat = "go"
        verifies = [f["title"] for f in facteurs if f.get("status") == "ok"]
        resume = T["go"].format(verifies=" ; ".join(verifies)) if verifies else T["go_vide"]
    elif score >= 70 and couverture < COUVERTURE_MINIMALE_POUR_UN_GO:
        etat = "suspendue"
        resume = T["suspendue"].format(score=f"{score:g}", k=k, total=total, min=minimum)
    else:
        etat = "reserves"
        resume = T["reserves"]

    raisons: List[str] = []
    for f in bloquants:
        raisons.append(T["raison_bloquant"].format(titre=f["title"], constat=f["detail"]))
    for f in manquants:
        raisons.append(T["raison_manque"].format(titre=f["title"], constat=f["detail"]))
    for f in faibles:
        raisons.append(T["raison_faible"].format(titre=f["title"], constat=f["detail"]))

    actions = []
    for f in bloquants + manquants + faibles:
        if f.get("action"):
            actions.append({"texte": f["action"], "detail": f.get("recommendation"), "lien": f.get("lien")})

    return {
        "id": str(analysis.id),
        "tenant_id": str(analysis.tenant_id),
        "project_id": pid,
        "recommendation": analysis.recommendation,
        "score": score,
        "summary": resume,
        "factors": facteurs,
        "mandatory_criteria_met": bool(analysis.mandatory_criteria_met),
        "blocking_issues": [f["detail"] for f in bloquants] or (analysis.blocking_issues or []),
        "completion_rate": float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        "has_sufficient_data": bool(analysis.has_sufficient_data),
        "evaluated_by": str(analysis.evaluated_by) if analysis.evaluated_by else None,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
        "etat": etat,
        "raisons": raisons,
        "actions": actions,
        "langue": L,
    }
