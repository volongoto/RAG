from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.constant import CommonConstant
from common.vo import CrudResponseModel
from exceptions.exception import ServiceException, ServiceWarning
from module_admin.entity.do.dept_do import SysDept
from module_admin.entity.do.role_do import SysRoleDept
from module_rag.dao.knowledge_base_dao import KnowledgeBaseDao
from module_rag.entity.do.rag_do import RagKnowledgeBase
from module_rag.entity.vo.rag_vo import DeleteKnowledgeBaseModel, KnowledgeBaseModel, KnowledgeBaseQueryModel
from utils.common_util import CamelCaseUtil


class KnowledgeBaseService:
    """
    知识库管理模块服务层
    """

    @classmethod
    async def get_kb_list_services(
        cls, query_db: AsyncSession, page_object: KnowledgeBaseQueryModel, data_scope_sql: ColumnElement
    ) -> list[dict[str, Any]]:
        """
        获取知识库列表服务
        """
        kb_query = KnowledgeBaseModel(
            kb_id=page_object.kb_id,
            kb_name=page_object.kb_name,
            kb_type=page_object.kb_type,
            status=page_object.status,
        )
        kb_list_result = await KnowledgeBaseDao.get_kb_list(query_db, kb_query, data_scope_sql)
        return CamelCaseUtil.transform_result(kb_list_result)

    @classmethod
    async def get_kb_detail_services(cls, query_db: AsyncSession, kb_id: int) -> KnowledgeBaseModel:
        """
        获取知识库详情服务
        """
        kb = await KnowledgeBaseDao.get_kb_by_id(query_db, kb_id)
        result = KnowledgeBaseModel(**CamelCaseUtil.transform_result(kb)) if kb else KnowledgeBaseModel()
        return result

    @classmethod
    async def check_kb_data_scope_services(
        cls, query_db: AsyncSession, kb_id: int, data_scope_sql: ColumnElement
    ) -> CrudResponseModel:
        """
        校验知识库是否有数据权限
        """
        kb_query = KnowledgeBaseModel(kb_id=kb_id)
        kbs = await KnowledgeBaseDao.get_kb_list(query_db, kb_query, data_scope_sql)
        if kbs:
            return CrudResponseModel(is_success=True, message='校验通过')
        raise ServiceException(message='没有权限访问知识库数据')

    @classmethod
    async def add_kb_services(cls, query_db: AsyncSession, page_object: KnowledgeBaseModel) -> CrudResponseModel:
        """
        新增知识库服务
        """
        if not await KnowledgeBaseDao.check_kb_name_unique_dao(
            query_db,
            page_object.kb_name,
            page_object.kb_type,
            page_object.dept_id,
            page_object.user_id,
        ):
            raise ServiceException(message=f'新增知识库{page_object.kb_name}失败，知识库名称已存在')
        try:
            await KnowledgeBaseDao.add_kb_dao(query_db, page_object)
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_kb_services(cls, query_db: AsyncSession, page_object: KnowledgeBaseModel) -> CrudResponseModel:
        """
        编辑知识库服务
        """
        if not await KnowledgeBaseDao.check_kb_name_unique_dao(
            query_db,
            page_object.kb_name,
            page_object.kb_type,
            page_object.dept_id,
            page_object.user_id,
            page_object.kb_id,
        ):
            raise ServiceException(message=f'修改知识库{page_object.kb_name}失败，知识库名称已存在')
        try:
            edit_kb = page_object.model_dump(exclude_unset=True)
            await KnowledgeBaseDao.edit_kb_dao(query_db, edit_kb)
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='更新成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def delete_kb_services(cls, query_db: AsyncSession, page_object: DeleteKnowledgeBaseModel) -> CrudResponseModel:
        """
        删除知识库服务
        """
        if page_object.kb_ids:
            kb_id_list = page_object.kb_ids.split(',')
            try:
                from module_rag.dao.chunk_dao import ChunkDao
                from module_rag.dao.document_dao import DocumentDao

                for kb_id in kb_id_list:
                    doc_count = await KnowledgeBaseDao.count_kb_documents_dao(query_db, int(kb_id))
                    if doc_count > 0:
                        raise ServiceWarning(message=f'知识库下存在{doc_count}个文档，不允许删除')

                    await KnowledgeBaseDao.delete_kb_dao(
                        query_db, KnowledgeBaseModel(kbId=int(kb_id), updateBy=page_object.update_by, updateTime=page_object.update_time)
                    )
                await query_db.commit()
                return CrudResponseModel(is_success=True, message='删除成功')
            except Exception as e:
                await query_db.rollback()
                raise e
        else:
            raise ServiceException(message='传入知识库ID为空')

    @classmethod
    async def get_kb_tree_services(
        cls, query_db: AsyncSession, data_scope_sql: ColumnElement
    ) -> list[dict[str, Any]]:
        """
        获取知识库树信息服务（用于下拉选择）
        """
        kb_query = KnowledgeBaseModel(status='0')
        kb_list_result = await KnowledgeBaseDao.get_kb_list(query_db, kb_query, data_scope_sql)
        
        dept_kbs = [kb for kb in kb_list_result if kb.kb_type == 'dept']
        personal_kbs = [kb for kb in kb_list_result if kb.kb_type == 'personal']
        
        result = []
        if dept_kbs:
            result.append({
                'id': 'dept',
                'label': '部门知识库',
                'children': [{'id': kb.kb_id, 'label': kb.kb_name} for kb in dept_kbs]
            })
        if personal_kbs:
            result.append({
                'id': 'personal',
                'label': '个人知识库',
                'children': [{'id': kb.kb_id, 'label': kb.kb_name} for kb in personal_kbs]
            })
        return result


class KnowledgeBaseDataScope:
    """
    知识库数据权限依赖
    """

    def __init__(self, query_alias: RagKnowledgeBase = RagKnowledgeBase):
        self.query_alias = query_alias

    async def __call__(self, request: Request) -> ColumnElement:
        from common.context import RequestContext

        current_user = RequestContext.get_current_user()
        user_id = current_user.user.user_id
        dept_id = current_user.user.dept_id

        param_sql_list = []
        for role in current_user.user.role:
            if current_user.user.admin or role.data_scope == '1':
                param_sql_list = [True]
                break

            if role.data_scope == '2':
                param_sql_list.append(
                    or_(
                        self.query_alias.kb_type == 'personal',
                        self.query_alias.dept_id.in_(
                            select(SysRoleDept.dept_id).where(SysRoleDept.role_id == role.role_id)
                        ),
                    )
                )

            elif role.data_scope == '3':
                param_sql_list.append(
                    or_(
                        self.query_alias.kb_type == 'personal',
                        self.query_alias.dept_id == dept_id,
                    )
                )

            elif role.data_scope == '4':
                param_sql_list.append(
                    or_(
                        self.query_alias.kb_type == 'personal',
                        self.query_alias.dept_id.in_(
                            select(SysDept.dept_id).where(
                                or_(SysDept.dept_id == dept_id, func.find_in_set(dept_id, SysDept.ancestors))
                            )
                        ),
                    )
                )

            elif role.data_scope == '5':
                param_sql_list.append(
                    or_(
                        self.query_alias.kb_type == 'personal',
                        self.query_alias.user_id == user_id,
                    )
                )

        return or_(*param_sql_list)
