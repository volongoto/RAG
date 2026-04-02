"""
API 限流中间件
基于 Redis 的分布式限流实现
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.log_util import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    基于滑动窗口的 API 限流中间件
    使用 Redis 实现分布式限流
    """

    def __init__(
        self,
        app: FastAPI,
        redis_client=None,
        default_limit: int = 100,
        default_window: int = 60,
        key_prefix: str = 'rate_limit',
    ):
        super().__init__(app)
        self.redis = redis_client
        self.default_limit = default_limit
        self.default_window = default_window
        self.key_prefix = key_prefix

        # 特定路径的限流配置 (path_pattern: (limit, window_seconds))
        self.path_limits: dict[str, tuple[int, int]] = {
            '/login': (5, 60),  # 登录接口：每分钟 5 次
            '/captcha': (10, 60),  # 验证码接口：每分钟 10 次
            '/api/v1/rag/query': (30, 60),  # RAG 查询：每分钟 30 次
            '/api/v1/rag/retrieve': (50, 60),  # RAG 检索：每分钟 50 次
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 如果没有 Redis 连接，跳过限流检查
        if self.redis is None:
            try:
                self.redis = request.app.state.redis
            except AttributeError:
                return await call_next(request)

        # 获取客户端标识
        client_id = self._get_client_id(request)
        path = request.url.path

        # 检查是否需要限流
        limit, window = self._get_limit_config(path)

        # 如果该路径不限流，直接放行
        if limit <= 0:
            return await call_next(request)

        # 检查限流
        is_allowed, current_count, reset_time = await self._check_rate_limit(
            client_id, path, limit, window
        )

        if not is_allowed:
            logger.warning(
                f'Rate limit exceeded: client={client_id}, path={path}, '
                f'count={current_count}, limit={limit}'
            )
            return JSONResponse(
                status_code=429,
                content={
                    'code': 429,
                    'msg': '请求过于频繁，请稍后再试',
                    'data': {
                        'limit': limit,
                        'window': window,
                        'reset_time': reset_time,
                    },
                },
                headers={
                    'X-RateLimit-Limit': str(limit),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(reset_time),
                    'Retry-After': str(reset_time - int(time.time())),
                },
            )

        # 执行请求
        response = await call_next(request)

        # 添加限流响应头
        remaining = max(0, limit - current_count)
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        response.headers['X-RateLimit-Reset'] = str(reset_time)

        return response

    def _get_client_id(self, request: Request) -> str:
        """获取客户端唯一标识"""
        # 优先使用 X-Forwarded-For 中的真实 IP
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else 'unknown'

        # 如果有用户认证信息，结合用户 ID
        try:
            user_id = getattr(request.state, 'user_id', None)
            if user_id:
                return f'{client_ip}:{user_id}'
        except AttributeError:
            pass

        return client_ip

    def _get_limit_config(self, path: str) -> tuple[int, int]:
        """获取路径的限流配置"""
        for pattern, (limit, window) in self.path_limits.items():
            if path.startswith(pattern) or pattern in path:
                return limit, window
        return self.default_limit, self.default_window

    async def _check_rate_limit(
        self, client_id: str, path: str, limit: int, window: int
    ) -> tuple[bool, int, int]:
        """
        检查是否超过限流阈值
        使用 Redis 有序集合实现滑动窗口

        Returns:
            (是否允许请求, 当前请求数, 重置时间戳)
        """
        now = int(time.time())
        window_start = now - window
        key = f'{self.key_prefix}:{client_id}:{path}'

        try:
            pipe = self.redis.pipeline()

            # 移除窗口外的旧记录
            pipe.zremrangebyscore(key, 0, window_start)

            # 添加当前请求记录
            pipe.zadd(key, {str(now): now})

            # 获取当前窗口内的请求数
            pipe.zcard(key)

            # 设置过期时间
            pipe.expire(key, window + 1)

            results = await pipe.execute()
            current_count = results[2]

            # 计算重置时间
            reset_time = now + window

            # 检查是否超过限制
            if current_count > limit:
                # 超过限制，移除刚才添加的记录
                await self.redis.zrem(key, str(now))
                return False, current_count - 1, reset_time

            return True, current_count, reset_time

        except Exception as e:
            logger.error(f'Rate limit check failed: {e}')
            # 限流检查失败时，允许请求通过（fail open）
            return True, 0, now + window


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """
    基于内存的 API 限流中间件（用于没有 Redis 的环境）
    注意：此实现仅适用于单实例部署
    """

    def __init__(
        self,
        app: FastAPI,
        default_limit: int = 100,
        default_window: int = 60,
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        self.request_records: dict[str, list[int]] = {}

        self.path_limits: dict[str, tuple[int, int]] = {
            '/login': (5, 60),
            '/captcha': (10, 60),
            '/api/v1/rag/query': (30, 60),
            '/api/v1/rag/retrieve': (50, 60),
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_id = self._get_client_id(request)
        path = request.url.path
        limit, window = self._get_limit_config(path)

        if limit <= 0:
            return await call_next(request)

        is_allowed, current_count, reset_time = self._check_rate_limit(
            client_id, path, limit, window
        )

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    'code': 429,
                    'msg': '请求过于频繁，请稍后再试',
                    'data': {
                        'limit': limit,
                        'window': window,
                        'reset_time': reset_time,
                    },
                },
            )

        response = await call_next(request)
        remaining = max(0, limit - current_count)
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = str(remaining)

        return response

    def _get_client_id(self, request: Request) -> str:
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else 'unknown'
        return client_ip

    def _get_limit_config(self, path: str) -> tuple[int, int]:
        for pattern, (limit, window) in self.path_limits.items():
            if path.startswith(pattern) or pattern in path:
                return limit, window
        return self.default_limit, self.default_window

    def _check_rate_limit(
        self, client_id: str, path: str, limit: int, window: int
    ) -> tuple[bool, int, int]:
        now = int(time.time())
        window_start = now - window
        key = f'{client_id}:{path}'

        # 清理过期记录
        if key in self.request_records:
            self.request_records[key] = [
                ts for ts in self.request_records[key] if ts > window_start
            ]
        else:
            self.request_records[key] = []

        current_count = len(self.request_records[key])

        if current_count >= limit:
            return False, current_count, now + window

        self.request_records[key].append(now)
        return True, current_count + 1, now + window


def add_rate_limit_middleware(app: FastAPI, redis_client=None) -> None:
    """
    添加限流中间件到应用

    Args:
        app: FastAPI 应用实例
        redis_client: 可选的 Redis 客户端，如果不提供则使用内存限流
    """
    if redis_client:
        app.add_middleware(
            RateLimitMiddleware,
            redis_client=redis_client,
            default_limit=100,
            default_window=60,
        )
        logger.info('Redis-based rate limit middleware enabled')
    else:
        app.add_middleware(
            InMemoryRateLimitMiddleware,
            default_limit=100,
            default_window=60,
        )
        logger.info('In-memory rate limit middleware enabled (single instance only)')
