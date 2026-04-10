import json
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.env import InternalRagBridgeConfig
from exceptions.exception import ServiceException
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.user_do import SysUser
from module_rag.entity.do.rag_do import RagKnowledgeBase
from module_rag.entity.vo.rag_vo import KnowledgeBaseModel, QueryRequestModel, QueryResponseModel
from module_rag.entity.vo.runtime_vo import (
    ExternalPrincipalModel,
    RetrieveRequestModel,
    RetrieveResponseModel,
    InternalVisibleKnowledgeBasesResponseModel,
    ResolvedPrincipalModel,
)
from module_rag.service.query_service import QueryService
from utils.common_util import CamelCaseUtil


class InternalRagBridgeService:
    @classmethod
    async def get_visible_knowledge_bases(
        cls,
        query_db: AsyncSession,
        principal: ExternalPrincipalModel,
    ) -> InternalVisibleKnowledgeBasesResponseModel:
        resolved_principal = await cls.resolve_principal(query_db, principal)
        kb_rows = await cls._load_visible_kbs(query_db, resolved_principal)
        kb_models = [KnowledgeBaseModel(**CamelCaseUtil.transform_result(row)) for row in kb_rows]
        return InternalVisibleKnowledgeBasesResponseModel(
            principal=resolved_principal,
            kb_ids=[int(item.kb_id) for item in kb_models if item.kb_id is not None],
            knowledge_bases=kb_models,
        )

    @classmethod
    async def query_knowledge_bases(
        cls,
        query_db: AsyncSession,
        principal: ExternalPrincipalModel,
        query_request: QueryRequestModel,
    ) -> QueryResponseModel:
        visible_result = await cls.get_visible_knowledge_bases(query_db, principal)
        final_kb_ids = cls._resolve_final_kb_ids(query_request.kb_ids, visible_result.kb_ids)

        if not final_kb_ids:
            raise ServiceException(message='当前主体在知识库系统中没有可访问的知识库')

        effective_query = query_request.model_copy(update={'kb_ids': final_kb_ids})
        query_service = QueryService()
        caller_meta = {
            'source_system': principal.source_system,
            'external_user_id': principal.external_user_id,
            'external_user_name': principal.external_user_name,
            'external_dept_id': principal.external_dept_id,
            'mapped_user_id': visible_result.principal.mapped_user_id,
            'mapped_dept_id': visible_result.principal.mapped_dept_id,
            'resolution_mode': visible_result.principal.resolution_mode,
        }
        return await query_service.query_services(
            query_db,
            effective_query,
            visible_result.principal.mapped_user_id or 0,
            caller_meta=caller_meta,
        )

    @classmethod
    async def retrieve_knowledge_bases(
        cls,
        query_db: AsyncSession,
        principal: ExternalPrincipalModel,
        retrieve_request: RetrieveRequestModel,
    ) -> RetrieveResponseModel:
        visible_result = await cls.get_visible_knowledge_bases(query_db, principal)
        final_kb_ids = cls._resolve_final_kb_ids(retrieve_request.kb_ids, visible_result.kb_ids)

        if not final_kb_ids:
            raise ServiceException(message='当前主体在知识库系统中没有可访问的知识库')

        effective_request = retrieve_request.model_copy(update={'kb_ids': final_kb_ids})
        query_service = QueryService()
        return await query_service.retrieve_services(query_db, effective_request)

    @classmethod
    async def resolve_principal(
        cls,
        query_db: AsyncSession,
        principal: ExternalPrincipalModel,
    ) -> ResolvedPrincipalModel:
        source_system = principal.source_system
        external_user_id = (principal.external_user_id or '').strip() or None
        external_user_name = (principal.external_user_name or '').strip() or None
        external_dept_id = (principal.external_dept_id or '').strip() or None

        resolution_mode = 'unresolved'
        user_row: SysUser | None = None
        dept_row: SysDept | None = None

        user_id_map = cls._load_json_map(InternalRagBridgeConfig.rag_external_user_map)
        user_name_map = cls._load_json_map(InternalRagBridgeConfig.rag_external_user_name_map)
        dept_id_map = cls._load_json_map(InternalRagBridgeConfig.rag_external_dept_map)

        mapped_user_id = cls._coerce_map_value(user_id_map.get(external_user_id)) if external_user_id else None
        if mapped_user_id is not None:
            user_row = await cls._get_user_by_id(query_db, mapped_user_id)
            if user_row:
                resolution_mode = 'user_id_map'

        if user_row is None and external_user_name:
            mapped_user_id = cls._coerce_map_value(user_name_map.get(external_user_name))
            if mapped_user_id is None:
                mapped_user_id = cls._coerce_map_value(user_name_map.get(external_user_name.lower()))
            if mapped_user_id is not None:
                user_row = await cls._get_user_by_id(query_db, mapped_user_id)
                if user_row:
                    resolution_mode = 'user_name_map'

        if user_row is None and external_user_id and InternalRagBridgeConfig.rag_internal_allow_direct_user_id_fallback:
            direct_user_id = cls._coerce_map_value(external_user_id)
            if direct_user_id is not None:
                user_row = await cls._get_user_by_id(query_db, direct_user_id)
                if user_row:
                    mapped_user_id = direct_user_id
                    resolution_mode = 'direct_user_id'

        if user_row is None and external_user_name:
            user_row = await cls._get_user_by_name(query_db, external_user_name)
            if user_row:
                mapped_user_id = int(user_row.user_id)
                resolution_mode = 'username_lookup'

        mapped_dept_id = None
        mapped_dept_name = None
        mapped_user_name = None
        is_admin = False

        if user_row is not None:
            mapped_user_id = int(user_row.user_id)
            mapped_user_name = user_row.user_name
            is_admin = int(user_row.user_id) == 1
            if user_row.dept_id is not None:
                dept_row = await cls._get_dept_by_id(query_db, int(user_row.dept_id))
                if dept_row:
                    mapped_dept_id = int(dept_row.dept_id)
                    mapped_dept_name = dept_row.dept_name
                else:
                    mapped_dept_id = int(user_row.dept_id)
        else:
            if external_dept_id:
                mapped_dept_id = cls._coerce_map_value(dept_id_map.get(external_dept_id))
                if mapped_dept_id is not None:
                    dept_row = await cls._get_dept_by_id(query_db, mapped_dept_id)
                    if dept_row:
                        mapped_dept_name = dept_row.dept_name
                    resolution_mode = 'dept_id_map'
            if mapped_dept_id is None and external_dept_id and InternalRagBridgeConfig.rag_internal_allow_direct_dept_id_fallback:
                mapped_dept_id = cls._coerce_map_value(external_dept_id)
                if mapped_dept_id is not None:
                    dept_row = await cls._get_dept_by_id(query_db, mapped_dept_id)
                    if dept_row:
                        mapped_dept_name = dept_row.dept_name
                        resolution_mode = 'direct_dept_id'
                    else:
                        mapped_dept_id = None

        return ResolvedPrincipalModel(
            source_system=source_system,
            external_user_id=external_user_id,
            external_user_name=external_user_name,
            external_dept_id=external_dept_id,
            mapped_user_id=mapped_user_id,
            mapped_user_name=mapped_user_name,
            mapped_dept_id=mapped_dept_id,
            mapped_dept_name=mapped_dept_name,
            is_admin=is_admin,
            resolution_mode=resolution_mode,
        )

    @classmethod
    async def _load_visible_kbs(
        cls,
        query_db: AsyncSession,
        principal: ResolvedPrincipalModel,
    ) -> list[RagKnowledgeBase]:
        query = select(RagKnowledgeBase).where(RagKnowledgeBase.del_flag == '0', RagKnowledgeBase.status == '0')
        if not principal.is_admin:
            access_conditions = []
            if principal.mapped_dept_id is not None:
                access_conditions.append(
                    and_(RagKnowledgeBase.kb_type == 'dept', RagKnowledgeBase.dept_id == principal.mapped_dept_id)
                )
            if principal.mapped_user_id is not None:
                access_conditions.append(
                    and_(RagKnowledgeBase.kb_type == 'personal', RagKnowledgeBase.user_id == principal.mapped_user_id)
                )
            if not access_conditions:
                return []
            query = query.where(or_(*access_conditions))
        query = query.order_by(RagKnowledgeBase.create_time.desc())
        return list((await query_db.execute(query)).scalars().all())

    @classmethod
    async def _get_user_by_id(cls, query_db: AsyncSession, user_id: int) -> SysUser | None:
        return (
            (
                await query_db.execute(
                    select(SysUser).where(SysUser.user_id == user_id, SysUser.status == '0', SysUser.del_flag == '0')
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def _get_user_by_name(cls, query_db: AsyncSession, user_name: str) -> SysUser | None:
        return (
            (
                await query_db.execute(
                    select(SysUser).where(
                        SysUser.user_name == user_name,
                        SysUser.status == '0',
                        SysUser.del_flag == '0',
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def _get_dept_by_id(cls, query_db: AsyncSession, dept_id: int) -> SysDept | None:
        return (
            (
                await query_db.execute(
                    select(SysDept).where(SysDept.dept_id == dept_id, SysDept.status == '0', SysDept.del_flag == '0')
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def upload_document(
        cls,
        query_db: AsyncSession,
        principal: ExternalPrincipalModel,
        kb_id: int,
        file_name: str,
        file_content: bytes,
        file_type: str | None = None,
        redis=None,
    ) -> dict[str, Any]:
        """
        上传文档到知识库（供外部系统调用）

        Args:
            query_db: 数据库会话
            principal: 外部调用方身份
            kb_id: 目标知识库 ID
            file_name: 文件名
            file_content: 文件内容（二进制）
            file_type: 文件类型（可选，自动从文件名推断）
            redis: Redis 客户端

        Returns:
            上传结果字典
        """
        from module_rag.service.document_storage_service import DocumentStorageService
        from module_rag.service.rag_service import DocumentService

        # 解析外部主体，获取映射的本地用户
        resolved_principal = await cls.resolve_principal(query_db, principal)

        # 检查知识库访问权限
        visible_result = await cls.get_visible_knowledge_bases(query_db, principal)
        allowed_kb_ids = set(visible_result.kb_ids)

        if kb_id not in allowed_kb_ids:
            raise ServiceException(message=f'没有权限访问知识库 {kb_id}')

        # 检查文件类型
        if file_type is None:
            file_type = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''

        allowed_extensions = {'pdf', 'doc', 'docx', 'txt', 'md', 'html'}
        if file_type.lower() not in allowed_extensions:
            raise ServiceException(
                message=f'不支持的文件类型: {file_type}，支持的类型: {", ".join(allowed_extensions)}'
            )

        # 检查文件大小（最大 200MB）
        max_size = 200 * 1024 * 1024  # 200MB
        if len(file_content) > max_size:
            raise ServiceException(message=f'文件大小超过限制 (最大 200MB)')

        # 规范化文件名
        normalized_file_name = DocumentStorageService.normalize_db_file_name(file_name)

        # 存储文件
        file_path = await DocumentStorageService.store_uploaded_file(kb_id, normalized_file_name, file_content)

        # 创建文档记录
        create_by = resolved_principal.mapped_user_name or principal.external_user_name or 'system'
        upload_result = await DocumentService.upload_document_services(
            query_db,
            redis,
            kb_id=kb_id,
            file_name=normalized_file_name,
            file_path=file_path,
            file_size=len(file_content),
            file_type=file_type.lower(),
            create_by=create_by,
        )

        return {
            'doc_id': upload_result.data.get('doc_id') if hasattr(upload_result, 'data') else 0,
            'file_name': normalized_file_name,
            'file_size': len(file_content),
            'parse_status': '0',
            'message': upload_result.message if hasattr(upload_result, 'message') else '文档上传成功',
        }

    @classmethod
    async def get_document_list(
        cls,
        query_db: AsyncSession,
        principal: ExternalPrincipalModel,
        kb_id: int | None = None,
        page_num: int = 1,
        page_size: int = 10,
        redis=None,
    ) -> dict[str, Any]:
        """
        获取文档列表（供外部系统调用）

        Args:
            query_db: 数据库会话
            principal: 外部调用方身份
            kb_id: 知识库 ID（可选）
            page_num: 页码
            page_size: 每页数量
            redis: Redis 客户端

        Returns:
            文档列表和分页信息
        """
        from module_rag.entity.vo.rag_vo import DocumentQueryModel
        from module_rag.service.rag_service import DocumentService

        # 检查权限
        visible_result = await cls.get_visible_knowledge_bases(query_db, principal)
        allowed_kb_ids = set(visible_result.kb_ids)

        if kb_id is not None and kb_id not in allowed_kb_ids:
            raise ServiceException(message=f'没有权限访问知识库 {kb_id}')

        # 构建查询条件
        query_model = DocumentQueryModel(
            kb_id=kb_id,
            page_num=page_num,
            page_size=page_size,
        )

        # 查询文档列表
        doc_list = await DocumentService.get_doc_list_services(query_db, query_model, redis=redis)

        return {
            'principal': visible_result.principal,
            'kb_ids': list(allowed_kb_ids),
            'documents': doc_list,
            'page_num': page_num,
            'page_size': page_size,
        }

    @classmethod
    async def delete_document(
        cls,
        query_db: AsyncSession,
        principal: ExternalPrincipalModel,
        doc_id: int,
        redis=None,
    ) -> dict[str, Any]:
        """
        删除文档（供外部系统调用）

        Args:
            query_db: 数据库会话
            principal: 外部调用方身份
            doc_id: 文档 ID
            redis: Redis 客户端

        Returns:
            删除结果
        """
        from module_rag.service.rag_service import DocumentService

        # 检查权限（通过可见知识库间接验证）
        visible_result = await cls.get_visible_knowledge_bases(query_db, principal)

        # 执行删除
        update_by = visible_result.principal.mapped_user_name or principal.external_user_name or 'system'
        delete_result = await DocumentService.delete_document_services(
            query_db, redis, str(doc_id), update_by
        )

        return {
            'doc_id': doc_id,
            'message': delete_result.message if hasattr(delete_result, 'message') else '文档删除成功',
        }

    @staticmethod
    def _load_json_map(raw_value: str) -> dict[str, Any]:
        try:
            data = json.loads(raw_value or '{}')
        except json.JSONDecodeError as exc:
            raise ServiceException(message=f'内部桥接映射配置不是合法 JSON: {exc}') from exc
        if isinstance(data, dict):
            return data
        raise ServiceException(message='内部桥接映射配置必须是 JSON 对象')

    @staticmethod
    def _coerce_map_value(raw_value: Any) -> int | None:
        if raw_value is None or raw_value == '':
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _resolve_final_kb_ids(cls, requested_kb_ids: list[int] | None, visible_kb_ids: list[int]) -> list[int]:
        allowed_kb_ids = set(visible_kb_ids)
        candidate_kb_ids = requested_kb_ids or visible_kb_ids
        final_kb_ids: list[int] = []
        for kb_id in candidate_kb_ids:
            try:
                normalized_kb_id = int(kb_id)
            except (TypeError, ValueError):
                continue
            if normalized_kb_id in allowed_kb_ids and normalized_kb_id not in final_kb_ids:
                final_kb_ids.append(normalized_kb_id)
        return final_kb_ids
