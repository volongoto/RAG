from collections.abc import Sequence
from typing import Union

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from module_rag.entity.do.rag_do import RagChunk
from module_rag.entity.vo.rag_vo import ChunkModel


class ChunkDao:
    """
    Chunk data access.
    """

    @classmethod
    async def get_chunk_by_id(cls, db: AsyncSession, chunk_id: int) -> Union[RagChunk, None]:
        chunk_info = (
            (await db.execute(select(RagChunk).where(RagChunk.chunk_id == chunk_id, RagChunk.del_flag == '0')))
            .scalars()
            .first()
        )
        return chunk_info

    @classmethod
    async def get_chunks_by_doc_id(cls, db: AsyncSession, doc_id: int) -> Sequence[RagChunk]:
        query = select(RagChunk).where(RagChunk.doc_id == doc_id, RagChunk.del_flag == '0').order_by(RagChunk.chunk_index)
        chunks = (await db.execute(query)).scalars().all()
        return chunks

    @classmethod
    async def add_chunk_dao(cls, db: AsyncSession, chunk: ChunkModel, embedding: list[float] = None) -> RagChunk:
        chunk_data = chunk.model_dump(exclude_unset=True)
        if embedding:
            chunk_data['embedding'] = embedding
        db_chunk = RagChunk(**chunk_data)
        db.add(db_chunk)
        await db.flush()
        return db_chunk

    @classmethod
    async def batch_add_chunks_dao(cls, db: AsyncSession, chunks: list[dict]) -> None:
        db_chunks = [RagChunk(**chunk) for chunk in chunks]
        db.add_all(db_chunks)
        await db.flush()

    @classmethod
    async def delete_chunks_by_doc_id_dao(cls, db: AsyncSession, doc_id: int) -> None:
        await db.execute(delete(RagChunk).where(RagChunk.doc_id == doc_id))

    @classmethod
    async def delete_chunks_by_kb_id_dao(cls, db: AsyncSession, kb_id: int) -> None:
        await db.execute(delete(RagChunk).where(RagChunk.kb_id == kb_id))

    @classmethod
    async def similarity_search(
        cls,
        db: AsyncSession,
        kb_ids: list[int],
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> Sequence:
        """
        Vector retrieval with document metadata join.
        """
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        query = text(
            f"""
            SELECT c.chunk_id, c.doc_id, c.kb_id, c.chunk_index, c.content, c.metadata,
                   d.file_name, d.file_path,
                   1 - (c.embedding <=> '{embedding_str}'::vector) AS similarity
            FROM rag_chunk c
            JOIN rag_document d ON d.doc_id = c.doc_id AND d.del_flag = '0'
            WHERE c.kb_id = ANY(:kb_ids)
              AND c.del_flag = '0'
              AND 1 - (c.embedding <=> '{embedding_str}'::vector) >= :threshold
            ORDER BY c.embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
            """
        )
        result = await db.execute(query, {'kb_ids': kb_ids, 'top_k': top_k, 'threshold': threshold})
        return result.fetchall()

    @classmethod
    async def lexical_search(cls, db: AsyncSession, kb_ids: list[int], query_text: str, top_k: int = 5) -> Sequence:
        """
        Lightweight lexical retrieval on chunk content.
        """
        text_query = text(
            """
            SELECT c.chunk_id, c.doc_id, c.kb_id, c.chunk_index, c.content, c.metadata,
                   d.file_name, d.file_path,
                   CASE
                     WHEN lower(c.content) = lower(:query_text) THEN 1.0
                     WHEN POSITION(lower(:query_text) IN lower(c.content)) > 0 THEN 0.8
                     ELSE 0.0
                   END AS lexical_score
            FROM rag_chunk c
            JOIN rag_document d ON d.doc_id = c.doc_id AND d.del_flag = '0'
            WHERE c.kb_id = ANY(:kb_ids)
              AND c.del_flag = '0'
              AND c.content ILIKE :like_pattern
            ORDER BY lexical_score DESC, c.create_time DESC
            LIMIT :top_k
            """
        )
        result = await db.execute(
            text_query,
            {
                'kb_ids': kb_ids,
                'query_text': query_text,
                'like_pattern': f'%{query_text}%',
                'top_k': top_k,
            },
        )
        return result.fetchall()

    @classmethod
    async def get_max_chunk_index(cls, db: AsyncSession, doc_id: int) -> int:
        result = await db.execute(select(func.max(RagChunk.chunk_index)).where(RagChunk.doc_id == doc_id, RagChunk.del_flag == '0'))
        return result.scalar() or 0
