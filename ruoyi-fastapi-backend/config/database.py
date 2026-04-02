from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.env import DataBaseConfig
from utils.log_util import logger

ASYNC_SQLALCHEMY_DATABASE_URL = (
    f'mysql+asyncmy://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
    f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
)
if DataBaseConfig.db_type == 'postgresql':
    ASYNC_SQLALCHEMY_DATABASE_URL = (
        f'postgresql+asyncpg://{DataBaseConfig.db_username}:{quote_plus(DataBaseConfig.db_password)}@'
        f'{DataBaseConfig.db_host}:{DataBaseConfig.db_port}/{DataBaseConfig.db_database}'
    )

# 数据库连接池配置优化
async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    echo=DataBaseConfig.db_echo,
    pool_size=DataBaseConfig.db_pool_size,
    max_overflow=DataBaseConfig.db_max_overflow,
    pool_recycle=DataBaseConfig.db_pool_recycle,
    pool_timeout=DataBaseConfig.db_pool_timeout,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=async_engine,
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


async def get_pool_status() -> dict:
    """获取数据库连接池状态"""
    pool = async_engine.pool
    return {
        'size': pool.size(),
        'checked_in': pool.checkedin(),
        'checked_out': pool.checkedout(),
        'overflow': pool.overflow(),
    }


def log_pool_status() -> None:
    """记录连接池状态日志"""
    pool = async_engine.pool
    logger.info(
        f'Database pool status: '
        f'size={pool.size()}, '
        f'checked_in={pool.checkedin()}, '
        f'checked_out={pool.checkedout()}, '
        f'overflow={pool.overflow()}'
    )
