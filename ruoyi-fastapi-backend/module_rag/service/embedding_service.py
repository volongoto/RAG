from typing import Optional

from config.env import RAGConfig
from llama_index.embeddings.openai import OpenAIEmbedding
from loguru import logger


class EmbeddingService:
    """Embedding service wrapper."""

    _instance: Optional['EmbeddingService'] = None
    _embed_model: Optional[OpenAIEmbedding] = None

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
        logger.info(
            'Embedding model initialized: '
            f'api_base={RAGConfig.rag_embedding_api_base}, '
            f'model={RAGConfig.rag_embedding_model}, '
            f'batch_size={RAGConfig.rag_embedding_batch_size}'
        )

    def get_embed_model(self) -> OpenAIEmbedding:
        return self._embed_model

    async def get_text_embedding(self, text: str) -> list[float]:
        try:
            logger.info(
                'Embedding request started: '
                f'api_base={RAGConfig.rag_embedding_api_base}, '
                f'model={RAGConfig.rag_embedding_model}, '
                f'text_length={len(text or "")}'
            )
            # Use the batch embedding API even for a single query so the
            # online query path matches the document indexing path exactly.
            embeddings = await self._embed_model.aget_text_embedding_batch([text])
            embedding = embeddings[0] if embeddings else []
            logger.info(
                'Embedding request finished: '
                f'model={RAGConfig.rag_embedding_model}, '
                f'vector_dim={len(embedding or [])}'
            )
            return embedding
        except Exception as exc:
            logger.exception(
                'Embedding request failed: '
                f'api_base={RAGConfig.rag_embedding_api_base}, '
                f'model={RAGConfig.rag_embedding_model}, '
                f'text_length={len(text or "")}, error={exc}'
            )
            raise

    async def get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        try:
            text_lengths = [len(text or '') for text in texts]
            logger.info(
                'Embedding batch request started: '
                f'api_base={RAGConfig.rag_embedding_api_base}, '
                f'model={RAGConfig.rag_embedding_model}, '
                f'batch_count={len(texts)}, text_lengths={text_lengths}'
            )
            embeddings = await self._embed_model.aget_text_embedding_batch(texts)
            logger.info(
                'Embedding batch request finished: '
                f'model={RAGConfig.rag_embedding_model}, '
                f'batch_count={len(embeddings or [])}, '
                f'vector_dim={len((embeddings or [[]])[0]) if embeddings else 0}'
            )
            return embeddings
        except Exception as exc:
            logger.exception(
                'Embedding batch request failed: '
                f'api_base={RAGConfig.rag_embedding_api_base}, '
                f'model={RAGConfig.rag_embedding_model}, '
                f'batch_count={len(texts)}, error={exc}'
            )
            raise

    @classmethod
    def get_instance(cls) -> 'EmbeddingService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
