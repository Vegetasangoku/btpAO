-- ==============================================================================
-- btpAO Seed Demo Data for BTP Technical Memo Generator
-- ==============================================================================

-- 1. Create Default Demo Tenant
INSERT INTO public.tenants (id, name, slug, plan, s3_bucket_prefix, branding_config)
VALUES (
    '11111111-1111-1111-1111-111111111111'::UUID,
    'EiffaBTP Construction SAS',
    'eiffabtp-sas',
    'enterprise',
    'tenants/11111111-1111-1111-1111-111111111111',
    '{
        "primary_color": "#0ea5e9",
        "secondary_color": "#0f172a",
        "font_family": "Inter",
        "company_name": "EiffaBTP Construction SAS",
        "header_text": "Mémoire Technique Justificatif - Offre BTP",
        "footer_text": "EiffaBTP SAS - Document soumis dans le cadre de l''appel d''offres"
    }'::jsonb
) ON CONFLICT (id) DO NOTHING;

-- 2. Create Demo User
INSERT INTO public.users (id, tenant_id, email, full_name, role)
VALUES (
    '22222222-2222-2222-2222-222222222222'::UUID,
    '11111111-1111-1111-1111-111111111111'::UUID,
    'conducteur@eiffabtp.fr',
    'Jean-Marc Alibert',
    'conducteur_travaux'
) ON CONFLICT (id) DO NOTHING;

-- 3. Create Demo Project
INSERT INTO public.projects (
    id, tenant_id, title, reference_code, client_name, location, lot_number, status, budget_estimate, submission_deadline, scoring_notes, created_by
)
VALUES (
    '33333333-3333-3333-3333-333333333333'::UUID,
    '11111111-1111-1111-1111-111111111111'::UUID,
    'Construction du Groupe Scolaire & Gymnase HQE',
    'AO-2026-MGP-089',
    'Métropole du Grand Paris & Ville de Saint-Denis',
    'ZAC Plaine Saulnier, 93200 Saint-Denis',
    'Lot 01 - Terrassement, Démolition & Gros Œuvre',
    'review',
    3450000.00,
    now() + INTERVAL '14 days',
    '{"technical_weight": 60, "price_weight": 40}'::jsonb,
    '22222222-2222-2222-2222-222222222222'::UUID
) ON CONFLICT (id) DO NOTHING;

-- 4. Create DCE Criteria (RC Requirements)
INSERT INTO public.dce_criteria (tenant_id, project_id, criterion_title, weight_percentage, description, key_expectations, required_evidence, mandatory)
VALUES
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    '1. Moyens humains & Organisation de chantier',
    25.00,
    'Pertinence de l''organigramme d''encadrement dédié, CVs du personnel d''encadrement (Conducteur de travaux, Chef de chantier) et temps de présence effectif.',
    '["Organigramme précis du chantier", "CVs détaillés avec références similaires en milieu contraint", "Taux d''encadrement minimum de 15%"]'::jsonb,
    '["CVs nominatifs signés", "Attestations de formation SST et habilitations électriques", "Organigramme BTP"]'::jsonb,
    true
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    '2. Méthodologie d''exécution, Matériels & Phasage',
    35.00,
    'Procédés d''exécution du gros œuvre, implantation des grues et zones de stockage, phasage détaillé avec chemin critique et respect impératif du délai global de 6 mois.',
    '["Plan d''installation de chantier (PIC)", "Planning Gantt hebdomadaire avec marge météo", "Fiches techniques des engins (Grue à tour Potain 50m)"]'::jsonb,
    '["Planning Gantt détaillé", "Plan de calepinage banches et rotation des voiles", "Notice technique de coulage des bétons"]'::jsonb,
    true
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    '3. Démarche Environnementale (RSE) & Gestion des Déchets',
    25.00,
    'Mesures concrètes de réduction de l''empreinte carbone (Béton bas carbone), tri 5 flux des déchets in situ, filières de recyclage locales (<30km) et charte chantier propre.',
    '["Bordereau de Suivi des Déchets (BSD)", "Objectif valorisation >= 85%", "Utilisation de bétons formulés CEM III/A ou B à faible impact carbone", "Acoustique et limitation des poussières"]'::jsonb,
    '["Contrats cadres filières agréées", "Fiches FDES des bétons bas carbone", "Plan de gestion des eaux de ruissellement et de décantation"]'::jsonb,
    true
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    '4. Qualité (PAQ) & Sécurité (PPSPS)',
    15.00,
    'Plan d''Assurance Qualité, contrôle interne des armatures et des réservations, procédures d''accueil sécurité et prévention des risques de coactivité.',
    '["Contrôles préalables aux coulage des voiles/dalles", "Fiches d''autocontrôle informatisées", "PPSPS détaillé adapté aux contraintes urbaines denses"]'::jsonb,
    '["Procédure PAQ type", "Trame de fiche de non-conformité", "Mesures anti-chutes de hauteur"]'::jsonb,
    true
);

-- 5. Create Company Assets (Références & Matériels Entreprise)
INSERT INTO public.company_assets (tenant_id, category, title, description, tags, metadata_json)
VALUES
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    'certificat_qualibat',
    'Certification QUALIBAT 1112 & 2112',
    'Démolition (technicité confirmée) et Maçonnerie & Béton Armé (technicité supérieure)',
    ARRAY['qualibat', 'beton_arme', 'gros_oeuvre'],
    '{"validite": "2027-12-31", "numero": "QBT-98421", "organisme": "Qualibat France"}'::jsonb
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    'materiel_engins',
    'Grue à tour Potain MDT 219 J10',
    'Grue Topless 10t avec flèche 65m, système Top Tracing anti-collision et cabine vision UltraView',
    ARRAY['grue', 'levage', 'potain', 'topless'],
    '{"hauteur_sous_crochet_m": 45, "portee_max_m": 65, "charge_max_t": 10, "annee": 2024}'::jsonb
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    'reference_chantier',
    'Lycée International Rosa Parks - 12 000 m²',
    'Construction en béton bas carbone et structure mixte bois-béton. Durée: 14 mois. Budget: 8.2M€.',
    ARRAY['scolaire', 'hqe', 'bas_carbone', 'saint-denis'],
    '{"maitre_ouvrage": "Région Île-de-France", "annee_livraison": 2024, "surface_m2": 12000, "note_satisfaction": "5/5"}'::jsonb
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    'cv_encadrement',
    'Jean-Marc Alibert - Conducteur de Travaux Principal',
    '15 ans d''expérience en réhabilitation lourde et construction neuve scolaire et tertiaire en milieu urbain dense.',
    ARRAY['cv', 'encadrement', 'conducteur_travaux'],
    '{"diplome": "Ingénieur ESTP Paris", "chantiers_majeurs": ["Campus Condorcet", "Collège Éco-Quartier Clichy"]}'::jsonb
);

-- 6. Pre-fill Project Decisions
INSERT INTO public.project_decisions (tenant_id, project_id, form_data, updated_by)
VALUES (
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    '{
        "delai_mois": 6,
        "date_demarrage": "2026-10-01",
        "materiel_principal": "Grue à tour Potain MDT 219 (flèche 50m), 2 pelles Liebherr 22t, 4 camions 8x4 avec bâchage automatique, centrale à coulis et banches manuportables Alphi",
        "travail_de_nuit": false,
        "gestion_dechets": "Tri sélectif 5 flux sur plateforme sécurisée avec compacteur in situ. Objectif 88% de valorisation matière via plateforme locale Paprec / Veolia à 12 km du site.",
        "equipe_cadres": [
            {"nom": "Jean-Marc Alibert", "role": "Directeur de Projet & Conducteur Principal", "experience_ans": 15, "presence_hebdo_pct": 100},
            {"nom": "Sébastien Vasseur", "role": "Chef de Chantier Gros Œuvre", "experience_ans": 12, "presence_hebdo_pct": 100},
            {"nom": "Chloé Fontaine", "role": "Ingénieur QSE & Environnement", "experience_ans": 7, "presence_hebdo_pct": 50}
        ],
        "mesures_securite": "PPSPS déposé 30j avant démarrage, sas d''accueil sécurité avec contrôle biométrique, protection collective intégrée sur banches (garde-corps verrouillés), défibrillateur et 4 SST sur site en permanence.",
        "demarche_rse_environnement": "Béton bas carbone CEM III/A avec réduction de 42% des émissions CO2 (NF EN 206/CN), bâchage acoustique des compresseurs, circuit fermé de recyclage des eaux de lavage des toupies à béton.",
        "phasage_travaux": [
            {"phase": "1. Installation de chantier, PIC & Terrassements", "duree_semaines": 4, "jalon": "Accès voirie & base-vie opérationnels"},
            {"phase": "2. Fondations profondes et longrines", "duree_semaines": 4, "jalon": "Réception plateforme géotechnique"},
            {"phase": "3. Infrastructure & Superstructure R+2 Gros Œuvre", "duree_semaines": 10, "jalon": "Hors d''eau / Hors d''air structurel"},
            {"phase": "4. Réseaux enterrés, VRD & Aménagements extérieurs", "duree_semaines": 4, "jalon": "Essais d''étanchéité & OPR"},
            {"phase": "5. Repli de chantier, levée des réserves & Livraison", "duree_semaines": 2, "jalon": "Parfait Achèvement & Remise des clés"}
        ]
    }'::jsonb,
    '22222222-2222-2222-2222-222222222222'::UUID
) ON CONFLICT (project_id) DO NOTHING;

-- 7. Create Default Generated Sections
INSERT INTO public.generated_sections (
    tenant_id, project_id, section_key, title, order_index, content_html, content_json, status, compliance_score, compliance_notes
)
VALUES
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    'moyens_humains',
    '1. Moyens Humains & Organisation du Chantier',
    1,
    '<h2>1.1 Organigramme d''Encadrement et Rôles Clés</h2><p>Pour garantir la parfaite maîtrise technique et le respect scrupuleux du planning de 6 mois, notre entreprise mobilise une équipe dédiée et hautement qualifiée :</p><ul><li><strong>Directeur de Projet / Conducteur Principal :</strong> Jean-Marc Alibert (15 ans d''expérience, Ingénieur ESTP). Présence effective sur site : 100%. Interlocuteur unique auprès de la Maîtrise d''Ouvrage et du Maître d''Œuvre.</li><li><strong>Chef de Chantier Gros Œuvre :</strong> Sébastien Vasseur (12 ans d''expérience). Présence permanente sur le site, responsable direct de l''application stricte du PPSPS et du contrôle journalier des rotations de banches.</li><li><strong>Responsable Qualité, Sécurité & Environnement (QSE) :</strong> Chloé Fontaine (7 ans d''expérience, Master QSE BTP). Audits hebdomadaires in situ et suivi du tri 5 flux.</li></ul><p>Taux d''encadrement global garanti sur le chantier : <strong>18,5%</strong> (largement supérieur à l''exigence minimale de 15% fixée par le Règlement de Consultation).</p>',
    '{"sections": [{"title": "1.1 Organigramme d''Encadrement", "paragraphs": ["Équipe dédiée 100%"]}]}'::jsonb,
    'validated',
    98.5,
    'Conformité totale avec les exigences du RC (taux d''encadrement >15%, CVs joints et présence effective 100%).'
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    'moyens_materiels',
    '2. Moyens Matériels & Plan d''Installation de Chantier (PIC)',
    2,
    '<h2>2.1 Équipements Lourds & Matériels Dédiés</h2><p>L''ensemble du parc matériel affecté à cette opération est conforme aux normes CE et bénéficie de contrôles périodiques VGP à jour :</p><ul><li><strong>Grue à tour Potain MDT 219 J10 :</strong> Flèche de 50 m permettant de couvrir 100% de l''emprise du futur Groupe Scolaire et du Gymnase, charge de 1,9 t en bout de flèche. Système anti-collision Top Tracing intégré.</li><li><strong>Engins de terrassement :</strong> 2 pelles sur chenilles Liebherr 22t équipées de filtres à particules Tier V et d''attaches rapides sécurisées.</li><li><strong>Matériel de coffrage :</strong> Banches métalliques manuportables Alphi avec passerelles de sécurité intégrées et lests sécurisés.</li></ul>',
    '{"sections": [{"title": "2.1 Équipements Lourds", "paragraphs": ["Grue Potain MDT 219"]}]}'::jsonb,
    'validated',
    96.0,
    'Fiches techniques conformes aux exigences du CCTP.'
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    'methodologie_phasage',
    '3. Méthodologie d''Exécution & Phasage des Travaux',
    3,
    '<h2>3.1 Phasage Chronologique et Chemin Critique</h2><p>Le chantier est décomposé en 5 phases séquentielles optimisées pour garantir une livraison dans le délai strict de 6 mois (24 semaines ouvrées) :</p><ol><li><strong>Semaines 1 à 4 :</strong> Installation de chantier, mise en place de la base-vie modulaire R+1, voirie lourde provisoire et terrassements généraux en pleine masse.</li><li><strong>Semaines 5 à 8 :</strong> Réalisation des fondations profondes (pieux forés tubés) et longrines préfabriquées.</li><li><strong>Semaines 9 à 18 :</strong> Élévation gros œuvre R+2 avec cadence de 2 voiles banchés par jour et dalles alvéolaires précontraintes.</li><li><strong>Semaines 19 à 22 :</strong> Réseaux sous dallage, VRD périphériques et raccordements concessionnaires.</li><li><strong>Semaines 23 à 24 :</strong> Repli progressif, essais acoustiques et OPR.</li></ol>',
    '{"sections": [{"title": "3.1 Phasage Chronologique", "paragraphs": ["Phasage 24 semaines"]}]}'::jsonb,
    'generated',
    95.0,
    'Planning cohérent intégrant un buffer intempéries de 10 jours ouvrés.'
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    'qse_environnement',
    '4. Démarche RSE, Environnement & Gestion des Déchets',
    4,
    '<h2>4.1 Réduction de l''Empreinte Carbone et Bétons Bas Carbone</h2><p>Dans le cadre de l''objectif HQE du projet, nous nous engageons sur les points suivants :</p><ul><li><strong>Béton Bas Carbone CEM III/A :</strong> Réduction certifiée de 42% des émissions équivalent CO2 par rapport à un béton standard CEM I, formulé selon la norme NF EN 206/CN.</li><li><strong>Gestion des Déchets de Chantier :</strong> Tri à la source en 5 flux distincts (Gravats inertes, Bois classe B, Métaux ferreux, Plastiques/Cartons, DIB) sur une aire dédiée étanche.</li><li><strong>Filière de Recyclage de Proximité :</strong> Partenariat avec le centre de tri agréé situé à 12 km du chantier, garantissant un taux de revalorisation matière supérieur à <strong>88%</strong> (supérieur aux 85% du RC).</li><li><strong>Protection des Riverains et Acoustique :</strong> Bâches acoustiques absorbantes sur compresseurs et nettoyeurs haute pression, lavage automatique des roues de camions avant insertion sur la voirie publique.</li></ul>',
    '{"sections": [{"title": "4.1 Démarche RSE", "paragraphs": ["Béton CEM III/A", "Tri 5 flux"]}]}'::jsonb,
    'validated',
    99.0,
    'Exigences RSE exemplaires avec traçabilité BSD informatisée.'
),
(
    '11111111-1111-1111-1111-111111111111'::UUID,
    '33333333-3333-3333-3333-333333333333'::UUID,
    'securite_ppsps',
    '5. Sécurité, Santé (PPSPS) & Plan d''Assurance Qualité (PAQ)',
    5,
    '<h2>5.1 Plan Particulier de Sécurité et de Protection de la Santé (PPSPS)</h2><p>La sécurité absolue des intervenants et des usagers riverains constitue notre priorité opérationnelle :</p><ul><li><strong>Accueil Sécurité Obligatoire :</strong> Tout intervenant (compagnon ou sous-traitant) suit un sas d''accueil de 30 minutes avec délivrance d''un badge nominatif après vérification des habilitations.</li><li><strong>Prévention des Risques de Chutes :</strong> Utilisation systématique de garde-corps télescopiques fixes et filets anti-chutes périphériques dès le coulage des planchers hauts.</li><li><strong>Plan d''Assurance Qualité (PAQ) :</strong> Fiches d''autocontrôle numériques systématiques avant tout coulage béton (conformité ferraillage, enrobage, réservations).</li></ul>',
    '{"sections": [{"title": "5.1 Sécurité PPSPS", "paragraphs": ["Sas d''accueil sécurité", "PAQ numérique"]}]}'::jsonb,
    'validated',
    97.5,
    'Conforme aux exigences SPS niveau 1.'
)
ON CONFLICT (project_id, section_key) DO NOTHING;

-- 8. Create Default Export Template
INSERT INTO public.export_templates (tenant_id, name, description, s3_docx_key, is_default, styles_config)
VALUES (
    '11111111-1111-1111-1111-111111111111'::UUID,
    'Modèle Standard Entreprise BTP - Charte Bleue',
    'Gabarit Word officiel avec en-têtes dynamiques, logos, styles de titres H1-H3 et intégration automatique du Gantt et de l''Organigramme.',
    'tenants/11111111-1111-1111-1111-111111111111/templates/charte_officielle_btp.docx',
    true,
    '{
        "primary_color_hex": "#0284c7",
        "secondary_color_hex": "#0f172a",
        "font_family_title": "Calibri",
        "font_family_body": "Calibri Light",
        "include_cover_page": true,
        "include_toc": true
    }'::jsonb
) ON CONFLICT (id) DO NOTHING;
