import argparse
import configparser
import os
import sys
from typing import Literal

from dotenv import load_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """
    应用配置
    """

    app_env: str = 'dev'
    app_name: str = 'Cradle-FastAPI'
    app_root_path: str = '/dev-api'
    app_host: str = '0.0.0.0'
    app_port: int = 29099
    app_version: str = '1.0.0'
    app_reload: bool = True
    app_ip_location_query: bool = True
    app_same_time_login: bool = True


class JwtSettings(BaseSettings):
    """
    Jwt配置
    """

    jwt_secret_key: str = 'replace-with-a-strong-secret'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 1440
    jwt_redis_expire_minutes: int = 30


class DataBaseSettings(BaseSettings):
    """
    数据库配置
    """

    db_type: Literal['mysql', 'postgresql'] = 'postgresql'
    db_host: str = '127.0.0.1'
    db_port: int = 54322
    db_username: str = 'postgres'
    db_password: str = 'root'
    db_database: str = 'cradle-fastapi'
    db_echo: bool = True
    db_max_overflow: int = 10
    db_pool_size: int = 50
    db_pool_recycle: int = 3600
    db_pool_timeout: int = 30

    @computed_field
    @property
    def sqlglot_parse_dialect(self) -> str:
        if self.db_type == 'postgresql':
            return 'postgres'
        return self.db_type


class RedisSettings(BaseSettings):
    """
    Redis配置
    """

    redis_host: str = '127.0.0.1'
    redis_port: int = 6379
    redis_username: str = ''
    redis_password: str = ''
    redis_database: int = 2


class UploadSettings:
    """
    上传配置
    """

    UPLOAD_PREFIX = '/profile'
    UPLOAD_PATH = 'vf_admin/upload_path'
    UPLOAD_MACHINE = 'A'
    DEFAULT_ALLOWED_EXTENSION = [
        # 图片
        'bmp',
        'gif',
        'jpg',
        'jpeg',
        'png',
        # word excel powerpoint
        'doc',
        'docx',
        'xls',
        'xlsx',
        'ppt',
        'pptx',
        'html',
        'htm',
        'txt',
        # 压缩文件
        'rar',
        'zip',
        'gz',
        'bz2',
        # 视频格式
        'mp4',
        'avi',
        'rmvb',
        # pdf
        'pdf',
    ]
    DOWNLOAD_PATH = 'vf_admin/download_path'

    def __init__(self) -> None:
        if not os.path.exists(self.UPLOAD_PATH):
            os.makedirs(self.UPLOAD_PATH)
        if not os.path.exists(self.DOWNLOAD_PATH):
            os.makedirs(self.DOWNLOAD_PATH)


class RAGSettings(BaseSettings):
    """
    RAG配置
    """

    rag_llm_api_base: str = 'https://api.siliconflow.cn/v1'
    rag_llm_api_key: str = ''
    rag_llm_model: str = 'Qwen/Qwen2.5-32B-Instruct'
    rag_llm_temperature: float = 0.7
    rag_llm_max_tokens: int = 2000
    rag_embedding_api_base: str = 'https://api.siliconflow.cn/v1'
    rag_embedding_api_key: str = ''
    rag_embedding_model: str = 'BAAI/bge-m3'
    rag_embedding_batch_size: int = 50
    rag_embedding_dimension: int = 1024
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7
    rag_security_brief_enabled: bool = False
    rag_security_brief_scenario_markers: str = 'national-security,intel,intelligence,国安,情报,安全风险'
    rag_security_brief_query_markers: str = '国安,情报,安全风险,反间谍,克格勃,渗透,泄密'
    rag_era_mismatch_guard_enabled: bool = False
    rag_era_mismatch_left_markers: str = 'kgb,克格勃'
    rag_era_mismatch_right_markers: str = '韦小宝,鹿鼎记,康熙,清朝'


class InternalRagBridgeSettings(BaseSettings):
    rag_internal_shared_secret: str = ''
    rag_internal_allowed_source_systems: str = 'ksguoaj-google'
    rag_external_user_map: str = '{}'
    rag_external_user_name_map: str = '{}'
    rag_external_dept_map: str = '{}'
    rag_internal_allow_direct_user_id_fallback: bool = True
    rag_internal_allow_direct_dept_id_fallback: bool = True
    rag_internal_signature_ttl_seconds: int = 300


class CachePathConfig:
    """
    缓存目录配置
    """

    PATH = os.path.join(os.path.abspath(os.getcwd()), 'caches')
    PATHSTR = 'caches'


class GetConfig:
    """
    获取配置
    """

    def __init__(self) -> None:
        self.parse_cli_args()

    def get_app_config(self) -> AppSettings:
        """
        获取应用配置
        """
        # 实例化应用配置模型
        return AppSettings()

    def get_jwt_config(self) -> JwtSettings:
        """
        获取Jwt配置
        """
        # 实例化Jwt配置模型
        return JwtSettings()

    def get_database_config(self) -> DataBaseSettings:
        """
        获取数据库配置
        """
        # 实例化数据库配置模型
        return DataBaseSettings()

    def get_redis_config(self) -> RedisSettings:
        """
        获取Redis配置
        """
        # 实例化Redis配置模型
        return RedisSettings()

    def get_upload_config(self) -> UploadSettings:
        """
        获取上传配置
        """
        # 实例上传配置
        return UploadSettings()

    def get_rag_config(self) -> RAGSettings:
        """
        获取RAG配置
        """
        return RAGSettings()

    def get_internal_rag_bridge_config(self) -> InternalRagBridgeSettings:
        """
        获取内部RAG桥接配置
        """
        return InternalRagBridgeSettings()

    @staticmethod
    def parse_cli_args() -> None:
        """
        解析命令行参数
        """
        # 检查是否在alembic环境中运行，如果是则跳过参数解析
        if 'alembic' in sys.argv[0] or any('alembic' in arg for arg in sys.argv):
            ini_config = configparser.ConfigParser()
            ini_config.read('alembic.ini', encoding='utf-8')
            if 'settings' in ini_config:
                # 获取env选项
                env_value = ini_config['settings'].get('env')
                os.environ['APP_ENV'] = env_value if env_value else 'dev'
        elif 'uvicorn' in sys.argv[0]:
            # 使用uvicorn启动时，命令行参数需要按照uvicorn的文档进行配置，无法自定义参数
            pass
        else:
            # 使用argparse定义命令行参数
            parser = argparse.ArgumentParser(description='命令行参数')
            parser.add_argument('--env', type=str, default='', help='运行环境')
            # 解析命令行参数
            args = parser.parse_args()
            # 设置环境变量，如果未设置命令行参数，默认APP_ENV为dev
            os.environ['APP_ENV'] = args.env if args.env else 'dev'
        # 读取运行环境
        run_env = os.environ.get('APP_ENV', '')
        # 运行环境未指定时默认加载.env.dev
        env_file = '.env.dev'
        # 运行环境不为空时按命令行参数加载对应.env文件
        if run_env != '':
            env_file = f'.env.{run_env}'
        # 加载配置
        for candidate in (env_file, f'{env_file}.example'):
            if os.path.exists(candidate):
                load_dotenv(candidate)
                break


# 实例化获取配置类
get_config = GetConfig()
# 应用配置
AppConfig = get_config.get_app_config()
# Jwt配置
JwtConfig = get_config.get_jwt_config()
# 数据库配置
DataBaseConfig = get_config.get_database_config()
# Redis配置
RedisConfig = get_config.get_redis_config()
# 上传配置
UploadConfig = get_config.get_upload_config()
# RAG配置
RAGConfig = get_config.get_rag_config()
# 内部RAG桥接配置
InternalRagBridgeConfig = get_config.get_internal_rag_bridge_config()
