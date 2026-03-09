# RAG + Agent Orchestrator 对外 API 接口说明

版本: `v1`  
更新时间: `2026-03-09`

## 1. 适用范围

本文档用于其他平台（业务系统、中台、第三方服务）通过 HTTP 调用当前系统的 RAG 与 Agent 编排能力。

目标架构:

`Business App -> Agent Orchestrator -> RAG Runtime`

说明:

- Agentic 场景建议统一走 `Orchestrator`。
- 纯检索/索引场景可直接调用 `RAG Runtime` API。

## 2. 服务地址与网关前缀

服务基地址由部署环境决定，常见方式如下:

| 场景 | 示例地址 |
|---|---|
| 直连后端 | `http://{host}:9099` |
| 开发环境代理 | `http://{host}/dev-api` |
| 生产环境代理 | `http://{host}/prod-api` |
| Docker 前端代理 | `http://{host}/docker-api` |

建议与平台团队约定统一网关前缀（下文示例用 `{baseUrl}` 表示）。

## 3. 鉴权与上下文透传

### 3.1 必填 Header

| Header | 是否必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | 登录 token，通常格式 `Bearer {token}` |
| `X-Tenant-Id` | 建议 | 租户标识 |
| `X-User-Id` | 建议 | 用户标识（可由服务端从 token 推导） |
| `X-Request-Id` | 建议 | 请求唯一 ID，用于审计与排障 |
| `X-Trace-Id` | 建议 | 链路追踪 ID，不传时默认跟随 `X-Request-Id` |

### 3.2 幂等 Header

以下接口必须传 `Idempotency-Key`:

- `POST /orchestrator/tasks`
- `POST /rag/index/jobs`

重复 key 会被拒绝（默认 1 小时窗口）。

### 3.3 权限点

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

管理员或包含 `*:*:*` 权限的账号可放行全部接口。

## 4. 通用请求体上下文

以下字段在 Orchestrator 与 Runtime 的核心接口中均要求提供:

| 字段 | 类型 | 说明 |
|---|---|---|
| `sessionId` | `string` | 会话 ID |
| `scenario` | `string` | 场景标识，如 `qa` / `report` |
| `locale` | `string` | 语言区域，如 `zh-CN` |

## 5. 通用响应格式

除流式 SSE 外，接口统一返回 JSON 包装:

```json
{
  "code": 200,
  "msg": "操作成功",
  "success": true,
  "time": "2026-03-09T10:00:00",
  "data": {}
}
```

注意:

- 业务异常多数情况下 HTTP 状态仍为 `200`，需以 `code/success/msg` 判定结果。
- 常见 `code`: `200`(成功), `401`(未认证), `403`(无权限), `500`(服务异常), `601`(警告/失败)。

## 6. API 总览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/orchestrator/chat` | Agent 单轮/多轮对话，支持流式 |
| POST | `/orchestrator/tasks` | 创建长任务（报告、批处理） |
| GET | `/orchestrator/tasks/{taskId}` | 查询长任务状态 |
| GET | `/orchestrator/sessions/{sessionId}` | 查询会话视图 |
| POST | `/rag/retrieve` | 检索证据（不生成答案） |
| POST | `/rag/query` | 检索 + 生成答案 |
| GET | `/rag/query/logs` | 查询历史日志 |
| POST | `/rag/index/jobs` | 创建索引任务 |
| GET | `/rag/index/jobs/{jobId}` | 查询索引任务状态 |

## 7. 接口明细

### 7.1 POST `/orchestrator/chat`

用途:

- 统一 Agent 入口。
- `stream=false` 返回完整答案。
- `stream=true` 返回 `text/event-stream`。

请求体:

```json
{
  "sessionId": "s-001",
  "scenario": "qa",
  "locale": "zh-CN",
  "message": "请总结合同审批流程",
  "kbIds": [1, 2],
  "stream": false,
  "topK": 5,
  "retrievalMode": "hybrid",
  "includeSource": true
}
```

字段说明:

- `retrievalMode`: `vector | lexical | hybrid`
- `topK`: 检索条数，默认 `5`
- `includeSource`: 是否返回 citations

非流式响应 `data`:

```json
{
  "sessionId": "s-001",
  "requestId": "req-001",
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
    {"tool": "rag.retrieve", "status": "success", "latencyMs": 120, "summary": "returned 5 chunks"},
    {"tool": "rag.query", "status": "success", "latencyMs": 890, "summary": "answer generated"}
  ],
  "latencyMs": 1040
}
```

流式响应（SSE）:

- `Content-Type: text/event-stream`
- 每条消息格式（注意使用 `data:` 行，事件类型在 JSON 的 `event` 字段里）:

```text
data: {"event":"tool","data":{"tool":"rag.retrieve","status":"success","latencyMs":120,"summary":"returned 5 chunks"}}

data: {"event":"token","data":"审"}

data: {"event":"token","data":"批"}

data: {"event":"done","data":{"sessionId":"s-001","requestId":"req-001","finalAnswer":"...","citations":[],"toolCalls":[],"latencyMs":1040}}

```

### 7.2 POST `/orchestrator/tasks`

用途:

- 创建异步 Agent 长任务（报告、批量分析等）。

请求 Header:

- 必填 `Idempotency-Key`

请求体:

```json
{
  "sessionId": "s-task-001",
  "scenario": "report",
  "locale": "zh-CN",
  "taskType": "report_generation",
  "payload": {
    "message": "生成本月风险分析报告",
    "kbIds": [1, 2],
    "topK": 5,
    "retrievalMode": "hybrid",
    "includeSource": true
  }
}
```

当前实现中 `payload` 建议至少包含:

- `message`（必需）
- `kbIds`（必需）

响应 `data`:

```json
{
  "taskId": "a1b2c3",
  "status": "pending",
  "taskType": "report_generation",
  "sessionId": "s-task-001",
  "result": null,
  "error": null,
  "createTime": "2026-03-09T10:00:00",
  "updateTime": "2026-03-09T10:00:00"
}
```

### 7.3 GET `/orchestrator/tasks/{taskId}`

用途:

- 查询任务状态与结果。

路径参数:

- `taskId`: 任务 ID

状态值:

- `pending | running | success | failed`

### 7.4 GET `/orchestrator/sessions/{sessionId}`

用途:

- 查询会话消息视图。

响应 `data`:

```json
{
  "sessionId": "s-001",
  "messages": [
    {"role": "user", "content": "问题1", "time": "2026-03-09T10:00:00"},
    {"role": "assistant", "content": "回答1", "time": "2026-03-09T10:00:01"}
  ],
  "updateTime": "2026-03-09T10:00:01"
}
```

### 7.5 POST `/rag/retrieve`

用途:

- 仅检索，不做答案生成。

请求体:

```json
{
  "sessionId": "s-001",
  "scenario": "qa",
  "locale": "zh-CN",
  "kbIds": [1, 2],
  "queryText": "合同审批流程",
  "topK": 5,
  "retrievalMode": "hybrid"
}
```

响应 `data`:

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

### 7.6 POST `/rag/query`

用途:

- 检索 + 生成答案（非 Agent 场景可直接使用）。

请求体:

```json
{
  "sessionId": "s-001",
  "scenario": "qa",
  "locale": "zh-CN",
  "kbIds": [1, 2],
  "queryText": "合同审批流程",
  "topK": 5,
  "retrievalMode": "hybrid",
  "includeSource": true
}
```

响应 `data`:

```json
{
  "answerText": "审批流程分为发起、审核、复核、归档。",
  "sourceChunks": [],
  "responseTime": 620
}
```

### 7.7 GET `/rag/query/logs`

用途:

- 查询 RAG 历史日志（可用于审计/回放）。

查询参数（可选）:

- `logId`
- `userId`
- `queryText`
- `beginTime`
- `endTime`
- `pageNum`（默认 1）
- `pageSize`（默认 10）

### 7.8 POST `/rag/index/jobs`

用途:

- 创建文档重解析/知识库重建索引任务。

请求 Header:

- 必填 `Idempotency-Key`

请求体:

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

字段说明:

- `mode`: `reparse_docs | rebuild_kb`
- 当不传 `docIds` 且传 `kbIds` 时，系统会按知识库拉取文档集合进行处理。

响应 `data`:

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
  "createTime": "2026-03-09T10:00:00",
  "updateTime": "2026-03-09T10:00:00"
}
```

### 7.9 GET `/rag/index/jobs/{jobId}`

用途:

- 查询索引任务状态。

状态值:

- `pending | running | success | failed`

## 8. 对接建议与约束

1. Agentic 对话请优先调用 `/orchestrator/chat`，不要让业务系统直接拼接 RAG + LLM 流程。
2. 对 `tasks` 与 `index jobs` 强制使用幂等 key，建议 key 规则:
   `业务主键 + 任务类型 + 日期小时`。
3. 调用方必须按 `code/success/msg` 判定是否成功，不能只看 HTTP 状态码。
4. 非管理员账号会触发知识库数据权限校验，跨租户/跨权限访问会被拒绝。
5. 若 Orchestrator 出现下游超时，会返回降级结果，并在 `toolCalls` 中标记失败原因。

## 9. cURL 快速示例

### 9.1 Chat（非流式）

```bash
curl -X POST "{baseUrl}/orchestrator/chat" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-Id: t1" \
  -H "X-User-Id: u1001" \
  -H "X-Request-Id: req-1001" \
  -H "X-Trace-Id: trace-1001" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId":"s-001",
    "scenario":"qa",
    "locale":"zh-CN",
    "message":"请总结合同审批流程",
    "kbIds":[1,2],
    "stream":false,
    "topK":5,
    "retrievalMode":"hybrid",
    "includeSource":true
  }'
```

### 9.2 创建索引任务

```bash
curl -X POST "{baseUrl}/rag/index/jobs" \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: idx-20260309-001" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId":"s-index-001",
    "scenario":"indexing",
    "locale":"zh-CN",
    "mode":"reparse_docs",
    "docIds":[1001]
  }'
```

## 10. 登录获取 Token（可选）

如平台侧尚未拿到 token，可调用登录接口:

- `POST /login`（表单）
- 成功后返回字段中包含 `token`（或 Swagger 场景返回 `access_token`）。

建议由统一认证中心颁发并托管 token，业务调用方仅做透传。
