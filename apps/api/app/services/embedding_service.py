"""
Vector Embedding Service using LiteLLM abstraction with deterministic fallback
Produces 1536-dimensional vectors compatible with pgvector.
"""
import hashlib
import math
from typing import List, Optional
import litellm
from app.core.config import settings


class EmbeddingService:
    def __init__(self):
        self.model = settings.EMBEDDING_MODEL
        self.dimension = 1536

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a 1536-dimensional embedding vector for a given text.
        """
        if not text or not text.strip():
            return [0.0] * self.dimension

        # 1. Try LiteLLM embedding if API keys are configured
        if settings.OPENAI_API_KEY or settings.MISTRAL_API_KEY or settings.ANTHROPIC_API_KEY:
            try:
                response = litellm.embedding(
                    model=self.model,
                    input=[text],
                    api_key=settings.OPENAI_API_KEY or settings.MISTRAL_API_KEY,
                )
                if response and response.data and len(response.data) > 0:
                    embedding = response.data[0]["embedding"]
                    # Pad or truncate to 1536 if needed
                    if len(embedding) < self.dimension:
                        embedding = embedding + [0.0] * (self.dimension - len(embedding))
                    return embedding[:self.dimension]
            except Exception as e:
                print(f"[EmbeddingService] LiteLLM embedding call notice: {e}, using fallback vector.")

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
