# RAG + Agent Orchestrator 对外 API 接口说明

版本: `v1`
更新时间: `2026-03-27`
对齐实现: `cradle-main` 当前代码

## 1. 适用范围

本文档用于其他平台、业务系统、中台服务或第三方服务通过 HTTP 调用当前系统的 RAG 与 Agent 编排能力。

当前代码中，对外接口分为两类：

- 用户态接口：基于后台登录态 JWT 调用，适合前端、BFF、业务后台直接接入。
- 系统态接口：基于服务签名调用，适合系统到系统集成，不依赖后台用户登录态。

典型链路：

`Business App -> Agent Orchestrator -> RAG Runtime`

`Business Service -> Internal RAG Bridge -> RAG Runtime`

建议：

- 多轮问答、统一对话入口优先使用 `/orchestrator/*`
- 纯检索、纯问答可直接使用 `/rag/*`
- 系统到系统集成、外部系统用户映射场景使用 `/internal/rag/*`

## 2. 服务地址与文档入口

### 2.1 当前仓库可确认的访问入口

| 场景 | 实际地址 | 说明 |
|---|---|---|
| Docker 统一入口 | `http://{host}:18080` | `docker-compose.yml` 暴露的前端 Nginx 入口 |
| Docker API 基地址 | `http://{host}:18080/docker-api` | 外部系统通过 Docker 部署访问时，推荐使用这个基地址 |
| 后端直连 | `http://{host}:29099` | 直接访问 FastAPI 服务 |
| 容器内服务名 | `http://cradle-backend:29099` | 同一 Docker 网络内的其他容器可直接访问 |
| 开发代理基地址 | `http://{host}/dev-api` | 对应 `.env.dev.example` 中 `APP_ROOT_PATH=/dev-api` |
| 生产代理基地址 | `http://{host}/prod-api` | 对应 `.env.prod.example` 中 `APP_ROOT_PATH=/prod-api` |
| Swagger UI | `http://{host}:29099/docs` | 直连后端查看 OpenAPI 页面 |
| ReDoc | `http://{host}:29099/redoc` | 直连后端查看 ReDoc |
| OpenAPI JSON | `http://{host}:29099/openapi.json` | 原始 OpenAPI Schema |

说明：

- 下文统一使用 `{apiBase}` 表示“实际发请求时的基地址”。
- Docker 部署下，推荐取值：`http://{host}:18080/docker-api`
- 后端直连时，取值：`http://{host}:29099`
- 实际请求地址计算方式：`{apiBase}{path}`

示例：

- Docker 代理方式：`POST http://127.0.0.1:18080/docker-api/orchestrator/chat`
- 后端直连方式：`POST http://127.0.0.1:29099/orchestrator/chat`

### 2.2 反向代理路径说明

当前 Docker Nginx 配置将：

`/docker-api/* -> cradle-backend:29099/*`

也就是说：

- 外部请求路径：`/docker-api/orchestrator/chat`
- 后端实际收到的路径：`/orchestrator/chat`

这一点对系统签名接口很重要：如果你调用 `/internal/rag/*`，签名头中的路径必须填写后端真实路径，不带网关前缀。

例如：

- 实际请求 URL：`http://{host}:18080/docker-api/internal/rag/query`
- `X-Service-Path` 必须填写：`/internal/rag/query`

## 3. 快速对接方式

### 3.1 用户态 JWT 接入

1. 调用 `POST {apiBase}/login` 获取 token
2. 后续业务请求统一带上 `Authorization: Bearer {token}`
3. 对话场景调用 `POST {apiBase}/orchestrator/chat`
4. 纯 RAG 问答调用 `POST {apiBase}/rag/query`
5. 异步长任务调用 `POST {apiBase}/orchestrator/tasks`

### 3.2 系统态签名接入

1. 由服务端配置来源系统白名单与共享密钥
2. 按文档生成 `X-Service-Signature`
3. 先调用 `POST http://{host}:29099/internal/rag/kbs/visible` 获取可见知识库
4. 再调用 `POST http://{host}:29099/internal/rag/query` 执行问答

说明：

- 系统态接口更适合“外部系统用户 -> 本系统用户/部门”映射后访问知识库的场景。
- 该类接口不使用后台登录态 JWT，而是使用服务签名。

## 4. 鉴权、请求头与调用方式

### 4.1 用户态接口请求头

| Header | 是否必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | 固定使用 `Bearer {token}` |
| `Content-Type` | POST 时是 | 除登录外统一为 `application/json` |
| `X-Tenant-Id` | 否 | 不传时默认按 `default` 处理 |
| `X-User-Id` | 否 | 可传；但当前实现优先使用 token 中解析出的用户 ID |
| `X-Request-Id` | 建议 | 请求唯一 ID，便于审计与排障 |
| `X-Trace-Id` | 建议 | 链路追踪 ID；不传时默认跟随 `X-Request-Id` |
| `Idempotency-Key` | 部分接口必填 | 见下文幂等说明 |
| `Accept` | 流式时建议 | SSE 场景建议传 `text/event-stream` |

### 4.2 幂等说明

以下接口必须传 `Idempotency-Key`：

- `POST /orchestrator/tasks`
- `POST /rag/index/jobs`

当前实现：

- 幂等窗口为 `3600` 秒
- 重复 key 会被拒绝
- 拒绝时通常返回统一 JSON 包装，`code=500`，`msg=Duplicate idempotency key`

### 4.3 用户态权限点

| 接口 | 权限 |
|---|---|
| `/orchestrator/chat` | `rag:query:execute` |
| `/orchestrator/tasks` | `rag:query:execute` |
| `/orchestrator/tasks/{taskId}` | `rag:query:execute` |
| `/orchestrator/sessions/{sessionId}` | `rag:query:execute` |
| `/rag/retrieve` | `rag:query:execute` |
| `/rag/query` | `rag:query:execute` |
| `/rag/query/logs` | `rag:query:logs` |
| `/rag/index/jobs` (POST) | `rag:doc:edit` |
| `/rag/index/jobs/{jobId}` (GET) | `rag:doc:query` |

### 4.4 系统态签名接口请求头

| Header | 是否必填 | 说明 |
|---|---|---|
| `Content-Type` | 是 | `application/json` |
| `X-Service-Source-System` | 是 | 来源系统编码，必须在服务端白名单中 |
| `X-Service-Timestamp` | 是 | Unix 秒级时间戳 |
| `X-Service-Path` | 是 | 后端真实请求路径，如 `/internal/rag/query` |
| `X-Service-Signature` | 是 | HMAC-SHA256 十六进制签名 |
| `X-Service-Request-Id` | 否 | 调用方请求 ID，便于排障 |

当前实现还会校验：

- 时间戳是否在有效窗口内，默认 `300` 秒
- 来源系统是否命中 `RAG_INTERNAL_ALLOWED_SOURCE_SYSTEMS`
- 请求体是否为合法 JSON

### 4.5 签名算法

签名明文拼接规则：

```text
{METHOD}
{PATH}
{SOURCE_SYSTEM}
{TIMESTAMP}
{CANONICAL_JSON_BODY}
```

其中：

- `METHOD` 为大写 HTTP 方法，如 `POST`
- `PATH` 为后端真实路径，如 `/internal/rag/query`
- `SOURCE_SYSTEM` 为 `X-Service-Source-System`
- `TIMESTAMP` 为 `X-Service-Timestamp`
- `CANONICAL_JSON_BODY` 为请求体 JSON 按 key 排序、无多余空格后的字符串

签名算法：

`HMAC-SHA256(secret, canonical_message).hexdigest()`

Python 示例：

```python
import hashlib
import hmac
import json
import time

method = "POST"
path = "/internal/rag/query"
source_system = "your-source-system"
timestamp = str(int(time.time()))
payload = {
    "principal": {
        "sourceSystem": source_system,
        "externalUserId": "10001"
    },
    "query": {
        "sessionId": "s-001",
        "scenario": "qa",
        "locale": "zh-CN",
        "queryText": "请总结合同审批流程",
        "kbIds": [1, 2],
        "topK": 10,
        "retrievalMode": "hybrid",
        "answerMode": "detailed",
        "includeSource": True
    }
}
secret = "replace-with-your-shared-secret"

canonical_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
canonical_message = "\n".join([method, path, source_system, timestamp, canonical_payload])
signature = hmac.new(secret.encode("utf-8"), canonical_message.encode("utf-8"), hashlib.sha256).hexdigest()

print(signature)
```

## 5. 登录与 Token 获取

### 5.1 登录地址

`POST {apiBase}/login`

### 5.2 请求方式

- 方法：`POST`
- `Content-Type: application/x-www-form-urlencoded`

表单字段：

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `username` | 是 | 用户名 |
| `password` | 是 | 密码 |
| `grant_type` | 否 | 可传 `password` |
| `code` | 按配置 | 开启验证码时必填 |
| `uuid` | 按配置 | 开启验证码时必填 |

说明：

- 当前登录接口不是 JSON，而是表单提交。
- 如果服务端开启验证码，必须同时传 `code` 和 `uuid`。

### 5.3 成功响应示例

```json
{
  "code": 200,
  "msg": "登录成功",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "success": true,
  "time": "2026-03-27T10:00:00"
}
```

后续业务调用统一使用：

```text
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

## 6. 通用响应格式

除 SSE 流式接口外，其他接口统一返回 JSON 包装：

```json
{
  "code": 200,
  "msg": "操作成功",
  "success": true,
  "time": "2026-03-27T10:00:00",
  "data": {}
}
```

说明：

- 当前项目大量业务异常仍返回 HTTP `200`
- 结果判定必须以 `code`、`success`、`msg` 为准，不要只看 HTTP 状态码

常见 `code`：

| code | 说明 |
|---|---|
| `200` | 成功 |
| `401` | 未登录或 token 无效 |
| `403` | 权限不足 |
| `500` | 服务异常、参数不满足当前实现要求、重复幂等 key 等 |
| `601` | 业务警告 |

## 7. API 总览

| 类别 | 方法 | 路径 | 鉴权方式 | 说明 |
|---|---|---|---|---|
| 用户态 | POST | `/orchestrator/chat` | JWT | Agent 单轮/多轮对话，支持 SSE |
| 用户态 | POST | `/orchestrator/tasks` | JWT + 幂等 | 创建异步长任务 |
| 用户态 | GET | `/orchestrator/tasks/{taskId}` | JWT | 查询长任务状态 |
| 用户态 | GET | `/orchestrator/sessions/{sessionId}` | JWT | 查询会话消息视图 |
| 用户态 | POST | `/rag/retrieve` | JWT | 仅检索证据，不生成答案 |
| 用户态 | POST | `/rag/query` | JWT | 检索 + 生成答案 |
| 用户态 | GET | `/rag/query/logs` | JWT | 查询 RAG 历史日志 |
| 用户态 | POST | `/rag/index/jobs` | JWT + 幂等 | 创建索引任务 |
| 用户态 | GET | `/rag/index/jobs/{jobId}` | JWT | 查询索引任务状态 |
| 系统态 | POST | `/internal/rag/kbs/visible` | 服务签名 | 获取映射主体可访问知识库 |
| 系统态 | POST | `/internal/rag/query` | 服务签名 | 外部系统身份映射后的 RAG 问答 |

## 8. 接口明细

### 8.1 POST `/orchestrator/chat`

用途：

- 统一 Agent 对话入口
- `stream=false` 返回完整 JSON
- `stream=true` 返回 `text/event-stream`

调用地址：

- `{apiBase}/orchestrator/chat`

请求体：

```json
{
  "sessionId": "s-001",
  "scenario": "qa",
  "locale": "zh-CN",
  "message": "请总结合同审批流程",
  "kbIds": [1, 2],
  "stream": false,
  "topK": 10,
  "retrievalMode": "hybrid",
  "includeSource": true
}
```

字段说明：

- `kbIds`：知识库 ID 列表，必填
- `message`：用户输入，必填
- `stream`：是否流式输出，默认 `false`
- `topK`：检索条数，默认 `10`，范围 `1~50`
- `retrievalMode`：`vector | lexical | hybrid`
- `includeSource`：是否返回证据片段

非流式响应 `data`：

```json
{
  "sessionId": "s-001",
  "requestId": "req-001",
  "traceId": "trace-001",
  "finalAnswer": "审批流程分为发起、部门审核、法务复核、归档。",
  "citations": [
    {
      "kbId": 1,
      "docId": 10,
      "fileName": "合同制度.md",
      "filePath": "/docs/合同制度.md",
      "chunkId": 101,
      "section": "审批流程",
      "page": 2,
      "paragraph": 5,
      "snippet": "审批流程包括...",
      "retrievalScore": 0.88,
      "rerankScore": null,
      "retrievalChannel": "hybrid"
    }
  ],
  "toolCalls": [
    {
      "tool": "rag.retrieve",
      "status": "success",
      "latencyMs": 120,
      "summary": "returned 10 chunks"
    },
    {
      "tool": "rag.query",
      "status": "success",
      "latencyMs": 890,
      "summary": "answer generated"
    }
  ],
  "traceEvents": [],
  "latencyMs": 1040
}
```

流式响应：

- `Content-Type: text/event-stream`
- 返回值不是统一 JSON 包装，而是原始 SSE 数据流

事件示例：

```text
data: {"event":"step","data":{"stepKey":"request.accepted","status":"started"}}

data: {"event":"step","data":{"stepKey":"rag.retrieve","status":"success"}}

data: {"event":"answer","data":{"finalAnswer":"审批流程分为发起、部门审核、法务复核、归档。","citations":[]}}

data: {"event":"done","data":{"sessionId":"s-001","requestId":"req-001","traceId":"trace-001","finalAnswer":"...","citations":[],"toolCalls":[],"traceEvents":[],"latencyMs":1040}}
```

流式事件类型：

- `step`：步骤状态变化
- `answer`：答案与证据已准备完成
- `done`：最终完整结果
- `error`：流式执行失败

当前实现补充说明：

- 如果下游 `rag.query` 超时或失败，Orchestrator 会返回降级答案，而不是直接中断
- 降级答案通常基于已检索到的证据片段拼接生成

### 8.2 POST `/orchestrator/tasks`

用途：

- 创建异步 Agent 长任务，例如报告生成、批量分析

调用地址：

- `{apiBase}/orchestrator/tasks`

请求头：

- 必填 `Idempotency-Key`

请求体：

```json
{
  "sessionId": "s-task-001",
  "scenario": "report",
  "locale": "zh-CN",
  "taskType": "report_generation",
  "payload": {
    "message": "生成本月风险分析报告",
    "kbIds": [1, 2],
    "topK": 10,
    "retrievalMode": "hybrid",
    "includeSource": true
  }
}
```

字段说明：

- `taskType`：当前实现未限定枚举，建议传业务定义值，如 `report_generation`
- `payload.message`：当前实现必填
- `payload.kbIds`：当前实现必填

响应 `data`：

```json
{
  "taskId": "a1b2c3",
  "status": "pending",
  "taskType": "report_generation",
  "sessionId": "s-task-001",
  "requestId": "req-task-001",
  "traceId": "trace-task-001",
  "currentStep": "等待执行",
  "progressPercent": 0,
  "traceEvents": [],
  "result": null,
  "error": null,
  "createTime": "2026-03-27T10:00:00",
  "updateTime": "2026-03-27T10:00:00"
}
```

当前实现补充说明：

- Orchestrator 任务状态优先保存在 Redis，Redis 不可用时退回进程内存
- 任务与会话状态默认保留约 `24` 小时，不适合作为长期归档数据源

### 8.3 GET `/orchestrator/tasks/{taskId}`

用途：

- 查询任务状态与结果

调用地址：

- `{apiBase}/orchestrator/tasks/{taskId}`

状态值：

- `pending | running | success | failed`

补充字段：

- `currentStep`：当前执行步骤
- `progressPercent`：进度，范围 `0~100`
- `traceEvents`：结构化步骤轨迹
- `result`：成功时返回最终问答结果结构
- `error`：失败原因

当前实现补充说明：

- 如果任务处于 `running` 且超过约 `120` 秒没有状态更新，会被标记为失败

### 8.4 GET `/orchestrator/sessions/{sessionId}`

用途：

- 查询会话消息视图

调用地址：

- `{apiBase}/orchestrator/sessions/{sessionId}`

响应 `data`：

```json
{
  "sessionId": "s-001",
  "messages": [
    {
      "role": "user",
      "content": "问题1",
      "time": "2026-03-27T10:00:00"
    },
    {
      "role": "assistant",
      "content": "回答1",
      "time": "2026-03-27T10:00:01"
    }
  ],
  "updateTime": "2026-03-27T10:00:01"
}
```

说明：

- `role` 取值：`user | assistant`
- 当前实现返回的是运行时会话视图，不是永久聊天归档

### 8.5 POST `/rag/retrieve`

用途：

- 仅检索，不生成答案

调用地址：

- `{apiBase}/rag/retrieve`

请求体：

```json
{
  "sessionId": "s-001",
  "scenario": "qa",
  "locale": "zh-CN",
  "kbIds": [1, 2],
  "queryText": "合同审批流程",
  "topK": 10,
  "retrievalMode": "hybrid"
}
```

响应 `data`：

```json
{
  "chunks": [
    {
      "kbId": 1,
      "docId": 10,
      "fileName": "合同制度.md",
      "filePath": "/docs/合同制度.md",
      "chunkId": 101,
      "section": "审批流程",
      "page": 2,
      "paragraph": 5,
      "snippet": "审批流程包括...",
      "retrievalScore": 0.88,
      "rerankScore": null,
      "retrievalChannel": "hybrid"
    }
  ],
  "responseTime": 95
}
```

### 8.6 POST `/rag/query`

用途：

- 检索 + 生成答案

调用地址：

- `{apiBase}/rag/query`

请求体：

```json
{
  "sessionId": "s-001",
  "scenario": "qa",
  "locale": "zh-CN",
  "kbIds": [1, 2],
  "queryText": "合同审批流程",
  "topK": 10,
  "retrievalMode": "hybrid",
  "includeSource": true,
  "answerMode": "detailed"
}
```

字段说明：

- `topK`：默认 `10`，范围 `1~50`
- `retrievalMode`：`vector | lexical | hybrid`
- `answerMode`：`concise | detailed`，默认 `detailed`
- `includeSource`：兼容字段；当前实现仍会返回 `sourceChunks`

响应 `data`：

```json
{
  "answerText": "审批流程分为发起、审核、复核、归档。",
  "sourceChunks": [
    {
      "kbId": 1,
      "chunkId": 101,
      "docId": 10,
      "fileName": "合同制度.md",
      "filePath": "/docs/合同制度.md",
      "section": "审批流程",
      "page": 2,
      "paragraph": 5,
      "snippet": "审批流程包括...",
      "retrievalScore": 0.88,
      "rerankScore": null,
      "retrievalChannel": "hybrid",
      "docName": "合同制度.md",
      "content": "审批流程包括...",
      "pageNum": 2,
      "paragraphIndex": 5,
      "similarity": 0.88
    }
  ],
  "responseTime": 620
}
```

### 8.7 GET `/rag/query/logs`

用途：

- 查询 RAG 历史日志

调用地址：

- `{apiBase}/rag/query/logs`

查询参数：

- `logId`
- `userId`
- `queryText`
- `beginTime`
- `endTime`
- `pageNum`
- `pageSize`

说明：

- 当前实现支持以上筛选字段
- 当前实现返回的是匹配日志列表，未实际执行分页裁剪

### 8.8 POST `/rag/index/jobs`

用途：

- 创建文档重解析 / 知识库重建索引任务

调用地址：

- `{apiBase}/rag/index/jobs`

请求头：

- 必填 `Idempotency-Key`

请求体：

```json
{
  "sessionId": "s-index-001",
  "scenario": "indexing",
  "locale": "zh-CN",
  "mode": "reparse_docs",
  "docIds": [1001, 1002],
  "kbIds": []
}
```

字段说明：

- `mode`：`reparse_docs | rebuild_kb`
- 如果 `docIds` 为空且传入 `kbIds`，系统会先根据知识库解析出文档集合

响应 `data`：

```json
{
  "jobId": "job-001",
  "status": "pending",
  "mode": "reparse_docs",
  "totalDocs": 0,
  "processedDocs": 0,
  "failedDocs": 0,
  "message": "Job accepted",
  "error": null,
  "createBy": "admin",
  "createTime": "2026-03-27T10:00:00",
  "updateTime": "2026-03-27T10:00:00"
}
```

### 8.9 GET `/rag/index/jobs/{jobId}`

用途：

- 查询索引任务状态

调用地址：

- `{apiBase}/rag/index/jobs/{jobId}`

状态值：

- `pending | running | success | failed`

当前实现补充说明：

- 索引任务状态当前保存在进程内存中
- 如果服务重启，旧 `jobId` 的状态无法继续查询

### 8.10 POST `/internal/rag/kbs/visible`

用途：

- 按“外部系统主体”解析本系统用户/部门映射，并返回可访问知识库

调用地址：

- 后端直连：`http://{host}:29099/internal/rag/kbs/visible`
- 容器内调用：`http://cradle-backend:29099/internal/rag/kbs/visible`

请求体：

```json
{
  "principal": {
    "sourceSystem": "your-source-system",
    "externalUserId": "10001",
    "externalUserName": "zhangsan",
    "externalDeptId": "2001"
  }
}
```

响应 `data`：

```json
{
  "principal": {
    "sourceSystem": "your-source-system",
    "externalUserId": "10001",
    "externalUserName": "zhangsan",
    "externalDeptId": "2001",
    "mappedUserId": 12,
    "mappedUserName": "zhangsan",
    "mappedDeptId": 103,
    "mappedDeptName": "法务部",
    "isAdmin": false,
    "resolutionMode": "user_id_map"
  },
  "kbIds": [1, 2],
  "knowledgeBases": [
    {
      "kbId": 1,
      "kbName": "法务知识库",
      "kbType": "dept"
    }
  ]
}
```

说明：

- 不需要 JWT
- 必须使用服务签名头
- 返回的 `resolutionMode` 表示映射命中方式，如 `user_id_map`、`user_name_map`、`direct_user_id`、`username_lookup`、`dept_id_map`

### 8.11 POST `/internal/rag/query`

用途：

- 基于外部系统用户/部门映射执行 RAG 问答

调用地址：

- 后端直连：`http://{host}:29099/internal/rag/query`
- 容器内调用：`http://cradle-backend:29099/internal/rag/query`

请求体：

```json
{
  "principal": {
    "sourceSystem": "your-source-system",
    "externalUserId": "10001",
    "externalUserName": "zhangsan",
    "externalDeptId": "2001"
  },
  "query": {
    "sessionId": "s-001",
    "scenario": "qa",
    "locale": "zh-CN",
    "queryText": "请总结合同审批流程",
    "kbIds": [1, 2],
    "topK": 10,
    "includeSource": true,
    "retrievalMode": "hybrid",
    "answerMode": "detailed"
  }
}
```

响应结构：

- 与 `/rag/query` 的 `data` 结构一致

说明：

- 如果 `query.kbIds` 为空，当前实现会自动使用该主体可见的全部知识库
- 如果映射后没有任何可访问知识库，接口会返回错误

## 9. cURL 调用示例

### 9.1 登录获取 token

```bash
curl -X POST "{apiBase}/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=admin" \
  --data-urlencode "password=123456"
```

### 9.2 Orchestrator Chat 非流式

```bash
curl -X POST "{apiBase}/orchestrator/chat" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-Id: t1" \
  -H "X-Request-Id: req-1001" \
  -H "X-Trace-Id: trace-1001" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "s-001",
    "scenario": "qa",
    "locale": "zh-CN",
    "message": "请总结合同审批流程",
    "kbIds": [1, 2],
    "stream": false,
    "topK": 10,
    "retrievalMode": "hybrid",
    "includeSource": true
  }'
```

### 9.3 Orchestrator Chat 流式 SSE

```bash
curl -N -X POST "{apiBase}/orchestrator/chat" \
  -H "Authorization: Bearer <token>" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "s-001",
    "scenario": "qa",
    "locale": "zh-CN",
    "message": "请总结合同审批流程",
    "kbIds": [1, 2],
    "stream": true,
    "topK": 10,
    "retrievalMode": "hybrid",
    "includeSource": true
  }'
```

### 9.4 RAG Query

```bash
curl -X POST "{apiBase}/rag/query" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "s-001",
    "scenario": "qa",
    "locale": "zh-CN",
    "kbIds": [1],
    "queryText": "请总结合同审批流程",
    "topK": 10,
    "retrievalMode": "hybrid",
    "includeSource": true,
    "answerMode": "concise"
  }'
```

### 9.5 创建异步任务

```bash
curl -X POST "{apiBase}/orchestrator/tasks" \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: task-20260327-001" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "s-task-001",
    "scenario": "report",
    "locale": "zh-CN",
    "taskType": "report_generation",
    "payload": {
      "message": "生成本月风险分析报告",
      "kbIds": [1, 2],
      "topK": 10,
      "retrievalMode": "hybrid",
      "includeSource": true
    }
  }'
```

### 9.6 创建索引任务

```bash
curl -X POST "{apiBase}/rag/index/jobs" \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: idx-20260327-001" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "s-index-001",
    "scenario": "indexing",
    "locale": "zh-CN",
    "mode": "reparse_docs",
    "docIds": [1001]
  }'
```

### 9.7 系统态签名调用：查询可见知识库

```bash
curl -X POST "http://{host}:29099/internal/rag/kbs/visible" \
  -H "Content-Type: application/json" \
  -H "X-Service-Source-System: your-source-system" \
  -H "X-Service-Timestamp: <unix-seconds>" \
  -H "X-Service-Path: /internal/rag/kbs/visible" \
  -H "X-Service-Signature: <hex-signature>" \
  -H "X-Service-Request-Id: req-bridge-001" \
  -d '{
    "principal": {
      "sourceSystem": "your-source-system",
      "externalUserId": "10001",
      "externalUserName": "zhangsan",
      "externalDeptId": "2001"
    }
  }'
```

### 9.8 系统态签名调用：执行问答

```bash
curl -X POST "http://{host}:29099/internal/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-Service-Source-System: your-source-system" \
  -H "X-Service-Timestamp: <unix-seconds>" \
  -H "X-Service-Path: /internal/rag/query" \
  -H "X-Service-Signature: <hex-signature>" \
  -H "X-Service-Request-Id: req-bridge-002" \
  -d '{
    "principal": {
      "sourceSystem": "your-source-system",
      "externalUserId": "10001"
    },
    "query": {
      "sessionId": "s-001",
      "scenario": "qa",
      "locale": "zh-CN",
      "queryText": "请总结合同审批流程",
      "kbIds": [1, 2],
      "topK": 10,
      "retrievalMode": "hybrid",
      "answerMode": "detailed",
      "includeSource": true
    }
  }'
```

## 10. 对接建议与当前实现约束

1. 前端或用户态业务接入优先走 `/orchestrator/chat`，避免业务侧自行编排“检索 + 生成 + 降级”流程。
2. 长任务和索引任务必须携带 `Idempotency-Key`，建议规则：`业务主键 + 任务类型 + 时间窗口`。
3. 所有业务结果都必须按 `code/success/msg` 判定，不要只看 HTTP `200`。
4. `/orchestrator/tasks` 当前要求 `payload.message` 和 `payload.kbIds` 必填。
5. `/rag/index/jobs/{jobId}` 当前为进程内状态，服务重启后旧任务状态不可追踪。
6. `/orchestrator/sessions/*` 与 `/orchestrator/tasks/*` 当前属于运行时状态视图，不是长期存档接口。
7. 系统态签名接口的 `X-Service-Path` 必须填写后端真实路径，不能带 `/docker-api`、`/dev-api`、`/prod-api` 这类网关前缀。

## 11. 本次补充内容

本次文档已补充并校正以下信息：

- 当前仓库实际可用的 Docker、直连、开发、生产调用地址
- Swagger / ReDoc / OpenAPI JSON 文档入口
- 登录接口的真实调用方式和表单参数
- JWT 用户态调用头、幂等头和权限点
- 系统态 `/internal/rag/*` 签名接口说明
- 服务签名算法与 Python 生成示例
- Docker 代理转发下真实路径与网关前缀的区别
- 当前实现中的运行时约束、状态保存方式和已知行为
