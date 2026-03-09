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
    """RAG runtime engine."""

    def __init__(self):
        self.llm = self._init_llm()
        self.embedding_service = EmbeddingService.get_instance()

    def _init_llm(self):
        return OpenAILike(
            api_key=RAGConfig.rag_llm_api_key or 'sk-dummy',
            api_base=RAGConfig.rag_llm_api_base,
            model=RAGConfig.rag_llm_model,
            temperature=RAGConfig.rag_llm_temperature,
            max_tokens=RAGConfig.rag_llm_max_tokens,
        )

    async def retrieve(
        self,
        query_db: AsyncSession,
        query_text: str,
        kb_ids: list[int],
        top_k: int = None,
        threshold: float = None,
        retrieval_mode: str = 'hybrid',
    ) -> dict[str, Any]:
        start_time = datetime.now()
        try:
            if query_db is None:
                raise ServiceException(message='Database session is not available')

            query_text = (query_text or '').strip()
            if not query_text:
                raise ServiceException(message='Query text cannot be empty')

            if not kb_ids:
                raise ServiceException(message='Knowledge base IDs are required')

            top_k = top_k if top_k is not None else RAGConfig.rag_top_k
            threshold = threshold if threshold is not None else RAGConfig.rag_similarity_threshold

            chunks = await self._retrieve_chunks(
                query_db=query_db,
                query_text=query_text,
                kb_ids=kb_ids,
                top_k=top_k,
                threshold=threshold,
                retrieval_mode=retrieval_mode,
            )

            response_time = int((datetime.now() - start_time).total_seconds() * 1000)
            return {
                'chunks': self._format_source_chunks(chunks),
                'response_time': response_time,
            }
        except Exception as e:
            logger.error(f'RAG retrieve failed: {e}')
            raise ServiceException(message=f'Retrieve failed: {e}')

    async def query(
        self,
        query_db: AsyncSession,
        query_text: str,
        kb_ids: list[int],
        top_k: int = None,
        threshold: float = None,
        retrieval_mode: str = 'hybrid',
    ) -> dict[str, Any]:
        """Execute retrieval + generation."""
        start_time = datetime.now()
        try:
            retrieve_result = await self.retrieve(
                query_db=query_db,
                query_text=query_text,
                kb_ids=kb_ids,
                top_k=top_k,
                threshold=threshold,
                retrieval_mode=retrieval_mode,
            )
            source_chunks = retrieve_result.get('chunks', [])
            if not source_chunks:
                return {
                    'answer_text': '在所选知识库中未检索到与问题相关的信息。',
                    'source_chunks': [],
                    'response_time': int((datetime.now() - start_time).total_seconds() * 1000),
                }

            context = self._build_context(source_chunks)
            prompt = self._build_prompt(query_text, context)
            answer = self._post_process_answer(await self._generate_answer(prompt))
            return {
                'answer_text': answer,
                'source_chunks': source_chunks,
                'response_time': int((datetime.now() - start_time).total_seconds() * 1000),
            }
        except Exception as e:
            logger.error(f'RAG query failed: {e}')
            raise ServiceException(message=f'Query failed: {e}')

    async def _retrieve_chunks(
        self,
        *,
        query_db: AsyncSession,
        query_text: str,
        kb_ids: list[int],
        top_k: int,
        threshold: float,
        retrieval_mode: str,
    ) -> list[dict[str, Any]]:
        mode = (retrieval_mode or 'hybrid').lower()
        if mode not in ('vector', 'lexical', 'hybrid'):
            mode = 'hybrid'

        vector_chunks: list[dict[str, Any]] = []
        if mode in ('vector', 'hybrid'):
            query_embedding = await self.embedding_service.get_text_embedding(query_text)
            vector_rows = await ChunkDao.similarity_search(query_db, kb_ids, query_embedding, top_k, threshold)
            vector_chunks = [self._normalize_vector_row(row) for row in vector_rows]

        # lexical branch
        lexical_chunks: list[dict[str, Any]] = []
        if mode in ('lexical', 'hybrid'):
            lexical_rows = await ChunkDao.lexical_search(query_db, kb_ids, query_text, top_k)
            lexical_chunks = [self._normalize_lexical_row(row) for row in lexical_rows]

        # threshold fallback for vector/hybrid
        if mode in ('vector', 'hybrid') and not vector_chunks and threshold > 0:
            logger.warning(f'No vector chunks with threshold={threshold}, fallback to threshold=0.0')
            query_embedding = await self.embedding_service.get_text_embedding(query_text)
            vector_rows = await ChunkDao.similarity_search(query_db, kb_ids, query_embedding, top_k, 0.0)
            vector_chunks = [self._normalize_vector_row(row) for row in vector_rows]

        if mode == 'vector':
            return vector_chunks[:top_k]
        if mode == 'lexical':
            return lexical_chunks[:top_k]

        # hybrid mode
        if not vector_chunks and not lexical_chunks:
            return []
        return self._hybrid_fuse(vector_chunks, lexical_chunks, top_k)

    @staticmethod
    def _row_get(row: Any, key: str, default: Any = None) -> Any:
        if isinstance(row, dict):
            return row.get(key, default)
        if hasattr(row, key):
            return getattr(row, key, default)
        mapping = getattr(row, '_mapping', None)
        if mapping is not None:
            return mapping.get(key, default)
        return default

    def _normalize_vector_row(self, row: Any) -> dict[str, Any]:
        metadata = self._row_get(row, 'metadata') or self._row_get(row, 'chunk_metadata') or {}
        page_nums = metadata.get('page_nums') or []
        paragraph_indices = metadata.get('paragraph_indices') or []
        file_name = self._row_get(row, 'file_name')
        file_path = self._row_get(row, 'file_path')
        snippet = self._row_get(row, 'content') or ''
        score = self._row_get(row, 'similarity')
        return {
            'kb_id': self._row_get(row, 'kb_id'),
            'chunk_id': self._row_get(row, 'chunk_id'),
            'doc_id': self._row_get(row, 'doc_id'),
            'file_name': file_name,
            'file_path': file_path,
            'section': metadata.get('section'),
            'page': page_nums[0] if page_nums else None,
            'paragraph': paragraph_indices[0] if paragraph_indices else None,
            'snippet': snippet,
            'retrieval_score': score,
            'rerank_score': None,
            'retrieval_channel': 'vector',
            # backward compatible fields
            'doc_name': file_name or f"文档 {self._row_get(row, 'doc_id')}",
            'content': snippet,
            'page_num': page_nums[0] if page_nums else None,
            'paragraph_index': paragraph_indices[0] if paragraph_indices else None,
            'similarity': score,
        }

    def _normalize_lexical_row(self, row: Any) -> dict[str, Any]:
        metadata = self._row_get(row, 'metadata') or self._row_get(row, 'chunk_metadata') or {}
        page_nums = metadata.get('page_nums') or []
        paragraph_indices = metadata.get('paragraph_indices') or []
        file_name = self._row_get(row, 'file_name')
        file_path = self._row_get(row, 'file_path')
        snippet = self._row_get(row, 'content') or ''
        score = self._row_get(row, 'lexical_score')
        return {
            'kb_id': self._row_get(row, 'kb_id'),
            'chunk_id': self._row_get(row, 'chunk_id'),
            'doc_id': self._row_get(row, 'doc_id'),
            'file_name': file_name,
            'file_path': file_path,
            'section': metadata.get('section'),
            'page': page_nums[0] if page_nums else None,
            'paragraph': paragraph_indices[0] if paragraph_indices else None,
            'snippet': snippet,
            'retrieval_score': score,
            'rerank_score': None,
            'retrieval_channel': 'lexical',
            # backward compatible fields
            'doc_name': file_name or f"文档 {self._row_get(row, 'doc_id')}",
            'content': snippet,
            'page_num': page_nums[0] if page_nums else None,
            'paragraph_index': paragraph_indices[0] if paragraph_indices else None,
            'similarity': score,
        }

    def _hybrid_fuse(self, vector_chunks: list[dict[str, Any]], lexical_chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        # Reciprocal Rank Fusion (RRF)
        k = 60.0
        fused: dict[int, dict[str, Any]] = {}
        score_map: dict[int, float] = {}

        for rank, chunk in enumerate(vector_chunks, start=1):
            chunk_id = int(chunk['chunk_id'])
            fused.setdefault(chunk_id, chunk.copy())
            score_map[chunk_id] = score_map.get(chunk_id, 0.0) + 1.0 / (k + rank)

        for rank, chunk in enumerate(lexical_chunks, start=1):
            chunk_id = int(chunk['chunk_id'])
            if chunk_id not in fused:
                fused[chunk_id] = chunk.copy()
            score_map[chunk_id] = score_map.get(chunk_id, 0.0) + 1.0 / (k + rank)

        ranked = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:top_k]
        result: list[dict[str, Any]] = []
        for chunk_id, rrf_score in ranked:
            item = fused[chunk_id]
            item['retrieval_score'] = round(rrf_score, 6)
            item['rerank_score'] = None
            item['retrieval_channel'] = 'hybrid'
            item['similarity'] = item['retrieval_score']
            result.append(item)
        return result

    def _build_context(self, chunks: list[dict[str, Any]]) -> str:
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f'[参考内容 {i}]\n{chunk.get("snippet", "")}')
        return '\n\n'.join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        return (
            '你是企业知识库问答助手，请严格基于参考资料回答用户问题。\n'
            '回答规则：\n'
            '1. 必须使用简体中文作答。\n'
            '2. 先给结论，再给简要依据；最多 3 条要点，总字数不超过 180 字。\n'
            '3. 严禁重复同一句话或同一含义的句子。\n'
            '4. 如果参考资料不足以回答，请明确说明：根据当前知识库内容无法确定。\n'
            '5. 不要输出与问题无关的信息。\n\n'
            f'参考资料：\n{context}\n\n'
            f'用户问题：\n{query}\n'
        )

    async def _generate_answer(self, prompt: str) -> str:
        response = await self.llm.acomplete(prompt)
        return str(response).strip()

    def _post_process_answer(self, answer: str) -> str:
        text = (answer or '').strip()
        if not text:
            return '根据当前知识库内容无法确定。'

        text = re.sub(r'\s+', ' ', text)
        segments = re.split(r'(?<=[。！？；.!?;])\s*', text)
        unique_segments: list[str] = []
        seen_keys: set[str] = set()
        for segment in segments:
            seg = segment.strip()
            if not seg:
                continue
            key = re.sub(r'[\s，。！？；,.!?;:]+', '', seg)
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

    def _format_source_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formatted = []
        for chunk in chunks:
            formatted.append(
                {
                    'kb_id': chunk.get('kb_id'),
                    'chunk_id': chunk.get('chunk_id'),
                    'doc_id': chunk.get('doc_id'),
                    'file_name': chunk.get('file_name'),
                    'file_path': chunk.get('file_path'),
                    'section': chunk.get('section'),
                    'page': chunk.get('page'),
                    'paragraph': chunk.get('paragraph'),
                    'snippet': chunk.get('snippet'),
                    'retrieval_score': chunk.get('retrieval_score'),
                    'rerank_score': chunk.get('rerank_score'),
                    'retrieval_channel': chunk.get('retrieval_channel'),
                    # backward-compatible fields
                    'doc_name': chunk.get('doc_name'),
                    'content': chunk.get('content'),
                    'page_num': chunk.get('page_num'),
                    'paragraph_index': chunk.get('paragraph_index'),
                    'similarity': chunk.get('similarity'),
                }
            )
        return formatted


class DocumentService:
    """Document management service."""

    @classmethod
    async def get_doc_list_services(
        cls, query_db: AsyncSession, page_object: DocumentModel, data_scope_sql=None
    ) -> list[dict[str, Any]]:
        doc_list_result = await DocumentDao.get_doc_list(query_db, page_object, data_scope_sql)
        from utils.common_util import CamelCaseUtil

        return CamelCaseUtil.transform_result(doc_list_result)

    @classmethod
    async def get_doc_detail_services(cls, query_db: AsyncSession, doc_id: int) -> DocumentModel:
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
        try:
            await ChunkDao.delete_chunks_by_doc_id_dao(query_db, doc_id)
            await DocumentDao.update_parse_status_dao(query_db, doc_id, '0')
            await query_db.commit()
            asyncio.create_task(cls._parse_document_async(doc_id))
            return CrudResponseModel(is_success=True, message='Reparse task submitted')
        except Exception:
            await query_db.rollback()
            raise
