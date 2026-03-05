from typing import Optional

from config.env import RAGConfig
from llama_index.embeddings.openai import OpenAIEmbedding
from loguru import logger


class EmbeddingService:
    """
    向量化服务
    """

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
        """
        初始化Embedding模型
        """
        self._embed_model = OpenAIEmbedding(
            api_key=RAGConfig.rag_embedding_api_key or 'sk-dummy',
            api_base=RAGConfig.rag_embedding_api_base,
            model_name=RAGConfig.rag_embedding_model,
            embed_batch_size=RAGConfig.rag_embedding_batch_size,
        )
        logger.info(f'Embedding模型初始化完成: {RAGConfig.rag_embedding_model}')

    def get_embed_model(self) -> OpenAIEmbedding:
        """
        获取Embedding模型实例
        """
        return self._embed_model

    async def get_text_embedding(self, text: str) -> list[float]:
        """
        获取单个文本的向量
        """
        try:
            embedding = await self._embed_model.aget_text_embedding(text)
            return embedding
        except Exception as e:
            logger.error(f'获取文本向量失败: {str(e)}')
            raise e

    async def get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        批量获取文本向量
        """
        try:
            embeddings = await self._embed_model.aget_text_embedding_batch(texts)
            return embeddings
        except Exception as e:
            logger.error(f'批量获取文本向量失败: {str(e)}')
            raise e

    @classmethod
    def get_instance(cls) -> 'EmbeddingService':
        """
        获取单例实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
