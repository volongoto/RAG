import asyncio
import io
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from config.env import RAGConfig, UploadConfig
from exceptions.exception import ServiceException
from utils.log_util import logger


class DocumentStorageService:
    """Document storage abstraction for local disk and optional MinIO."""

    MAX_DB_FILE_NAME_LENGTH = 255
    MAX_STORAGE_FILE_NAME_LENGTH = 120
    _client: Minio | None = None
    _bucket_ready = False

    @classmethod
    def storage_mode(cls) -> str:
        mode = getattr(RAGConfig, 'rag_document_storage', 'local') or 'local'
        return mode.strip().lower()

    @classmethod
    def is_minio_enabled(cls) -> bool:
        return cls.storage_mode() == 'minio'

    @classmethod
    def _normalize_file_name(cls, file_name: str) -> str:
        normalized = Path(file_name or '').name.strip()
        return normalized or f'document-{uuid.uuid4().hex}'

    @classmethod
    def _truncate_file_name(cls, file_name: str, max_length: int) -> str:
        normalized = cls._normalize_file_name(file_name)
        if len(normalized) <= max_length:
            return normalized

        suffix = Path(normalized).suffix
        stem = Path(normalized).stem
        hash_suffix = uuid.uuid5(uuid.NAMESPACE_URL, normalized).hex[:8]
        reserved_length = len(suffix) + len(hash_suffix) + 1
        available_stem_length = max(1, max_length - reserved_length)
        truncated_stem = stem[:available_stem_length]
        return f'{truncated_stem}_{hash_suffix}{suffix}'

    @classmethod
    def normalize_db_file_name(cls, file_name: str) -> str:
        return cls._truncate_file_name(file_name, cls.MAX_DB_FILE_NAME_LENGTH)

    @classmethod
    def normalize_storage_file_name(cls, file_name: str) -> str:
        return cls._truncate_file_name(file_name, cls.MAX_STORAGE_FILE_NAME_LENGTH)

    @classmethod
    def _build_storage_key(cls, kb_id: int, file_name: str) -> str:
        safe_name = cls.normalize_storage_file_name(file_name)
        return f"rag/{kb_id}/{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex}_{safe_name}"

    @classmethod
    def _normalize_minio_endpoint(cls, endpoint: str) -> tuple[str, bool]:
        normalized_endpoint = (endpoint or '').strip()
        secure = bool(getattr(RAGConfig, 'rag_minio_secure', False))
        if not normalized_endpoint:
            return normalized_endpoint, secure

        if '://' not in normalized_endpoint:
            return normalized_endpoint, secure

        parsed = urlparse(normalized_endpoint)
        if not parsed.netloc:
            raise ServiceException(message='MinIO endpoint format is invalid')
        if parsed.path not in ('', '/'):
            raise ServiceException(message='MinIO endpoint must not contain a path')
        if parsed.scheme == 'https':
            secure = True
        elif parsed.scheme == 'http':
            secure = False
        else:
            raise ServiceException(message='MinIO endpoint scheme must be http or https')
        return parsed.netloc, secure

    @classmethod
    def _get_minio_client(cls) -> Minio:
        if cls._client is not None:
            return cls._client

        endpoint = (getattr(RAGConfig, 'rag_minio_endpoint', '') or '').strip()
        access_key = getattr(RAGConfig, 'rag_minio_access_key', '') or ''
        secret_key = getattr(RAGConfig, 'rag_minio_secret_key', '') or ''
        if not endpoint or not access_key or not secret_key:
            raise ServiceException(message='MinIO storage is enabled but configuration is incomplete')

        endpoint, secure = cls._normalize_minio_endpoint(endpoint)

        cls._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=(getattr(RAGConfig, 'rag_minio_region', '') or None),
        )
        return cls._client

    @classmethod
    def _ensure_local_parent_dir(cls, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)

    @classmethod
    def _ensure_minio_bucket(cls) -> None:
        if cls._bucket_ready:
            return

        try:
            client = cls._get_minio_client()
            bucket_name = getattr(RAGConfig, 'rag_minio_bucket', 'cradle-rag')
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
            cls._bucket_ready = True
        except Exception as exc:
            logger.exception(f'Failed to initialize MinIO bucket: {exc}')
            raise ServiceException(message='MinIO is unavailable or misconfigured') from exc

    @classmethod
    async def store_uploaded_file(cls, kb_id: int, file_name: str, file_content: bytes) -> str:
        if cls.is_minio_enabled():
            return await cls._store_file_to_minio(kb_id, file_name, file_content)
        return await cls._store_file_to_local(kb_id, file_name, file_content)

    @classmethod
    async def _store_file_to_local(cls, kb_id: int, file_name: str, file_content: bytes) -> str:
        safe_name = cls._normalize_file_name(file_name)
        storage_path = os.path.abspath(os.path.join(UploadConfig.UPLOAD_PATH, cls._build_storage_key(kb_id, safe_name)))

        def _write_local_file() -> str:
            cls._ensure_local_parent_dir(storage_path)
            with open(storage_path, 'wb') as file_obj:
                file_obj.write(file_content)
            return storage_path

        return await asyncio.to_thread(_write_local_file)

    @classmethod
    async def _store_file_to_minio(cls, kb_id: int, file_name: str, file_content: bytes) -> str:
        object_key = cls._build_storage_key(kb_id, file_name)
        bucket_name = getattr(RAGConfig, 'rag_minio_bucket', 'cradle-rag')
        content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'

        def _upload_to_minio() -> str:
            cls._ensure_minio_bucket()
            client = cls._get_minio_client()
            client.put_object(
                bucket_name,
                object_key,
                io.BytesIO(file_content),
                length=len(file_content),
                content_type=content_type,
            )
            return object_key

        try:
            return await asyncio.to_thread(_upload_to_minio)
        except Exception as exc:
            logger.exception(f'Failed to upload document to MinIO: {object_key}, error={exc}')
            raise ServiceException(message='文档上传到对象存储失败，请检查 MinIO 配置和容器状态') from exc

    @classmethod
    async def prepare_parse_file(cls, stored_path: str, file_name: str) -> tuple[str, bool]:
        if not stored_path:
            raise ServiceException(message='Document storage path is missing')

        if not cls.is_minio_enabled():
            local_path = os.path.abspath(stored_path)
            if not os.path.exists(local_path):
                raise ServiceException(message='Document file is missing in storage, please re-upload')
            return local_path, False

        bucket_name = getattr(RAGConfig, 'rag_minio_bucket', 'cradle-rag')
        suffix = Path(file_name or stored_path).suffix
        temp_dir = os.path.abspath(os.path.join(UploadConfig.DOWNLOAD_PATH, 'rag_parse_cache'))
        temp_path = os.path.join(temp_dir, f'{uuid.uuid4().hex}{suffix}')

        def _download_from_minio() -> str:
            os.makedirs(temp_dir, exist_ok=True)
            cls._ensure_minio_bucket()
            client = cls._get_minio_client()
            client.fget_object(bucket_name, stored_path, temp_path)
            return temp_path

        try:
            return await asyncio.to_thread(_download_from_minio), True
        except S3Error as exc:
            logger.error(f'Failed to fetch document from MinIO: {stored_path}, error={exc}')
            raise ServiceException(message='Document file is missing in object storage, please re-upload') from exc

    @classmethod
    async def cleanup_parse_file(cls, file_path: str, should_delete: bool) -> None:
        if not should_delete or not file_path:
            return

        def _remove_file() -> None:
            if os.path.exists(file_path):
                os.remove(file_path)

        await asyncio.to_thread(_remove_file)

    @classmethod
    async def delete_stored_file(cls, stored_path: str) -> None:
        if not stored_path:
            return

        if cls.is_minio_enabled():
            bucket_name = getattr(RAGConfig, 'rag_minio_bucket', 'cradle-rag')

            def _delete_minio_object() -> None:
                try:
                    client = cls._get_minio_client()
                    client.remove_object(bucket_name, stored_path)
                except S3Error as exc:
                    logger.warning(f'Failed to remove MinIO object: {stored_path}, error={exc}')

            await asyncio.to_thread(_delete_minio_object)
            return

        def _delete_local_file() -> None:
            if os.path.exists(stored_path):
                os.remove(stored_path)

        await asyncio.to_thread(_delete_local_file)
