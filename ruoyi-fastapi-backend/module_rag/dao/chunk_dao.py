from collections.abc import Sequence
from typing import Union

from pgvector.sqlalchemy import Vector
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from module_rag.entity.do.rag_do import RagChunk
from module_rag.entity.vo.rag_vo import ChunkModel


class ChunkDao:
    """
    文档切片管理模块数据库操作层
    """

    @classmethod
    async def get_chunk_by_id(cls, db: AsyncSession, chunk_id: int) -> Union[RagChunk, None]:
        """
        根据切片ID获取切片信息
        """
        chunk_info = (
            (await db.execute(select(RagChunk).where(RagChunk.chunk_id == chunk_id, RagChunk.del_flag == '0')))
            .scalars()
            .first()
        )
        return chunk_info

    @classmethod
    async def get_chunks_by_doc_id(cls, db: AsyncSession, doc_id: int) -> Sequence[RagChunk]:
        """
        根据文档ID获取所有切片
        """
        query = (
            select(RagChunk)
            .where(RagChunk.doc_id == doc_id, RagChunk.del_flag == '0')
            .order_by(RagChunk.chunk_index)
        )
        chunks = (await db.execute(query)).scalars().all()
        return chunks

    @classmethod
    async def add_chunk_dao(cls, db: AsyncSession, chunk: ChunkModel, embedding: list[float] = None) -> RagChunk:
        """
        新增切片
        """
        chunk_data = chunk.model_dump(exclude_unset=True)
        if embedding:
            chunk_data['embedding'] = embedding
        db_chunk = RagChunk(**chunk_data)
        db.add(db_chunk)
        await db.flush()
        return db_chunk

    @classmethod
    async def batch_add_chunks_dao(cls, db: AsyncSession, chunks: list[dict]) -> None:
        """
        批量新增切片
        """
        db_chunks = [RagChunk(**chunk) for chunk in chunks]
        db.add_all(db_chunks)
        await db.flush()

    @classmethod
    async def delete_chunks_by_doc_id_dao(cls, db: AsyncSession, doc_id: int) -> None:
        """
        删除文档的所有切片
        """
        await db.execute(
            delete(RagChunk).where(RagChunk.doc_id == doc_id)
        )

    @classmethod
    async def delete_chunks_by_kb_id_dao(cls, db: AsyncSession, kb_id: int) -> None:
        """
        删除知识库的所有切片
        """
        await db.execute(
            delete(RagChunk).where(RagChunk.kb_id == kb_id)
        )

    @classmethod
    async def similarity_search(
        cls, db: AsyncSession, kb_ids: list[int], query_embedding: list[float], top_k: int = 5, threshold: float = 0.0
    ) -> Sequence[RagChunk]:
        """
        向量相似度检索
        """
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        query = text(f"""
            SELECT chunk_id, doc_id, kb_id, chunk_index, content, metadata,
                   1 - (embedding <=> '{embedding_str}'::vector) as similarity
            FROM rag_chunk
            WHERE kb_id = ANY(:kb_ids)
              AND del_flag = '0'
              AND 1 - (embedding <=> '{embedding_str}'::vector) >= :threshold
            ORDER BY embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
        """)
        
        result = await db.execute(query, {'kb_ids': kb_ids, 'top_k': top_k, 'threshold': threshold})
        return result.fetchall()

    @classmethod
    async def get_max_chunk_index(cls, db: AsyncSession, doc_id: int) -> int:
        """
        获取文档的最大切片序号
        """
        result = await db.execute(
            select(func.max(RagChunk.chunk_index)).where(RagChunk.doc_id == doc_id, RagChunk.del_flag == '0')
        )
        return result.scalar() or 0
