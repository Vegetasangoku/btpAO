# Plan d'Implémentation — P8 : Refonte Navigation, Wizard 5 Étapes & Identité Visuelle

**Date** : Août 2026  
**Branche / Projet** : btpAO — Refonte P8  
**Objectif** : Refonte complète de l'expérience utilisateur btpAO avec une arborescence à 6 entrées sans jargon interne, un wizard 5 étapes guidé, l'intégration du design system Direction 1 (Manrope + IBM Plex Sans + JetBrains Mono) avec support Dark/Light mode et sélecteur de thème dans les Paramètres.

---

## 1. Architecture des Menus & Arborescence Client (6 Entrées)

```
┌─────────────────────────────────────────────────────────────┐
│  btpAO — Menu Principal                                     │
├─────────────────────────────────────────────────────────────┤
│  📊 Tableau de bord (/dashboard)                            │
│     Vue d'ensemble, dossiers en cours, alertes délais        │
│                                                             │
│  ⚡ Répondre à un appel d'offres (/dashboard/wizard)         │
│     Lancement du wizard guidé pas-à-pas                      │
│                                                             │
│  📁 Mes appels d'offres (/dashboard/projects)               │
│     Liste, historique, filtres et résultats d'attribution    │
│                                                             │
│  🏢 Mon entreprise (/dashboard/company)                     │
│     1 seul endroit unifié avec 3 sous-onglets :             │
│     ├── Savoir-faire & Documents (ex-RAG : fiches, certifs) │
│     ├── Équipe & Conducteurs (gestion des rôles RBAC)       │
│     └── Sites & Références web (adresses entreprises)       │
│                                                             │
│  🎨 Modèles & Mise en forme (/dashboard/branding)           │
│     Template Word (.docx), charte graphique, logo, couleurs │
│                                                             │
│  ⚙️ Paramètres (/dashboard/settings)                         │
│     Sélecteur de Thème (Clair / Sombre / Système),           │
│     Règles économiques (taux, marges), abonnement/quotas     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Identité Visuelle & Tokens (Dark Mode & Light Mode)

### Typographies (Google Fonts)
- **Titres & Chiffres Clés** : `Manrope` (SemiBold 600, Bold 700, ExtraBold 800)
- **Corps de texte & Formulaires** : `IBM Plex Sans` (Regular 400, Medium 500, SemiBold 600)
- **Données techniques, SIRET, devises** : `JetBrains Mono`

### Tokens de Couleurs

#### Mode Sombre (Dark Mode)
- **Fond principal** : `#0C0F17` (Graphite Nuit minéral)
- **Cartes & Conteneurs** : `#131823` (Ardoise dense)
- **Bordures** : `#1E2638` (Lignes fines 1px nettes)
- **Accent Métier Principal** : `#D97706` / `#F59E0B` (Ambre architectural / Ocre BTP)
- **Accent d'Action Secondaire** : `#2563EB` (Bleu technique sobre)
- **Validation / Succès** : `#059669` (Émeraude minéral)
- **Texte Titres** : `#F9FAFB` (Blanc pur)
- **Texte Corps** : `#9CA3AF` (Gris technique lisible)

#### Mode Clair (Light Mode — Sur-mesure, adapté aux contrastes)
- **Fond principal** : `#F8FAFC` (Blanc minéral cassé / Calcaire doux)
- **Cartes & Conteneurs** : `#FFFFFF` (Surface blanche pure)
- **Bordures** : `#E2E8F0` / `#CBD5E1` (Lignes nettes et fines)
- **Accent Métier Principal** : `#B45309` / `#92400E` (Ocre chaud profond, contrasté)
- **Accent d'Action Secondaire** : `#1D4ED8` (Bleu cobalt technique précis)
- **Validation / Succès** : `#047857` (Vert forêt minéral)
- **Texte Titres** : `#0F172A` (Ardoise sombre dense)
- **Texte Corps** : `#475569` (Gris technique équilibré)

### Géométrie UI & Finitions
- **Boutons & Badges** : `rounded-lg` (8px)
- **Cartes & Panneaux** : `rounded-xl` (12px)
- **Ombres** : Suppression intégrale des halos `shadow-glow` artificiels, ombres portées discrètes `shadow-sm` / `shadow-md`.

---

## 3. Wizard de Réponse à un Appel d'Offres (5 Étapes)

Le wizard est un tunnel linéaire guidé :
1. **Étape 1 : Importer l'appel d'offres** — Glisser-déposer des pièces de consultation (CCTP, RC, DPGF en PDF/Word/Zip) avec OCR automatique.
2. **Étape 2 : Vérifier les informations extraites** — Formulaire pré-rempli par l'IA (Acheteur, Référence, Lot, Date limite, Critères de notation) avec ajustements en 1 clic.
3. **Étape 3 : Rédiger le mémoire technique** — Génération des chapitres fondée sur le savoir-faire validé et l'historique, avec citations de sources et marqueurs explicites `[À COMPLÉTER]` sans aucune invention.
4. **Étape 4 : Compléter les pièces administratives** — Formulaires types DC1, DC2, DUME ou formulaires régionaux MEA (Arabie Saoudite GTPL, Qatar, etc.) sans hallucination.
5. **Étape 5 : Exporter et finaliser** — Modèle Word (.docx) déduit par défaut de l'historique, sélecteur de langue (Français, Anglais, Arabe RTL OpenXML), téléchargement immédiat Word et PDF.

> [!NOTE]
> **Go/No-Go & Planning Chantier** :
> - L'analyse Go/No-Go reste consultable et recalculable dès l'amont ou à tout moment dans la fiche dossier (*Mes appels d'offres* -> `/projects/[id]`).
> - Le Planning Chantier (Gantt & Phasage) reste un livrable transversal éditable à tout moment dans la fiche dossier sans bloquer le tunnel des 5 étapes.

---

## 4. Plan de Déploiement par Fichiers

1. **Tokens CSS & Polices** :
   - `apps/web/src/app/globals.css` : Import des polices Google Fonts, variables CSS Dark/Light, refonte des classes.
   - `apps/web/tailwind.config.ts` : Polices Manrope, IBM Plex Sans, JetBrains Mono, couleurs BTP.
   - `apps/web/src/components/theme-provider.tsx` : Contexte React pour la gestion du thème Clair / Sombre / Système.
   - `apps/web/src/app/layout.tsx` : Intégration du `ThemeProvider`.

2. **Navigation & Barre Latérale** :
   - `apps/web/src/components/layout/user-sidebar.tsx` : Nouvelle barre latérale 6 entrées, indicateur actif, design épuré sans glow.
   - `apps/web/src/app/dashboard/layout.tsx` : Layout principal avec gestion des thèmes.

3. **Pages de l'Espace Utilisateur** :
   - `apps/web/src/app/dashboard/page.tsx` : Vrai tableau de bord d'accueil exécutif avec KPI, alertes délais et accès rapide.
   - `apps/web/src/app/dashboard/wizard/page.tsx` : Parcours complet du Wizard 5 étapes.
   - `apps/web/src/app/dashboard/company/page.tsx` : Page unifiée *Mon entreprise* (Savoir-faire, Équipe RBAC, Références web).
   - `apps/web/src/app/dashboard/branding/page.tsx` : Page dédiée *Modèles & mise en forme* (Template Word auto-déduit, Logo, Couleurs).
   - `apps/web/src/app/dashboard/settings/page.tsx` : Paramètres avec sélecteur de thème Clair/Sombre/Système, règles économiques, abonnement/quotas, RGPD.
   - `apps/web/src/app/projects/[id]/page.tsx` : Vue d'ensemble du dossier avec onglets transversaux (Go/No-Go, Planning, Mémoire, Pièces Admin, Exports).
