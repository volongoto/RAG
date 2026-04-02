import hashlib
from functools import lru_cache
from typing import Optional
from time import perf_counter

from async_lru import alru_cache
from config.env import RAGConfig
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
        self._embed_model = OpenAIEmbedding(
            api_key=RAGConfig.rag_embedding_api_key or 'sk-dummy',
            api_base=RAGConfig.rag_embedding_api_base,
            model_name=RAGConfig.rag_embedding_model,
            embed_batch_size=RAGConfig.rag_embedding_batch_size,
        )
        # 从配置读取缓存设置
        self._cache_enabled = getattr(RAGConfig, 'rag_embedding_cache_enabled', True)
        self._cache_max_size = getattr(RAGConfig, 'rag_embedding_cache_size', 1000)
        logger.debug(
            'Embedding model initialized: '
            f'api_base={RAGConfig.rag_embedding_api_base}, '
            f'model={RAGConfig.rag_embedding_model}, '
            f'batch_size={RAGConfig.rag_embedding_batch_size}, '
            f'cache_enabled={self._cache_enabled}, '
            f'cache_size={self._cache_max_size}'
        )

    def get_embed_model(self) -> OpenAIEmbedding:
        return self._embed_model

    @staticmethod
    def _generate_cache_key(text: str) -> str:
        """生成文本的缓存键（使用 MD5 哈希）"""
        # 标准化文本：去除首尾空白，统一换行符
        normalized = text.strip().replace('\r\n', '\n').replace('\r', '\n')
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    async def get_text_embedding(self, text: str) -> list[float]:
        """获取单条文本的 embedding，支持缓存"""
        if not text or not text.strip():
            return []

        # 如果缓存启用，尝试从缓存获取
        if self._cache_enabled:
            cache_key = self._generate_cache_key(text)
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                logger.debug(f'Embedding cache hit: key={cache_key[:8]}...')
                return cached

        # 缓存未命中，调用 API
        request_start = perf_counter()
        try:
            embeddings = await self._embed_model.aget_text_embedding_batch([text])
            embedding = embeddings[0] if embeddings else []

            # 存入缓存
            if self._cache_enabled and embedding:
                self._add_to_cache(self._generate_cache_key(text), embedding)

            return embedding
        except Exception as exc:
            logger.exception(
                'Embedding 调用失败: '
                f'api_base={RAGConfig.rag_embedding_api_base}, '
                f'model={RAGConfig.rag_embedding_model}, '
                f'text_length={len(text)}, '
                f'elapsed_ms={int((perf_counter() - request_start) * 1000)}, error={exc}'
            )
            raise

    async def get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """批量获取文本的 embedding，支持缓存"""
        if not texts:
            return []

        batch_start = perf_counter()
        results: list[list[float]] = []
        texts_to_fetch: list[tuple[int, str]] = []  # (index, text)

        # 检查缓存
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
                    results.append(None)  # 占位
                    texts_to_fetch.append((i, text))
        else:
            texts_to_fetch = [(i, text) for i, text in enumerate(texts) if text and text.strip()]
            results = [[] for _ in range(len(texts))]

        # 如果有未缓存的文本，批量获取
        if texts_to_fetch:
            try:
                fetch_texts = [t[1] for t in texts_to_fetch]
                fetched_embeddings = await self._embed_model.aget_text_embedding_batch(fetch_texts)

                # 更新结果和缓存
                for (idx, text), embedding in zip(texts_to_fetch, fetched_embeddings):
                    results[idx] = embedding
                    if self._cache_enabled and embedding:
                        self._add_to_cache(self._generate_cache_key(text), embedding)

            except Exception as exc:
                logger.exception(
                    'Embedding 批量调用失败: '
                    f'api_base={RAGConfig.rag_embedding_api_base}, '
                    f'model={RAGConfig.rag_embedding_model}, '
                    f'batch_count={len(texts_to_fetch)}, '
                    f'elapsed_ms={int((perf_counter() - batch_start) * 1000)}, error={exc}'
                )
                raise

        return results

    def _get_from_cache(self, cache_key: str) -> Optional[list[float]]:
        """从缓存获取 embedding"""
        return self._embedding_cache.get(cache_key)

    def _add_to_cache(self, cache_key: str, embedding: list[float]) -> None:
        """添加 embedding 到缓存"""
        # 使用 LRU 策略：如果缓存已满，移除最早的条目
        if len(self._embedding_cache) >= self._cache_max_size:
            # 移除最早添加的 10% 条目
            keys_to_remove = list(self._embedding_cache.keys())[:self._cache_max_size // 10]
            for key in keys_to_remove:
                del self._embedding_cache[key]
        self._embedding_cache[cache_key] = embedding

    @property
    def _embedding_cache(self) -> dict:
        """获取缓存字典（惰性初始化）"""
        if not hasattr(self, '_cache'):
            self._cache: dict[str, list[float]] = {}
        return self._cache

    def clear_cache(self) -> None:
        """清空 embedding 缓存"""
        if hasattr(self, '_cache'):
            self._cache.clear()
            logger.info('Embedding cache cleared')

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
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
