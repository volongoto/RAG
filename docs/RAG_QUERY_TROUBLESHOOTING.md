# RAG Query 排查定位手册

本文用于排查内网部署后 `/prod-api/rag/query` 查询报错。

## 1. 先判断问题在哪一层

按下面顺序判断：

1. 浏览器请求层
2. 前端 Nginx 代理层
3. 后端 FastAPI 路由层
4. RAG 检索层
5. 外部 Embedding / LLM 服务层

## 2. 浏览器侧先看什么

在浏览器开发者工具中确认：

- 请求 URL 是否为 `/prod-api/rag/query`
- 请求方法是否为 `POST`
- 响应状态码
- 响应体中的 `code`、`msg`

如果浏览器地址已经正确，但后端没有收到请求，则继续查前端代理层。

## 3. 前端代理层检查项

确认以下配置一致：

- 前端构建命令包含 `--build-arg BUILD_MODE=prod`
- 前端环境变量为 `VITE_APP_BASE_API=/prod-api`
- [nginx.prod.conf](D:/dev/code/RAG/LlamaIndex_RAG/github/cradle-main/ruoyi-fastapi-frontend/bin/nginx.prod.conf) 中存在：
  - `location /prod-api/`
  - `proxy_pass http://cradle-backend:29099/;`

## 4. 后端路由层检查项

确认以下配置一致：

- [ruoyi-fastapi-backend/.env.prod](D:/dev/code/RAG/LlamaIndex_RAG/github/cradle-main/ruoyi-fastapi-backend/.env.prod) 中 `APP_ROOT_PATH='/prod-api'`
- [app.py](D:/dev/code/RAG/LlamaIndex_RAG/github/cradle-main/ruoyi-fastapi-backend/app.py) 使用 `root_path=AppConfig.app_root_path`

请求进入后端后，日志中应看到：

- `RAG query request received`
- `QueryService.query_services started`
- `RAGEngine.query started`

如果这三条都没有，说明问题还在路由到达前。

## 5. 外部服务层检查项

当前查询链路会调用：

- Embedding：`RAG_EMBEDDING_API_BASE`
- LLM：`RAG_LLM_API_BASE`

如果返回的是 `code50002` 或“请求路径错误”，而本项目代码里并没有这个错误码，通常说明是上游模型服务或内网代理返回的。

### 5.1 Embedding 相关日志

现在后端会打印：

- `Embedding model initialized`
- `Embedding request started`
- `Embedding batch request started`
- `Embedding request finished`
- `Embedding batch request finished`
- `Embedding request failed`
- `Embedding batch request failed`

重点看：

- `api_base`
- `model`
- `batch_count`
- `text_length`
- `error`

### 5.2 LLM 相关日志

现在后端会打印：

- `LLM client initialized`
- `LLM completion request started`
- `LLM completion request finished`

重点看：

- `api_base`
- `model`
- `prompt_length`
- `response_length`

如果只有 `started` 没有 `finished`，通常说明：

- 上游路径错误
- 上游接口超时
- 内网代理改写了 `/v1`
- API Key 无效

## 6. 上传与解析问题怎么查

上传和解析相关日志包括：

- `Document upload request received`
- `Document upload payload loaded`
- `Document stored successfully`
- `Document parsing started`
- `Document parse source prepared`
- `Word parser detected format`

如果是 `.doc` 自动兼容链路，还会看到：

- `Converting DOC to DOCX with LibreOffice`
- `DOC converted to DOCX successfully`

## 7. 长文件名问题怎么判断

数据库字段限制：

- `rag_document.file_name = varchar(255)`

当前后端已做两层兜底：

- 数据库存储文件名自动截断
- 实际对象存储文件名自动缩短

如果仍失败，继续检查：

- 宿主机路径长度限制
- MinIO / 文件系统对象 key 限制
- 上传前浏览器或网关是否拦截

## 8. 推荐排查顺序

1. 浏览器确认 URL、状态码、响应体
2. 看后端是否打印 `RAG query request received`
3. 如果没有，查前端 Nginx 和 `APP_ROOT_PATH`
4. 如果有，继续看 Embedding 日志
5. Embedding 正常，再看 LLM 日志
6. 如果是上传/解析问题，再看上传和解析日志

## 9. 建议记录模板

建议用下面格式记录一次排查：

```text
现象：
- /prod-api/rag/query 返回 code=50002, msg=请求路径错误

浏览器侧：
- 请求 URL:
- HTTP 状态码:
- 返回体:

后端入口日志：
- 是否出现 RAG query request received:
- path:
- root_path:

Embedding 日志：
- api_base:
- model:
- started/finished:
- error:

LLM 日志：
- api_base:
- model:
- started/finished:
- error:

结论：
- 问题层级：
- 根因：
- 修复动作：
```

## 10. 重点配置文件

排查时建议同时核对：

- [docker-compose-prod.yml](D:/dev/code/RAG/LlamaIndex_RAG/github/cradle-main/docker-compose-prod.yml)
- [ruoyi-fastapi-backend/.env.prod](D:/dev/code/RAG/LlamaIndex_RAG/github/cradle-main/ruoyi-fastapi-backend/.env.prod)
- [ruoyi-fastapi-frontend/bin/nginx.prod.conf](D:/dev/code/RAG/LlamaIndex_RAG/github/cradle-main/ruoyi-fastapi-frontend/bin/nginx.prod.conf)
- [ruoyi-fastapi-backend/app.py](D:/dev/code/RAG/LlamaIndex_RAG/github/cradle-main/ruoyi-fastapi-backend/app.py)

尤其是：

- `APP_ROOT_PATH`
- `RAG_LLM_API_BASE`
- `RAG_LLM_MODEL`
- `RAG_EMBEDDING_API_BASE`
- `RAG_EMBEDDING_MODEL`
