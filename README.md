# Cradle RAG 知识库平台

这是一个基于 RuoYi-Vue3-FastAPI 二次开发的知识库与 RAG 问答平台。管理端沿用 RuoYi 的用户、角色、菜单和权限体系，后端使用 FastAPI；RAG 能力基于 LlamaIndex 构建，通过 OpenAI 兼容接口接入 LLM 和 Embedding 服务，并使用 PostgreSQL + pgvector 完成向量存储与检索。

## 核心功能

- 知识库管理：知识库创建、修改、删除、列表查询和数据权限控制。
- 文档管理：支持 PDF、DOC、DOCX、WPS 文档上传、异步解析、解析进度、重新解析和删除。
- 文档解析：PDF 使用 PyMuPDF，Word 文档使用 python-docx，并通过 LibreOffice 处理 DOC/WPS 及复杂 Word 文件的兜底转换。
- 文档切分：按段落、标题和配置的切片大小进行切分，支持重叠窗口和元数据保留。
- 向量化：使用 LlamaIndex 接入 OpenAI 兼容的 Embedding API，默认模型为 `BAAI/bge-m3`，向量维度为 1024。
- 检索问答：支持向量检索、关键词检索和混合检索，默认通过 pgvector 计算余弦相似度，并使用 RRF 融合结果。
- RAG 问答：检索到的证据片段交给大模型生成回答，并返回引用来源和查询日志。
- 智能编排：提供会话、任务、SSE 流式输出、执行步骤和 Trace 记录，状态可保存到 Redis。
- 文件存储：支持本地磁盘和 MinIO 对象存储。
- 基础后台：用户、角色、菜单、部门、日志、监控、定时任务等 RuoYi 管理能力。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、Pinia、Vue Router、Axios、Element Plus、Ant Design Vue、ECharts |
| 后端 | Python 3.12、FastAPI、Pydantic、SQLAlchemy 2、Alembic |
| 数据库 | PostgreSQL 17、pgvector、Redis |
| RAG 与 AI | LlamaIndex、LangChain Core、OpenAI 兼容 API、SiliconFlow |
| 文档处理 | PyMuPDF、python-docx、LibreOffice、pandas、openpyxl |
| 文件存储 | 本地文件系统、MinIO |
| 认证与权限 | JWT、bcrypt、RuoYi 动态菜单和权限控制 |
| 部署 | Docker、Docker Compose、Nginx |

## RAG 处理流程

```text
文档上传
  -> 文档类型识别
  -> 本地磁盘或 MinIO 存储
  -> Redis 队列异步解析
  -> 段落和标题切分
  -> Embedding 向量化
  -> PostgreSQL + pgvector 存储
  -> 向量 / 关键词 / 混合检索
  -> LLM 生成回答
  -> 返回引用来源和查询日志
```

## 代码结构

```text
ruoyi-fastapi-frontend/          Vue 3 管理端和 RAG 页面
ruoyi-fastapi-backend/
├── module_admin/                RuoYi 用户、角色、菜单、权限等基础模块
├── module_rag/                  知识库、文档、解析、切片、向量和检索问答
├── module_orchestrator/         会话、任务、SSE 和 Trace 编排
├── sql/                         数据库初始化脚本
├── app.py                       后端启动入口
└── requirements.txt             后端依赖
docker-compose.yml               开发环境容器编排
docker-compose-prod.yml          生产环境容器编排
```

后端 RAG 接口主要分布在：

- `/rag/kb`：知识库管理
- `/rag/doc`：文档上传和文档管理
- `/rag/retrieve`：只检索证据，不生成回答
- `/rag/query`：检索并生成回答
- `/orchestrator`：会话、任务和流式编排
- `/api/docs`：FastAPI 接口文档，实际路径由 `APP_ROOT_PATH` 决定

## 快速开始

### Docker Compose

先根据 `ruoyi-fastapi-backend/.env.dev.example` 准备运行环境变量，至少配置数据库、Redis、LLM 和 Embedding 服务。启用 MinIO 时使用：

```bash
docker compose --profile minio up -d --build
```

不使用 MinIO 时，将 `RAG_DOCUMENT_STORAGE` 设置为 `local`，然后执行：

```bash
docker compose up -d --build
```

默认访问地址：

- 管理端：`http://localhost:18080`
- 后端服务：`http://localhost:29099`
- 默认账号：`admin`
- 默认密码：`admin123`

### 本地开发

启动后端：

```bash
cd ruoyi-fastapi-backend
pip3 install -r requirements.txt
cp .env.dev.example .env.dev
python3 app.py --env=dev
```

启动前端：

```bash
cd ruoyi-fastapi-frontend
npm install --registry=https://registry.npmmirror.com
npm run dev
```

## 主要配置

RAG 相关配置集中在后端环境变量中：

| 配置 | 说明 |
| --- | --- |
| `RAG_LLM_API_BASE` | OpenAI 兼容的大模型接口地址 |
| `RAG_LLM_API_KEY` | 大模型接口密钥 |
| `RAG_LLM_MODEL` | 问答使用的模型 |
| `RAG_EMBEDDING_API_BASE` | Embedding 接口地址 |
| `RAG_EMBEDDING_API_KEY` | Embedding 接口密钥 |
| `RAG_EMBEDDING_MODEL` | Embedding 模型，默认 `BAAI/bge-m3` |
| `RAG_EMBEDDING_DIMENSION` | 向量维度，默认 1024 |
| `RAG_CHUNK_SIZE` | 文档切片大小，默认 512 |
| `RAG_CHUNK_OVERLAP` | 切片重叠长度，默认 50 |
| `RAG_TOP_K` | 默认召回数量 |
| `RAG_SIMILARITY_THRESHOLD` | 向量检索相似度阈值 |
| `RAG_DOCUMENT_STORAGE` | 文档存储方式，可选 `local` 或 `minio` |

`.env.docker`、`.env.prod` 等文件可能包含真实密钥，不应提交到 GitHub。仓库中只保留 `.env.dev.example` 这类占位配置。

## 项目说明

本项目基于 [RuoYi-Vue3-FastAPI](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI) 二次开发，保留了 RuoYi 的后台管理能力，并在其上增加了知识库、文档解析、向量检索、RAG 问答和智能编排模块。

License: MIT
