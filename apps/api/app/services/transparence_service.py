"""
« Ce que l'application a fait à votre place » (11/09).

Demande Charbel : « tu dois dire dans l'application clairement ce que tu as fait
automatiquement car il n'y avait pas telle ou telle donnée ». Chaque fois qu'une
donnée manque, l'application prend une decision (valeur laissee a completer,
pieces standard du pays, planning detaille par l'IA, modele Word choisi...). Ce
service les rassemble pour un projet, en langage clair et dans la langue de
l'interface (FR / EN / AR, en-tete X-UI-Language), avec pour chacune : ce qui a
ete fait, pourquoi, et ou corriger.

Gravites : a_completer (une valeur figure « [à compléter] » dans un document
remis), a_verifier (production automatique a relire), info (choix sans risque).
"""
import uuid
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    CompanyAsset, DCECriterionEntity, DCEDocument, GeneratedSection, Project, ProjectDecision,
    ProjectOrganigrammeNode, Tenant, TenantReferenceUrl,
)

DEFAUT_ACHETEUR = {"acheteur public détecté", "acheteur public detecte"}
DEFAUT_LOT = {"lot 01 - gros œuvre", "lot 01 - gros oeuvre"}
DEFAUT_BUDGET = 3_500_000.0
NOMS_LANGUES = {
    "fr": {"fr": "français", "en": "French", "ar": "الفرنسية"},
    "en": {"fr": "anglais", "en": "English", "ar": "الإنجليزية"},
    "ar": {"fr": "arabe", "en": "Arabic", "ar": "العربية"},
}
_MOTS_FR = (" les ", " des ", " pour ", " est ", " une ", " dans ", " sur ", " avec ", " du ")
_MOTS_EN = (" the ", " and ", " for ", " with ", " is ", " of ", " on ", " our ", " to ")


def _langue_texte(html: str) -> str:
    """Langue dominante d'un texte redige (fr / en / ar), None si trop court."""
    import re as _re
    t = " " + _re.sub(r"<[^>]+>", " ", html or "").lower() + " "
    t = " ".join(t.split())
    t = f" {t} "
    if len(t) < 200:
        return None
    arabes = sum(1 for c in t if "\u0600" <= c <= "\u06ff")
    lettres = sum(1 for c in t if c.isalpha()) or 1
    if arabes / lettres > 0.3:
        return "ar"
    fr = sum(t.count(m) for m in _MOTS_FR)
    en = sum(t.count(m) for m in _MOTS_EN)
    return "fr" if fr >= en else "en"


# Valeurs d'exemple de l'ancien formulaire « Données chantier » (voir decision-form.tsx).
SIGNATURES_EXEMPLE = {
    "equipe": ("Jean-Marc Alibert", "Sébastien Vasseur", "Chloé Fontaine", "Tarek Benali"),
    "materiel": ("Potain MDT 219", "Grue à tour Potain 50m, 2 pelles Liebherr 22t"),
    "dechets": ("Paprec / Veolia à 12 km", "Paprec/Veolia à 12 km"),
}

DOMAINES = {
    "marche": {"fr": "Marché", "en": "Tender", "ar": "المناقصة"},
    "pays": {"fr": "Pays du marché", "en": "Market country", "ar": "بلد السوق"},
    "pieces": {"fr": "Pièces du marché", "en": "Tender documents", "ar": "وثائق المناقصة"},
    "planning": {"fr": "Planning", "en": "Schedule", "ar": "الجدول الزمني"},
    "equipe": {"fr": "Équipe", "en": "Team", "ar": "الفريق"},
    "redaction": {"fr": "Rédaction", "en": "Writing", "ar": "التحرير"},
    "mise_en_page": {"fr": "Mise en page", "en": "Layout", "ar": "التنسيق"},
    "entreprise": {"fr": "Entreprise", "en": "Company", "ar": "الشركة"},
}

# code -> langue -> (ce qui a ete fait, pourquoi, libelle du lien)
MESSAGES: Dict[str, Dict[str, tuple]] = {
    "acheteur": {
        "fr": ("Le nom de l'acheteur est laissé « [à compléter] » sur la page de garde, le DC1, le DC2 et le DUME.",
               "Aucun acheteur n'a été saisi ni trouvé dans les pièces du marché.", "Compléter le projet"),
        "en": ("The buyer's name is left “[à compléter]” (to complete) on the cover page, DC1, DC2 and DUME.",
               "No buyer was entered or found in the tender documents.", "Complete the project"),
        "ar": ("تُرك اسم المشتري «[à compléter]» (للإكمال) في صفحة الغلاف ونماذج DC1 وDC2 وDUME.",
               "لم يُدخل اسم المشتري ولم يُعثر عليه في وثائق المناقصة.", "إكمال المشروع")},
    "lot": {
        "fr": ("Le lot est laissé « [à compléter] » sur la page de garde.",
               "« Lot 01 - Gros Œuvre » est une valeur par défaut, pas une donnée du marché.", "Compléter le projet"),
        "en": ("The lot is left “[à compléter]” (to complete) on the cover page.",
               "“Lot 01 - Gros Œuvre” is a default value, not tender data.", "Complete the project"),
        "ar": ("تُركت الحصة «[à compléter]» في صفحة الغلاف.",
               "«Lot 01 - Gros Œuvre» قيمة افتراضية وليست من بيانات المناقصة.", "إكمال المشروع")},
    "budget_defaut": {
        "fr": ("Le budget affiché (3 500 000 € HT) est la valeur proposée par défaut à la création du projet.",
               "Aucun montant n'a été trouvé dans les pièces du marché.", "Vérifier le budget"),
        "en": ("The displayed budget (€3,500,000 excl. VAT) is the default value proposed when the project was created.",
               "No amount was found in the tender documents.", "Check the budget"),
        "ar": ("الميزانية المعروضة (3,500,000 يورو دون ضريبة) هي القيمة الافتراضية عند إنشاء المشروع.",
               "لم يُعثر على أي مبلغ في وثائق المناقصة.", "التحقق من الميزانية")},
    "budget_absent": {
        "fr": ("Le budget est laissé « [à compléter] ».", "Aucun montant n'a été saisi ni trouvé.", "Compléter le projet"),
        "en": ("The budget is left “[à compléter]” (to complete).", "No amount was entered or found.", "Complete the project"),
        "ar": ("تُركت الميزانية «[à compléter]».", "لم يُدخل أي مبلغ ولم يُعثر عليه.", "إكمال المشروع")},
    "date_limite": {
        "fr": ("Aucune date limite de remise n'est connue.", "Elle n'a été ni saisie ni trouvée dans les pièces.", "Compléter le projet"),
        "en": ("No submission deadline is known.", "It was neither entered nor found in the documents.", "Complete the project"),
        "ar": ("لا يوجد موعد نهائي معروف للتسليم.", "لم يُدخل ولم يُعثر عليه في الوثائق.", "إكمال المشروع")},
    "pays_auto": {
        "fr": ("Pays du marché choisi automatiquement : {pays}.", "{raison}", "Changer le pays"),
        "en": ("Market country chosen automatically: {pays}.", "{raison}", "Change the country"),
        "ar": ("تم اختيار بلد السوق تلقائياً: {pays}.", "{raison}", "تغيير البلد")},
    "aucune_piece": {
        "fr": ("Aucune pièce du marché n'a été déposée.", "La rédaction ne peut alors s'appuyer que sur vos documents d'entreprise.", "Déposer les pièces"),
        "en": ("No tender document has been uploaded.", "Writing can then only rely on your company documents.", "Upload documents"),
        "ar": ("لم تُرفع أي وثيقة من وثائق المناقصة.", "لا يمكن للتحرير حينها الاعتماد إلا على وثائق شركتك.", "رفع الوثائق")},
    "rc_absent": {
        "fr": ("La liste des pièces à fournir a été établie d'après les usages du pays, et la rédaction n'a pas pu viser la grille de notation de l'acheteur.",
               "Le règlement de consultation (RC) — le document de l'acheteur qui liste les pièces demandées et les critères de notation — n'a pas été déposé.", "Ajouter le RC"),
        "en": ("The list of required documents follows the country's usual practice, and the writing could not target the buyer's scoring grid.",
               "The tender regulations (RC) — the buyer's document listing required documents and scoring criteria — were not uploaded.", "Add the RC"),
        "ar": ("أُعدّت قائمة الوثائق المطلوبة وفق الأعراف المعتادة في البلد، ولم يتمكن التحرير من استهداف معايير التقييم لدى المشتري.",
               "لم يُرفع نظام المناقصة (RC) — وثيقة المشتري التي تحدد الوثائق المطلوبة ومعايير التقييم.", "إضافة نظام المناقصة")},
    "criteres_gabarit": {
        "fr": ("Les critères de notation affichés sont un barème générique (25/35/25/15), pas ceux de l'acheteur.",
               "Le règlement de consultation n'a pas pu être lu automatiquement.", "Relancer l'analyse du RC"),
        "en": ("The scoring criteria shown are a generic scale (25/35/25/15), not the buyer's.",
               "The tender regulations (RC) could not be read automatically.", "Rerun the RC analysis"),
        "ar": ("معايير التقييم المعروضة سُلّم عام (25/35/25/15) وليست معايير المشتري.",
               "تعذرت قراءة نظام المناقصة (RC) تلقائيًا.", "إعادة تحليل نظام المناقصة")},
    "rc_sans_criteres": {
        "fr": ("Aucun critère de notation n'a été extrait du RC déposé.", "Le RC est peut-être encore en cours d'analyse, ou scanné sans texte lisible.", "Voir l'analyse"),
        "en": ("No scoring criterion was extracted from the uploaded RC.", "The RC may still be under analysis, or scanned without readable text.", "See the analysis"),
        "ar": ("لم يُستخرج أي معيار تقييم من نظام المناقصة المرفوع.", "ربما لا يزال قيد التحليل، أو ممسوحاً ضوئياً دون نص مقروء.", "عرض التحليل")},
    "donnees_exemple": {
        "fr": ("Les données chantier enregistrées sont les valeurs d'exemple de l'application ({quoi}).",
               "Elles ont été enregistrées sans être modifiées : le mémoire et l'organigramme les présentent comme les vôtres.",
               "Corriger les données chantier"),
        "en": ("The saved site data are the app's sample values ({quoi}).",
               "They were saved unchanged: the bid and the organisation chart present them as yours.",
               "Fix the site data"),
        "ar": ("بيانات الورشة المحفوظة هي القيم النموذجية للتطبيق ({quoi}).",
               "حُفظت دون تعديل: تعرضها المذكرة والهيكل التنظيمي على أنها بياناتك.",
               "تصحيح بيانات الورشة")},
    "langue_contenu": {
        "fr": ("{n} section(s) sont rédigées en {ecrite} alors que le document est demandé en {voulue}.",
               "Elles ont été rédigées avant le changement de langue : titres et page de garde sont traduits, pas le texte.",
               "Traduire les sections"),
        "en": ("{n} section(s) are written in {ecrite} while the document is requested in {voulue}.",
               "They were written before the language was changed: headings and cover page are translated, not the text.",
               "Translate the sections"),
        "ar": ("{n} قسم مكتوب بـ{ecrite} بينما الوثيقة مطلوبة بـ{voulue}.",
               "كُتبت قبل تغيير اللغة: العناوين وصفحة الغلاف مترجمة، أما النص فلا.",
               "ترجمة الأقسام")},
    "phasage_absent": {
        "fr": ("Aucun phasage n'a été saisi : le planning part de phases types.", "Le formulaire « Données chantier » n'a pas été rempli.", "Saisir le phasage"),
        "en": ("No phasing was entered: the schedule starts from standard phases.", "The “Site data” form was not filled in.", "Enter the phasing"),
        "ar": ("لم تُدخل أي مراحل: يبدأ الجدول من مراحل نموذجية.", "لم يُملأ نموذج «بيانات الموقع».", "إدخال المراحل")},
    "gantt_detail": {
        "fr": ("Le détail du planning ({taches} tâches, {sous} sous-tâches) a été proposé automatiquement : {origine}.",
               "Vous avez demandé « Détailler le planning » ; les dates de vos phases n'ont pas été modifiées.", "Relire le planning"),
        "en": ("The schedule detail ({taches} tasks, {sous} sub-tasks) was proposed automatically: {origine}.",
               "You asked to “Detail the schedule”; your phase dates were not changed.", "Review the schedule"),
        "ar": ("تم اقتراح تفاصيل الجدول ({taches} مهمة، {sous} مهمة فرعية) تلقائياً: {origine}.",
               "طلبت «تفصيل الجدول»؛ لم تتغير تواريخ مراحلك.", "مراجعة الجدول")},
    "a_pourvoir": {
        "fr": ("{n} poste(s) de l'organigramme portent la mention « À pourvoir ».", "Aucun nom n'a été déclaré pour ces postes ; l'application n'invente jamais de nom.", "Compléter l'équipe"),
        "en": ("{n} position(s) in the org chart are marked “À pourvoir” (to be filled).", "No name was declared for these positions; the app never invents names.", "Complete the team"),
        "ar": ("{n} منصب في الهيكل التنظيمي مُعلَّم «À pourvoir» (شاغر).", "لم يُعلن أي اسم لهذه المناصب؛ التطبيق لا يخترع الأسماء أبداً.", "إكمال الفريق")},
    "orga_vide": {
        "fr": ("L'organigramme est vide.", "Aucune équipe n'a été déclarée dans « Données chantier ».", "Déclarer l'équipe"),
        "en": ("The org chart is empty.", "No team was declared in “Site data”.", "Declare the team"),
        "ar": ("الهيكل التنظيمي فارغ.", "لم يُعلن أي فريق في «بيانات الموقع».", "إعلان الفريق")},
    "sections_echec": {
        "fr": ("{n} section(s) n'ont pas pu être rédigées et sont exclues du mémoire.", "La génération a échoué : {liste}", "Relancer"),
        "en": ("{n} section(s) could not be written and are excluded from the bid.", "Generation failed: {liste}", "Retry"),
        "ar": ("تعذر تحرير {n} قسم واستُبعدت من المذكرة.", "فشل التوليد: {liste}", "إعادة المحاولة")},
    "manques": {
        "fr": ("Les sections ont été rédigées avec {n} information(s) manquante(s), signalées dans chaque section.",
               "Les pièces et documents fournis ne couvraient pas tout ce que demande un jury.", "Voir les manques"),
        "en": ("Sections were written with {n} missing item(s) of information, flagged in each section.",
               "The documents provided did not cover everything a jury expects.", "See the gaps"),
        "ar": ("حُررت الأقسام مع {n} معلومة ناقصة، مُشار إليها في كل قسم.",
               "لم تغطِّ الوثائق المقدمة كل ما تطلبه لجنة التقييم.", "عرض النواقص")},
    "sans_web": {
        "fr": ("{n} section(s) ont été rédigées sans source officielle en ligne.",
               "Aucune page officielle pertinente n'a été trouvée ou n'a pu être lue au moment de la rédaction.", "Voir les sections"),
        "en": ("{n} section(s) were written without any official online source.",
               "No relevant official page was found or readable at writing time.", "See the sections"),
        "ar": ("حُرر {n} قسم دون أي مصدر رسمي على الإنترنت.",
               "لم يُعثر على صفحة رسمية مناسبة أو تعذرت قراءتها وقت التحرير.", "عرض الأقسام")},
    "modele_memoire": {
        "fr": ("L'en-tête, les styles et les couleurs du Word sont repris de votre mémoire « {titre} ».",
               "Aucun modèle Word n'est enregistré ; c'est votre mémoire de référence le plus complet.", "Choisir un modèle"),
        "en": ("The Word header, styles and colours are taken from your bid “{titre}”.",
               "No Word template is registered; this is your most complete reference bid.", "Choose a template"),
        "ar": ("تم اعتماد ترويسة Word والأنماط والألوان من مذكرتك «{titre}».",
               "لا يوجد قالب Word مسجل؛ هذه أكمل مذكرة مرجعية لديك.", "اختيار قالب")},
    "modele_standard": {
        "fr": ("Le Word utilise la mise en page standard de l'application.",
               "Aucun modèle Word ni mémoire de référence au format Word n'a été déposé.", "Déposer un modèle"),
        "en": ("The Word file uses the app's standard layout.",
               "No Word template or Word reference bid was uploaded.", "Upload a template"),
        "ar": ("يستخدم ملف Word التنسيق القياسي للتطبيق.",
               "لم يُرفع أي قالب Word أو مذكرة مرجعية بصيغة Word.", "رفع قالب")},
    "siret": {
        "fr": ("Le SIRET est laissé « [à compléter] » dans le DC1, le DC2 et le DUME.", "Il n'est pas renseigné dans la fiche entreprise.", "Compléter"),
        "en": ("The SIRET number is left “[à compléter]” in DC1, DC2 and DUME.", "It is missing from the company profile.", "Complete"),
        "ar": ("تُرك رقم SIRET «[à compléter]» في DC1 وDC2 وDUME.", "غير مُدخل في ملف الشركة.", "إكمال")},
    "ville": {
        "fr": ("Le lieu de signature du DC1 est laissé « [à compléter] ».", "La ville de l'entreprise n'est pas renseignée.", "Compléter"),
        "en": ("The DC1 place of signature is left “[à compléter]”.", "The company's city is not filled in.", "Complete"),
        "ar": ("تُرك مكان توقيع DC1 «[à compléter]».", "مدينة الشركة غير مُدخلة.", "إكمال")},
    "sites_muets": {
        "fr": ("{n} site(s) de référence ne sont pas utilisés : {liste}.",
               "La page est inaccessible, ou son contenu est construit par le navigateur (page d'accueil de portail) : indiquez plutôt l'adresse d'une page de contenu, puis relancez la lecture.",
               "Corriger les sites"),
        "en": ("{n} reference site(s) are not used: {liste}.",
               "The page is unreachable, or its content is built by the browser (portal home page): point to a content page instead, then run the read again.",
               "Fix the sites"),
        "ar": ("{n} موقع مرجعي غير مستخدم: {liste}.",
               "الصفحة غير متاحة أو يبنيها المتصفح (صفحة رئيسية لبوابة): أدخل عنوان صفحة محتوى ثم أعد القراءة.",
               "تصحيح المواقع")},
    "sans_memoires": {
        "fr": ("Le style de rédaction est générique.", "Aucun ancien mémoire n'a été déposé dans la base de connaissances.", "Déposer des mémoires"),
        "en": ("The writing style is generic.", "No past bid was uploaded to the knowledge base.", "Upload past bids"),
        "ar": ("أسلوب التحرير عام.", "لم تُرفع أي مذكرة سابقة إلى قاعدة المعرفة.", "رفع مذكرات سابقة")},
}


def _lang(l: str) -> str:
    l = (l or "fr").lower()[:2]
    return l if l in ("fr", "en", "ar") else "fr"


async def rapport_transparence(db: AsyncSession, tenant_uuid: uuid.UUID, project: Project, langue: str = "fr") -> Dict[str, Any]:
    L = _lang(langue)
    pid = project.id
    base = f"/projects/{pid}"
    items: List[Dict[str, Any]] = []

    def add(domaine: str, gravite: str, code: str, lien: str = None, **params):
        fait, pourquoi, libelle = MESSAGES[code][L]
        items.append({"code": code, "domaine": DOMAINES[domaine][L], "gravite": gravite,
                      "fait": fait.format(**params), "parce_que": pourquoi.format(**params),
                      "lien": lien, "lien_libelle": libelle})

    tenant = await db.get(Tenant, tenant_uuid)

    if not project.client_name or project.client_name.strip().lower() in DEFAUT_ACHETEUR:
        add("marche", "a_completer", "acheteur", f"{base}#infos")
    if not project.lot_number or project.lot_number.strip().lower() in DEFAUT_LOT:
        add("marche", "a_completer", "lot", f"{base}#infos")
    if project.budget_estimate is None:
        add("marche", "a_completer", "budget_absent", f"{base}#infos")
    elif float(project.budget_estimate) == DEFAUT_BUDGET:
        add("marche", "a_verifier", "budget_defaut", f"{base}#infos")
    if not project.submission_deadline:
        add("marche", "a_completer", "date_limite", f"{base}#infos")
    det = project.country_detection or {}
    if det.get("auto_applied") and not det.get("overridden_by_user"):
        from app.services.pieces_service import nom_pays
        _cc = project.country_code or det.get("detected_code") or "?"
        add("pays", "info", "pays_auto", base, pays=nom_pays(_cc, L, _cc),
            raison=det.get("reason") or "")

    docs = (await db.execute(select(DCEDocument.doc_type).where(DCEDocument.project_id == pid,
                                                                DCEDocument.tenant_id == tenant_uuid))).scalars().all()
    types = {str(t or "").lower() for t in docs}
    if not docs:
        add("pieces", "a_completer", "aucune_piece", f"{base}/dce")
    elif "rc" not in types:
        add("pieces", "a_verifier", "rc_absent", f"{base}/dce")
    else:
        nb = (await db.execute(select(func.count()).select_from(DCECriterionEntity)
                               .where(DCECriterionEntity.project_id == pid))).scalar() or 0
        if not nb:
            add("pieces", "a_verifier", "rc_sans_criteres", f"{base}/dce")
        else:
            # 11/09 : quand la lecture du RC echoue, un bareme generique est pose a sa place.
            gabarit = (await db.execute(select(func.count()).select_from(DCECriterionEntity).where(
                DCECriterionEntity.project_id == pid,
                DCECriterionEntity.extracted_from.ilike("gabarit%")))).scalar() or 0
            if gabarit:
                add("pieces", "a_completer", "criteres_gabarit", f"{base}/dce")

    dec = (await db.execute(select(ProjectDecision).where(ProjectDecision.project_id == pid,
                                                          ProjectDecision.tenant_id == tenant_uuid))).scalar_one_or_none()
    form = (dec.form_data if dec and dec.form_data else {}) or {}
    # 11/09 : le formulaire proposait un chantier d'exemple complet ; enregistre tel
    # quel, il partait dans le memoire comme des faits (constate sur 2 projets).
    exemples = []
    noms = " ".join(str(c.get("nom") or "") for c in (form.get("equipe_cadres") or []) if isinstance(c, dict))
    if any(n in noms for n in SIGNATURES_EXEMPLE["equipe"]):
        exemples.append({"fr": "équipe fictive", "en": "fictitious team", "ar": "فريق وهمي"}[L])
    if any(x in str(form.get("materiel_principal") or "") for x in SIGNATURES_EXEMPLE["materiel"]):
        exemples.append({"fr": "matériel", "en": "equipment", "ar": "المعدات"}[L])
    if any(x in str(form.get("gestion_dechets") or "") for x in SIGNATURES_EXEMPLE["dechets"]):
        exemples.append({"fr": "déchets", "en": "waste", "ar": "النفايات"}[L])
    if exemples:
        add("equipe", "a_completer", "donnees_exemple", f"{base}/decisions", quoi=("، " if L == "ar" else ", ").join(exemples))
    if not form.get("phasage_travaux"):
        add("planning", "a_verifier", "phasage_absent", f"{base}/decisions")
    gd = (project.metadata_json or {}).get("gantt_detail")
    if gd:
        add("planning", "a_verifier", "gantt_detail", f"{base}/visuals",
            taches=gd.get("taches", 0), sous=gd.get("sous_taches", 0), origine=gd.get("origine", ""))
    nb_noeuds = (await db.execute(select(func.count()).select_from(ProjectOrganigrammeNode)
                                  .where(ProjectOrganigrammeNode.project_id == pid))).scalar() or 0
    a_pourvoir = (await db.execute(select(func.count()).select_from(ProjectOrganigrammeNode).where(
        ProjectOrganigrammeNode.project_id == pid, ProjectOrganigrammeNode.nom.ilike("%pourvoir%")))).scalar() or 0
    if not nb_noeuds:
        add("equipe", "a_completer", "orga_vide", f"{base}/decisions")
    elif a_pourvoir:
        add("equipe", "a_completer", "a_pourvoir", f"{base}/visuals", n=a_pourvoir)

    secs = (await db.execute(select(GeneratedSection).where(GeneratedSection.project_id == pid,
                                                            GeneratedSection.tenant_id == tenant_uuid))).scalars().all()
    manques, sans_web, echecs = 0, 0, []
    for s in secs:
        if s.status == "failed":
            echecs.append(s.title)
        for bloc in (s.visual_placeholders or []):
            if isinstance(bloc, dict) and bloc.get("type") == "lacunes":
                manques += len(bloc.get("items") or [])
            if isinstance(bloc, dict) and bloc.get("type") == "consommation" and not (bloc.get("contexte") or {}).get("web_chars"):
                sans_web += 1
    # 11/09 : changer la langue du document traduit la mise en page (titres, page de
    # garde), pas le texte deja redige. On le dit, section par section.
    langue_doc = (getattr(project, "output_language", None) or "fr")[:2]
    autre_langue = []
    for s in secs:
        if s.status == "failed" or not s.content_html:
            continue
        lg = _langue_texte(s.content_html)
        if lg and lg != langue_doc:
            autre_langue.append(lg)
    if autre_langue:
        lg = max(set(autre_langue), key=autre_langue.count)
        add("redaction", "a_verifier", "langue_contenu", f"{base}/export#traduction", n=len(autre_langue),
            ecrite=NOMS_LANGUES[lg][L], voulue=NOMS_LANGUES.get(langue_doc, NOMS_LANGUES["fr"])[L])
    if echecs:
        add("redaction", "a_completer", "sections_echec", f"{base}/editor", n=len(echecs), liste=", ".join(echecs[:3]))
    if manques:
        add("redaction", "a_verifier", "manques", f"{base}/editor", n=manques)
    if sans_web:
        add("redaction", "info", "sans_web", f"{base}/editor", n=sans_web)

    from app.models.entities import ExportTemplate
    from app.services.template_source_service import memoire_client_le_plus_fourni
    tmpl = (await db.execute(select(ExportTemplate).where(ExportTemplate.tenant_id == tenant_uuid,
                                                          ExportTemplate.is_default == True))).scalars().first()  # noqa: E712
    if not tmpl:
        mem = await memoire_client_le_plus_fourni(db, tenant_uuid)
        if mem:
            add("mise_en_page", "info", "modele_memoire", "/dashboard/branding", titre=mem.title)
        else:
            add("mise_en_page", "info", "modele_standard", "/dashboard/branding")

    if tenant and not tenant.siret:
        add("entreprise", "a_completer", "siret", "/dashboard/company")
    if tenant and not (tenant.branding_config or {}).get("city"):
        add("entreprise", "a_completer", "ville", "/dashboard/company")
    muets = (await db.execute(select(TenantReferenceUrl.url).where(
        TenantReferenceUrl.tenant_id == tenant_uuid,
        (TenantReferenceUrl.status != "active") | (func.coalesce(func.length(TenantReferenceUrl.content_excerpt), 0) < 400)
    ))).scalars().all()
    if muets:
        add("entreprise", "info", "sites_muets", "/dashboard/company", n=len(muets),
            liste=", ".join(u.replace("https://", "").split("/")[0] for u in muets[:3]))
    nb_memoires = (await db.execute(select(func.count()).select_from(CompanyAsset).where(
        CompanyAsset.tenant_id == tenant_uuid, CompanyAsset.category.in_(("memoire_reference", "memoire")),
        CompanyAsset.obsolete_at.is_(None)))).scalar() or 0
    if not nb_memoires:
        add("entreprise", "a_verifier", "sans_memoires", "/dashboard/company")

    ordre = {"a_completer": 0, "a_verifier": 1, "info": 2}
    items.sort(key=lambda i: ordre[i["gravite"]])
    return {"langue": L, "items": items, "resume": {g: sum(1 for i in items if i["gravite"] == g) for g in ordre}}
