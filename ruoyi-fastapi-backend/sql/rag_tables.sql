-- ----------------------------
-- RAG知识库系统数据库脚本
-- 依赖：PostgreSQL 17 + pgvector 扩展
-- ----------------------------

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- ----------------------------
-- 1、知识库表
-- ----------------------------
DROP TABLE IF EXISTS rag_knowledge_base;
CREATE TABLE rag_knowledge_base (
    kb_id           BIGSERIAL PRIMARY KEY,
    kb_name         VARCHAR(200) NOT NULL,
    kb_type         VARCHAR(20) NOT NULL,
    description     VARCHAR(500),
    dept_id         BIGINT,
    user_id         BIGINT,
    embedding_model VARCHAR(100) DEFAULT 'BAAI/bge-m3',
    status          CHAR(1) DEFAULT '0',
    del_flag        CHAR(1) DEFAULT '0',
    create_by       VARCHAR(64) DEFAULT '',
    create_time     TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_by       VARCHAR(64) DEFAULT '',
    update_time     TIMESTAMP(0),
    remark          VARCHAR(500)
);

COMMENT ON COLUMN rag_knowledge_base.kb_id IS '知识库ID';
COMMENT ON COLUMN rag_knowledge_base.kb_name IS '知识库名称';
COMMENT ON COLUMN rag_knowledge_base.kb_type IS '知识库类型（dept部门/personal个人）';
COMMENT ON COLUMN rag_knowledge_base.description IS '描述';
COMMENT ON COLUMN rag_knowledge_base.dept_id IS '所属部门ID（部门知识库）';
COMMENT ON COLUMN rag_knowledge_base.user_id IS '所属用户ID（个人知识库）';
COMMENT ON COLUMN rag_knowledge_base.embedding_model IS '向量模型';
COMMENT ON COLUMN rag_knowledge_base.status IS '状态（0正常 1停用）';
COMMENT ON COLUMN rag_knowledge_base.del_flag IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN rag_knowledge_base.create_by IS '创建者';
COMMENT ON COLUMN rag_knowledge_base.create_time IS '创建时间';
COMMENT ON COLUMN rag_knowledge_base.update_by IS '更新者';
COMMENT ON COLUMN rag_knowledge_base.update_time IS '更新时间';
COMMENT ON COLUMN rag_knowledge_base.remark IS '备注';
COMMENT ON TABLE rag_knowledge_base IS '知识库表';

CREATE INDEX idx_kb_dept_id ON rag_knowledge_base(dept_id);
CREATE INDEX idx_kb_user_id ON rag_knowledge_base(user_id);

-- ----------------------------
-- 2、文档表
-- ----------------------------
DROP TABLE IF EXISTS rag_document;
CREATE TABLE rag_document (
    doc_id          BIGSERIAL PRIMARY KEY,
    kb_id           BIGINT NOT NULL,
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    file_size       BIGINT,
    file_type       VARCHAR(20) NOT NULL,
    chunk_count     INT DEFAULT 0,
    parse_status    CHAR(1) DEFAULT '0',
    parse_error     TEXT,
    del_flag        CHAR(1) DEFAULT '0',
    create_by       VARCHAR(64) DEFAULT '',
    create_time     TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_by       VARCHAR(64) DEFAULT '',
    update_time     TIMESTAMP(0)
);

COMMENT ON COLUMN rag_document.doc_id IS '文档ID';
COMMENT ON COLUMN rag_document.kb_id IS '知识库ID';
COMMENT ON COLUMN rag_document.file_name IS '文件名称';
COMMENT ON COLUMN rag_document.file_path IS '文件存储路径';
COMMENT ON COLUMN rag_document.file_size IS '文件大小（字节）';
COMMENT ON COLUMN rag_document.file_type IS '文件类型（docx/pdf）';
COMMENT ON COLUMN rag_document.chunk_count IS '切片数量';
COMMENT ON COLUMN rag_document.parse_status IS '解析状态（0待解析/1解析中/2成功/3失败）';
COMMENT ON COLUMN rag_document.parse_error IS '解析错误信息';
COMMENT ON COLUMN rag_document.del_flag IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN rag_document.create_by IS '上传者';
COMMENT ON COLUMN rag_document.create_time IS '创建时间';
COMMENT ON COLUMN rag_document.update_by IS '更新者';
COMMENT ON COLUMN rag_document.update_time IS '更新时间';
COMMENT ON TABLE rag_document IS '文档表';

CREATE INDEX idx_doc_kb_id ON rag_document(kb_id);
CREATE INDEX idx_doc_create_by ON rag_document(create_by);

-- ----------------------------
-- 3、文档切片表（向量存储）
-- ----------------------------
DROP TABLE IF EXISTS rag_chunk;
CREATE TABLE rag_chunk (
    chunk_id        BIGSERIAL PRIMARY KEY,
    doc_id          BIGINT NOT NULL,
    kb_id           BIGINT NOT NULL,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    metadata        JSONB,
    embedding       vector(1024),
    del_flag        CHAR(1) DEFAULT '0',
    create_time     TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON COLUMN rag_chunk.chunk_id IS '切片ID';
COMMENT ON COLUMN rag_chunk.doc_id IS '文档ID';
COMMENT ON COLUMN rag_chunk.kb_id IS '知识库ID';
COMMENT ON COLUMN rag_chunk.chunk_index IS '切片序号';
COMMENT ON COLUMN rag_chunk.content IS '文本内容';
COMMENT ON COLUMN rag_chunk.metadata IS '元数据（页码、段落位置等）';
COMMENT ON COLUMN rag_chunk.embedding IS '向量（BGE-m3 1024维）';
COMMENT ON COLUMN rag_chunk.del_flag IS '删除标志（0代表存在 2代表删除）';
COMMENT ON COLUMN rag_chunk.create_time IS '创建时间';
COMMENT ON TABLE rag_chunk IS '文档切片表';

CREATE INDEX idx_chunk_doc_id ON rag_chunk(doc_id);
CREATE INDEX idx_chunk_kb_id ON rag_chunk(kb_id);

-- 创建向量索引（IVFFlat，适用于大规模向量检索）
CREATE INDEX idx_chunk_embedding ON rag_chunk 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- ----------------------------
-- 4、查询记录表
-- ----------------------------
DROP TABLE IF EXISTS rag_query_log;
CREATE TABLE rag_query_log (
    log_id          BIGSERIAL PRIMARY KEY,
    kb_ids          VARCHAR(500),
    query_text      TEXT NOT NULL,
    answer_text     TEXT,
    source_chunks   JSONB,
    query_time      TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    user_id         BIGINT,
    response_time   INT
);

COMMENT ON COLUMN rag_query_log.log_id IS '日志ID';
COMMENT ON COLUMN rag_query_log.kb_ids IS '查询的知识库ID列表';
COMMENT ON COLUMN rag_query_log.query_text IS '查询内容';
COMMENT ON COLUMN rag_query_log.answer_text IS '回答内容';
COMMENT ON COLUMN rag_query_log.source_chunks IS '引用的切片信息';
COMMENT ON COLUMN rag_query_log.query_time IS '查询时间';
COMMENT ON COLUMN rag_query_log.user_id IS '查询用户ID';
COMMENT ON COLUMN rag_query_log.response_time IS '响应时间（毫秒）';
COMMENT ON TABLE rag_query_log IS '查询记录表';

CREATE INDEX idx_query_log_user_id ON rag_query_log(user_id);
CREATE INDEX idx_query_log_time ON rag_query_log(query_time);

-- ----------------------------
-- 5. RAG menu seed data
-- ----------------------------
INSERT INTO sys_menu (
    menu_id,
    menu_name,
    parent_id,
    order_num,
    path,
    component,
    query,
    route_name,
    is_frame,
    is_cache,
    menu_type,
    visible,
    status,
    perms,
    icon,
    create_by,
    create_time,
    remark
)
VALUES
    (2000, 'RAG知识库', 0, 10, 'rag', NULL, NULL, '', 1, 0, 'M', '0', '0', '', 'documentation', 'admin', CURRENT_TIMESTAMP, 'RAG知识库管理'),
    (2001, '知识库管理', 2000, 1, 'knowledge-base', 'rag/knowledge-base/index', NULL, '', 1, 0, 'C', '0', '0', 'rag:kb:list', 'tree', 'admin', CURRENT_TIMESTAMP, '知识库管理菜单'),
    (2002, '知识库查询', 2001, 1, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:query', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2003, '知识库新增', 2001, 2, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:add', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2004, '知识库修改', 2001, 3, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:edit', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2005, '知识库删除', 2001, 4, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:remove', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2010, '文档管理', 2000, 2, 'document', 'rag/document/index', NULL, '', 1, 0, 'C', '0', '0', 'rag:doc:list', 'documentation', 'admin', CURRENT_TIMESTAMP, '文档管理菜单'),
    (2011, '文档查询', 2010, 1, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:query', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2012, '文档上传', 2010, 2, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:add', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2013, '文档修改', 2010, 3, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:edit', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2014, '文档删除', 2010, 4, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:remove', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2020, '知识查询', 2000, 3, 'query', 'rag/query/index', NULL, '', 1, 0, 'C', '0', '0', 'rag:query:execute', 'search', 'admin', CURRENT_TIMESTAMP, '知识查询菜单'),
    (2021, '执行查询', 2020, 1, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:query:execute', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2022, '查询记录', 2020, 2, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:query:logs', '#', 'admin', CURRENT_TIMESTAMP, ''),
    (2030, '编排可视化', 2000, 4, 'orchestrator', 'rag/orchestrator/index', NULL, '', 1, 0, 'C', '0', '0', 'rag:query:execute', 'druid', 'admin', CURRENT_TIMESTAMP, 'Agent 编排轨迹可视化')
ON CONFLICT (menu_id) DO NOTHING;
