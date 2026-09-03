"""
Application Settings & Environment Configuration — Pydantic v2 compatible
"""
from typing import List, Optional
import litellm
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 29/08 (2e confirmation redemarrage) : au moins 5 sites d'appel litellm.completion() dans ce
# depot (llm_generator.py, dce.py, projects.py, company_bootstrap.py/_service.py) codent en dur
# un `temperature=`. Certains modeles (ex. claude-opus-5, decouvert en testant une vraie
# generation de section) rejettent toute valeur de temperature autre que 1.0 avec
# litellm.UnsupportedParamsError -- sans repli fournisseur configure, cela fait echouer
# SILENCIEUSEMENT l'appel LLM primaire et retombe sur le moteur de gabarits (aucune erreur
# visible cote utilisateur). drop_params=True est le mecanisme officiel LiteLLM (suggere par le
# message d'erreur lui-meme) qui retire uniquement les parametres non supportes par le modele
# cible avant l'appel. Pose ICI (app.core.config, importe en tout premier par main.py ET
# celery_app.py) plutot que dans un seul service, pour garantir qu'il est actif AVANT le tout
# premier appel litellm.completion(), quel que soit le fichier/process qui l'emet en premier.
litellm.drop_params = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    # App General
    APP_NAME: str = "btpAO - SaaS B2B Mémoires Techniques BTP"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    API_V1_PREFIX: str = "/api"
    SECRET_KEY: str = Field(default="super-secret-btp-jwt-key-change-in-prod-123456789")
    # Origines autorisees pour les requetes CORS du frontend. Modifiable sans
    # redeploiement de code via la variable d'environnement CORS_ORIGINS (format
    # JSON, ex. '["https://app.btpao.fr","https://www.btpao.fr"]') -- voir main.py,
    # qui lit desormais settings.CORS_ORIGINS au lieu d'une liste codee en dur.
    # Les origines localhost restent presentes par defaut pour ne pas casser le dev local.
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "http://localhost:8000",
        "https://app.btpao.fr"
    ]

    # Supabase (Org: Appel offre Charb / Project: boyloyvoy@gmail.com's ProjectBTP)
    SUPABASE_URL: str = Field(
        default="https://ykdbjsvwzxeftlddubgy.supabase.co"
    )
    SUPABASE_ANON_KEY: str = Field(
        default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlrZGJqc3Z3enhlZnRsZGR1Ymd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxNDE0MTQsImV4cCI6MjEwMjcxNzQxNH0.aeE6paE278N4ZFamvfpIaiIJurzWKRT4hpYXfzToQM8"
    )
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = Field(default=None)
    SUPABASE_JWT_SECRET: Optional[str] = Field(default=None)
    DATABASE_URL: Optional[str] = Field(
        default="postgresql://postgres.ykdbjsvwzxeftlddubgy:password@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"
    )

    # Storage S3 / MinIO
    S3_ENDPOINT_URL: Optional[str] = Field(default="http://localhost:9000")
    S3_ACCESS_KEY: str = Field(default="minioadmin")
    S3_SECRET_KEY: str = Field(default="minioadmin")
    S3_BUCKET_NAME: str = Field(default="btp-storage")
    S3_REGION: str = Field(default="eu-west-3")
    S3_USE_SSL: bool = Field(default=False)

    # Redis & Celery
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")

    # LLM & AI (LiteLLM abstraction)
    DEFAULT_LLM_MODEL: str = Field(default="anthropic/claude-sonnet-5")
    FALLBACK_LLM_MODEL: str = Field(default="mistral/mistral-large-3-25-12")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    MISTRAL_API_KEY: Optional[str] = Field(default=None)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None)

    # Azure Document Intelligence / OCR
    AZURE_DOC_INTELLIGENCE_ENDPOINT: Optional[str] = Field(default=None)
    AZURE_DOC_INTELLIGENCE_KEY: Optional[str] = Field(default=None)

    # Stripe Billing
    STRIPE_SECRET_KEY: Optional[str] = Field(default=None)
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(default=None)

    # Web Search (Serper / Brave Search API)
    SERPER_API_KEY: Optional[str] = Field(default=None)
    BRAVE_SEARCH_API_KEY: Optional[str] = Field(default=None)
    WEB_SEARCH_PROVIDER: str = Field(default="serper")  # 'serper', 'brave', 'auto' 

    # Demo & Mock Settings
    ALLOW_MOCK_FALLBACK: bool = Field(default=False)
    DEFAULT_DEMO_TENANT_ID: str = "11111111-1111-1111-1111-111111111111"
    DEFAULT_DEMO_USER_ID: str = "22222222-2222-2222-2222-222222222222"
    DISABLE_WHERE_CLAUSE_FOR_RLS_TEST: bool = Field(default=False)

    # RGPD Cron / Automation
    CRON_PURGE_SECRET: Optional[str] = Field(default=None)


settings = Settings()


