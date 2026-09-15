import pathlib
p = pathlib.Path.home() / "mnt/reponse_au_ao/apps/api/app/services/pieces_service.py"
content = p.read_text()

def replace_once(content, old, new, label):
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match, got {n}"
    return content.replace(old, new, 1)

# Edit 1: signature
old1 = '''async def analyser_pieces(db: AsyncSession, tenant_uuid: uuid.UUID, project: Project, chercher: bool = True,
                          langue: str = "fr") -> Dict[str, Any]:'''
new1 = '''async def analyser_pieces(db: AsyncSession, tenant_uuid: uuid.UUID, project: Project, chercher: bool = True,
                          langue: str = "fr", pieces_confirmees: Optional[List[str]] = None) -> Dict[str, Any]:'''
content = replace_once(content, old1, new1, "Edit1-signature")

# Edit 2: fetch historique after profil
old2 = '''    pays = (project.country_code or (tenant.country_code if tenant else None) or "FR").upper()
    profil = await db.get(CountryRegulatoryProfile, pays)

    # 1. Exigences'''
new2 = '''    pays = (project.country_code or (tenant.country_code if tenant else None) or "FR").upper()
    profil = await db.get(CountryRegulatoryProfile, pays)
    # 15/09 : pieces deja vues (citees dans un vrai RC/DCE) pour ce tenant, dans ce pays --
    # alimente a la fois l'injection des pieces confirmees ci-dessous et les recommandations.
    historique = (await db.execute(select(TenantPieceHistory).where(
        TenantPieceHistory.tenant_id == tenant_uuid, TenantPieceHistory.country_code == pays,
    ))).scalars().all()

    # 1. Exigences'''
content = replace_once(content, old2, new2, "Edit2-historique-fetch")

# Edit 3: inject confirmed pieces after DUME block, before dedup
old3 = '''    if pays == "FR" and not any("dume" in _norm(e["piece"]) for e in exigences):
        exigences.append({"piece": "DUME", "citation": None,
                          "origine": _t("dume_origine", L)})
    # Dedoublonnage (meme piece citee par le profil pays et par le DCE)'''
new3 = '''    if pays == "FR" and not any("dume" in _norm(e["piece"]) for e in exigences):
        exigences.append({"piece": "DUME", "citation": None,
                          "origine": _t("dume_origine", L)})
    # 15/09 : pieces recommandees (vues dans un dossier precedent, meme tenant/pays) que
    # l'utilisateur vient de confirmer pour CE dossier -- rejoignent les exigences, avec la
    # citation/le type retrouves dans l'historique ; renforcees comme les autres plus bas.
    for _label in (pieces_confirmees or []):
        _lbl = str(_label)[:250]
        _h = next((h for h in historique if h.piece_key == _cle_historique(_lbl)), None)
        if not _h:
            _kl = _cle(_lbl)
            _h = next((h for h in historique if _kl and (_kl <= _cle(h.piece_label) or _cle(h.piece_label) <= _kl)), None)
        if _h:
            exigences.append({
                "piece": _h.piece_label, "citation": _h.piece_citation,
                "origine": _t("historique", L, pays=nom_pays(pays, L, profil.country_name if profil else pays)),
                "type": _h.piece_type,
            })
    # Dedoublonnage (meme piece citee par le profil pays et par le DCE)'''
content = replace_once(content, old3, new3, "Edit3-inject-confirmed")

# Edit 4: recommandations computed after dedup loop, before "# 2. Disponible"
old4 = '''        uniques.append(e)

    # 2. Disponible'''
new4 = '''        uniques.append(e)

    # 15/09 : recommandations -- pieces vues dans un dossier precedent (meme tenant, meme pays)
    # mais absentes de celui-ci ; jamais ajoutees d'office, seulement proposees (pieces_confirmees
    # au prochain appel les fait rejoindre les exigences ci-dessus, cf. bloc precedent).
    recommandations: List[Dict[str, Any]] = []
    for h in sorted(historique, key=lambda h: h.seen_count or 0, reverse=True):
        kh = _cle(h.piece_label)
        if not kh or any(kh <= _cle(u["piece"]) or _cle(u["piece"]) <= kh for u in uniques):
            continue
        recommandations.append({
            "piece": h.piece_label, "type": h.piece_type, "vu_fois": h.seen_count or 1,
            "dernier_dossier_le": h.last_seen_at.isoformat() if h.last_seen_at else None,
        })

    # 2. Disponible'''
content = replace_once(content, old4, new4, "Edit4-recommandations-compute")

# Edit 5: upsert history pass + add recommandations to return dict
old5 = '''        resultat.append(ligne)

    return {
        "pays": pays,
        "pays_nom": nom_pays(pays, L, profil.country_name if profil else pays),
        "portails": domaines,
        "dce_analyse": dce_lu,
        "pieces": resultat,
        "resume": {s: sum(1 for r in resultat if r["statut"] == s) for s in ("fourni", "generable", "redigeable", "manquant")},
        "pieces_du_dce": nb_dce,
        "rc_absent": not nb_dce and not rc_depose,
        "lecture_simple": lecture_simple,
        "avertissement": (None if nb_dce else
                          _t("rc_illisible", L) if rc_depose else
                          _t("rc_absent", L, pays=nom_pays(pays, L, profil.country_name if profil else pays))),
    }'''
new5 = '''        resultat.append(ligne)

    # 15/09 : renforce l'historique tenant+pays avec tout ce qui a une citation reelle (DCE
    # de ce dossier, ou confirme depuis une recommandation) -- alimente les recommandations
    # des PROCHAINS dossiers similaires ("on fait les reco et on apprend").
    for e in uniques:
        if e.get("citation"):
            await _upsert_piece_history(db, tenant_uuid, pays, e["piece"], e.get("type"), e["citation"], project.id)

    return {
        "pays": pays,
        "pays_nom": nom_pays(pays, L, profil.country_name if profil else pays),
        "portails": domaines,
        "dce_analyse": dce_lu,
        "pieces": resultat,
        "resume": {s: sum(1 for r in resultat if r["statut"] == s) for s in ("fourni", "generable", "redigeable", "manquant")},
        "pieces_du_dce": nb_dce,
        "rc_absent": not nb_dce and not rc_depose,
        "lecture_simple": lecture_simple,
        "recommandations": recommandations,
        "avertissement": (None if nb_dce else
                          _t("rc_illisible", L) if rc_depose else
                          _t("rc_absent", L, pays=nom_pays(pays, L, profil.country_name if profil else pays))),
    }'''
content = replace_once(content, old5, new5, "Edit5-upsert-and-return")

p.write_text(content)
print("OK: all 5 edits applied")
