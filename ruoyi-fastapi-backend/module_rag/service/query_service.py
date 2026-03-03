from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel
from module_rag.dao.chunk_dao import ChunkDao
from module_rag.entity.vo.rag_vo import QueryLogModel, QueryLogQueryModel, QueryRequestModel, QueryResponseModel
from module_rag.service.rag_service import RAGEngine
from utils.common_util import CamelCaseUtil


class QueryService:
    """
    知识查询服务
    """

    def __init__(self):
        self.rag_engine = RAGEngine()

    async def query_services(
        self,
        query_db: AsyncSession,
        query_request: QueryRequestModel,
        user_id: int,
    ) -> QueryResponseModel:
        """
        执行知识查询
        """
        start_time = datetime.now()
        
        try:
            result = await self.rag_engine.query(
                query_text=query_request.query_text,
                kb_ids=query_request.kb_ids,
                top_k=query_request.top_k,
            )
            
            await self._save_query_log(
                query_db,
                query_request,
                result,
                user_id,
                start_time,
            )
            
            return QueryResponseModel(**result)
        except Exception as e:
            raise e

    async def _save_query_log(
        self,
        query_db: AsyncSession,
        query_request: QueryRequestModel,
        result: dict[str, Any],
        user_id: int,
        start_time: datetime,
    ):
        """
        保存查询日志
        """
        from module_rag.entity.do.rag_do import RagQueryLog
        
        try:
            log = RagQueryLog(
                kb_ids=','.join(map(str, query_request.kb_ids)) if query_request.kb_ids else None,
                query_text=query_request.query_text,
                answer_text=result.get('answer_text'),
                source_chunks=result.get('source_chunks'),
                query_time=start_time,
                user_id=user_id,
                response_time=result.get('response_time'),
            )
            query_db.add(log)
            await query_db.commit()
        except Exception as e:
            await query_db.rollback()

    async def get_query_logs_services(
        self,
        query_db: AsyncSession,
        page_object: QueryLogQueryModel,
        user_id: int = None,
    ) -> list[dict[str, Any]]:
        """
        获取查询记录列表
        """
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
        
        query = (
            select(RagQueryLog)
            .where(*conditions if conditions else [True])
            .order_by(RagQueryLog.query_time.desc())
        )
        
        logs = (await query_db.execute(query)).scalars().all()
        return CamelCaseUtil.transform_result(logs)
