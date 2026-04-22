import pytest

from module_rag.service.rag_service import RAGEngine


class DummyCleaner:
    async def ainvoke(self, text: str) -> str:
        return text


def build_engine() -> RAGEngine:
    engine = object.__new__(RAGEngine)
    engine.output_cleaner = DummyCleaner()
    engine.llm = object()
    return engine


def build_metrics() -> dict[str, int | str | bool]:
    return {
        'retrieval_mode': 'hybrid',
        'embedding_ms': 0,
        'db_ms': 0,
        'retrieval_ms': 0,
        'vector_embedding_ms': 0,
        'vector_db_ms': 0,
        'lexical_db_ms': 0,
        'fallback_embedding_ms': 0,
        'fallback_vector_db_ms': 0,
        'fallback_embedding_reused': False,
        'threshold_fallback_used': False,
        'vector_chunk_count': 1,
        'lexical_chunk_count': 1,
        'source_chunk_count': 1,
    }


def test_build_prompt_allows_lower_bound_answer():
    engine = build_engine()

    system_prompt, _ = engine._build_prompt(
        query='2023年发生多少案件',
        context='[参考内容 1]\n二、案情概述 2023年11月，某省国安部门在例行网络巡查中发现……',
    )

    assert '至少 N 起/个' in system_prompt
    assert '无法据此确定精确总数' in system_prompt


def test_build_lower_bound_answer_from_chunks():
    engine = build_engine()
    source_chunks = [
        {
            'chunk_id': 11,
            'doc_id': 101,
            'snippet': '二、案情概述 2023年11月，某省国安部门在例行网络巡查中发现……',
        }
    ]

    answer = engine._build_lower_bound_answer_from_chunks(
        query_text='2023年发生多少案件',
        source_chunks=source_chunks,
        answer_mode='detailed',
    )

    assert answer is not None
    assert '至少有1起发生在2023年的案件' in answer
    assert '精确总数' in answer


@pytest.mark.asyncio
async def test_query_applies_lower_bound_fallback_when_model_returns_unknown():
    engine = build_engine()
    retrieved_chunks = [
        {
            'kb_id': 1,
            'chunk_id': 11,
            'doc_id': 101,
            'file_name': 'case-2023.docx',
            'file_path': '/tmp/case-2023.docx',
            'section': None,
            'page': None,
            'paragraph': 1,
            'snippet': '二、案情概述 2023年11月，某省国安部门在例行网络巡查中发现……',
            'retrieval_score': 0.95,
            'rerank_score': None,
            'retrieval_channel': 'hybrid',
            'doc_name': 'case-2023.docx',
            'content': '二、案情概述 2023年11月，某省国安部门在例行网络巡查中发现……',
            'page_num': None,
            'paragraph_index': 1,
            'similarity': 0.95,
        }
    ]

    async def fake_retrieve_chunks_with_metrics(**kwargs):
        return retrieved_chunks, build_metrics()

    async def fake_generate_answer(system_prompt: str, user_prompt: str) -> str:
        return '根据当前知识库内容无法确定2023年的案件数量。'

    engine._retrieve_chunks_with_metrics = fake_retrieve_chunks_with_metrics
    engine._generate_answer = fake_generate_answer

    result = await engine.query(
        query_db=object(),
        query_text='2023年发生多少案件',
        kb_ids=[1],
        top_k=10,
        threshold=0.7,
        retrieval_mode='hybrid',
        scenario='rag-query-ui',
        answer_mode='detailed',
    )

    assert result['source_chunks'][0]['doc_id'] == 101
    assert result['answer_text'].startswith('根据当前已检索到的参考资料，至少有1起发生在2023年的案件。')
