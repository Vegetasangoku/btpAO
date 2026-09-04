-- ==============================================================================
-- 00029_fix_btp_app_user_missing_grants.sql
-- Miroir local d'un correctif deja applique et deja suivi cote Supabase (version
-- distante 20260830230509 "fix_btp_app_user_missing_grants", appliquee le 30/08
-- via mcp__Supabase__apply_migration) mais jusqu'ici absent du depot local --
-- donc invisible pour quiconque lit le code source ou recree la base depuis les
-- fichiers de supabase/migrations/ uniquement (nouvelle branche, restauration,
-- CI). Contenu identique a la migration distante deja appliquee ; NE PAS la
-- re-appliquer via apply_migration, elle l'est deja (verifie le 02/09 via
-- information_schema.role_table_grants + supabase_migrations.schema_migrations).
-- Ce fichier existe uniquement pour la parite depot/base.
--
-- Retrouve pendant la cloture de la tache #64 ("diagnostiquer et corriger
-- erreur Gantt session expiree") : project_gantt_tasks et llm_usage_logs
-- avaient ete crees sans GRANT vers btp_app_user (le role applicatif reel du
-- backend FastAPI), contrairement a toutes les autres tables. Resultat :
-- "permission denied for table ..." sur chaque requete, que le frontend
-- affichait comme "session expiree ou service indisponible" -- un message
-- honnete (deja au conditionnel, jamais une fausse certitude) mais qui
-- n'avait rien a voir avec l'authentification. Cause racine : ALTER DEFAULT
-- PRIVILEGES pour le role postgres ne couvre que anon/authenticated/
-- service_role/postgres, jamais btp_app_user -- donc chaque nouvelle table
-- doit l'accorder explicitement. Le correctif d'origine (ci-dessous) pose
-- aussi une regle par defaut pour que ça ne se reproduise plus sur une future
-- table.
--
-- Complement (02/09) : le frontend (api.ts, gantt-preview.tsx,
-- interactive-gantt-chart.tsx, organigramme-preview.tsx) a ete corrige en
-- parallele pour ne plus jamais afficher "session expiree" sur une 500/403 --
-- desormais seul un vrai 401 declenche ce message precis, toute autre erreur
-- affiche le message generique "service indisponible".
-- ==============================================================================

GRANT ALL ON public.project_gantt_tasks TO btp_app_user;
GRANT ALL ON public.llm_usage_logs TO btp_app_user;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT ALL ON TABLES TO btp_app_user;
