from unittest.mock import AsyncMock

import pytest

from common.vo import PageModel
from module_rag.dao.document_dao import DocumentDao
from module_rag.entity.vo.rag_vo import DocumentQueryModel
from module_rag.service.rag_service import DocumentService


@pytest.mark.asyncio
async def test_get_doc_list_services_preserves_page_metadata(monkeypatch):
    page_result = PageModel(
        rows=[{'docId': 101, 'fileName': 'sample.docx', 'parseStatus': '0'}],
        pageNum=2,
        pageSize=5,
        total=11,
        hasNext=True,
    )
    monkeypatch.setattr(DocumentDao, 'get_doc_list', AsyncMock(return_value=page_result))
    monkeypatch.setattr(
        DocumentService,
        '_decorate_docs_with_progress',
        AsyncMock(return_value=[{'docId': 101, 'fileName': 'sample.docx', 'parseStatus': '0', 'parseProgress': 0}]),
    )

    result = await DocumentService.get_doc_list_services(
        query_db=None,
        page_object=DocumentQueryModel(pageNum=2, pageSize=5),
        redis=object(),
        is_page=True,
    )

    assert result.total == 11
    assert result.page_num == 2
    assert result.page_size == 5
    assert result.has_next is True
    assert result.rows == [{'docId': 101, 'fileName': 'sample.docx', 'parseStatus': '0', 'parseProgress': 0}]
