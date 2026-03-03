from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, CHAR, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from config.database import Base
from config.env import DataBaseConfig
from utils.common_util import SqlalchemyUtil


class RagKnowledgeBase(Base):
    """Knowledge base table."""

    __tablename__ = 'rag_knowledge_base'
    __table_args__ = {'comment': 'Knowledge base table'}

    kb_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='Knowledge base ID')
    kb_name = Column(String(200), nullable=False, comment='Knowledge base name')
    kb_type = Column(String(20), nullable=False, comment='Knowledge base type: dept/personal')
    description = Column(
        String(500),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Description',
    )
    dept_id = Column(
        BigInteger,
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Department ID',
    )
    user_id = Column(
        BigInteger,
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Owner user ID',
    )
    embedding_model = Column(String(100), nullable=True, server_default='BAAI/bge-m3', comment='Embedding model')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='Status: 0 enabled, 1 disabled')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='Delete flag: 0 exists, 2 deleted')
    create_by = Column(String(64), nullable=True, server_default='', comment='Created by')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='Created time')
    update_by = Column(String(64), nullable=True, server_default='', comment='Updated by')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='Updated time')
    remark = Column(
        String(500),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Remark',
    )


class RagDocument(Base):
    """Document table."""

    __tablename__ = 'rag_document'
    __table_args__ = {'comment': 'Document table'}

    doc_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='Document ID')
    kb_id = Column(BigInteger, nullable=False, comment='Knowledge base ID')
    file_name = Column(String(255), nullable=False, comment='File name')
    file_path = Column(String(500), nullable=False, comment='Stored file path')
    file_size = Column(
        BigInteger,
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='File size (bytes)',
    )
    file_type = Column(String(20), nullable=False, comment='File type: docx/pdf')
    chunk_count = Column(Integer, nullable=True, server_default='0', comment='Chunk count')
    parse_status = Column(
        CHAR(1),
        nullable=True,
        server_default='0',
        comment='Parse status: 0 pending, 1 running, 2 success, 3 failed',
    )
    parse_error = Column(
        Text,
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Parse error message',
    )
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='Delete flag: 0 exists, 2 deleted')
    create_by = Column(String(64), nullable=True, server_default='', comment='Uploaded by')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='Created time')
    update_by = Column(String(64), nullable=True, server_default='', comment='Updated by')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='Updated time')


class RagChunk(Base):
    """Document chunk table."""

    __tablename__ = 'rag_chunk'
    __table_args__ = {'comment': 'Document chunk table'}

    chunk_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='Chunk ID')
    doc_id = Column(BigInteger, nullable=False, comment='Document ID')
    kb_id = Column(BigInteger, nullable=False, comment='Knowledge base ID')
    chunk_index = Column(Integer, nullable=False, comment='Chunk index in document')
    content = Column(Text, nullable=False, comment='Chunk text content')
    # Use a non-reserved Python attribute while preserving DB column name "metadata".
    chunk_metadata = Column('metadata', JSONB, nullable=True, comment='Chunk metadata')
    embedding = Column(Vector(1024), nullable=True, comment='Embedding vector (1024 dim)')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='Delete flag: 0 exists, 2 deleted')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='Created time')


class RagQueryLog(Base):
    """Query log table."""

    __tablename__ = 'rag_query_log'
    __table_args__ = {'comment': 'Query log table'}

    log_id = Column(BigInteger, primary_key=True, autoincrement=True, comment='Log ID')
    kb_ids = Column(
        String(500),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Queried knowledge base IDs',
    )
    query_text = Column(Text, nullable=False, comment='Query text')
    answer_text = Column(
        Text,
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Answer text',
    )
    source_chunks = Column(JSONB, nullable=True, comment='Referenced chunk list')
    query_time = Column(DateTime, nullable=True, default=datetime.now, comment='Query time')
    user_id = Column(
        BigInteger,
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='User ID',
    )
    response_time = Column(
        Integer,
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Response time in ms',
    )
