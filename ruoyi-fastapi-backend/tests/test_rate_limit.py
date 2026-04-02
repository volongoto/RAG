"""
API 限流中间件测试
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from starlette.datastructures import Headers

from middlewares.rate_limit_middleware import (
    InMemoryRateLimitMiddleware,
    RateLimitMiddleware,
)


class TestInMemoryRateLimitMiddleware:
    """内存限流中间件测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        return FastAPI()

    @pytest.fixture
    def middleware(self, app):
        """创建限流中间件"""
        return InMemoryRateLimitMiddleware(
            app,
            default_limit=5,
            default_window=60,
        )

    def test_get_client_id(self, middleware):
        """测试客户端 ID 获取"""
        # 模拟请求
        request = MagicMock(spec=Request)
        request.headers = Headers({'X-Forwarded-For': '192.168.1.1, 10.0.0.1'})
        request.client = MagicMock()
        request.client.host = '127.0.0.1'

        client_id = middleware._get_client_id(request)
        assert client_id == '192.168.1.1'

    def test_get_client_id_without_forwarded(self, middleware):
        """测试无转发头时的客户端 ID 获取"""
        request = MagicMock(spec=Request)
        request.headers = Headers({})
        request.client = MagicMock()
        request.client.host = '127.0.0.1'

        client_id = middleware._get_client_id(request)
        assert client_id == '127.0.0.1'

    def test_get_limit_config(self, middleware):
        """测试限流配置获取"""
        # 测试特定路径
        limit, window = middleware._get_limit_config('/login')
        assert limit == 5
        assert window == 60

        # 测试默认路径
        limit, window = middleware._get_limit_config('/unknown')
        assert limit == 5  # default_limit
        assert window == 60  # default_window

    def test_check_rate_limit(self, middleware):
        """测试限流检查"""
        client_id = 'test_client'
        path = '/test'
        limit = 3
        window = 60

        # 前 3 次请求应通过
        for i in range(3):
            is_allowed, count, reset_time = middleware._check_rate_limit(
                client_id, path, limit, window
            )
            assert is_allowed is True
            assert count == i + 1

        # 第 4 次请求应被限制
        is_allowed, count, reset_time = middleware._check_rate_limit(
            client_id, path, limit, window
        )
        assert is_allowed is False
        assert count == 3


@pytest.mark.asyncio
class TestRateLimitMiddleware:
    """Redis 限流中间件测试"""

    @pytest.fixture
    def mock_redis(self):
        """创建模拟 Redis 客户端"""
        redis = AsyncMock()
        redis.pipeline = MagicMock(return_value=redis)
        redis.zremrangebyscore = AsyncMock()
        redis.zadd = AsyncMock()
        redis.zcard = AsyncMock(return_value=1)
        redis.expire = AsyncMock()
        redis.execute = AsyncMock(return_value=[None, None, 1, None])
        return redis

    async def test_check_rate_limit_allowed(self, mock_redis):
        """测试限流检查 - 允许通过"""
        app = FastAPI()
        middleware = RateLimitMiddleware(app, redis_client=mock_redis)

        is_allowed, count, reset_time = await middleware._check_rate_limit(
            'test_client', '/test', limit=10, window=60
        )

        assert is_allowed is True
        assert count == 1
        assert reset_time > int(time.time())

    async def test_check_rate_limit_denied(self, mock_redis):
        """测试限流检查 - 拒绝访问"""
        app = FastAPI()
        mock_redis.zcard = AsyncMock(return_value=11)  # 超过限制
        middleware = RateLimitMiddleware(app, redis_client=mock_redis)

        is_allowed, count, reset_time = await middleware._check_rate_limit(
            'test_client', '/test', limit=10, window=60
        )

        assert is_allowed is False
        assert count == 10
