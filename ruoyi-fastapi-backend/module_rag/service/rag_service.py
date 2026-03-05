import asyncio
import re
from datetime import datetime
from typing import Any

from config.env import RAGConfig
from llama_index.llms.openai_like import OpenAILike
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel
from exceptions.exception import ServiceException
from module_rag.dao.chunk_dao import ChunkDao
from module_rag.dao.document_dao import DocumentDao
from module_rag.entity.vo.rag_vo import DocumentModel
from module_rag.service.chunk_splitter import ChunkSplitter
from module_rag.service.embedding_service import EmbeddingService
from module_rag.service.parser.document_parser import DocumentParserFactory


class RAGEngine:
    """RAG query engine."""

    def __init__(self):
        self.llm = self._init_llm()
        self.embedding_service = EmbeddingService.get_instance()

    def _init_llm(self):
        """Initialize LLM client."""
        return OpenAILike(
            api_key=RAGConfig.rag_llm_api_key or 'sk-dummy',
            api_base=RAGConfig.rag_llm_api_base,
            model=RAGConfig.rag_llm_model,
            temperature=RAGConfig.rag_llm_temperature,
            max_tokens=RAGConfig.rag_llm_max_tokens,
        )

    async def query(
        self,
        query_db: AsyncSession,
        query_text: str,
        kb_ids: list[int],
        top_k: int = None,
        threshold: float = None,
    ) -> dict[str, Any]:
        """Execute a RAG query."""
        start_time = datetime.now()

        try:
            if query_db is None:
                raise ServiceException(message='Database session is not available')

            query_text = (query_text or '').strip()
            if not query_text:
                raise ServiceException(message='Query text cannot be empty')

            query_embedding = await self.embedding_service.get_text_embedding(query_text)

            top_k = top_k if top_k is not None else RAGConfig.rag_top_k
            threshold = threshold if threshold is not None else RAGConfig.rag_similarity_threshold

            chunks = await ChunkDao.similarity_search(query_db, kb_ids, query_embedding, top_k, threshold)

            # If strict threshold filtering returns no chunks, fallback to unfiltered top-k.
            if not chunks and threshold > 0:
                logger.warning(
                    f'No chunks found with threshold={threshold}, fallback to threshold=0.0, kb_ids={kb_ids}'
                )
                chunks = await ChunkDao.similarity_search(query_db, kb_ids, query_embedding, top_k, 0.0)

            if not chunks:
                return {
                    'answer_text': '\u5728\u6240\u9009\u77e5\u8bc6\u5e93\u4e2d\u672a\u68c0\u7d22\u5230\u4e0e\u95ee\u9898\u76f8\u5173\u7684\u4fe1\u606f\u3002',
                    'source_chunks': [],
                    'response_time': int((datetime.now() - start_time).total_seconds() * 1000),
                }

            context = self._build_context(chunks)
            prompt = self._build_prompt(query_text, context)
            answer = self._post_process_answer(await self._generate_answer(prompt))

            return {
                'answer_text': answer,
                'source_chunks': self._format_source_chunks(chunks),
                'response_time': int((datetime.now() - start_time).total_seconds() * 1000),
            }
        except Exception as e:
            logger.error(f'RAG query failed: {e}')
            raise ServiceException(message=f'Query failed: {e}')

    def _build_context(self, chunks: list) -> str:
        """Build textual context from retrieved chunks."""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            content = self._row_get(chunk, 'content')
            context_parts.append(f'[\u53c2\u8003\u5185\u5bb9 {i}]\n{content}')
        return '\n\n'.join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """Build prompt for LLM answer generation."""
        return (
            '\u4f60\u662f\u4f01\u4e1a\u77e5\u8bc6\u5e93\u95ee\u7b54\u52a9\u624b\uff0c\u8bf7\u4e25\u683c\u57fa\u4e8e\u53c2\u8003\u8d44\u6599\u56de\u7b54\u7528\u6237\u95ee\u9898\u3002\n'
            '\u56de\u7b54\u89c4\u5219\uff1a\n'
            '1. \u5fc5\u987b\u4f7f\u7528\u7b80\u4f53\u4e2d\u6587\u4f5c\u7b54\u3002\n'
            '2. \u5148\u7ed9\u7ed3\u8bba\uff0c\u518d\u7ed9\u7b80\u8981\u4f9d\u636e\uff1b\u6700\u591a 3 \u6761\u8981\u70b9\uff0c\u603b\u5b57\u6570\u4e0d\u8d85\u8fc7 180 \u5b57\u3002\n'
            '3. \u4e25\u7981\u91cd\u590d\u540c\u4e00\u53e5\u8bdd\u6216\u540c\u4e00\u542b\u4e49\u7684\u53e5\u5b50\u3002\n'
            '4. \u5982\u679c\u53c2\u8003\u8d44\u6599\u4e0d\u8db3\u4ee5\u56de\u7b54\uff0c\u8bf7\u660e\u786e\u8bf4\u660e\uff1a\u6839\u636e\u5f53\u524d\u77e5\u8bc6\u5e93\u5185\u5bb9\u65e0\u6cd5\u786e\u5b9a\u3002\n'
            '5. \u4e0d\u8981\u8f93\u51fa\u4e0e\u95ee\u9898\u65e0\u5173\u7684\u4fe1\u606f\u3002\n\n'
            f'\u53c2\u8003\u8d44\u6599\uff1a\n{context}\n\n'
            f'\u7528\u6237\u95ee\u9898\uff1a\n{query}\n'
        )

    async def _generate_answer(self, prompt: str) -> str:
        """Generate answer text from LLM."""
        try:
            response = await self.llm.acomplete(prompt)
            return str(response).strip()
        except Exception as e:
            logger.error(f'LLM answer generation failed: {e}')
            raise

    def _post_process_answer(self, answer: str) -> str:
        """
        Normalize model output to reduce repetitive content and keep it concise.
        """
        text = (answer or '').strip()
        if not text:
            return '\u6839\u636e\u5f53\u524d\u77e5\u8bc6\u5e93\u5185\u5bb9\u65e0\u6cd5\u786e\u5b9a\u3002'

        text = re.sub(r'\s+', ' ', text)
        segments = re.split(r'(?<=[。！？；.!?;])\s*', text)

        unique_segments: list[str] = []
        seen_keys: set[str] = set()
        for segment in segments:
            seg = segment.strip()
            if not seg:
                continue
            key = re.sub(r'[\s，。！？；,.!?;:：]+', '', seg)
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            unique_segments.append(seg)
            if len(unique_segments) >= 6:
                break

        cleaned = ' '.join(unique_segments).strip() if unique_segments else text
        if len(cleaned) > 240:
            cleaned = cleaned[:240].rstrip() + '...'
        return cleaned

    def _format_source_chunks(self, chunks: list) -> list[dict[str, Any]]:
        """Normalize chunk rows into response payload."""
        source_chunks = []
        for chunk in chunks:
            chunk_metadata = (
                self._row_get(chunk, 'chunk_metadata')
                or self._row_get(chunk, 'metadata')
                or {}
            )

            page_nums = chunk_metadata.get('page_nums') or []
            paragraph_indices = chunk_metadata.get('paragraph_indices') or []

            source_chunks.append(
                {
                    'chunk_id': self._row_get(chunk, 'chunk_id'),
                    'doc_id': self._row_get(chunk, 'doc_id'),
                    'doc_name': f"\u6587\u6863 {self._row_get(chunk, 'doc_id')}",
                    'content': self._row_get(chunk, 'content'),
                    'page_num': page_nums[0] if page_nums else None,
                    'paragraph_index': paragraph_indices[0] if paragraph_indices else None,
                    'similarity': self._row_get(chunk, 'similarity'),
                }
            )
        return source_chunks

    @staticmethod
    def _row_get(row: Any, key: str, default: Any = None) -> Any:
        """Read value from SQLAlchemy row/ORM object/dict safely."""
        if isinstance(row, dict):
            return row.get(key, default)

        if hasattr(row, key):
            return getattr(row, key, default)

        mapping = getattr(row, '_mapping', None)
        if mapping is not None:
            return mapping.get(key, default)

        return default


class DocumentService:
    """Document management service."""

    @classmethod
    async def get_doc_list_services(
        cls, query_db: AsyncSession, page_object: DocumentModel, data_scope_sql=None
    ) -> list[dict[str, Any]]:
        """Get document list."""
        doc_list_result = await DocumentDao.get_doc_list(query_db, page_object, data_scope_sql)
        from utils.common_util import CamelCaseUtil

        return CamelCaseUtil.transform_result(doc_list_result)

    @classmethod
    async def get_doc_detail_services(cls, query_db: AsyncSession, doc_id: int) -> DocumentModel:
        """Get document detail."""
        doc = await DocumentDao.get_doc_by_id(query_db, doc_id)
        from utils.common_util import CamelCaseUtil

        return DocumentModel(**CamelCaseUtil.transform_result(doc)) if doc else DocumentModel()

    @classmethod
    async def upload_document_services(
        cls,
        query_db: AsyncSession,
        kb_id: int,
        file_name: str,
        file_path: str,
        file_size: int,
        file_type: str,
        create_by: str,
    ) -> CrudResponseModel:
        """Create document record and trigger async parsing."""
        try:
            doc = DocumentModel(
                kb_id=kb_id,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                file_type=file_type,
                parse_status='0',
                create_by=create_by,
                create_time=datetime.now(),
            )
            db_doc = await DocumentDao.add_doc_dao(query_db, doc)
            doc_id = db_doc.doc_id
            await query_db.commit()

            asyncio.create_task(cls._parse_document_async(doc_id))
            return CrudResponseModel(is_success=True, message='Upload succeeded, parsing started.')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def _parse_document_async(cls, doc_id: int) -> None:
        """Background parse task for an uploaded document."""
        from config.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                doc = await DocumentDao.get_doc_by_id(db, doc_id)
                if not doc:
                    logger.error(f'Document not found: {doc_id}')
                    return

                file_type = doc.file_type
                file_path = doc.file_path
                kb_id = doc.kb_id
                await DocumentDao.update_parse_status_dao(db, doc_id, '1')
                await db.commit()

                parser = DocumentParserFactory.get_parser(file_type)
                paragraphs = await parser.parse(file_path)

                splitter = ChunkSplitter()
                chunks = splitter.split_paragraphs(paragraphs, doc_id, kb_id)

                embedding_service = EmbeddingService.get_instance()
                texts = [chunk['content'] for chunk in chunks]
                embeddings = await embedding_service.get_text_embeddings(texts)

                for chunk, embedding in zip(chunks, embeddings):
                    chunk['embedding'] = embedding
                    # ORM attribute name is chunk_metadata while DB column is metadata.
                    if 'metadata' in chunk and 'chunk_metadata' not in chunk:
                        chunk['chunk_metadata'] = chunk.pop('metadata')

                await ChunkDao.batch_add_chunks_dao(db, chunks)
                chunk_count = len(chunks)

                await DocumentDao.update_parse_status_dao(db, doc_id, '2', chunk_count=chunk_count)
                await db.commit()
                logger.info(f'Document parsed successfully: doc_id={doc_id}, chunks={chunk_count}')

        except Exception as e:
            logger.error(f'Document parsing failed: doc_id={doc_id}, error={e}')
            try:
                async with AsyncSessionLocal() as db:
                    await DocumentDao.update_parse_status_dao(db, doc_id, '3', error_msg=str(e))
                    await db.commit()
            except Exception:
                pass

    @classmethod
    async def delete_document_services(cls, query_db: AsyncSession, doc_ids: str, update_by: str) -> CrudResponseModel:
        """Delete documents and their chunks."""
        if not doc_ids:
            raise ServiceException(message='Document IDs are required')

        doc_id_list = doc_ids.split(',')
        try:
            for doc_id in doc_id_list:
                await ChunkDao.delete_chunks_by_doc_id_dao(query_db, int(doc_id))
                await DocumentDao.delete_doc_dao(
                    query_db, DocumentModel(docId=int(doc_id), updateBy=update_by, updateTime=datetime.now())
                )
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='Delete succeeded')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def reparse_document_services(cls, query_db: AsyncSession, doc_id: int) -> CrudResponseModel:
        """Re-run parse workflow for a document."""
        try:
            await ChunkDao.delete_chunks_by_doc_id_dao(query_db, doc_id)
            await DocumentDao.update_parse_status_dao(query_db, doc_id, '0')
            await query_db.commit()

            asyncio.create_task(cls._parse_document_async(doc_id))
            return CrudResponseModel(is_success=True, message='Reparse task submitted')
        except Exception:
            await query_db.rollback()
            raise
