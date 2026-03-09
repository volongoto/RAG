# RAG + Agent Orchestrator 对外 API 接口说明

版本: `v1`
更新时间: `2026-03-10`

## 1. 适用范围

本文档用于其他平台（业务系统、中台、第三方服务）通过 HTTP 调用当前系统的 RAG 与 Agent 编排能力。

目标链路:

`Business App -> Agent Orchestrator -> RAG Runtime`

说明:

- Agentic 场景建议统一走 `/orchestrator/*`。
- 纯检索/纯问答场景可直接调用 `/rag/*`。

## 2. 服务地址与网关前缀

服务基地址由部署环境决定，常见方式如下：

| 场景 | 示例地址 |
|---|---|
| 直连后端 | `http://{host}:9099` |
| 开发环境代理 | `http://{host}/dev-api` |
| 生产环境代理 | `http://{host}/prod-api` |
| Docker 前端代理 | `http://{host}/docker-api` |

下文统一使用 `{baseUrl}` 表示网关前缀后的基地址。

## 3. 鉴权与请求上下文

### 3.1 必填 Header

| Header | 是否必填 | 说明 |
|---|---|---|
| `Authorization` | 是 | 登录 token，通常格式 `Bearer {token}` |
| `X-Tenant-Id` | 建议 | 租户标识 |
| `X-User-Id` | 建议 | 用户标识（也可由服务端根据 token 推导） |
| `X-Request-Id` | 建议 | 请求唯一 ID（审计/排障） |
| `X-Trace-Id` | 建议 | 链路追踪 ID（不传时通常跟随 `X-Request-Id`） |

### 3.2 幂等 Header

以下接口必须传 `Idempotency-Key`：

- `POST /orchestrator/tasks`
- `POST /rag/index/jobs`

默认幂等窗口为 3600 秒，重复 key 会被拒绝。

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

## 4. 通用上下文字段

以下字段在 Orchestrator / Runtime 的核心接口中均使用：

| 字段 | 类型 | 说明 |
|---|---|---|
| `sessionId` | `string` | 会话 ID |
| `scenario` | `string` | 场景标识（如 `qa` / `report`） |
| `locale` | `string` | 语言区域（如 `zh-CN`） |

## 5. 通用响应格式

除 SSE 外，接口统一返回 JSON 包装：

```json
{
  "code": 200,
  "msg": "操作成功",
  "success": true,
  "time": "2026-03-10T10:00:00",
  "data": {}
}
```

说明：

- 业务异常场景下，HTTP 状态可能仍为 `200`，请以 `code/success/msg` 判定结果。
- 常见 `code`：`200`、`401`、`403`、`500`、`601`。

## 6. API 总览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/orchestrator/chat` | Agent 单轮/多轮对话，支持流式 |
| POST | `/orchestrator/tasks` | 创建长任务（报告、批处理） |
| GET | `/orchestrator/tasks/{taskId}` | 查询长任务状态 |
| GET | `/orchestrator/sessions/{sessionId}` | 查询会话视图 |
| POST | `/rag/retrieve` | 仅检索证据（不生成答案） |
| POST | `/rag/query` | 检索 + 生成答案 |
| GET | `/rag/query/logs` | 查询历史日志 |
| POST | `/rag/index/jobs` | 创建索引任务 |
| GET | `/rag/index/jobs/{jobId}` | 查询索引任务状态 |

## 7. 接口明细

### 7.1 POST `/orchestrator/chat`

用途：

- 统一 Agent 对话入口。
- `stream=false` 返回完整答案。
- `stream=true` 返回 `text/event-stream`。

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

- `retrievalMode`: `vector | lexical | hybrid`
- `topK`: 检索条数，默认 `10`，范围 `1~50`
- `includeSource`: 是否返回 `citations`

非流式响应 `data`：

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
    {"tool": "rag.retrieve", "status": "success", "latencyMs": 120, "summary": "returned 10 chunks"},
    {"tool": "rag.query", "status": "success", "latencyMs": 890, "summary": "answer generated"}
  ],
  "latencyMs": 1040
}
```

流式响应（SSE）：

- `Content-Type: text/event-stream`
- 消息格式（事件类型在 JSON 的 `event` 字段）：

```text
data: {"event":"tool","data":{"tool":"rag.retrieve","status":"success","latencyMs":120,"summary":"returned 10 chunks"}}

data: {"event":"token","data":"审"}

data: {"event":"token","data":"批"}

data: {"event":"done","data":{"sessionId":"s-001","requestId":"req-001","finalAnswer":"...","citations":[],"toolCalls":[],"latencyMs":1040}}
```

### 7.2 POST `/orchestrator/tasks`

用途：

- 创建异步 Agent 长任务（报告、批量分析等）。

请求 Header：

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

当前实现中 `payload` 至少应包含：

- `message`（必填）
- `kbIds`（必填）

响应 `data`：

```json
{
  "taskId": "a1b2c3",
  "status": "pending",
  "taskType": "report_generation",
  "sessionId": "s-task-001",
  "result": null,
  "error": null,
  "createTime": "2026-03-10T10:00:00",
  "updateTime": "2026-03-10T10:00:00"
}
```

### 7.3 GET `/orchestrator/tasks/{taskId}`

用途：查询任务状态与结果。

路径参数：

- `taskId`: 任务 ID

状态值：

- `pending | running | success | failed`

### 7.4 GET `/orchestrator/sessions/{sessionId}`

用途：查询会话消息视图。

响应 `data`：

```json
{
  "sessionId": "s-001",
  "messages": [
    {"role": "user", "content": "问题1", "time": "2026-03-10T10:00:00"},
    {"role": "assistant", "content": "回答1", "time": "2026-03-10T10:00:01"}
  ],
  "updateTime": "2026-03-10T10:00:01"
}
```

### 7.5 POST `/rag/retrieve`

用途：仅检索，不生成答案。

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

### 7.6 POST `/rag/query`

用途：检索 + 生成答案（非 Agent 场景可直接使用）。

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

字段补充说明：

- `topK`: 默认 `10`，范围 `1~50`
- `retrievalMode`: `vector | lexical | hybrid`
- `answerMode`: `concise | detailed`，默认 `detailed`
- `includeSource`: 请求兼容字段（后端当前始终返回 `sourceChunks`，前端可按此字段决定是否展示）

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

### 7.7 GET `/rag/query/logs`

用途：查询 RAG 历史日志（审计/回放）。

查询参数（可选）：

- `logId`
- `userId`
- `queryText`
- `beginTime`
- `endTime`
- `pageNum`（默认 `1`）
- `pageSize`（默认 `10`）

### 7.8 POST `/rag/index/jobs`

用途：创建文档重解析 / 知识库重建索引任务。

请求 Header：

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

- `mode`: `reparse_docs | rebuild_kb`
- 当不传 `docIds` 且传 `kbIds` 时，系统会按知识库拉取文档集合执行处理。

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
  "createTime": "2026-03-10T10:00:00",
  "updateTime": "2026-03-10T10:00:00"
}
```

### 7.9 GET `/rag/index/jobs/{jobId}`

用途：查询索引任务状态。

状态值：

- `pending | running | success | failed`

## 8. 近期变更（2026-03-10）

1. `/rag/query` 新增 `answerMode` 字段：`concise | detailed`，默认 `detailed`。
2. `/rag/query`、`/rag/retrieve`、`/orchestrator/chat` 的 `topK` 默认值统一为 `10`（范围 `1~50`）。
3. RAG 输出策略支持配置驱动：
   - 国安简报模板开关与关键词（`RAG_SECURITY_BRIEF_*`）
   - 时代错位守卫开关与关键词（`RAG_ERA_MISMATCH_*`）

## 9. 对接建议与约束

1. Agent 对话优先走 `/orchestrator/chat`，避免业务侧拼接多工具流程。
2. `tasks` 与 `index jobs` 必须使用幂等 key，建议 key 规则：
   `业务主键 + 任务类型 + 小时窗口`。
3. 结果判定必须基于 `code/success/msg`，不要只看 HTTP 状态码。
4. 非管理员账号会触发知识库数据权限校验。
5. Orchestrator 下游超时时会返回降级结果，并在 `toolCalls` 标记失败原因。

## 10. cURL 示例

### 10.1 Chat（非流式）

```bash
curl -X POST "{baseUrl}/orchestrator/chat" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-Id: t1" \
  -H "X-User-Id: u1001" \
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

### 10.2 RAG Query（精简模式）

```bash
curl -X POST "{baseUrl}/rag/query" \
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

### 10.3 创建索引任务

```bash
curl -X POST "{baseUrl}/rag/index/jobs" \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: idx-20260310-001" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "s-index-001",
    "scenario": "indexing",
    "locale": "zh-CN",
    "mode": "reparse_docs",
    "docIds": [1001]
  }'
```

## 11. 获取 Token（可选）

若调用方尚未获得 token，可使用统一认证链路获取。常见方式：

- `POST /login`（表单）

成功后返回 `token`（或 `access_token`，取决于接入形态）。
建议由统一认证中心颁发并托管 token，业务调用方仅透传。
