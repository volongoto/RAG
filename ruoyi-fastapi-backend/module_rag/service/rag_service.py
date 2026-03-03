import asyncio
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
            temperature=0.7,
            max_tokens=2000,
        )

    async def query(
        self,
        query_text: str,
        kb_ids: list[int],
        top_k: int = None,
        threshold: float = None,
    ) -> dict[str, Any]:
        """Execute a RAG query."""
        start_time = datetime.now()

        try:
            query_embedding = await self.embedding_service.get_text_embedding(query_text)

            top_k = top_k or RAGConfig.rag_top_k
            threshold = threshold or RAGConfig.rag_similarity_threshold

            chunks = await ChunkDao.similarity_search(None, kb_ids, query_embedding, top_k, threshold)

            if not chunks:
                return {
                    'answer_text': 'No relevant information was found in the selected knowledge bases.',
                    'source_chunks': [],
                    'response_time': int((datetime.now() - start_time).total_seconds() * 1000),
                }

            context = self._build_context(chunks)
            prompt = self._build_prompt(query_text, context)
            answer = await self._generate_answer(prompt)

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
            context_parts.append(f'[Document {i}]\n{content}')
        return '\n\n'.join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """Build prompt for LLM answer generation."""
        return (
            'You are a helpful assistant. Answer the user question using the reference content below.\n'
            'If the reference does not contain enough information, say so explicitly.\n\n'
            f'Reference:\n{context}\n\n'
            f'User question:\n{query}\n'
        )

    async def _generate_answer(self, prompt: str) -> str:
        """Generate answer text from LLM."""
        try:
            response = await self.llm.acomplete(prompt)
            return str(response).strip()
        except Exception as e:
            logger.error(f'LLM answer generation failed: {e}')
            raise

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
                    'doc_name': f"Document {self._row_get(chunk, 'doc_id')}",
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
