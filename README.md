# btpAO — SaaS B2B Multi-Tenant : Générateur Automatique de Mémoires Techniques BTP

> **Moteur IA Générative** Claude 3.5 Sonnet + RAG pgvector | **Stack** : FastAPI · Next.js 14 · Supabase RLS · Celery/Redis · MinIO · LibreOffice

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js 14 (Frontend)                 │
│  App Router · Tailwind · Shadcn UI · Tiptap WYSIWYG     │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────────┐
│               FastAPI Backend (Python 3.11)             │
│  JWT Auth · RLS Guard · OCR · RAG · LLM · Gantt        │
└────┬──────────┬───────────────┬─────────┬──────────────┘
     │          │               │         │
  Supabase  Celery/Redis     MinIO S3   LibreOffice
  Postgres   Workers        Stockage    PDF Export
  pgvector   Async tasks    Tenant ISO  Headless
```

---

## 🚀 Démarrage Rapide

### Prérequis
- Docker & Docker Compose v2
- Node.js 20+
- Python 3.11+

### 1. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Éditez `.env` et renseignez :
```env
SUPABASE_URL=https://ykdbjsvwzxeftlddubgy.supabase.co
SUPABASE_ANON_KEY=<votre_anon_key>
SUPABASE_SERVICE_ROLE_KEY=<votre_service_role_key>
SUPABASE_JWT_SECRET=<votre_jwt_secret>
DATABASE_URL=postgresql://postgres.ykdbjsvwzxeftlddubgy:<password>@aws-1-eu-west-3.pooler.supabase.com:6543/postgres

ANTHROPIC_API_KEY=sk-ant-...        # Claude 3.5 Sonnet
MISTRAL_API_KEY=...                 # Fallback LLM
OPENAI_API_KEY=sk-...               # Embeddings text-embedding-3-small

# Azure OCR (optionnel — fallback pdfplumber si absent)
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://...cognitiveservices.azure.com/
AZURE_DOC_INTELLIGENCE_KEY=...
```

### 2. Lancer toute la stack Docker

```bash
docker compose up -d
```

Services démarrés :
| Service | URL |
|---------|-----|
| Frontend Next.js | http://localhost:3000 |
| FastAPI Backend | http://localhost:8000 |
| Swagger/OpenAPI | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 (minioadmin/minioadmin) |
| Redis | localhost:6379 |

### 3. Développement local (sans Docker)

**Backend :**
```bash
cd apps/api
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Celery Worker :**
```bash
cd apps/api
celery -A app.core.celery_app worker --loglevel=info
```

**Frontend :**
```bash
cd apps/web
npm install
npm run dev
```

---

## 🔄 Pipeline de Génération (5 étapes)

```
1. INGESTION DCE          → Upload CCTP/RC PDF → OCR Azure/pdfplumber → Chunking sémantique BTP
                                                → Embeddings pgvector (1536 dims)
                                                → Extraction grille critères RC automatique

2. DÉCISIONS CONDUCTEUR   → Délais contractuels, matériel lourd (grues, engins)
                                                → Encadrement qualifié (CVs cadres)
                                                → Phasage travaux, RSE/déchets, PPSPS

3. GÉNÉRATION IA RAG      → RAG pgvector (match_dce_chunks + match_company_knowledge)
                                                → Claude 3.5 Sonnet (fallback Mistral Large)
                                                → 10 sections : présentation, références, moyens,
                                                  méthodologie, qualité, sécurité, RSE, Gantt…

4. VISUELS HD             → Gantt 300 DPI Matplotlib (phases, jalons, chemin critique)
                                                → Organigramme PNG encadrement chantier

5. EXPORT WORD & PDF      → Injection docxtpl Jinja2 + InlineImage (Gantt + Organigramme)
                                                → LibreOffice headless → PDF pixel-perfect
                                                → Stockage MinIO /tenants/{id}/exports/
```

---

## 🏢 Multi-Tenant & Sécurité

- **RLS Supabase** : 13 tables avec Row Level Security stricte par `tenant_id`
- **JWT Guard** : Vérification `app_metadata.tenant_id` à chaque requête API
- **Stockage isolé** : Chemin S3 `/tenants/{tenant_id}/...` — impossibilité d'accès cross-tenant
- **Fonctions RPC** : `match_dce_chunks` et `match_company_knowledge` filtrées par `tenant_id`

---

## 🧪 Tests

```bash
cd apps/api
python3 -m pytest tests/ -v
```

Couverture :
- ✅ Chunking sémantique BTP (articles, CCTP)
- ✅ Embeddings 1536 dims normalisés
- ✅ Gantt Matplotlib 300 DPI
- ✅ Organigramme PNG
- ✅ Exporter docx (python-docx)

---

## 📁 Structure du Projet

```
btpAO/
├── apps/
│   ├── api/                    # FastAPI Backend
│   │   ├── app/
│   │   │   ├── api/            # Routes REST (auth, projects, dce, generate, visuals, export…)
│   │   │   ├── core/           # Config, Security, Storage, Celery
│   │   │   ├── models/         # Pydantic Schemas
│   │   │   ├── services/       # OCR, Chunking, Embedding, RAG, LLM, Gantt, Diagram, Export
│   │   │   └── workers/        # Celery Tasks
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── web/                    # Next.js 14 Frontend
│       ├── src/
│       │   ├── app/            # Pages (Dashboard, Projects, DCE, Editor, Visuals, Export…)
│       │   ├── components/     # Layout, Editor Tiptap, DCE Uploader, Gantt/Organigramme Preview
│       │   └── lib/            # API Client, Types, Supabase Client
│       └── Dockerfile
├── supabase/
│   └── migrations/
│       ├── 00001_init_multi_tenant_schema.sql   # 13 tables + RLS + pgvector indexes
│       └── 00002_seed_demo_data.sql             # Démo : EiffaBTP + Groupe Scolaire HQE
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🔧 Variables d'Environnement

| Variable | Description | Requis |
|----------|-------------|--------|
| `SUPABASE_URL` | URL du projet Supabase | ✅ |
| `SUPABASE_ANON_KEY` | Clé publique Supabase | ✅ |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé service role (backend only) | ✅ |
| `SUPABASE_JWT_SECRET` | Secret JWT pour vérification tokens | ✅ |
| `DATABASE_URL` | PostgreSQL direct connection | ✅ |
| `ANTHROPIC_API_KEY` | Claude 3.5 Sonnet | Recommandé |
| `MISTRAL_API_KEY` | Mistral Large (fallback) | Recommandé |
| `OPENAI_API_KEY` | Embeddings text-embedding-3-small | Recommandé |
| `AZURE_DOC_INTELLIGENCE_*` | OCR premium Azure | Optionnel |
| `REDIS_URL` | Broker Celery | Auto (Docker) |
| `S3_*` | MinIO / AWS S3 | Auto (Docker) |

---

## 📄 Licence

Propriétaire — Organisation **Appel offre Charb** — Supabase project `ykdbjsvwzxeftlddubgy`
# btpAO
