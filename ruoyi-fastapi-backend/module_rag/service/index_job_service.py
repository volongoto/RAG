from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select

from config.database import AsyncSessionLocal
from module_rag.entity.do.rag_do import RagDocument
from module_rag.entity.vo.runtime_vo import IndexJobCreateModel, IndexJobModel
from module_rag.service.rag_service import DocumentService


class IndexJobService:
    """
    In-process index job manager for runtime indexing APIs.
    """

    _jobs: dict[str, IndexJobModel] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def create_job(cls, request_data: IndexJobCreateModel, create_by: str) -> IndexJobModel:
        now = datetime.now()
        job = IndexJobModel(
            job_id=uuid4().hex,
            status='pending',
            mode=request_data.mode,
            total_docs=0,
            processed_docs=0,
            failed_docs=0,
            message='Job accepted',
            error=None,
            create_by=create_by,
            create_time=now,
            update_time=now,
        )
        async with cls._lock:
            cls._jobs[job.job_id] = job

        asyncio.create_task(cls._run_job(job.job_id, request_data))
        return job

    @classmethod
    async def get_job(cls, job_id: str) -> Optional[IndexJobModel]:
        async with cls._lock:
            return cls._jobs.get(job_id)

    @classmethod
    async def _set_job_status(
        cls,
        job_id: str,
        *,
        status: Optional[str] = None,
        total_docs: Optional[int] = None,
        processed_docs: Optional[int] = None,
        failed_docs: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        async with cls._lock:
            job = cls._jobs.get(job_id)
            if not job:
                return
            data = job.model_dump()
            if status is not None:
                data['status'] = status
            if total_docs is not None:
                data['total_docs'] = total_docs
            if processed_docs is not None:
                data['processed_docs'] = processed_docs
            if failed_docs is not None:
                data['failed_docs'] = failed_docs
            if message is not None:
                data['message'] = message
            if error is not None:
                data['error'] = error
            data['update_time'] = datetime.now()
            cls._jobs[job_id] = IndexJobModel(**data)

    @classmethod
    async def _run_job(cls, job_id: str, request_data: IndexJobCreateModel) -> None:
        try:
            doc_ids = await cls._resolve_doc_ids(request_data)
            await cls._set_job_status(job_id, status='running', total_docs=len(doc_ids), message='Job running')

            processed_docs = 0
            failed_docs = 0
            for doc_id in doc_ids:
                try:
                    async with AsyncSessionLocal() as db:
                        await DocumentService.reparse_document_services(db, doc_id)
                    processed_docs += 1
                except Exception:
                    failed_docs += 1

                await cls._set_job_status(
                    job_id,
                    processed_docs=processed_docs,
                    failed_docs=failed_docs,
                )

            final_status = 'success' if failed_docs == 0 else 'failed'
            final_message = 'Job finished' if failed_docs == 0 else 'Job finished with failures'
            await cls._set_job_status(
                job_id,
                status=final_status,
                message=final_message,
                error=None if failed_docs == 0 else f'{failed_docs} documents failed',
            )
        except Exception as e:
            await cls._set_job_status(job_id, status='failed', message='Job failed', error=str(e))

    @classmethod
    async def _resolve_doc_ids(cls, request_data: IndexJobCreateModel) -> list[int]:
        if request_data.doc_ids:
            return sorted(list({int(doc_id) for doc_id in request_data.doc_ids}))

        if not request_data.kb_ids:
            return []

        async with AsyncSessionLocal() as db:
            query = (
                select(RagDocument.doc_id)
                .where(RagDocument.kb_id.in_(request_data.kb_ids), RagDocument.del_flag == '0')
                .order_by(RagDocument.doc_id.asc())
            )
            rows = (await db.execute(query)).all()
            return [int(row[0]) for row in rows]
