"""
Hybrid Billing & Quota Enforcement Service.
Handles Self-Service Stripe subscriptions, Enterprise manual quotas, and consumption tracking.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import SubscriptionPlan, TenantSubscription, TenantUsageCounter, LlmCatalogModel, LlmUsageLog
from app.services.llm_reference_catalog import price_for as reference_price_for


# Repli de tarification — voir BillingService.estimate_llm_cost_usd.
# Deux niveaux :
#   1. le socle de référence (llm_reference_catalog), relevé sur les pages tarifaires
#      officielles des fournisseurs et daté, qui couvre chaque identifiant exact ;
#   2. la table par famille ci-dessous, qui rattrape les chaînes de modèle héritées
#      ou datées encore présentes en base (journaux d'usage antérieurs) pour qu'un coût
#      estimé ne reste jamais silencieusement NULL.
# L'ordre compte : la première famille reconnue dans la chaîne gagne, du plus précis
# au plus général.
_FALLBACK_MODEL_PRICING_USD_PER_MILLION = [
    # Génération courante (miroir du socle de référence, pour les identifiants abrégés)
    ("claude-fable-5", 10.00, 50.00),
    ("claude-opus-5", 5.00, 25.00),
    ("claude-sonnet-5", 2.00, 10.00),
    ("claude-haiku-4-5", 1.00, 5.00),
    ("gpt-5.6-luna", 0.10, 0.60),
    ("gpt-5.6-terra", 1.00, 6.00),
    ("gpt-5.6-sol", 2.00, 10.00),
    ("gpt-5.3-codex", 1.75, 14.00),
    ("mistral-large-3", 0.50, 1.50),
    ("mistral-medium-3", 1.50, 7.50),
    ("mistral-small-4", 0.15, 0.60),
    ("ministral-3", 0.15, 0.15),
    ("gemini-3.8", 0.75, 3.75),
    ("gemini-3.5-flash-lite", 0.30, 2.50),
    ("gemini-2.5-pro", 1.25, 10.00),
    ("deepseek-v4-pro", 1.32, 3.96),
    ("deepseek-v4", 0.44, 1.32),
    # Générations retirées du catalogue mais encore présentes dans d'anciens journaux :
    # les tarifs ci-dessous ne sont conservés que pour rendre lisible l'historique de
    # consommation, jamais pour router un appel.
    ("claude-3-5-sonnet", 3.00, 15.00),
    ("claude-3-5-haiku", 0.80, 4.00),
    ("claude-3-opus", 15.00, 75.00),
    ("gpt-4o-mini", 0.15, 0.60),
    ("gpt-4o", 2.50, 10.00),
]


def infer_provider_id_from_model_string(model_string: Optional[str]) -> Optional[str]:
    """Deduit un provider_id lisible depuis une chaine de modele codee en dur, pour les points
    d'appel qui n'utilisent pas model_routing_service.get_credentials_for_model (donc n'ont pas
    de provider_id resolu) -- usage uniquement informatif pour le journal llm_usage_logs,
    n'affecte aucun routage reel (02/09)."""
    if not model_string:
        return None
    lower = model_string.lower()
    if "anthropic" in lower or "claude" in lower:
        return "anthropic"
    if "openai" in lower or "gpt" in lower:
        return "openai"
    if "mistral" in lower or "ministral" in lower:
        return "mistral"
    if "gemini" in lower or "google" in lower:
        return "gemini"
    if "deepseek" in lower:
        return "deepseek"
    return model_string.split("/")[0] if "/" in model_string else "unknown"


class BillingService:
    @staticmethod
    def get_current_period_bounds() -> tuple[datetime, datetime]:
        """Returns the start and end of the current calendar month in UTC."""
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        else:
            end = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        return start, end

    async def get_or_create_usage(self, tenant_id: uuid.UUID, db: AsyncSession) -> TenantUsageCounter:
        """Fetches or creates the usage counter for the current month."""
        start, end = self.get_current_period_bounds()

        stmt = (
            select(TenantUsageCounter)
            .where(
                TenantUsageCounter.tenant_id == tenant_id,
                TenantUsageCounter.period_start >= start,
                TenantUsageCounter.period_start < end,
            )
            .order_by(TenantUsageCounter.period_start.desc())
        )
        res = await db.execute(stmt)
        usage = res.scalars().first()

        if not usage:
            usage = TenantUsageCounter(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                period_start=start,
                period_end=end,
                dossiers_generated=0,
                sections_generated=0,
                exports_count=0,
                web_searches_count=0,
                pages_ingested=0,
                questions_asked=0,
                ocr_pages_azure=0,
                ocr_pages_local=0,
                sharepoint_files_indexed=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(usage)
            await db.flush()

        return usage


    async def get_tenant_subscription(self, tenant_id: uuid.UUID, db: AsyncSession) -> Optional[TenantSubscription]:
        """Fetches active subscription record for tenant."""
        stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def check_and_enforce_quota(
        self,
        tenant_id_str: str,
        action: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Enforces tenant subscription status and monthly dossier quotas before generation/export.
        Raises 402 Payment Required if subscription is suspended or quota exceeded without overage.
        """
        try:
            t_uuid = uuid.UUID(tenant_id_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

        sub = await self.get_tenant_subscription(t_uuid, db)
        if not sub:
            # Default to active starter trial if no record exists yet
            return {"status": "active", "quota": 3, "used": 0, "allow_overage": True}

        if sub.status != "active":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Abonnement inactif ou suspendu (statut: {sub.status}). Veuillez régulariser votre compte pour générer des dossiers.",
            )

        # Determine effective quota
        if sub.custom_quota_dossiers is not None:
            effective_quota = sub.custom_quota_dossiers
        else:
            plan_stmt = select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id)
            plan_res = await db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()
            effective_quota = plan.included_dossiers_month if plan else 3

        usage = await self.get_or_create_usage(t_uuid, db)

        # Check quota limit
        if usage.dossiers_generated >= effective_quota and not sub.allow_overage:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Quota mensuel de dossiers atteint ({usage.dossiers_generated}/{effective_quota}). "
                    f"Le dépassement n'est pas activé sur ce compte. Veuillez contacter votre administrateur ou passer au forfait supérieur."
                ),
            )

        return {
            "status": sub.status,
            "billing_mode": sub.billing_mode,
            "quota": effective_quota,
            "used": usage.dossiers_generated,
            "sections_generated": usage.sections_generated,
            "exports_count": usage.exports_count,
            "allow_overage": sub.allow_overage,
        }

    async def increment_usage(
        self,
        tenant_id_str: str,
        action: str,
        db: AsyncSession,
        amount: int = 1,
    ):
        """Increments usage counter for current month. `amount` lets a single call
        register several units at once (ex: 03/09, une ingestion de document ajoute
        plusieurs pages d'un coup -- voir check_and_enforce_page_quota)."""
        try:
            t_uuid = uuid.UUID(tenant_id_str)
        except ValueError:
            return

        usage = await self.get_or_create_usage(t_uuid, db)
        if action == "dossier":
            usage.dossiers_generated += amount
        elif action == "section":
            usage.sections_generated += amount
        elif action == "export":
            usage.exports_count += amount
        elif action == "page":
            usage.pages_ingested += amount
        elif action == "question":
            usage.questions_asked += amount
        elif action == "ocr_page_azure":
            usage.ocr_pages_azure += amount
        elif action == "ocr_page_local":
            usage.ocr_pages_local += amount
        elif action == "sharepoint_file":
            usage.sharepoint_files_indexed += amount
        usage.updated_at = datetime.utcnow()
        await db.flush()

    async def get_effective_cost_cap_usd(self, tenant_id: uuid.UUID, db: AsyncSession) -> Optional[float]:
        """
        Plafond mensuel de cout LLM effectif pour ce tenant, en USD reels estimes (voir
        llm_usage_logs.estimated_cost_usd) : surcharge par-tenant
        (tenant_subscriptions.custom_llm_cost_cap_usd) si definie, sinon valeur par defaut du
        forfait (subscription_plans.monthly_llm_cost_cap_usd), sinon None (aucun plafond
        configure -- non applique tant qu'un admin n'a pas choisi une valeur). Miroir exact du
        mecanisme deja en place pour custom_quota_dossiers / included_dossiers_month (02/09).
        """
        sub = await self.get_tenant_subscription(tenant_id, db)
        if sub and sub.custom_llm_cost_cap_usd is not None:
            return float(sub.custom_llm_cost_cap_usd)

        plan_id = sub.plan_id if sub else "starter"
        plan_stmt = select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        plan_res = await db.execute(plan_stmt)
        plan = plan_res.scalar_one_or_none()
        if plan and plan.monthly_llm_cost_cap_usd is not None:
            return float(plan.monthly_llm_cost_cap_usd)
        return None

    async def get_tenant_current_month_spend_usd(self, tenant_id: uuid.UUID, db: AsyncSession) -> float:
        """Somme de llm_usage_logs.estimated_cost_usd pour CE tenant depuis le 1er du mois en
        cours (UTC), tous points d'appel LLM reels confondus. Ne leve jamais d'exception (02/09,
        meme precaution que le plafond provider-level existant dans
        model_routing_service.get_current_month_spend_usd)."""
        try:
            month_start, _ = self.get_current_period_bounds()
            stmt = select(func.coalesce(func.sum(LlmUsageLog.estimated_cost_usd), 0)).where(
                LlmUsageLog.tenant_id == tenant_id,
                LlmUsageLog.created_at >= month_start,
            )
            res = await db.execute(stmt)
            return float(res.scalar() or 0.0)
        except Exception as e:
            print(f"[BillingService] get_tenant_current_month_spend_usd notice: {e} -- 0.0 par defaut.")
            return 0.0

    async def is_cost_cap_exceeded(self, tenant_id: uuid.UUID, db: AsyncSession) -> tuple[bool, Optional[float], float]:
        """Retourne (depasse, plafond, depense_actuelle). Ne leve jamais d'exception -- a
        utiliser directement par les points d'appel qui doivent degrader en repli plutot que de
        lever une erreur HTTP (ex. extraction de criteres, bootstrap entreprise)."""
        cap = await self.get_effective_cost_cap_usd(tenant_id, db)
        if cap is None or cap <= 0:
            return False, cap, 0.0
        spend = await self.get_tenant_current_month_spend_usd(tenant_id, db)
        return spend >= cap, cap, spend

    async def check_and_enforce_cost_cap(self, tenant_id_str: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Bloque (402) tout nouvel appel LLM facturable si le plafond mensuel de cout reel
        configure pour ce tenant (voir get_effective_cost_cap_usd) est atteint ou depasse.
        Reponse directe a une demande explicite de l'utilisateur (02/09) : garantir que le cout
        LLM reel consomme par un client ne depasse jamais ce que l'operateur tolere au regard du
        prix de son forfait (protection de marge), de facon parametrable par forfait ET par
        tenant -- jamais code en dur. Miroir exact de check_and_enforce_quota (meme convention
        d'appel, meme code d'erreur 402) mais sur le cout reel plutot qu'un nombre de dossiers.
        A utiliser dans les points d'appel synchrones cote utilisateur (chat, analyse) ou une
        erreur claire est acceptable ; utiliser is_cost_cap_exceeded pour les points d'appel qui
        doivent degrader silencieusement vers un repli existant a la place.
        """
        try:
            t_uuid = uuid.UUID(tenant_id_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant UUID")

        exceeded, cap, spend = await self.is_cost_cap_exceeded(t_uuid, db)
        if exceeded:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Plafond mensuel de cout IA atteint ({spend:.2f} $ US / {cap:.2f} $ US configures). "
                    f"Ce plafond protege la marge de votre forfait -- contactez votre administrateur pour "
                    f"l'ajuster si besoin, ou reessayez le mois prochain."
                ),
            )
        return {"cost_cap_usd": cap, "current_spend_usd": spend, "cap_enforced": cap is not None}

    @staticmethod
    async def estimate_llm_cost_usd(
        db: AsyncSession,
        model_string: Optional[str],
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
    ) -> Optional[float]:
        """
        Estime le cout USD d'un appel LLM a partir des tokens reellement consommes. Cherche
        d'abord le tarif dans llm_catalog_models (external_id == model_string) ; si absent
        (mismatch de nommage connu, voir _FALLBACK_MODEL_PRICING_USD_PER_MILLION ci-dessus),
        retombe sur une table de tarifs statique par famille de modele plutot que de laisser
        estimated_cost_usd silencieusement NULL. Retourne None seulement si le modele est
        vraiment inconnu des deux sources (02/09).
        """
        if not model_string or (not prompt_tokens and not completion_tokens):
            return None
        prompt_t = prompt_tokens or 0
        completion_t = completion_tokens or 0

        prompt_price = None
        completion_price = None
        try:
            catalog_res = await db.execute(
                select(LlmCatalogModel).where(LlmCatalogModel.external_id == model_string)
            )
            catalog_row = catalog_res.scalar_one_or_none()
            if (
                catalog_row
                and catalog_row.pricing_prompt_per_million is not None
                and catalog_row.pricing_completion_per_million is not None
            ):
                prompt_price = float(catalog_row.pricing_prompt_per_million)
                completion_price = float(catalog_row.pricing_completion_per_million)
        except Exception:
            pass

        if prompt_price is None or completion_price is None:
            reference = reference_price_for(model_string)
            if reference is not None:
                prompt_price, completion_price = reference

        if prompt_price is None or completion_price is None:
            lower_model = model_string.lower()
            for needle, p_price, c_price in _FALLBACK_MODEL_PRICING_USD_PER_MILLION:
                if needle in lower_model:
                    prompt_price, completion_price = p_price, c_price
                    break

        if prompt_price is None or completion_price is None:
            return None
        return (prompt_t / 1_000_000.0) * prompt_price + (completion_t / 1_000_000.0) * completion_price

    @staticmethod
    async def log_llm_usage(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        project_id: Optional[uuid.UUID],
        provider_id: Optional[str],
        model_string: Optional[str],
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        was_fallback: bool = False,
    ) -> None:
        """
        Journalise un appel LLM reel dans llm_usage_logs (tokens + cout estime avec repli de
        tarification, voir estimate_llm_cost_usd). Point d'entree partage utilise par TOUS les
        points d'appel LLM reels de l'application (02/09 -- avant cette factorisation, seule la
        generation de sections dans workers/tasks.py journalisait quoi que ce soit, et meme ce
        point d'appel echouait silencieusement -- voir correctif d'import manquant du meme jour
        -- ce qui explique les 0 lignes constatees en base malgre un usage LLM reel quotidien).
        Ne doit jamais faire echouer l'appelant : toute erreur est absorbee silencieusement.
        """
        try:
            estimated_cost = await BillingService.estimate_llm_cost_usd(
                db, model_string, prompt_tokens, completion_tokens
            )
            db.add(LlmUsageLog(
                tenant_id=tenant_id,
                project_id=project_id,
                provider_id=provider_id,
                model_string=model_string or "unknown",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                was_fallback=was_fallback,
            ))
        except Exception as e:
            print(f"[BillingService] log_llm_usage notice: {e} -- generation non affectee.")

    async def check_and_enforce_knowledge_quota(
        self,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Enforces tenant document quota in knowledge base:
        - starter: 20 documents max
        - pro: 100 documents max
        - enterprise: unlimited
        Raises 403 FORBIDDEN if quota is reached.
        """
        from app.models.entities import CompanyAsset, Tenant
        from sqlalchemy import func

        # 1. Determine tenant plan
        sub = await self.get_tenant_subscription(tenant_id, db)
        plan_id = sub.plan_id if sub else "starter"

        if not sub:
            t_stmt = select(Tenant).where(Tenant.id == tenant_id)
            t_res = await db.execute(t_stmt)
            t = t_res.scalar_one_or_none()
            if t and t.plan:
                plan_id = t.plan

        plan_id = plan_id.lower()
        quotas = {
            "starter": 20,
            "pro": 100,
            "enterprise": None,  # Unlimited
        }
        max_allowed = quotas.get(plan_id, 20)

        # 2. Count existing assets for this tenant
        count_stmt = select(func.count(CompanyAsset.id)).where(CompanyAsset.tenant_id == tenant_id)
        count_res = await db.execute(count_stmt)
        current_count = count_res.scalar() or 0

        if max_allowed is not None and current_count >= max_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Quota de documents atteint pour votre plan {plan_id.upper()} ({current_count}/{max_allowed} max). "
                    f"Mettez à niveau votre forfait vers le plan supérieur pour indexer plus de documents dans votre base de connaissances."
                ),
            )

        return {
            "plan": plan_id,
            "current_count": current_count,
            "max_allowed": max_allowed,
        }

    async def _effective_int_limit(
        self,
        tenant_id: uuid.UUID,
        db: AsyncSession,
        custom_field: str,
        plan_field: str,
    ) -> Optional[int]:
        """Resout un plafond entier (pages/questions/fichiers SharePoint) : surcharge
        tenant si definie, sinon valeur du forfait, sinon None (illimite). Miroir du
        motif deja utilise pour get_effective_cost_cap_usd, generalise ici pour eviter
        de dupliquer trois fois la meme resolution tenant -> forfait."""
        sub = await self.get_tenant_subscription(tenant_id, db)
        if sub is not None:
            custom_value = getattr(sub, custom_field, None)
            if custom_value is not None:
                return int(custom_value)

        plan_id = sub.plan_id if sub else "starter"
        plan_res = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        plan = plan_res.scalar_one_or_none()
        if plan is not None:
            plan_value = getattr(plan, plan_field, None)
            if plan_value is not None:
                return int(plan_value)
        return None

    async def check_and_enforce_page_quota(
        self,
        tenant_id: uuid.UUID,
        pages_to_add: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Plafonne le VOLUME de pages ingerees par mois (DCE + base de connaissances +
        SharePoint confondus) -- axe de cout distinct du nombre de dossiers ou du cout
        LLM : c'est le nombre de lignes ajoutees a dce_embeddings/knowledge_vectors
        (donc la charge Postgres/pgvector reelle, et le principal levier du cout
        Supabase a long terme) qui grossit avec le volume de PAGES, pas le nombre de
        documents. A appeler apres l'extraction OCR locale (le nombre de pages est
        alors connu gratuitement), avant tout calcul d'embedding. Repond a la demande
        explicite de gerer de gros volumes de fichiers sans faire exploser les couts
        Supabase (03/09).
        """
        sub = await self.get_tenant_subscription(tenant_id, db)
        allow_overage = sub.allow_page_overage if sub else True
        quota = await self._effective_int_limit(tenant_id, db, "custom_pages_month", "included_pages_month")

        if quota is None:
            return {"quota": None, "used": 0, "allow_overage": allow_overage, "blocked": False}

        usage = await self.get_or_create_usage(tenant_id, db)
        projected = usage.pages_ingested + max(pages_to_add, 0)

        if projected > quota and not allow_overage:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Volume mensuel de pages inclus atteint ({usage.pages_ingested}/{quota} pages, "
                    f"ce document en ajouterait {pages_to_add}). Le depassement n'est pas active sur ce "
                    f"compte -- contactez votre administrateur ou passez au forfait superieur."
                ),
            )

        return {
            "quota": quota,
            "used": usage.pages_ingested,
            "projected": projected,
            "allow_overage": allow_overage,
            "over_quota": projected > quota,
        }

    async def check_and_enforce_question_quota(
        self,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Plafonne le nombre de questions posees au chat assistant par mois (endpoint
        /projects/{id}/ask). Le plafond de cout LLM (check_and_enforce_cost_cap)
        protege deja le $ reel consomme sur CET appel comme sur tous les autres --
        celui-ci est un signal d'abus complementaire (frequence d'usage) avec
        depassement payant, miroir exact de check_and_enforce_quota (dossiers). A
        appeler AVANT de lancer la recherche RAG + l'appel LLM, pour ne pas facturer
        de cout inutile a une question qui sera de toute facon refusee (03/09).
        """
        sub = await self.get_tenant_subscription(tenant_id, db)
        allow_overage = sub.allow_question_overage if sub else True
        quota = await self._effective_int_limit(tenant_id, db, "custom_questions_month", "included_questions_month")

        if quota is None:
            return {"quota": None, "used": 0, "allow_overage": allow_overage, "blocked": False}

        usage = await self.get_or_create_usage(tenant_id, db)
        if usage.questions_asked >= quota and not allow_overage:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Quota mensuel de questions au chat atteint ({usage.questions_asked}/{quota}). "
                    f"Le depassement n'est pas active sur ce compte -- contactez votre administrateur "
                    f"ou passez au forfait superieur."
                ),
            )

        return {"quota": quota, "used": usage.questions_asked, "allow_overage": allow_overage}

    async def check_and_enforce_sharepoint_quota(
        self,
        tenant_id: uuid.UUID,
        files_to_add: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Plafonne le nombre de fichiers SharePoint (nouveaux/modifies) indexes
        automatiquement par mois via la synchronisation delta -- protection explicite
        contre un client qui ajouterait un site SharePoint entier (des milliers de
        fichiers) et ferait exploser le cout OCR/embeddings/stockage sans plafond
        dedie (03/09). Le connecteur (app/services/sharepoint_service.py) ne
        synchronise de toute facon QUE les fichiers nouveaux/modifies depuis le
        dernier delta -- ce plafond couvre le cas d'un tres gros premier import.
        """
        sub = await self.get_tenant_subscription(tenant_id, db)
        allow_overage = sub.allow_sharepoint_overage if sub else True
        quota = await self._effective_int_limit(
            tenant_id, db, "custom_sharepoint_files_month", "included_sharepoint_files_month"
        )

        if quota is None:
            return {"quota": None, "used": 0, "allow_overage": allow_overage, "blocked": False}

        usage = await self.get_or_create_usage(tenant_id, db)
        projected = usage.sharepoint_files_indexed + max(files_to_add, 0)

        if projected > quota and not allow_overage:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Quota mensuel de fichiers SharePoint atteint ({usage.sharepoint_files_indexed}/{quota}). "
                    f"Le depassement n'est pas active sur ce compte -- contactez votre administrateur ou "
                    f"passez au forfait superieur. La synchronisation reprendra au prochain cycle mensuel."
                ),
            )

        return {
            "quota": quota,
            "used": usage.sharepoint_files_indexed,
            "projected": projected,
            "allow_overage": allow_overage,
            "over_quota": projected > quota,
        }


billing_service = BillingService()

