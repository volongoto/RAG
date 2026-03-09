import re
from typing import Any

from config.env import RAGConfig
from loguru import logger


class ChunkSplitter:
    """
    文档切片服务
    支持段落/章节智能切分
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        self.chunk_size = chunk_size or RAGConfig.rag_chunk_size
        self.chunk_overlap = chunk_overlap or RAGConfig.rag_chunk_overlap

    def split_paragraphs(self, paragraphs: list[dict[str, Any]], doc_id: int, kb_id: int) -> list[dict[str, Any]]:
        """
        智能切分段落
        """
        chunks = []
        chunk_index = 0
        current_chunk_content = []
        current_chunk_size = 0
        current_metadata = {
            'doc_id': doc_id,
            'kb_id': kb_id,
            'page_nums': set(),
            'paragraph_indices': [],
        }

        for para in paragraphs:
            content = para['content']
            para_size = len(content)

            if self._is_heading(para) and current_chunk_content:
                chunk = self._create_chunk(
                    current_chunk_content,
                    current_metadata,
                    chunk_index,
                )
                if chunk:
                    chunks.append(chunk)
                    chunk_index += 1
                current_chunk_content = []
                current_chunk_size = 0
                current_metadata = {
                    'doc_id': doc_id,
                    'kb_id': kb_id,
                    'page_nums': set(),
                    'paragraph_indices': [],
                }

            if current_chunk_size + para_size > self.chunk_size and current_chunk_content:
                chunk = self._create_chunk(
                    current_chunk_content,
                    current_metadata,
                    chunk_index,
                )
                if chunk:
                    chunks.append(chunk)
                    chunk_index += 1

                overlap_content = self._get_overlap_content(current_chunk_content)
                current_chunk_content = overlap_content
                current_chunk_size = sum(len(c) for c in overlap_content)
                current_metadata = {
                    'doc_id': doc_id,
                    'kb_id': kb_id,
                    'page_nums': set(),
                    'paragraph_indices': [],
                }

            current_chunk_content.append(content)
            current_chunk_size += para_size
            if para.get('page_num'):
                current_metadata['page_nums'].add(para['page_num'])
            current_metadata['paragraph_indices'].append(para.get('paragraph_index', 0))

        if current_chunk_content:
            chunk = self._create_chunk(
                current_chunk_content,
                current_metadata,
                chunk_index,
            )
            if chunk:
                chunks.append(chunk)

        logger.info(f'文档切分完成，共生成 {len(chunks)} 个切片')
        return chunks

    def _is_heading(self, para: dict[str, Any]) -> bool:
        """
        判断是否为标题段落
        """
        if para.get('is_heading'):
            return True
        
        content = para['content'].strip()
        heading_patterns = [
            r'^第[一二三四五六七八九十]+[章节篇部]',
            r'^[一二三四五六七八九十]+[、.]',
            r'^\d+[、.]',
            r'^[（(]\d+[)）]',
            r'^[A-Z]\.',
        ]
        for pattern in heading_patterns:
            if re.match(pattern, content):
                return True
        return False

    def _create_chunk(
        self,
        contents: list[str],
        metadata: dict[str, Any],
        chunk_index: int,
    ) -> dict[str, Any]:
        """
        创建切片
        """
        content = '\n\n'.join(contents).strip()
        if not content:
            return None

        return {
            'doc_id': metadata['doc_id'],
            'kb_id': metadata['kb_id'],
            'chunk_index': chunk_index,
            'content': content,
            'metadata': {
                'page_nums': sorted(list(metadata['page_nums'])),
                'paragraph_indices': metadata['paragraph_indices'],
            },
            'del_flag': '0',
        }

    def _get_overlap_content(self, contents: list[str]) -> list[str]:
        """
        获取重叠内容
        """
        if self.chunk_overlap <= 0:
            return []

        overlap_content = []
        total_size = 0

        for content in reversed(contents):
            content_size = len(content)
            if total_size + content_size <= self.chunk_overlap:
                overlap_content.insert(0, content)
                total_size += content_size
            else:
                # Keep overlap at paragraph granularity. Avoid taking a
                # character-level suffix which splits one paragraph into
                # two incomplete pieces.
                if not overlap_content:
                    overlap_content.insert(0, content)
                break

        return overlap_content
