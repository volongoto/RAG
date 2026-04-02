"""
Pytest 配置文件
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config.database import Base
from server import create_app


# 使用内存数据库进行测试
TEST_DATABASE_URL = 'sqlite+aiosqlite:///:memory:'


@pytest.fixture(scope='session')
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope='session')
async def test_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话"""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def app(test_engine) -> FastAPI:
    """创建测试应用"""
    application = create_app()
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """创建测试客户端"""
    async with AsyncClient(app=app, base_url='http://test') as ac:
        yield ac
