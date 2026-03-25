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
        allowed_kb_ids = set(visible_result.kb_ids)
        requested_kb_ids = query_request.kb_ids or visible_result.kb_ids
        final_kb_ids = []
        for kb_id in requested_kb_ids:
            try:
                normalized_kb_id = int(kb_id)
            except (TypeError, ValueError):
                continue
            if normalized_kb_id in allowed_kb_ids and normalized_kb_id not in final_kb_ids:
                final_kb_ids.append(normalized_kb_id)

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
