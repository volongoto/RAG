from collections.abc import Sequence
from typing import Union

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_rag.entity.do.rag_do import RagKnowledgeBase
from module_rag.entity.vo.rag_vo import KnowledgeBaseModel


class KnowledgeBaseDao:
    """
    知识库管理模块数据库操作层
    """

    @classmethod
    async def get_kb_by_id(cls, db: AsyncSession, kb_id: int) -> Union[RagKnowledgeBase, None]:
        """
        根据知识库ID获取知识库信息
        """
        kb_info = (
            (await db.execute(select(RagKnowledgeBase).where(RagKnowledgeBase.kb_id == kb_id, RagKnowledgeBase.del_flag == '0')))
            .scalars()
            .first()
        )
        return kb_info

    @classmethod
    async def get_kb_list(
        cls, db: AsyncSession, query_object: KnowledgeBaseModel, data_scope_sql: ColumnElement
    ) -> Sequence[RagKnowledgeBase]:
        """
        根据查询参数获取知识库列表
        """
        query = (
            select(RagKnowledgeBase)
            .where(
                RagKnowledgeBase.del_flag == '0',
                RagKnowledgeBase.kb_id == query_object.kb_id if query_object.kb_id else True,
                RagKnowledgeBase.kb_name.like(f'%{query_object.kb_name}%') if query_object.kb_name else True,
                RagKnowledgeBase.kb_type == query_object.kb_type if query_object.kb_type else True,
                RagKnowledgeBase.status == query_object.status if query_object.status else True,
                data_scope_sql,
            )
            .order_by(RagKnowledgeBase.create_time.desc())
            .distinct()
        )
        kb_list = (await db.execute(query)).scalars().all()
        return kb_list

    @classmethod
    async def get_kb_list_by_ids(cls, db: AsyncSession, kb_ids: list[int]) -> Sequence[RagKnowledgeBase]:
        """
        根据知识库ID列表获取知识库列表
        """
        query = select(RagKnowledgeBase).where(
            RagKnowledgeBase.del_flag == '0',
            RagKnowledgeBase.status == '0',
            RagKnowledgeBase.kb_id.in_(kb_ids),
        )
        kb_list = (await db.execute(query)).scalars().all()
        return kb_list

    @classmethod
    async def add_kb_dao(cls, db: AsyncSession, kb: KnowledgeBaseModel) -> RagKnowledgeBase:
        """
        新增知识库
        """
        db_kb = RagKnowledgeBase(**kb.model_dump(exclude_unset=True))
        db.add(db_kb)
        await db.flush()
        return db_kb

    @classmethod
    async def edit_kb_dao(cls, db: AsyncSession, kb: dict) -> None:
        """
        编辑知识库
        """
        await db.execute(update(RagKnowledgeBase).where(RagKnowledgeBase.kb_id == kb['kb_id']), [kb])

    @classmethod
    async def delete_kb_dao(cls, db: AsyncSession, kb: KnowledgeBaseModel) -> None:
        """
        删除知识库
        """
        await db.execute(
            update(RagKnowledgeBase)
            .where(RagKnowledgeBase.kb_id == kb.kb_id)
            .values(del_flag='2', update_by=kb.update_by, update_time=kb.update_time)
        )

    @classmethod
    async def count_kb_documents_dao(cls, db: AsyncSession, kb_id: int) -> int:
        """
        统计知识库下的文档数量
        """
        from module_rag.entity.do.rag_do import RagDocument

        count = (
            await db.execute(
                select(func.count('*')).select_from(RagDocument).where(RagDocument.kb_id == kb_id, RagDocument.del_flag == '0')
            )
        ).scalar()
        return count or 0

    @classmethod
    async def check_kb_name_unique_dao(cls, db: AsyncSession, kb_name: str, kb_type: str, dept_id: int = None, user_id: int = None, exclude_kb_id: int = None) -> bool:
        """
        校验知识库名称是否唯一
        """
        conditions = [
            RagKnowledgeBase.kb_name == kb_name,
            RagKnowledgeBase.kb_type == kb_type,
            RagKnowledgeBase.del_flag == '0',
        ]
        if kb_type == 'dept' and dept_id:
            conditions.append(RagKnowledgeBase.dept_id == dept_id)
        if kb_type == 'personal' and user_id:
            conditions.append(RagKnowledgeBase.user_id == user_id)
        if exclude_kb_id:
            conditions.append(RagKnowledgeBase.kb_id != exclude_kb_id)
        
        kb = (await db.execute(select(RagKnowledgeBase).where(*conditions))).scalars().first()
        return kb is None
