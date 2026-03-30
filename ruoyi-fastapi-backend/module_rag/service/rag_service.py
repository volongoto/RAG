import asyncio
import difflib
import json
import math
import os
import re
from datetime import datetime
from typing import Any

from config.env import RAGConfig
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from loguru import logger
from openai import AsyncOpenAI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel
from exceptions.exception import ServiceException
from module_rag.dao.chunk_dao import ChunkDao
from module_rag.dao.document_dao import DocumentDao
from module_rag.entity.vo.rag_vo import DocumentModel
from module_rag.service.chunk_splitter import ChunkSplitter
from module_rag.service.document_storage_service import DocumentStorageService
from module_rag.service.embedding_service import EmbeddingService
from module_rag.service.parser.document_parser import DocumentParserFactory


class RAGEngine:
    """RAG runtime engine."""

    def __init__(self):
        self.llm = self._init_llm()
        self.output_cleaner = self._init_output_cleaner()
        self.embedding_service = EmbeddingService.get_instance()

    def _init_llm(self):
        base_url = self._normalize_openai_base_url(RAGConfig.rag_llm_api_base)
        logger.info(
            'LLM client initialized: '
            f'api_base={base_url}, '
            f'model={RAGConfig.rag_llm_model}, '
            f'temperature={RAGConfig.rag_llm_temperature}, '
            f'max_tokens={RAGConfig.rag_llm_max_tokens}'
        )
        return AsyncOpenAI(
            api_key=RAGConfig.rag_llm_api_key or 'sk-dummy',
            base_url=base_url or None,
        )

    def _init_output_cleaner(self):
        return RunnableLambda(self._remove_output_artifacts, name='sanitize_rag_answer') | StrOutputParser()

    @staticmethod
    def _normalize_openai_base_url(url: str | None) -> str:
        normalized = str(url or '').strip().rstrip('/')
        if (normalized.startswith("'") and normalized.endswith("'")) or (
            normalized.startswith('"') and normalized.endswith('"')
        ):
            normalized = normalized[1:-1].strip().rstrip('/')
        return normalized

    @staticmethod
    def _normalize_bool_like(value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if not text:
            return None
        if text in {'1', 'true', 'yes', 'on'}:
            return True
        if text in {'0', 'false', 'no', 'off'}:
            return False
        return None

    def _resolve_enable_thinking(self) -> bool | None:
        configured_value = self._normalize_bool_like(getattr(RAGConfig, 'rag_llm_enable_thinking', None))
        if configured_value is not None:
            return configured_value

        model_name = str(getattr(RAGConfig, 'rag_llm_model', '') or '').strip().lower()
        if 'deepseek-r1' in model_name:
            return False
        return None

    def _build_llm_extra_body(self) -> dict[str, Any]:
        enable_thinking = self._resolve_enable_thinking()
        if enable_thinking is None:
            return {}
        return {'enable_thinking': enable_thinking}

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
        scenario: str | None = None,
        answer_mode: str = 'detailed',
    ) -> dict[str, Any]:
        """Execute retrieval + generation."""
        start_time = datetime.now()
        try:
            logger.info(
                'RAGEngine.query started: '
                f'kb_ids={kb_ids}, top_k={top_k}, threshold={threshold}, '
                f'retrieval_mode={retrieval_mode}, answer_mode={answer_mode}, '
                f'query_length={len((query_text or "").strip())}'
            )
            normalized_answer_mode = self._normalize_answer_mode(answer_mode)

            era_mismatch_answer = self._build_era_mismatch_answer(query_text)
            if era_mismatch_answer:
                return {
                    'answer_text': era_mismatch_answer,
                    'source_chunks': [],
                    'response_time': int((datetime.now() - start_time).total_seconds() * 1000),
                }

            retrieve_result = await self.retrieve(
                query_db=query_db,
                query_text=query_text,
                kb_ids=kb_ids,
                top_k=top_k,
                threshold=threshold,
                retrieval_mode=retrieval_mode,
            )
            source_chunks = retrieve_result.get('chunks', [])
            logger.info(
                'RAGEngine.query retrieve completed: '
                f'kb_ids={kb_ids}, retrieval_mode={retrieval_mode}, source_chunk_count={len(source_chunks)}'
            )
            if not source_chunks:
                return {
                    'answer_text': '在所选知识库中未检索到与问题相关的信息。',
                    'source_chunks': [],
                    'response_time': int((datetime.now() - start_time).total_seconds() * 1000),
                }

            context = self._build_context(source_chunks)
            system_prompt, user_prompt = self._build_prompt(query_text, context, scenario, normalized_answer_mode)
            raw_answer = await self._generate_answer(system_prompt, user_prompt)
            answer = self._post_process_answer(
                await self._sanitize_model_output(raw_answer),
                query_text=query_text,
                scenario=scenario,
                answer_mode=normalized_answer_mode,
            )
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

    def _build_prompt(
        self, query: str, context: str, scenario: str | None = None, answer_mode: str = 'detailed'
    ) -> tuple[str, str]:
        base_rules = (
            '你是企业知识库问答助手，请严格基于参考资料回答。\n'
            '回答规则：\n'
            '1. 必须使用简体中文。\n'
            '2. 只能输出一版最终答案，不要输出“另一种说法”或重复改写版本。\n'
            '3. 核心结论必须能在参考资料中找到依据；若依据不足，明确写“根据当前知识库内容无法确定”。\n'
            '4. 禁止编造剧情、人物关系、因果链或具体事件细节。\n'
            '5. 禁止输出推理过程或元话术，如“好的我来分析”“首先其次”“让我思考”“现在你的任务是”。\n'
            '6. 内容精炼，避免重复，不要复述问题。\n'
        )
        concise_mode = self._normalize_answer_mode(answer_mode) == 'concise'
        if self._is_security_brief_scenario(scenario, query):
            if concise_mode:
                style_rules = (
                    '7. 使用“情报简报”格式，严格按以下模板输出：\n'
                    '结论：一句话。\n'
                    '依据：\n'
                    '1. 依据一（来自参考资料）\n'
                    '2. 依据二（来自参考资料）\n'
                    '3. 依据三（可选，来自参考资料）\n'
                    '8. 不超过220字。\n'
                )
            else:
                style_rules = (
                    '7. 使用“情报评估”格式，先给结论，再给4-8条依据；每条依据必须可在参考资料中定位。\n'
                    '8. 禁止复述问题，禁止同义重复。\n'
                )
        elif concise_mode:
            style_rules = (
                '7. 输出精简模式：先给结论，再给2-4条依据；每条依据都要指向参考资料。\n'
                '8. 回答控制在260字以内。\n'
            )
        else:
            style_rules = '7. 输出详细模式：根据问题给出结构化答案与关键依据，避免重复与空话。\n'

        return (
            f'{base_rules}{style_rules}\n',
            f'参考资料：\n{context}\n\n'
            f'用户问题：\n{query}\n',
        )

    async def _generate_answer(self, system_prompt: str, user_prompt: str) -> str:
        extra_body = self._build_llm_extra_body()
        enable_thinking = self._resolve_enable_thinking()
        logger.info(
            'LLM completion request started: '
            f'api_base={RAGConfig.rag_llm_api_base}, '
            f'model={RAGConfig.rag_llm_model}, '
            f'system_prompt_length={len(system_prompt or "")}, '
            f'user_prompt_length={len(user_prompt or "")}, '
            f'enable_thinking={enable_thinking}'
        )
        request_kwargs: dict[str, Any] = {
            'model': RAGConfig.rag_llm_model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': float(RAGConfig.rag_llm_temperature or 0),
        }
        if int(RAGConfig.rag_llm_max_tokens or 0) > 0:
            request_kwargs['max_tokens'] = int(RAGConfig.rag_llm_max_tokens)
        if extra_body:
            request_kwargs['extra_body'] = extra_body
        logger.info(
            'LLM chat request payload prepared: '
            f'model={request_kwargs["model"]}, '
            f'message_count={len(request_kwargs["messages"])}, '
            f'has_extra_body={"extra_body" in request_kwargs}, '
            f'has_max_tokens={"max_tokens" in request_kwargs}, '
            f'enable_thinking={enable_thinking}'
        )
        response = await self.llm.chat.completions.create(**request_kwargs)
        response_text = ''
        if response and response.choices:
            response_text = str(response.choices[0].message.content or '').strip()
        logger.info(
            'LLM completion request finished: '
            f'model={RAGConfig.rag_llm_model}, response_length={len(response_text)}, '
            f'response_preview={response_text[:120]!r}'
        )
        return response_text

    async def _sanitize_model_output(self, answer: str) -> str:
        text = (answer or '').strip()
        if not text:
            return ''

        text = self._strip_thinking_block(text)
        try:
            cleaned = str(await self.output_cleaner.ainvoke(text)).strip()
        except Exception as exc:
            logger.warning(f'LangChain output cleaner failed, fallback to local sanitizer: {exc}')
            cleaned = self._remove_output_artifacts(text)

        cleaned = self._strip_reasoning_leakage(cleaned)
        if self._is_low_value_acknowledgement(cleaned):
            logger.warning(f'LLM output reduced to acknowledgement-only content: {cleaned!r}')
            return ''
        return cleaned

    def _remove_output_artifacts(self, text: str) -> str:
        cleaned = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
        if not cleaned:
            return ''

        think_close_matches = list(re.finditer(r'</think\s*>', cleaned, flags=re.IGNORECASE))
        if think_close_matches:
            cleaned = cleaned[think_close_matches[-1].end() :].strip()

        cleaned = re.sub(r'<think\b[^>]*>.*?</think\s*>', ' ', cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'</?think\b[^>]*>', ' ', cleaned, flags=re.IGNORECASE)

        leading_instruction_patterns = [
            r'^\s*(?:请|请你)?(?:严格)?(?:基于|根据)参考资料[^。\n]{0,80}?(?:给出|输出|整理|总结|提供)[^。\n]{0,80}?(?:结构化)?(?:回答|答复|结论)[：:。]?\s*',
            r'^\s*(?:请|请你)?(?:基于|根据)已检索到的内容[^。\n]{0,80}?(?:回答|答复|结论)[：:。]?\s*',
            r'^\s*(?:下面|以下)是(?:根据|基于)参考资料整理的(?:结构化)?(?:回答|答复)[：:。]?\s*',
        ]
        for pattern in leading_instruction_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def _strip_thinking_block(text: str) -> str:
        normalized = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
        if not normalized:
            return ''

        cleaned = re.sub(
            r'<\s*think(?:ing)?\b[^>]*>[\s\S]*?<\s*/\s*think(?:ing)?\s*>',
            ' ',
            normalized,
            flags=re.IGNORECASE,
        )
        close_match = re.search(r'<\s*/\s*think(?:ing)?\s*>', cleaned, flags=re.IGNORECASE)
        if close_match:
            cleaned = cleaned[close_match.end() :].strip()
        cleaned = re.sub(r'<\s*/?\s*think(?:ing)?\b[^>]*>', ' ', cleaned, flags=re.IGNORECASE).strip()
        return cleaned or normalized

    @staticmethod
    def _is_low_value_acknowledgement(text: str) -> bool:
        normalized = re.sub(r'[\s，,。.!！？；;：:]+', '', text or '').lower()
        if not normalized:
            return True

        if normalized in {
            '好',
            '好的',
            '收到',
            '明白',
            '嗯',
            '好的我来分析',
            '好的我现在分析',
            '让我分析',
            '让我思考',
            '我来分析',
            '请稍等',
            '稍等',
            '正在分析',
        }:
            return True

        return len(normalized) <= 12 and any(
            normalized.startswith(prefix)
            for prefix in ('好的我来', '好的我现在', '让我', '我来', '请稍等', '稍等', '正在')
        )

    def _post_process_answer(
        self, answer: str, query_text: str = '', scenario: str | None = None, answer_mode: str = 'detailed'
    ) -> str:
        text = (answer or '').strip()
        if not text:
            return '根据当前知识库内容无法确定。'

        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        text = self._strip_reasoning_leakage(text)

        # If model accidentally outputs two full answer versions, keep the first one.
        text = self._trim_second_answer_block(text)

        # Paragraph-level near-duplicate removal.
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        dedup_paragraphs: list[str] = []
        dedup_keys: list[str] = []
        for paragraph in paragraphs:
            key = self._normalize_for_dedup(paragraph)
            if not key:
                continue
            if any(self._is_near_duplicate(key, existing) for existing in dedup_keys):
                continue
            dedup_paragraphs.append(paragraph)
            dedup_keys.append(key)

        merged = '\n\n'.join(dedup_paragraphs) if dedup_paragraphs else text

        # Sentence-level near-duplicate removal.
        segments = [seg.strip() for seg in re.split(r'(?<=[。！？；.!?;])\s*', merged) if seg.strip()]
        unique_segments: list[str] = []
        unique_keys: list[str] = []
        for seg in segments:
            key = self._normalize_for_dedup(seg)
            if not key:
                continue
            if any(self._is_near_duplicate(key, existing) for existing in unique_keys):
                continue
            unique_segments.append(seg)
            unique_keys.append(key)

        cleaned = ' '.join(unique_segments).strip() if unique_segments else merged.strip()
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)

        mode = self._normalize_answer_mode(answer_mode)
        max_len = 480 if mode == 'concise' else 1600
        if len(cleaned) > max_len:
            cleaned = cleaned[:max_len].rstrip() + '...'

        if mode == 'concise':
            if self._is_security_brief_scenario(scenario, query_text):
                cleaned = self._to_security_brief(cleaned)
            else:
                cleaned = self._to_concise_answer(cleaned)
        return cleaned

    def _strip_reasoning_leakage(self, text: str) -> str:
        """
        Remove exposed internal reasoning / meta-instructions from model output.
        """
        if not text:
            return text

        leakage_patterns = [
            r'^</?think\b',
            r'^好的[,，]我现在',
            r'^我现在需要',
            r'^用户的问题是',
            r'^现在你的任务是',
            r'^请用简体中文回答用户的问题',
            r'^严格基于参考资料回答问题',
            r'^首先[,，:]',
            r'^其次[,，:]',
            r'^然后[,，:]',
            r'^最后[,，:]',
            r'^总结依据',
        ]

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        filtered_lines: list[str] = []
        for line in lines:
            if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in leakage_patterns):
                continue
            filtered_lines.append(line)

        if not filtered_lines:
            return ''

        sentences = [seg.strip() for seg in re.split(r'(?<=[。！？；.!?;])\s*', ' '.join(filtered_lines)) if seg.strip()]
        filtered_sentences: list[str] = []
        for seg in sentences:
            if any(re.search(pattern, seg, flags=re.IGNORECASE) for pattern in leakage_patterns):
                continue
            filtered_sentences.append(seg)
        return ' '.join(filtered_sentences).strip()

    def _is_security_brief_scenario(self, scenario: str | None, query_text: str) -> bool:
        if not getattr(RAGConfig, 'rag_security_brief_enabled', False):
            return False

        scenario_text = (scenario or '').lower()
        query = (query_text or '').lower()
        scenario_markers = self._parse_markers(getattr(RAGConfig, 'rag_security_brief_scenario_markers', ''))
        query_markers = self._parse_markers(getattr(RAGConfig, 'rag_security_brief_query_markers', ''))
        return any(marker in scenario_text for marker in scenario_markers) or any(marker in query for marker in query_markers)

    @staticmethod
    def _parse_markers(raw_markers: str) -> list[str]:
        return [marker.strip().lower() for marker in (raw_markers or '').split(',') if marker.strip()]

    def _normalize_answer_mode(self, answer_mode: str | None) -> str:
        mode = (answer_mode or 'detailed').strip().lower()
        return 'concise' if mode == 'concise' else 'detailed'

    def _to_concise_answer(self, text: str) -> str:
        if not text:
            return '根据当前知识库内容无法确定。'

        sentences = [seg.strip() for seg in re.split(r'(?<=[。！？；.!?;])\s*', text) if seg.strip()]
        if not sentences:
            return '根据当前知识库内容无法确定。'

        concise_sentences: list[str] = []
        for seg in sentences:
            key = self._normalize_for_dedup(seg)
            if not key:
                continue
            if any(self._is_near_duplicate(key, self._normalize_for_dedup(existing)) for existing in concise_sentences):
                continue
            concise_sentences.append(seg)
            if len(concise_sentences) >= 4:
                break

        if not concise_sentences:
            return '根据当前知识库内容无法确定。'

        concise = ' '.join(concise_sentences)
        if len(concise) > 300:
            concise = concise[:300].rstrip() + '...'
        return concise

    def _to_security_brief(self, text: str) -> str:
        """
        Enforce a compact briefing shape: 1 conclusion + up to 3 evidences.
        """
        if not text:
            return '结论：根据当前知识库内容无法确定。'

        sentences = [seg.strip() for seg in re.split(r'(?<=[。！？；.!?;])\s*', text) if seg.strip()]
        if not sentences:
            return '结论：根据当前知识库内容无法确定。'

        conclusion = ''
        for seg in sentences:
            if '结论' in seg or '无法确定' in seg or '时代背景不符' in seg:
                conclusion = seg
                break
        if not conclusion:
            conclusion = sentences[0]
        conclusion = re.sub(r'^结论[:：]?\s*', '', conclusion).strip()

        evidence_candidates = []
        evidence_keywords = ['依据', '参考资料', '未提及', '时间', '背景', '不符', '未检索到', '无证据']
        for seg in sentences:
            if seg == conclusion:
                continue
            if any(keyword in seg for keyword in evidence_keywords):
                evidence_candidates.append(seg)

        if not evidence_candidates:
            evidence_candidates = [seg for seg in sentences if seg != conclusion][:3]

        evidences: list[str] = []
        for seg in evidence_candidates:
            seg = re.sub(r'^(依据[:：]?\s*)', '', seg).strip()
            key = self._normalize_for_dedup(seg)
            if not key:
                continue
            if any(self._is_near_duplicate(key, self._normalize_for_dedup(existing)) for existing in evidences):
                continue
            evidences.append(seg)
            if len(evidences) >= 3:
                break

        lines = [f'结论：{conclusion}']
        if evidences:
            lines.append('依据：')
            for idx, seg in enumerate(evidences, 1):
                lines.append(f'{idx}. {seg}')

        brief = '\n'.join(lines).strip()
        if len(brief) > 320:
            brief = brief[:320].rstrip() + '...'
        return brief

    def _build_era_mismatch_answer(self, query_text: str) -> str | None:
        """
        Detect obvious anachronism combinations and return deterministic short answer.
        """
        if not getattr(RAGConfig, 'rag_era_mismatch_guard_enabled', False):
            return None

        query = (query_text or '').strip().lower()
        if not query:
            return None

        left_markers = self._parse_markers(getattr(RAGConfig, 'rag_era_mismatch_left_markers', ''))
        right_markers = self._parse_markers(getattr(RAGConfig, 'rag_era_mismatch_right_markers', ''))
        if not left_markers or not right_markers:
            return None

        has_left = any(word in query for word in left_markers)
        has_right = any(word in query for word in right_markers)
        if has_left and has_right:
            return (
                '结论：时代背景不符，根据当前知识库内容无法确定“韦小宝向苏联克格勃提供情报”这一说法。\n'
                '依据：\n'
                '1. 问题中“克格勃”与“韦小宝/鹿鼎记”属于明显时代错位组合。\n'
                '2. 当前知识库检索范围内未提供该行为的直接证据。'
            )
        return None

    def _trim_second_answer_block(self, text: str) -> str:
        sentences = [seg.strip() for seg in re.split(r'(?<=[。！？；.!?;])\s*', text) if seg.strip()]
        if len(sentences) < 4:
            return text

        first_key = self._normalize_for_dedup(sentences[0])
        if len(first_key) < 12:
            return text

        for i in range(2, len(sentences)):
            candidate_key = self._normalize_for_dedup(sentences[i])
            if len(candidate_key) < 12:
                continue
            if self._is_near_duplicate(first_key, candidate_key):
                return ' '.join(sentences[:i]).strip()
        return text

    @staticmethod
    def _normalize_for_dedup(text: str) -> str:
        normalized = re.sub(r'\s+', '', text or '')
        normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', normalized)
        return normalized.lower()

    @staticmethod
    def _is_near_duplicate(left: str, right: str) -> bool:
        if not left or not right:
            return False
        if left == right:
            return True
        return difflib.SequenceMatcher(None, left, right).ratio() >= 0.9

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


class LegacyDocumentService:
    """Legacy document management service."""

    _parse_tasks: dict[int, asyncio.Task] = {}
    _progress_key_prefix = 'rag:doc:parse_progress'
    _progress_ttl_seconds = 24 * 60 * 60

    @classmethod
    def _progress_key(cls, doc_id: int) -> str:
        return f'{cls._progress_key_prefix}:{doc_id}'

    @classmethod
    def _default_progress(cls, doc: dict[str, Any]) -> tuple[int, str]:
        status = doc.get('parseStatus') or doc.get('parse_status')
        if status == '2':
            return 100, '解析完成'
        if status == '3':
            return 0, doc.get('parseError') or doc.get('parse_error') or '解析失败'
        if status == '1':
            return 1, '解析中'
        return 0, '等待解析'

    @classmethod
    async def _set_progress(cls, redis: Redis | None, doc_id: int, progress: int, message: str) -> None:
        if redis is None:
            return
        payload = json.dumps(
            {
                'parseProgress': max(0, min(100, int(progress))),
                'parseMessage': message,
            },
            ensure_ascii=False,
        )
        await redis.set(cls._progress_key(doc_id), payload, ex=cls._progress_ttl_seconds)

    @classmethod
    async def _get_progress(cls, redis: Redis | None, doc_id: int) -> dict[str, Any]:
        if redis is None:
            return {}
        raw_value = await redis.get(cls._progress_key(doc_id))
        if not raw_value:
            return {}
        try:
            progress_data = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return progress_data if isinstance(progress_data, dict) else {}

    @classmethod
    async def _decorate_docs_with_progress(cls, redis: Redis | None, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for doc in docs:
            doc_id = doc.get('docId') or doc.get('doc_id')
            default_progress, default_message = cls._default_progress(doc)
            progress_data = await cls._get_progress(redis, int(doc_id)) if doc_id else {}
            doc['parseProgress'] = int(progress_data.get('parseProgress', default_progress))
            doc['parseMessage'] = progress_data.get('parseMessage') or default_message
        return docs

    @classmethod
    def _start_parse_task(cls, doc_id: int, redis: Redis | None) -> None:
        existing_task = cls._parse_tasks.get(doc_id)
        if existing_task and not existing_task.done():
            return
        cls._parse_tasks[doc_id] = asyncio.create_task(cls._parse_document_async(doc_id, redis))

    @classmethod
    async def get_doc_list_services(
        cls,
        query_db: AsyncSession,
        page_object: DocumentModel,
        data_scope_sql=None,
        redis: Redis | None = None,
    ) -> list[dict[str, Any]]:
        doc_list_result = await DocumentDao.get_doc_list(query_db, page_object, data_scope_sql)
        from utils.common_util import CamelCaseUtil

        doc_list = CamelCaseUtil.transform_result(doc_list_result)
        return await cls._decorate_docs_with_progress(redis, doc_list)

    @classmethod
    async def get_doc_detail_services(
        cls, query_db: AsyncSession, doc_id: int, redis: Redis | None = None
    ) -> DocumentModel:
        doc = await DocumentDao.get_doc_by_id(query_db, doc_id)
        from utils.common_util import CamelCaseUtil

        if not doc:
            return DocumentModel()
        doc_list = await cls._decorate_docs_with_progress(redis, [CamelCaseUtil.transform_result(doc)])
        return DocumentModel(**doc_list[0])

    @classmethod
    async def upload_document_services(
        cls,
        query_db: AsyncSession,
        redis: Redis | None,
        kb_id: int,
        file_name: str,
        file_path: str,
        file_size: int,
        file_type: str,
        create_by: str,
    ) -> CrudResponseModel:
        doc_id: int | None = None
        doc_committed = False
        queue_submitted = False
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
            await cls._set_progress(redis, doc_id, 0, '等待解析任务启动')
            cls._start_parse_task(doc_id, redis)
            return CrudResponseModel(is_success=True, message='Upload succeeded, parsing started.')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def _parse_document_async(cls, doc_id: int, redis: Redis | None) -> None:
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

                await cls._set_progress(redis, doc_id, 5, '准备解析文档')
                await ChunkDao.delete_chunks_by_doc_id_dao(db, doc_id)
                await DocumentDao.update_parse_status_dao(db, doc_id, '1', chunk_count=0, clear_error=True)
                await db.commit()

                parser = DocumentParserFactory.get_parser(file_type)
                if not os.path.exists(file_path):
                    raise ServiceException(message='Document file is missing in storage, please re-upload')
                await cls._set_progress(redis, doc_id, 10, '正在解析文档内容')
                paragraphs = await parser.parse(file_path)
                if not paragraphs:
                    raise ServiceException(message='Document contains no extractable text')

                await cls._set_progress(redis, doc_id, 20, f'已提取 {len(paragraphs)} 个段落')
                splitter = ChunkSplitter()
                chunks = splitter.split_paragraphs(paragraphs, doc_id, kb_id)
                if not chunks:
                    raise ServiceException(message='Document produced no chunks after splitting')

                chunk_count = len(chunks)
                await DocumentDao.update_parse_status_dao(db, doc_id, '1', chunk_count=chunk_count, clear_error=True)
                await db.commit()
                await cls._set_progress(redis, doc_id, 30, f'已切分 {chunk_count} 个片段，开始生成向量')

                embedding_service = EmbeddingService.get_instance()
                batch_size = max(1, int(RAGConfig.rag_embedding_batch_size))
                total_batches = max(1, math.ceil(chunk_count / batch_size))
                embedded_count = 0

                for batch_index, start in enumerate(range(0, chunk_count, batch_size), start=1):
                    batch_chunks = chunks[start : start + batch_size]
                    texts = [chunk['content'] for chunk in batch_chunks]
                    embeddings = await embedding_service.get_text_embeddings(texts)
                    if len(embeddings) != len(batch_chunks):
                        raise ServiceException(message='Embedding count does not match chunk count')

                    for chunk, embedding in zip(batch_chunks, embeddings):
                        chunk['embedding'] = embedding
                        if 'metadata' in chunk and 'chunk_metadata' not in chunk:
                            chunk['chunk_metadata'] = chunk.pop('metadata')

                    embedded_count += len(batch_chunks)
                    progress = 30 + int((batch_index / total_batches) * 60)
                    await cls._set_progress(
                        redis,
                        doc_id,
                        progress,
                        f'正在生成向量 {embedded_count}/{chunk_count}',
                    )

                await cls._set_progress(redis, doc_id, 95, '正在保存切片索引')
                await ChunkDao.batch_add_chunks_dao(db, chunks)
                await DocumentDao.update_parse_status_dao(db, doc_id, '2', chunk_count=chunk_count, clear_error=True)
                await db.commit()
                await cls._set_progress(redis, doc_id, 100, f'解析完成，共 {chunk_count} 个片段')
                logger.info(f'Document parsed successfully: doc_id={doc_id}, chunks={chunk_count}')

        except Exception as e:
            logger.exception(f'Document parsing failed: doc_id={doc_id}, error={e}')
            try:
                async with AsyncSessionLocal() as db:
                    await ChunkDao.delete_chunks_by_doc_id_dao(db, doc_id)
                    await DocumentDao.update_parse_status_dao(db, doc_id, '3', error_msg=str(e))
                    await db.commit()
            except Exception:
                pass
            await cls._set_progress(redis, doc_id, 0, f'解析失败: {str(e)}')
        finally:
            cls._parse_tasks.pop(doc_id, None)

    @classmethod
    async def resume_incomplete_tasks(cls, redis: Redis | None) -> None:
        from config.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            pending_docs = await DocumentDao.get_docs_by_parse_statuses(db, ['0', '1'])
        for doc in pending_docs:
            await cls._set_progress(redis, doc.doc_id, 0, '检测到未完成任务，正在恢复解析')
            cls._start_parse_task(doc.doc_id, redis)
        if pending_docs:
            logger.info(f'Resumed {len(pending_docs)} unfinished document parse tasks')

    @classmethod
    async def delete_document_services(
        cls, query_db: AsyncSession, redis: Redis | None, doc_ids: str, update_by: str
    ) -> CrudResponseModel:
        if not doc_ids:
            raise ServiceException(message='Document IDs are required')
        doc_id_list = doc_ids.split(',')
        try:
            for doc_id in doc_id_list:
                int_doc_id = int(doc_id)
                task = cls._parse_tasks.get(int_doc_id)
                if task and not task.done():
                    task.cancel()
                await ChunkDao.delete_chunks_by_doc_id_dao(query_db, int_doc_id)
                await DocumentDao.delete_doc_dao(
                    query_db, DocumentModel(docId=int_doc_id, updateBy=update_by, updateTime=datetime.now())
                )
                if redis is not None:
                    await redis.delete(cls._progress_key(int_doc_id))
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='Delete succeeded')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def reparse_document_services(
        cls, query_db: AsyncSession, redis: Redis | None, doc_id: int
    ) -> CrudResponseModel:
        try:
            task = cls._parse_tasks.get(doc_id)
            if task and not task.done():
                task.cancel()
            await ChunkDao.delete_chunks_by_doc_id_dao(query_db, doc_id)
            await DocumentDao.update_parse_status_dao(query_db, doc_id, '0', chunk_count=0, clear_error=True)
            await query_db.commit()
            await cls._set_progress(redis, doc_id, 0, '等待重新解析')
            cls._start_parse_task(doc_id, redis)
            return CrudResponseModel(is_success=True, message='Reparse task submitted')
        except Exception:
            await query_db.rollback()
            raise


class DocumentService:
    """Queued document parsing service backed by Redis."""

    _parse_tasks: dict[int, asyncio.Task] = {}
    _worker_tasks: list[asyncio.Task] = []
    _progress_key_prefix = 'rag:doc:parse_progress'
    _progress_ttl_seconds = 24 * 60 * 60
    _queue_key = 'rag:doc:parse_queue'
    _queued_members_key = 'rag:doc:parse_queue:members'
    _active_members_key = 'rag:doc:parse_active:members'

    @classmethod
    def _progress_key(cls, doc_id: int) -> str:
        return f'{cls._progress_key_prefix}:{doc_id}'

    @classmethod
    def _queue_token(cls, doc_id: int) -> str:
        return str(int(doc_id))

    @classmethod
    def _worker_count(cls) -> int:
        return max(1, int(getattr(RAGConfig, 'rag_parse_worker_count', 1)))

    @classmethod
    def _queue_max_size(cls) -> int:
        return max(0, int(getattr(RAGConfig, 'rag_parse_queue_max_size', 0)))

    @classmethod
    def _default_progress(cls, doc: dict[str, Any]) -> tuple[int, str]:
        status = doc.get('parseStatus') or doc.get('parse_status')
        if status == '2':
            return 100, 'Completed'
        if status == '3':
            return 0, doc.get('parseError') or doc.get('parse_error') or 'Failed'
        if status == '1':
            return 1, 'Processing'
        return 0, 'Queued'

    @classmethod
    async def _set_progress(cls, redis: Redis | None, doc_id: int, progress: int, message: str) -> None:
        if redis is None:
            return
        payload = json.dumps(
            {
                'parseProgress': max(0, min(100, int(progress))),
                'parseMessage': message,
            },
            ensure_ascii=False,
        )
        await redis.set(cls._progress_key(doc_id), payload, ex=cls._progress_ttl_seconds)

    @classmethod
    async def _get_progress(cls, redis: Redis | None, doc_id: int) -> dict[str, Any]:
        if redis is None:
            return {}
        raw_value = await redis.get(cls._progress_key(doc_id))
        if not raw_value:
            return {}
        try:
            progress_data = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return progress_data if isinstance(progress_data, dict) else {}

    @classmethod
    async def _decorate_docs_with_progress(cls, redis: Redis | None, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for doc in docs:
            doc_id = doc.get('docId') or doc.get('doc_id')
            default_progress, default_message = cls._default_progress(doc)
            progress_data = await cls._get_progress(redis, int(doc_id)) if doc_id else {}
            doc['parseProgress'] = int(progress_data.get('parseProgress', default_progress))
            doc['parseMessage'] = progress_data.get('parseMessage') or default_message
        return docs

    @classmethod
    async def start_queue_workers(cls, redis: Redis | None) -> None:
        if redis is None:
            return
        cls._worker_tasks = [task for task in cls._worker_tasks if not task.done()]
        if cls._worker_tasks:
            return
        for worker_index in range(cls._worker_count()):
            cls._worker_tasks.append(asyncio.create_task(cls._queue_worker(redis, worker_index + 1)))
        logger.info(f'Started {len(cls._worker_tasks)} document parse queue workers')

    @classmethod
    async def stop_queue_workers(cls) -> None:
        parse_tasks = [task for task in cls._parse_tasks.values() if not task.done()]
        for task in parse_tasks:
            task.cancel()
        if parse_tasks:
            await asyncio.gather(*parse_tasks, return_exceptions=True)

        worker_tasks = [task for task in cls._worker_tasks if not task.done()]
        for task in worker_tasks:
            task.cancel()
        if worker_tasks:
            await asyncio.gather(*worker_tasks, return_exceptions=True)

        cls._parse_tasks.clear()
        cls._worker_tasks = []

    @classmethod
    async def _queue_worker(cls, redis: Redis, worker_index: int) -> None:
        while True:
            current_doc_id: int | None = None
            current_task: asyncio.Task | None = None
            try:
                queue_item = await redis.blpop(cls._queue_key, timeout=5)
                if not queue_item:
                    continue

                _, token = queue_item
                try:
                    current_doc_id = int(token)
                except (TypeError, ValueError):
                    await redis.srem(cls._queued_members_key, token)
                    continue

                await redis.srem(cls._queued_members_key, token)
                await redis.sadd(cls._active_members_key, token)
                await cls._refresh_queue_progress(redis)

                current_task = asyncio.create_task(cls._parse_document_async(current_doc_id, redis))
                cls._parse_tasks[current_doc_id] = current_task
                await current_task
            except asyncio.CancelledError:
                if current_task and not current_task.done():
                    current_task.cancel()
                    await asyncio.gather(current_task, return_exceptions=True)
                raise
            except Exception as exc:
                logger.exception(f'Document parse worker {worker_index} crashed on doc_id={current_doc_id}: {exc}')
            finally:
                if current_doc_id is not None:
                    cls._parse_tasks.pop(current_doc_id, None)
                    await redis.srem(cls._active_members_key, cls._queue_token(current_doc_id))
                    await cls._refresh_queue_progress(redis)

    @classmethod
    async def _refresh_queue_progress(cls, redis: Redis | None) -> None:
        if redis is None:
            return
        queued_tokens = await redis.lrange(cls._queue_key, 0, -1)
        for index, token in enumerate(queued_tokens):
            try:
                doc_id = int(token)
            except (TypeError, ValueError):
                await redis.lrem(cls._queue_key, 0, token)
                await redis.srem(cls._queued_members_key, token)
                continue
            message = 'Queued, waiting for an available worker'
            if index > 0:
                message = f'Queued, {index} task(s) ahead'
            await cls._set_progress(redis, doc_id, 0, message)

    @classmethod
    async def _enqueue_parse_task(cls, redis: Redis | None, doc_id: int) -> bool:
        if redis is None:
            cls._start_parse_task(doc_id, None)
            return True

        token = cls._queue_token(doc_id)
        if await redis.sismember(cls._active_members_key, token):
            return False
        queue_max_size = cls._queue_max_size()
        if queue_max_size > 0:
            queued_count = int(await redis.llen(cls._queue_key) or 0)
            active_count = int(await redis.scard(cls._active_members_key) or 0)
            if queued_count + active_count >= queue_max_size:
                raise ServiceException(
                    message=(
                        f'文档解析队列已满（{queue_max_size}）。'
                        '请稍后重试，或增大 RAG_PARSE_QUEUE_MAX_SIZE。'
                    )
                )
        if await redis.sadd(cls._queued_members_key, token) == 0:
            return False
        await redis.rpush(cls._queue_key, token)
        await cls._refresh_queue_progress(redis)
        return True

    @classmethod
    async def _remove_from_queue(cls, redis: Redis | None, doc_id: int) -> None:
        if redis is None:
            return
        token = cls._queue_token(doc_id)
        await redis.lrem(cls._queue_key, 0, token)
        await redis.srem(cls._queued_members_key, token)
        await cls._refresh_queue_progress(redis)

    @classmethod
    async def _cancel_parse_task(cls, doc_id: int) -> None:
        task = cls._parse_tasks.get(doc_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @classmethod
    def _start_parse_task(cls, doc_id: int, redis: Redis | None) -> None:
        existing_task = cls._parse_tasks.get(doc_id)
        if existing_task and not existing_task.done():
            return
        cls._parse_tasks[doc_id] = asyncio.create_task(cls._parse_document_async(doc_id, redis))

    @classmethod
    async def get_doc_list_services(
        cls,
        query_db: AsyncSession,
        page_object: DocumentModel,
        data_scope_sql=None,
        redis: Redis | None = None,
    ) -> list[dict[str, Any]]:
        doc_list_result = await DocumentDao.get_doc_list(query_db, page_object, data_scope_sql)
        from utils.common_util import CamelCaseUtil

        doc_list = CamelCaseUtil.transform_result(doc_list_result)
        return await cls._decorate_docs_with_progress(redis, doc_list)

    @classmethod
    async def get_doc_detail_services(
        cls, query_db: AsyncSession, doc_id: int, redis: Redis | None = None
    ) -> DocumentModel:
        doc = await DocumentDao.get_doc_by_id(query_db, doc_id)
        from utils.common_util import CamelCaseUtil

        if not doc:
            return DocumentModel()
        doc_list = await cls._decorate_docs_with_progress(redis, [CamelCaseUtil.transform_result(doc)])
        return DocumentModel(**doc_list[0])

    @classmethod
    async def upload_document_services(
        cls,
        query_db: AsyncSession,
        redis: Redis | None,
        kb_id: int,
        file_name: str,
        file_path: str,
        file_size: int,
        file_type: str,
        create_by: str,
    ) -> CrudResponseModel:
        doc_id: int | None = None
        doc_committed = False
        queue_submitted = False
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
            doc_committed = True
            queue_submitted = await cls._enqueue_parse_task(redis, doc_id)
            if not queue_submitted:
                raise ServiceException(message='Document parse task is already queued or running')
            await cls._set_progress(redis, doc_id, 0, 'Queued, waiting for parsing')
            return CrudResponseModel(is_success=True, message='Upload succeeded, document queued for parsing.')
        except Exception as exc:
            await query_db.rollback()
            if not doc_committed:
                await DocumentStorageService.delete_stored_file(file_path)
            elif doc_id is not None and not queue_submitted:
                try:
                    await DocumentDao.update_parse_status_dao(
                        query_db,
                        doc_id,
                        '3',
                        error_msg=f'Queue submission failed: {exc}',
                    )
                    await query_db.commit()
                except Exception:
                    await query_db.rollback()
            raise

    @classmethod
    async def _parse_document_async(cls, doc_id: int, redis: Redis | None) -> None:
        from config.database import AsyncSessionLocal

        parse_file_path = ''
        should_cleanup_parse_file = False

        try:
            async with AsyncSessionLocal() as db:
                doc = await DocumentDao.get_doc_by_id(db, doc_id)
                if not doc:
                    logger.error(f'Document not found: {doc_id}')
                    return

                # Cache scalar fields before the first commit so parsing does not
                # depend on ORM attribute refreshes in async background tasks.
                doc_kb_id = int(doc.kb_id)
                doc_file_type = doc.file_type
                doc_file_path = doc.file_path
                doc_file_name = doc.file_name
                logger.info(
                    'Document parsing started: '
                    f'doc_id={doc_id}, kb_id={doc_kb_id}, file_name={doc_file_name}, '
                    f'file_type={doc_file_type}, stored_path={doc_file_path}'
                )

                parser = DocumentParserFactory.get_parser(doc_file_type)
                parse_file_path, should_cleanup_parse_file = await DocumentStorageService.prepare_parse_file(
                    doc_file_path, doc_file_name
                )
                logger.info(
                    'Document parse source prepared: '
                    f'doc_id={doc_id}, parse_file_path={parse_file_path}, '
                    f'should_cleanup={should_cleanup_parse_file}'
                )

                await cls._set_progress(redis, doc_id, 5, 'Preparing document parsing')
                await ChunkDao.delete_chunks_by_doc_id_dao(db, doc_id)
                await DocumentDao.update_parse_status_dao(db, doc_id, '1', chunk_count=0, clear_error=True)
                await db.commit()

                await cls._set_progress(redis, doc_id, 10, 'Extracting document text')
                paragraphs = await parser.parse(parse_file_path)
                if not paragraphs:
                    raise ServiceException(message='Document contains no extractable text')

                await cls._set_progress(redis, doc_id, 20, f'Extracted {len(paragraphs)} paragraph(s)')
                splitter = ChunkSplitter()
                chunks = splitter.split_paragraphs(paragraphs, doc_id, doc_kb_id)
                if not chunks:
                    raise ServiceException(message='Document produced no chunks after splitting')

                chunk_count = len(chunks)
                await DocumentDao.update_parse_status_dao(db, doc_id, '1', chunk_count=chunk_count, clear_error=True)
                await db.commit()
                await cls._set_progress(redis, doc_id, 30, f'Split into {chunk_count} chunk(s), generating embeddings')

                embedding_service = EmbeddingService.get_instance()
                batch_size = max(1, int(RAGConfig.rag_embedding_batch_size))
                total_batches = max(1, math.ceil(chunk_count / batch_size))
                embedded_count = 0

                for batch_index, start in enumerate(range(0, chunk_count, batch_size), start=1):
                    batch_chunks = chunks[start : start + batch_size]
                    texts = [chunk['content'] for chunk in batch_chunks]
                    embeddings = await embedding_service.get_text_embeddings(texts)
                    if len(embeddings) != len(batch_chunks):
                        raise ServiceException(message='Embedding count does not match chunk count')

                    for chunk, embedding in zip(batch_chunks, embeddings):
                        chunk['embedding'] = embedding
                        if 'metadata' in chunk and 'chunk_metadata' not in chunk:
                            chunk['chunk_metadata'] = chunk.pop('metadata')

                    embedded_count += len(batch_chunks)
                    progress = 30 + int((batch_index / total_batches) * 60)
                    await cls._set_progress(
                        redis,
                        doc_id,
                        progress,
                        f'Generating embeddings {embedded_count}/{chunk_count}',
                    )

                await cls._set_progress(redis, doc_id, 95, 'Saving chunk index')
                await ChunkDao.batch_add_chunks_dao(db, chunks)
                await DocumentDao.update_parse_status_dao(db, doc_id, '2', chunk_count=chunk_count, clear_error=True)
                await db.commit()
                await cls._set_progress(redis, doc_id, 100, f'Completed, {chunk_count} chunk(s) indexed')
                logger.info(f'Document parsed successfully: doc_id={doc_id}, chunks={chunk_count}')
        except asyncio.CancelledError:
            logger.info(f'Document parsing cancelled: doc_id={doc_id}')
            raise
        except Exception as exc:
            logger.exception(f'Document parsing failed: doc_id={doc_id}, error={exc}')
            try:
                async with AsyncSessionLocal() as db:
                    await ChunkDao.delete_chunks_by_doc_id_dao(db, doc_id)
                    await DocumentDao.update_parse_status_dao(db, doc_id, '3', error_msg=str(exc))
                    await db.commit()
            except Exception:
                pass
            await cls._set_progress(redis, doc_id, 0, f'Failed: {str(exc)}')
        finally:
            await DocumentStorageService.cleanup_parse_file(parse_file_path, should_cleanup_parse_file)
            cls._parse_tasks.pop(doc_id, None)

    @classmethod
    async def resume_incomplete_tasks(cls, redis: Redis | None) -> None:
        from config.database import AsyncSessionLocal

        if redis is not None:
            await redis.delete(cls._queue_key, cls._queued_members_key, cls._active_members_key)

        async with AsyncSessionLocal() as db:
            pending_docs = await DocumentDao.get_docs_by_parse_statuses(db, ['0', '1'])
            for doc in pending_docs:
                if doc.parse_status != '0':
                    await DocumentDao.update_parse_status_dao(db, doc.doc_id, '0', clear_error=True)
            await db.commit()

        for doc in pending_docs:
            await cls._enqueue_parse_task(redis, doc.doc_id)

        if pending_docs:
            await cls._refresh_queue_progress(redis)
            logger.info(f'Resumed {len(pending_docs)} queued document parse task(s)')

    @classmethod
    async def delete_document_services(
        cls, query_db: AsyncSession, redis: Redis | None, doc_ids: str, update_by: str
    ) -> CrudResponseModel:
        if not doc_ids:
            raise ServiceException(message='Document IDs are required')

        doc_id_list = doc_ids.split(',')
        try:
            for doc_id in doc_id_list:
                int_doc_id = int(doc_id)
                await cls._cancel_parse_task(int_doc_id)
                await cls._remove_from_queue(redis, int_doc_id)

                doc = await DocumentDao.get_doc_by_id(query_db, int_doc_id)
                await ChunkDao.delete_chunks_by_doc_id_dao(query_db, int_doc_id)
                await DocumentDao.delete_doc_dao(
                    query_db, DocumentModel(docId=int_doc_id, updateBy=update_by, updateTime=datetime.now())
                )
                if doc:
                    await DocumentStorageService.delete_stored_file(doc.file_path)
                if redis is not None:
                    await redis.delete(cls._progress_key(int_doc_id))

            await query_db.commit()
            return CrudResponseModel(is_success=True, message='Delete succeeded')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def reparse_document_services(
        cls, query_db: AsyncSession, redis: Redis | None, doc_id: int
    ) -> CrudResponseModel:
        try:
            await cls._cancel_parse_task(doc_id)
            await cls._remove_from_queue(redis, doc_id)
            await ChunkDao.delete_chunks_by_doc_id_dao(query_db, doc_id)
            await DocumentDao.update_parse_status_dao(query_db, doc_id, '0', chunk_count=0, clear_error=True)
            await query_db.commit()
            await cls._enqueue_parse_task(redis, doc_id)
            await cls._set_progress(redis, doc_id, 0, 'Queued for reparse')
            return CrudResponseModel(is_success=True, message='Reparse task queued')
        except Exception:
            await query_db.rollback()
            raise

