import hashlib
from time import perf_counter
from typing import Optional

from config.env import RAGConfig, normalize_env_string
from llama_index.embeddings.openai import OpenAIEmbedding
from loguru import logger


class EmbeddingService:
    """Embedding service wrapper with caching support."""

    _instance: Optional['EmbeddingService'] = None
    _embed_model: Optional[OpenAIEmbedding] = None
    _cache_enabled: bool = True
    _cache_max_size: int = 1000

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._embed_model is None:
            self._init_embed_model()

    def _init_embed_model(self):
        api_base = normalize_env_string(RAGConfig.rag_embedding_api_base)
        api_key = normalize_env_string(RAGConfig.rag_embedding_api_key) or 'sk-dummy'
        model_name = normalize_env_string(RAGConfig.rag_embedding_model)

        self._embed_model = OpenAIEmbedding(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
            embed_batch_size=RAGConfig.rag_embedding_batch_size,
        )
        self._cache_enabled = getattr(RAGConfig, 'rag_embedding_cache_enabled', True)
        self._cache_max_size = getattr(RAGConfig, 'rag_embedding_cache_size', 1000)
        logger.debug(
            'Embedding model initialized: '
            f'api_base={api_base}, '
            f'model={model_name}, '
            f'batch_size={RAGConfig.rag_embedding_batch_size}, '
            f'cache_enabled={self._cache_enabled}, '
            f'cache_size={self._cache_max_size}'
        )

    def get_embed_model(self) -> OpenAIEmbedding:
        return self._embed_model

    @staticmethod
    def _generate_cache_key(text: str) -> str:
        normalized = text.strip().replace('\r\n', '\n').replace('\r', '\n')
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    async def get_text_embedding(self, text: str) -> list[float]:
        if not text or not text.strip():
            return []

        if self._cache_enabled:
            cache_key = self._generate_cache_key(text)
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                logger.debug(f'Embedding cache hit: key={cache_key[:8]}...')
                return cached

        request_start = perf_counter()
        try:
            embeddings = await self._embed_model.aget_text_embedding_batch([text])
            embedding = embeddings[0] if embeddings else []

            if self._cache_enabled and embedding:
                self._add_to_cache(self._generate_cache_key(text), embedding)

            return embedding
        except Exception as exc:
            logger.exception(
                'Embedding request failed: '
                f'api_base={normalize_env_string(RAGConfig.rag_embedding_api_base)}, '
                f'model={normalize_env_string(RAGConfig.rag_embedding_model)}, '
                f'text_length={len(text)}, '
                f'elapsed_ms={int((perf_counter() - request_start) * 1000)}, error={exc}'
            )
            raise

    async def get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_start = perf_counter()
        results: list[list[float]] = []
        texts_to_fetch: list[tuple[int, str]] = []

        if self._cache_enabled:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results.append([])
                    continue

                cache_key = self._generate_cache_key(text)
                cached = self._get_from_cache(cache_key)
                if cached is not None:
                    results.append(cached)
                    logger.debug(f'Embedding cache hit: key={cache_key[:8]}...')
                else:
                    results.append(None)
                    texts_to_fetch.append((i, text))
        else:
            texts_to_fetch = [(i, text) for i, text in enumerate(texts) if text and text.strip()]
            results = [[] for _ in range(len(texts))]

        if texts_to_fetch:
            try:
                fetch_texts = [item[1] for item in texts_to_fetch]
                fetched_embeddings = await self._embed_model.aget_text_embedding_batch(fetch_texts)

                for (idx, text), embedding in zip(texts_to_fetch, fetched_embeddings):
                    results[idx] = embedding
                    if self._cache_enabled and embedding:
                        self._add_to_cache(self._generate_cache_key(text), embedding)
            except Exception as exc:
                logger.exception(
                    'Embedding batch request failed: '
                    f'api_base={normalize_env_string(RAGConfig.rag_embedding_api_base)}, '
                    f'model={normalize_env_string(RAGConfig.rag_embedding_model)}, '
                    f'batch_count={len(texts_to_fetch)}, '
                    f'elapsed_ms={int((perf_counter() - batch_start) * 1000)}, error={exc}'
                )
                raise

        return results

    def _get_from_cache(self, cache_key: str) -> Optional[list[float]]:
        return self._embedding_cache.get(cache_key)

    def _add_to_cache(self, cache_key: str, embedding: list[float]) -> None:
        if len(self._embedding_cache) >= self._cache_max_size:
            keys_to_remove = list(self._embedding_cache.keys())[: self._cache_max_size // 10]
            for key in keys_to_remove:
                del self._embedding_cache[key]
        self._embedding_cache[cache_key] = embedding

    @property
    def _embedding_cache(self) -> dict:
        if not hasattr(self, '_cache'):
            self._cache: dict[str, list[float]] = {}
        return self._cache

    def clear_cache(self) -> None:
        if hasattr(self, '_cache'):
            self._cache.clear()
            logger.info('Embedding cache cleared')

    def get_cache_stats(self) -> dict:
        cache = getattr(self, '_cache', {})
        return {
            'enabled': self._cache_enabled,
            'max_size': self._cache_max_size,
            'current_size': len(cache),
            'hit_rate': getattr(self, '_cache_hits', 0) / max(getattr(self, '_cache_total', 1), 1),
        }

    @classmethod
    def get_instance(cls) -> 'EmbeddingService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
