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

## 9. 容器内直接验证上游接口

如果怀疑是内网代理、上游 `/v1` 路径或模型服务地址问题，建议直接进入后端容器执行 `curl`。

先进入容器：

```bash
docker exec -it cradle-backend /bin/bash
```

### 9.1 验证 Embedding 接口

将下面的变量替换成你线上实际值：

- `EMBED_BASE`：通常来自 `RAG_EMBEDDING_API_BASE`
- `EMBED_KEY`：通常来自 `RAG_EMBEDDING_API_KEY`
- `EMBED_MODEL`：通常来自 `RAG_EMBEDDING_MODEL`

```bash
export EMBED_BASE="https://api.siliconflow.cn/v1"
export EMBED_KEY="your-key"
export EMBED_MODEL="BAAI/bge-m3"

curl -i --max-time 60 \
  "$EMBED_BASE/embeddings" \
  -H "Authorization: Bearer $EMBED_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$EMBED_MODEL\",\"input\":\"测试 embedding 连通性\"}"
```

重点看：

- HTTP 状态码是否为 `200`
- 返回体是否包含 `data`
- 如果报“请求路径错误”，看是不是 `EMBED_BASE` 多了或少了 `/v1`

### 9.2 验证 LLM 接口

将下面的变量替换成你线上实际值：

- `LLM_BASE`：通常来自 `RAG_LLM_API_BASE`
- `LLM_KEY`：通常来自 `RAG_LLM_API_KEY`
- `LLM_MODEL`：通常来自 `RAG_LLM_MODEL`

```bash
export LLM_BASE="https://api.siliconflow.cn/v1"
export LLM_KEY="your-key"
export LLM_MODEL="Qwen/Qwen3-32B"

curl -i --max-time 60 \
  "$LLM_BASE/chat/completions" \
  -H "Authorization: Bearer $LLM_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$LLM_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"只回复：ok\"}],\"temperature\":0}"
```

重点看：

- HTTP 状态码是否为 `200`
- 返回体是否包含 `choices`
- 如果报 `404`、`50002` 或“请求路径错误”，大概率是代理路径配置不对

### 9.3 快速判断 `/v1` 是否重复或缺失

如果你们内网做了模型代理，最常见错误是：

- 实际应配 `https://xxx-proxy/v1`，却写成了 `https://xxx-proxy`
- 实际应配 `https://xxx-proxy`，却写成了 `https://xxx-proxy/v1`

可以直接对比下面两种：

```bash
curl -i "$EMBED_BASE/embeddings" ...
curl -i "${EMBED_BASE%/v1}/v1/embeddings" ...
```

如果只有其中一种能通，说明问题就是 `api_base` 路径前缀不一致。

### 9.4 验证 DNS 与网络连通性

如果 `curl` 超时或连不上，可以继续验证：

```bash
getent hosts api.siliconflow.cn
```

```bash
curl -I --max-time 20 https://api.siliconflow.cn
```

如果是你们内网代理域名，就把域名替换成代理域名。

### 9.5 验证当前进程实际环境变量

如果怀疑容器里读取到的不是你以为的 `.env.prod`，可以直接在容器里执行：

```bash
python - <<'PY'
from config.env import RAGConfig
print("RAG_LLM_API_BASE =", RAGConfig.rag_llm_api_base)
print("RAG_LLM_MODEL =", RAGConfig.rag_llm_model)
print("RAG_EMBEDDING_API_BASE =", RAGConfig.rag_embedding_api_base)
print("RAG_EMBEDDING_MODEL =", RAGConfig.rag_embedding_model)
PY
```

如果这里打印出来的值和你部署预期不一致，优先检查：

- `docker-compose-prod.yml` 的 `env_file`
- 容器是否用了旧镜像/旧配置
- `.env.prod` 是否真的在部署机上被更新

## 10. 建议记录模板

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

## 11. 重点配置文件

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
