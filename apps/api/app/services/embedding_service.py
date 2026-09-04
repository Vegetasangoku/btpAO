"""
Vector Embedding Service using LiteLLM abstraction with deterministic fallback
Produces 1536-dimensional vectors compatible with pgvector.

Résolution de clé (29/08) : avant, ce service ne lisait QUE .env
(settings.OPENAI_API_KEY / settings.MISTRAL_API_KEY), en ignorant totalement
la clé qu'un administrateur configure via l'UI Super Admin > "Fournisseurs LLM"
(stockée chiffrée dans platform_settings, la même table que model_routing_service
utilise déjà pour la génération de texte). Résultat concret observé : même une
fois une vraie clé OpenAI/Mistral collée dans l'UI admin, les embeddings
continuaient à retomber sur le vecteur pseudo-aléatoire de secours. Corrigé :
sync_platform_key() va lire cette même source (platform_settings, priorité
admin > .env, avec un court cache pour ne pas taper la base à chaque chunk
d'un document de 200 pages) et generate_embedding() l'utilise en priorité.
"""
import hashlib
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import litellm
from app.core.config import settings

# Modèle d'embedding à apparier avec la clé effectivement disponible -- ne
# jamais envoyer un modèle "text-embedding-3-small" (OpenAI) avec une clé
# Mistral ou inversement, litellm router par le nom du modèle, pas par la clé.
EMBEDDING_MODEL_BY_PROVIDER = {
    "openai": "text-embedding-3-small",
    "mistral": "mistral-embed",
}

_PLATFORM_KEY_CACHE_TTL_SECONDS = 30.0


def _looks_like_placeholder(value: Optional[str]) -> bool:
    if not value:
        return True
    v = value.strip()
    return v.startswith("sk-...") or v.startswith("...") or v == ""


class EmbeddingService:
    def __init__(self):
        self.model = settings.EMBEDDING_MODEL
        self.dimension = 1536
        # Cache court-terme du résultat de sync_platform_key() : (api_key, provider)
        self._runtime_key: Optional[str] = None
        self._runtime_provider: Optional[str] = None
        self._runtime_cached_at: float = 0.0

    async def sync_platform_key(self, db) -> None:
        """
        Recherche une clé OpenAI/Mistral configurée par un admin via l'UI
        (platform_settings.settings, chiffrée) et la met en cache pour les
        prochains appels à generate_embedding() de ce process. Ne lève jamais
        d'exception -- en cas d'échec (table absente, DB indisponible), le
        cache reste inchangé et generate_embedding() retombe sur .env comme
        avant. À appeler une fois avant une boucle d'embeddings (pas par chunk).
        """
        now = time.monotonic()
        if now - self._runtime_cached_at < _PLATFORM_KEY_CACHE_TTL_SECONDS:
            return
        try:
            from sqlalchemy import select
            from app.models.entities import PlatformSettings
            from app.core.crypto_vault import decrypt_api_key

            stmt = select(PlatformSettings).where(PlatformSettings.id == "global")
            res = await db.execute(stmt)
            ps = res.scalar_one_or_none()
            settings_dict = (ps.settings if ps and ps.settings else {}) or {}

            found_key: Optional[str] = None
            found_provider: Optional[str] = None

            raw_openai = settings_dict.get("openai_api_key")
            raw_mistral = settings_dict.get("mistral_api_key")

            if raw_openai:
                decrypted = decrypt_api_key(raw_openai)
                if decrypted and not _looks_like_placeholder(decrypted):
                    found_key, found_provider = decrypted, "openai"
            if not found_key and raw_mistral:
                decrypted = decrypt_api_key(raw_mistral)
                if decrypted and not _looks_like_placeholder(decrypted):
                    found_key, found_provider = decrypted, "mistral"

            if not found_key:
                for prov in settings_dict.get("custom_providers", []) or []:
                    if not prov.get("enabled", True):
                        continue
                    prov_id = (prov.get("id") or "").lower()
                    litellm_id = (prov.get("litellm_id") or "").lower()
                    if "openai" not in prov_id and "openai" not in litellm_id:
                        if "mistral" not in prov_id and "mistral" not in litellm_id:
                            continue
                    decrypted = decrypt_api_key(prov.get("api_key", ""))
                    if decrypted and not _looks_like_placeholder(decrypted):
                        found_key = decrypted
                        found_provider = "mistral" if "mistral" in prov_id or "mistral" in litellm_id else "openai"
                        break

            self._runtime_key = found_key
            self._runtime_provider = found_provider
            self._runtime_cached_at = now
        except Exception as e:
            print(f"[EmbeddingService] sync_platform_key notice: {e} -- repli sur .env uniquement.")

    def _resolve_key_and_model(self) -> Tuple[Optional[str], str]:
        """Retourne (clé, modèle) toujours appariés à la même source pour éviter d'envoyer
        le mauvais modèle à la mauvaise clé (ex: modèle OpenAI + clé Mistral)."""
        if self._runtime_key and not _looks_like_placeholder(self._runtime_key):
            provider = self._runtime_provider or "openai"
            return self._runtime_key, EMBEDDING_MODEL_BY_PROVIDER.get(provider, self.model)

        if settings.OPENAI_API_KEY and not _looks_like_placeholder(settings.OPENAI_API_KEY):
            return settings.OPENAI_API_KEY, EMBEDDING_MODEL_BY_PROVIDER["openai"]

        if settings.MISTRAL_API_KEY and not _looks_like_placeholder(settings.MISTRAL_API_KEY):
            return settings.MISTRAL_API_KEY, EMBEDDING_MODEL_BY_PROVIDER["mistral"]

        return None, self.model

    def get_embedding_status(self) -> Dict[str, Any]:
        """État courant (pour affichage admin) : les prochains embeddings seront-ils
        de vrais vecteurs sémantiques (mode 'real') ou le repli pseudo-aléatoire
        déterministe basé sur des hashs de mots (mode 'degraded_fallback') ?"""
        key, model = self._resolve_key_and_model()
        if not key:
            return {"mode": "degraded_fallback", "provider": None, "model": None}
        if model == EMBEDDING_MODEL_BY_PROVIDER.get("mistral"):
            provider = "mistral"
        else:
            provider = "openai"
        source = "admin" if (self._runtime_key and key == self._runtime_key) else "env"
        return {"mode": "real", "provider": provider, "model": model, "key_source": source}

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a 1536-dimensional embedding vector for a given text.
        """
        if not text or not text.strip():
            return [0.0] * self.dimension

        # 1. Try LiteLLM embedding if a valid key is available (clé admin en priorité, sinon .env)
        api_key, model_to_use = self._resolve_key_and_model()
        if api_key:
            try:
                response = litellm.embedding(
                    model=model_to_use,
                    input=[text],
                    api_key=api_key,
                )
                if response and response.data and len(response.data) > 0:
                    embedding = response.data[0]["embedding"]
                    # Pad or truncate to 1536 if needed
                    if len(embedding) < self.dimension:
                        embedding = embedding + [0.0] * (self.dimension - len(embedding))
                    return embedding[:self.dimension]
            except Exception as e:
                print(f"[EmbeddingService] LiteLLM embedding call notice (model={model_to_use}): {e}, using fallback vector.")

        # 2. Deterministic high-entropy pseudo-embedding fallback
        return self._generate_deterministic_vector(text)


    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self.generate_embedding(t) for t in texts]

    def _generate_deterministic_vector(self, text: str) -> List[float]:
        """
        Creates a normalized 1536-dim unit vector derived from the content's token hashes.
        Maintains cosine similarity properties for matching words and semantic keywords.
        """
        vector = [0.0] * self.dimension
        words = text.lower().split()

        for word in words:
            # Hash word into bucket indices
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            val = (int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16) % 1000) / 500.0 - 1.0
            vector[idx] += val

        # Normalize vector to unit length (L2 norm)
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-9:
            vector = [x / norm for x in vector]
        else:
            vector[0] = 1.0

        return vector


embedding_service = EmbeddingService()
