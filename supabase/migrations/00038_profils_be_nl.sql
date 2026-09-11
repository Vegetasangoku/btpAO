-- 11/09 : les profils Belgique et Pays-Bas n'avaient aucune piece standard : la carte
-- « Pieces administratives » etait vide pour ces pays quand le RC manque.
-- (Deja applique sur la base le 11/09 ; idempotent.)
update country_regulatory_profiles set
  standard_requirements = '["DUME (Document unique de marché européen)","Extrait de la Banque-Carrefour des Entreprises (BCE)","Attestations ONSS et fiscale (vérifiées par l''acheteur via Télémarc)"]'::jsonb,
  mandatory_certifications = '["Agréation des entrepreneurs de travaux (catégorie et classe selon le montant)"]'::jsonb
where country_code = 'BE';

update country_regulatory_profiles set
  standard_requirements = '["UEA (Uniform Europees Aanbestedingsdocument)","Uittreksel Kamer van Koophandel (KvK)","Gedragsverklaring Aanbesteden (GVA)","Verklaring betalingsgedrag Belastingdienst"]'::jsonb,
  mandatory_certifications = '["VCA (sécurité chantier, souvent exigé)"]'::jsonb
where country_code = 'NL';
