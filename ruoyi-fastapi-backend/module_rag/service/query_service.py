from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_rag.entity.vo.rag_vo import QueryLogQueryModel, QueryRequestModel, QueryResponseModel
from module_rag.entity.vo.runtime_vo import RetrieveRequestModel, RetrieveResponseModel
from module_rag.service.rag_service import RAGEngine
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class QueryService:
    """Knowledge query service."""

    def __init__(self):
        self.rag_engine = RAGEngine()

    async def query_services(
        self,
        query_db: AsyncSession,
        query_request: QueryRequestModel,
        user_id: int,
        caller_meta: dict[str, Any] | None = None,
    ) -> QueryResponseModel:
        start_time = datetime.now()
        query_text = (query_request.query_text or '').strip()
        logger.info(
            'QueryService.query_services started: '
            f'user_id={user_id}, kb_ids={query_request.kb_ids}, '
            f'top_k={query_request.top_k}, retrieval_mode={query_request.retrieval_mode}, '
            f'answer_mode={query_request.answer_mode}, query_length={len(query_text)}'
        )

        result = await self.rag_engine.query(
            query_db=query_db,
            query_text=query_text,
            kb_ids=query_request.kb_ids,
            top_k=query_request.top_k,
            retrieval_mode=query_request.retrieval_mode,
            scenario=query_request.scenario,
            answer_mode=query_request.answer_mode,
        )
        await self._save_query_log(query_db, query_request, result, user_id, start_time, caller_meta=caller_meta)
        response_model = QueryResponseModel(**CamelCaseUtil.transform_result(result))
        logger.info(
            'QueryService.query_services completed: '
            f'user_id={user_id}, kb_ids={query_request.kb_ids}, '
            f'response_time={response_model.response_time}, '
            f'source_chunk_count={len(response_model.source_chunks or [])}'
        )
        return response_model

    async def retrieve_services(
        self,
        query_db: AsyncSession,
        retrieve_request: RetrieveRequestModel,
    ) -> RetrieveResponseModel:
        result = await self.rag_engine.retrieve(
            query_db=query_db,
            query_text=retrieve_request.query_text,
            kb_ids=retrieve_request.kb_ids,
            top_k=retrieve_request.top_k,
            retrieval_mode=retrieve_request.retrieval_mode,
        )
        return RetrieveResponseModel(**CamelCaseUtil.transform_result(result))

    async def _save_query_log(
        self,
        query_db: AsyncSession,
        query_request: QueryRequestModel,
        result: dict[str, Any],
        user_id: int,
        start_time: datetime,
        caller_meta: dict[str, Any] | None = None,
    ) -> None:
        from module_rag.entity.do.rag_do import RagQueryLog

        try:
            source_chunks = result.get('source_chunks')
            if caller_meta:
                source_chunks = {
                    'chunks': source_chunks or [],
                    'bridge_meta': caller_meta,
                }
            log = RagQueryLog(
                kb_ids=','.join(map(str, query_request.kb_ids)) if query_request.kb_ids else None,
                query_text=query_request.query_text,
                answer_text=result.get('answer_text'),
                source_chunks=source_chunks,
                query_time=start_time,
                user_id=user_id,
                response_time=result.get('response_time'),
            )
            query_db.add(log)
            await query_db.commit()
        except Exception:
            await query_db.rollback()
            logger.exception(
                'Failed to persist RAG query log: '
                f'user_id={user_id}, kb_ids={query_request.kb_ids}, query_text={query_request.query_text}'
            )

    async def get_query_logs_services(
        self,
        query_db: AsyncSession,
        page_object: QueryLogQueryModel,
        user_id: int = None,
    ) -> list[dict[str, Any]]:
        from sqlalchemy import select
        from module_rag.entity.do.rag_do import RagQueryLog

        conditions = []
        if page_object.log_id:
            conditions.append(RagQueryLog.log_id == page_object.log_id)
        if user_id:
            conditions.append(RagQueryLog.user_id == user_id)
        if page_object.query_text:
            conditions.append(RagQueryLog.query_text.like(f'%{page_object.query_text}%'))
        if page_object.begin_time:
            conditions.append(RagQueryLog.query_time >= page_object.begin_time)
        if page_object.end_time:
            conditions.append(RagQueryLog.query_time <= page_object.end_time)

        query = select(RagQueryLog).where(*conditions if conditions else [True]).order_by(RagQueryLog.query_time.desc())
        logs = (await query_db.execute(query)).scalars().all()
        return CamelCaseUtil.transform_result(logs)
