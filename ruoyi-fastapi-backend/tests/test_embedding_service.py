"""
Embedding 服务测试
"""

import pytest

from module_rag.service.embedding_service import EmbeddingService


class TestEmbeddingService:
    """EmbeddingService 测试类"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        service1 = EmbeddingService.get_instance()
        service2 = EmbeddingService.get_instance()
        assert service1 is service2

    def test_cache_key_generation(self):
        """测试缓存键生成"""
        text1 = 'Hello World'
        text2 = 'Hello World'  # 相同文本
        text3 = 'hello world'  # 不同大小写

        key1 = EmbeddingService._generate_cache_key(text1)
        key2 = EmbeddingService._generate_cache_key(text2)
        key3 = EmbeddingService._generate_cache_key(text3)

        # 相同文本应生成相同缓存键
        assert key1 == key2
        # 不同文本应生成不同缓存键
        assert key1 != key3

    def test_cache_key_normalization(self):
        """测试缓存键标准化"""
        # 测试换行符标准化
        text1 = 'Hello\nWorld'
        text2 = 'Hello\r\nWorld'
        text3 = 'Hello\rWorld'

        key1 = EmbeddingService._generate_cache_key(text1)
        key2 = EmbeddingService._generate_cache_key(text2)
        key3 = EmbeddingService._generate_cache_key(text3)

        # 标准化后应生成相同缓存键
        assert key1 == key2 == key3

    def test_cache_operations(self):
        """测试缓存操作"""
        service = EmbeddingService()

        # 测试添加和获取缓存
        cache_key = 'test_key'
        embedding = [0.1, 0.2, 0.3]

        service._add_to_cache(cache_key, embedding)
        cached = service._get_from_cache(cache_key)

        assert cached == embedding

        # 测试清空缓存
        service.clear_cache()
        cached_after_clear = service._get_from_cache(cache_key)
        assert cached_after_clear is None

    def test_cache_stats(self):
        """测试缓存统计"""
        service = EmbeddingService()
        service.clear_cache()

        stats = service.get_cache_stats()
        assert 'enabled' in stats
        assert 'max_size' in stats
        assert 'current_size' in stats
        assert stats['current_size'] == 0


@pytest.mark.asyncio
class TestEmbeddingServiceAsync:
    """EmbeddingService 异步测试类"""

    async def test_get_text_embedding_empty(self):
        """测试空文本处理"""
        service = EmbeddingService()

        # 空文本应返回空列表
        result = await service.get_text_embedding('')
        assert result == []

        result = await service.get_text_embedding('   ')
        assert result == []

    async def test_get_text_embeddings_empty_list(self):
        """测试空列表处理"""
        service = EmbeddingService()

        result = await service.get_text_embeddings([])
        assert result == []
