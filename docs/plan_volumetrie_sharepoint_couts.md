# Gros volumes, chat, SharePoint : plan de dev et ce qui a été livré

Note technique — 3 septembre 2026 — répond à la demande de faire évoluer `reponse_au_ao` (btpAO) pour absorber de gros dossiers, du chat et un connecteur SharePoint sans faire déraper les coûts, avec une marge garantie sur le forfait vendu à Thierry.

## 1. Ce que j'ai vérifié avant de répondre

Le point de départ n'était pas une page blanche : btpAO a déjà un système de plafonds de coût réel bien construit (migration `00030`, note `plafonds-ia-et-modele-gratuit.md` du 2 septembre) — un plafond de dépense LLM en dollars réels, à trois niveaux (fournisseur / forfait / client), avec dépassement bloquant proprement (HTTP 402) plutôt qu'une facture surprise. Les forfaits actuels : PME & artisan (199 €, 3 dossiers, plafond 32 $), Entreprise générale (499 €, 10 dossiers, plafond 80 $), Grand compte (sur devis, 50 dossiers, plafond 400 $).

Ce système protège déjà bien l'axe **LLM** (génération de sections, chat, extraction de critères). Trois axes de coût restaient sans filet :

1. **Le volume de pages ingérées** (DCE + base de connaissances) — c'est ce qui fait grossir `dce_embeddings`/`knowledge_vectors`, donc la charge Postgres/pgvector réelle et, à terme, la facture de calcul Supabase. Aucun plafond n'existait sur cet axe, seulement un plafond par *nombre de documents* (20/100/illimité), pas par *volume*.
2. **Le coût OCR Azure Document Intelligence** — jamais journalisé, jamais plafonné, et surtout : appelé sur l'intégralité de chaque document dès qu'une clé Azure était configurée, même pour un PDF 100 % numérique natif que `pdfplumber` (gratuit) sait déjà lire parfaitement.
3. **SharePoint** — n'existait pas du tout.

## 2. Définir "gros fichier" et "grosse entreprise"

Pour un marché public français ou MEA de taille significative, un dossier de consultation complet (RC + CCTP + CCAP + annexes techniques/BPU) pèse couramment **300 à 600 pages cumulées**, parfois plus de 1000 avec les annexes techniques. C'est ça, un "gros fichier" dans ce métier — pas une exception, la norme pour les gros comptes.

Pour "8 à 10 dossiers majeurs par mois simultanés" (le chiffre que tu as donné à Thierry), en comptant ~3 documents par dossier (RC, CCTP, CCAP) et une moyenne de 250 à 300 pages par document réellement soumis à l'ingestion (OCR + embeddings) :

- **Volume mensuel réaliste : 6 000 à 9 000 pages/mois** pour une "grosse entreprise" au sens de ce contrat.
- J'ai posé les compteurs et plafonds pour couvrir large au-delà de ça (15 000 pages/mois sur le forfait Grand Compte) — voir §5.

## 3. Le modèle de coût et de marge, avec de vrais chiffres

Sur la base du benchmark déjà mesuré dans la note du 2 septembre (Claude Sonnet 5, 2 $/10 $ par million de tokens) : **~5 $ de coût LLM par dossier complet**, embeddings compris (négligeables : `text-embedding-3-small` à 0,02 $/million de tokens — même un dossier de 500 pages ne coûte qu'un centime ou deux en embeddings).

Le poste qui pouvait vraiment déraper, c'est l'OCR Azure — pas parce qu'il est cher à la page (~0,01 $/page en modèle Layout), mais parce qu'il était appelé sur **toutes** les pages de **tous** les documents, y compris les 90%+ de CCTP/RC français qui sont des PDF numériques natifs et n'ont besoin d'aucun OCR payant. Un dossier de 500 pages 100% natif coûtait ~5 $ d'Azure pour rien. Le triage livré ci-dessous fait tomber ce coût à **zéro** sur un document natif, et le réserve aux seules pages réellement scannées.

**Calcul de marge pour un forfait à 700 $/mois avec 75-80 % de marge visée** : le budget de coût variable total (LLM + OCR + embeddings) ne doit pas dépasser ~140-175 $/mois. Avec le plafond LLM existant réglable à ~100-120 $ et un plafond OCR neuf réglable à ~50 $ (largement suffisant même en cas d'usage anormal, le triage ayant déjà éliminé l'essentiel du volume), la marge cible est tenable **même si le client utilise l'intégralité de ses 8-10 dossiers, pose beaucoup de questions au chat, et connecte SharePoint**.

Point important à ne pas perdre de vue : **le coût Supabase (calcul/stockage Postgres) est un coût de portefeuille, pas un coût par tenant.** Il grossit avec le nombre total de lignes dans `dce_embeddings`/`knowledge_vectors`, tous clients confondus. Le vrai levier n'est donc pas seulement "plafonner Thierry", mais aussi la purge/l'archivage des vecteurs de dossiers anciens ou perdus — c'est en tête de la liste des prochaines étapes (§6), pas encore fait faute de temps ce tour-ci.

## 4. Ce qui a été livré maintenant

Tout ce qui suit a été appliqué directement sur ton projet Supabase (`ykdbjsvwzxeftlddubgy`) et sur le code dans `reponse_au_ao/apps/api`.

### 4.1 Triage OCR local → Azure (le plus gros levier de coût)

`app/services/ocr_service.py` : `pdfplumber` (gratuit, local) lit maintenant **systématiquement tout le document en premier**. Seules les pages dont le rendement textuel est trop faible (moins de 40 caractères utiles — signe qu'elles sont scannées/en image) sont extraites dans un mini-PDF et envoyées à Azure Document Intelligence. Sur un CCTP 100% natif, Azure n'est plus appelé du tout. Testé (`tests/test_ocr_triage_reduces_azure_cost.py`, 3 tests, tous passent) : un document mixte de 3 pages n'escalade que la page réellement faible, jamais les deux autres.

### 4.2 Coût OCR enfin journalisé et plafonné

Nouveau service `app/services/ocr_cost_service.py`, nouvelle table `ocr_usage_logs` (miroir de `llm_usage_logs`) : chaque cycle OCR journalise ses pages locales/Azure et son coût estimé. Nouveau plafond mensuel `monthly_llm_cost_cap_usd`-like : `subscription_plans.monthly_ocr_cost_cap_usd` / `tenant_subscriptions.custom_ocr_cost_cap_usd` — même mécanique exacte que le plafond LLM existant (dépassement → 402 propre, jamais une facture surprise).

### 4.3 Volume de pages : nouveau plafond indépendant du nombre de dossiers

`subscription_plans.included_pages_month` / `tenant_subscriptions.custom_pages_month`, avec dépassement payant configurable (`extra_pages_price_cents_per_1000`, comme le dépassement de dossiers existant). Vérifié dans `parse_dce_task` (le worker Celery qui traite chaque DCE) **juste après l'OCR local, avant tout calcul d'embedding** — pour ne jamais facturer un coût inutile à un document qui sera de toute façon refusé. Un document qui dépasse le quota est marqué `blocked_quota` avec un message clair, pas une erreur technique.

### 4.4 Chat : quota de questions + dépassement payant

`billing_service.check_and_enforce_question_quota` (nouveau), câblé dans `/projects/{id}/ask`. Le plafond de coût LLM existant protège déjà le $ réel consommé par le chat ; celui-ci ajoute un signal de fréquence d'usage complémentaire avec dépassement payant, mêmes conventions que le quota de dossiers (`included_questions_month` / `custom_questions_month`).

### 4.5 Anti-abus : déduplication des dépôts DCE

Le dépôt de DCE (`/dce/upload`) rejette maintenant un fichier identique déjà déposé sur le même dossier (empreinte SHA-256), comme c'était déjà le cas pour la base de connaissances. Ça règle directement ton "s'il s'amuse à m'en foutre plein" pour le cas le plus simple (redépôt du même fichier).

### 4.6 Connecteur SharePoint (Microsoft Graph), synchronisation incrémentale

C'est le morceau le plus gros. Architecture :

- **Une App Registration Azure AD par client**, créée et consentie par l'IT de Thierry (jamais par toi) — permissions lecture seule sur le site/dossier choisi. Le `client_id`/`client_secret` sont fournis par leur IT et chiffrés au repos (`crypto_vault`, déjà utilisé pour les clés LLM).
- **Synchronisation par `delta-query` Microsoft Graph** (`app/services/sharepoint_service.py`) : le premier passage liste tout, chaque passage suivant ne renvoie QUE les fichiers nouveaux/modifiés/supprimés depuis le dernier curseur (`delta_link`, stocké en base). C'est ce qui garantit qu'"on ne prend que les nouveaux", exactement ta demande — jamais un rebalayage complet.
- **Filtrage avant tout téléchargement** : extension (pdf/docx/xlsx par défaut, configurable), taille max (50 Mo par défaut). Les dossiers et les suppressions sont ignorés proprement.
- **Déduplication par contenu** (`sharepoint_sync_items.file_hash`) : un fichier renommé/déplacé mais dont le contenu n'a pas changé n'est jamais réindexé.
- **Réutilise le pipeline d'ingestion existant** de la base de connaissances (`extract_text_from_upload` + `chunk_and_embed_asset_text`, déjà dans `knowledge.py`) — aucune logique dupliquée, donc les mêmes quotas (pages, coût OCR, coût LLM) s'appliquent automatiquement.
- **Plafond dédié** `included_sharepoint_files_month` / `custom_sharepoint_files_month`, vérifié **avant** tout téléchargement — protège explicitement contre le cas "il connecte tout son SharePoint d'un coup".
- **Synchronisation automatique toutes les 6h** (Celery Beat) + déclenchement manuel (`POST /sharepoint/sync`).
- Routes API : `POST /sharepoint/connect`, `GET /sharepoint/status`, `POST /sharepoint/sync`, `DELETE /sharepoint/disconnect`.

Testé sans réseau réel (impossible de simuler une vraie App Registration Azure AD) : `tests/test_sharepoint_connector_filtering_and_delta.py`, 5 tests — filtrage par extension/taille, dossiers ignorés, suppressions détectées, et suivi correct du curseur delta à travers la pagination. Tous passent.

### 4.7 Migrations appliquées

`00032_volume_quotas_ocr_and_questions.sql` et `00033_sharepoint_connectors.sql`, appliquées en direct sur ton projet Supabase et versionnées dans `supabase/migrations/`. Valeurs de départ posées sur les 3 forfaits existants :

| Forfait | Pages incluses/mois | Plafond OCR | Questions incluses/mois | Fichiers SharePoint/mois |
|---|---|---|---|---|
| PME & artisan | 750 | 5 $ | 150 | 0 (fonctionnalité réservée aux forfaits supérieurs) |
| Entreprise générale | 3 000 | 20 $ | 500 | 150 |
| Grand compte | 15 000 | 50 $ | 2 500 | 1 000 |

Tout est ajustable depuis la même console admin que les plafonds LLM existants (`/admin/costs`), ou par surcharge nominative une fois le tenant de Thierry créé.

## 5. Configuration recommandée pour le contrat de Thierry (650-750 $/mois)

Une fois son tenant créé (probablement sur le forfait "Grand compte" avec surcharges nominatives, vu le prix négocié hors grille) :

- `custom_llm_cost_cap_usd` : 110-130 $ (16-18 % du prix de vente, cohérent avec la règle des 15 % déjà en place)
- `custom_pages_month` : 8 000 (large au-dessus des 6 000-9 000 estimés au §2)
- `custom_ocr_cost_cap_usd` : 25 $ (généreux, le triage ayant déjà éliminé l'essentiel du volume)
- `custom_questions_month` : 800 (~80-100/dossier, confortable pour un usage itératif du chat)
- `custom_sharepoint_files_month` : 300 (couvre un import initial conséquent + le flux mensuel de nouveaux documents)
- `allow_*_overage` : `true` partout — cohérent avec "qu'il paye s'il veut plus" plutôt qu'un blocage sec, avec les tarifs de dépassement déjà posés par défaut (5 $/1000 pages, 3 $/100 questions, 4 $/100 fichiers SharePoint — ajustables).

## 6. Ce qu'il reste à faire avant la démo à Thierry

1. **Tester la suite complète en environnement local** (Docker + Postgres + Redis) — je n'ai pu exécuter que les tests qui ne dépendent d'aucun service externe depuis cette session (77 tests passent, dont les 8 nouveaux). Les tests qui touchent réellement la base (isolation DCE, upload knowledge, chat assistant, etc.) n'ont pas pu tourner ici : ce poste de travail n'a pas d'accès réseau direct vers le pooler Postgres de Supabase ni de Redis local. Lance `cd apps/api && pytest tests/ -v` depuis ton terminal habituel avant tout déploiement — c'est la vérification qui manque pour être sûr à 100 %.
2. **Interface d'administration SharePoint côté client** : les routes API existent, mais il n'y a pas encore d'écran dans `apps/web` pour que Thierry (ou son équipe) saisisse lui-même son `client_id`/`client_secret`/URL de site. À faire si tu veux qu'il s'auto-connecte plutôt que de passer par toi.
3. **Purge/archivage des vecteurs de dossiers anciens** : c'est le vrai levier long terme contre la dérive du coût Supabase (portefeuille, pas par tenant — voir §3). Pas encore fait, à prioriser dès que le volume de tenants augmente.
4. **Azure AD App Registration côté Thierry** : c'est son IT qui doit la créer (permissions `Sites.Selected` ou `Sites.Read.All`/`Files.Read.All`, lecture seule) — un point à mettre dans ta prochaine étude avec eux, ça fait partie des "pièces" à demander en plus du RFP et de la réponse technique.
5. **Calibrer les tarifs de dépassement en euros réels** une fois Stripe/facturation manuelle branchée sur ces nouveaux compteurs — pour l'instant les prix de dépassement sont posés (5 $/1000 pages etc.) mais rien ne les facture encore automatiquement, exactement comme le dépassement de dossiers existant aujourd'hui (`allow_overage`) n'a pas encore de facturation Stripe automatique câblée non plus.

## 7. Fichiers modifiés / créés

```
supabase/migrations/00032_volume_quotas_ocr_and_questions.sql   (nouveau)
supabase/migrations/00033_sharepoint_connectors.sql              (nouveau)
apps/api/app/models/entities.py                                  (colonnes + 3 nouvelles tables ORM)
apps/api/app/services/ocr_service.py                             (triage local → Azure)
apps/api/app/services/ocr_cost_service.py                        (nouveau)
apps/api/app/services/billing_service.py                         (3 nouvelles méthodes de quota)
apps/api/app/services/sharepoint_service.py                      (nouveau, Microsoft Graph)
apps/api/app/api/sharepoint.py                                   (nouveau, 4 routes)
apps/api/app/api/dce.py                                          (dédup par empreinte)
apps/api/app/api/projects.py                                     (quota questions sur /ask)
apps/api/app/workers/tasks.py                                    (quotas pages/OCR dans parse_dce_task, tâches SharePoint)
apps/api/app/core/celery_app.py                                  (sync SharePoint toutes les 6h)
apps/api/app/main.py                                              (route SharePoint enregistrée)
apps/api/requirements.txt                                        (+ reportlab, tests uniquement)
apps/api/tests/test_ocr_triage_reduces_azure_cost.py             (nouveau, 3 tests)
apps/api/tests/test_sharepoint_connector_filtering_and_delta.py  (nouveau, 5 tests)
```

Rien n'a été committé dans git — les fichiers sont modifiés sur le disque, prêts à être relus et committés quand tu veux.
