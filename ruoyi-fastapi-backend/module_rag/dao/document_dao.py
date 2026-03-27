from collections.abc import Sequence
from typing import Union

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_rag.entity.do.rag_do import RagDocument
from module_rag.entity.vo.rag_vo import DocumentModel


class DocumentDao:
    """
    文档管理模块数据库操作层
    """

    @classmethod
    async def get_doc_by_id(cls, db: AsyncSession, doc_id: int) -> Union[RagDocument, None]:
        """
        根据文档ID获取文档信息
        """
        doc_info = (
            (await db.execute(select(RagDocument).where(RagDocument.doc_id == doc_id, RagDocument.del_flag == '0')))
            .scalars()
            .first()
        )
        return doc_info

    @classmethod
    async def get_doc_list(
        cls, db: AsyncSession, query_object: DocumentModel, data_scope_sql: ColumnElement = None
    ) -> Sequence[RagDocument]:
        """
        根据查询参数获取文档列表
        """
        conditions = [
            RagDocument.del_flag == '0',
            RagDocument.doc_id == query_object.doc_id if query_object.doc_id else True,
            RagDocument.kb_id == query_object.kb_id if query_object.kb_id else True,
            RagDocument.file_name.like(f'%{query_object.file_name}%') if query_object.file_name else True,
            RagDocument.file_type == query_object.file_type if query_object.file_type else True,
            RagDocument.parse_status == query_object.parse_status if query_object.parse_status else True,
        ]
        if data_scope_sql is not None:
            conditions.append(data_scope_sql)
        
        query = (
            select(RagDocument)
            .where(*conditions)
            .order_by(RagDocument.create_time.desc())
            .distinct()
        )
        doc_list = (await db.execute(query)).scalars().all()
        return doc_list

    @classmethod
    async def get_docs_by_parse_statuses(cls, db: AsyncSession, statuses: list[str]) -> Sequence[RagDocument]:
        """
        Get documents by parse status for task recovery.
        """
        query = (
            select(RagDocument)
            .where(RagDocument.del_flag == '0', RagDocument.parse_status.in_(statuses))
            .order_by(RagDocument.create_time.asc())
        )
        return (await db.execute(query)).scalars().all()

    @classmethod
    async def add_doc_dao(cls, db: AsyncSession, doc: DocumentModel) -> RagDocument:
        """
        新增文档
        """
        db_doc = RagDocument(**doc.model_dump(exclude_unset=True))
        db.add(db_doc)
        await db.flush()
        return db_doc

    @classmethod
    async def edit_doc_dao(cls, db: AsyncSession, doc: dict) -> None:
        """
        编辑文档
        """
        await db.execute(update(RagDocument).where(RagDocument.doc_id == doc['doc_id']), [doc])

    @classmethod
    async def update_parse_status_dao(
        cls,
        db: AsyncSession,
        doc_id: int,
        status: str,
        error_msg: str = None,
        chunk_count: int = None,
        clear_error: bool = False,
    ) -> None:
        """
        更新文档解析状态
        """
        values = {'parse_status': status, 'update_time': func.now()}
        if error_msg is not None:
            values['parse_error'] = error_msg
        elif clear_error:
            values['parse_error'] = None
        if chunk_count is not None:
            values['chunk_count'] = chunk_count
        await db.execute(
            update(RagDocument).where(RagDocument.doc_id == doc_id).values(values)
        )

    @classmethod
    async def delete_doc_dao(cls, db: AsyncSession, doc: DocumentModel) -> None:
        """
        删除文档
        """
        await db.execute(
            update(RagDocument)
            .where(RagDocument.doc_id == doc.doc_id)
            .values(del_flag='2', update_by=doc.update_by, update_time=doc.update_time)
        )

    @classmethod
    async def count_doc_chunks_dao(cls, db: AsyncSession, doc_id: int) -> int:
        """
        统计文档下的切片数量
        """
        from module_rag.entity.do.rag_do import RagChunk

        count = (
            await db.execute(
                select(func.count('*')).select_from(RagChunk).where(RagChunk.doc_id == doc_id, RagChunk.del_flag == '0')
            )
        ).scalar()
        return count or 0
