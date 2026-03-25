# RAG 调用示例

本文档整理了“事实枚举类问题”（例如：`韦小宝有几个老婆`）的推荐调用方式。

## 1. 编排查询（推荐）

接口：`POST /orchestrator/chat`

适用场景：
- 需要统一编排“检索 + 生成”
- 需要工具调用链路（`toolCalls`）和引用来源（`citations`）
- 希望可切换流式与非流式

### curl 示例

```bash
curl -X POST "http://localhost:29099/orchestrator/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -d '{
    "sessionId": "ldj-001",
    "scenario": "fact-enumeration",
    "locale": "zh-CN",
    "message": "请根据知识库完整回答：韦小宝有几个老婆？先给总数，再列出全部姓名，不要遗漏。",
    "kbIds": [1],
    "topK": 30,
    "retrievalMode": "hybrid",
    "includeSource": true,
    "stream": false
  }'
```

### 请求体示例

```json
{
  "sessionId": "ldj-001",
  "scenario": "fact-enumeration",
  "locale": "zh-CN",
  "message": "请根据知识库完整回答：韦小宝有几个老婆？先给总数，再列出全部姓名，不要遗漏。",
  "kbIds": [1],
  "topK": 30,
  "retrievalMode": "hybrid",
  "includeSource": true,
  "stream": false
}
```

## 2. 仅检索证据（排查召回覆盖）

接口：`POST /rag/retrieve`

适用场景：
- 先验证向量库是否召回到足够证据
- 调试 `topK` 与 `retrievalMode` 参数

### curl 示例

```bash
curl -X POST "http://localhost:29099/rag/retrieve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -d '{
    "sessionId": "ldj-001",
    "scenario": "fact-enumeration",
    "locale": "zh-CN",
    "kbIds": [1],
    "queryText": "韦小宝有几个老婆？",
    "topK": 30,
    "retrievalMode": "hybrid"
  }'
```

### 请求体示例

```json
{
  "sessionId": "ldj-001",
  "scenario": "fact-enumeration",
  "locale": "zh-CN",
  "kbIds": [1],
  "queryText": "韦小宝有几个老婆？",
  "topK": 30,
  "retrievalMode": "hybrid"
}
```

## 3. 参数建议

- `topK`：事实枚举类问题建议 `20~50`（默认值一般偏小）
- `retrievalMode`：优先 `hybrid`；若文本匹配特别强可试 `lexical`
- `includeSource`：建议开启，便于核对答案依据

## 4. 注意事项

- 若文档是旧切片策略入库，建议先重建索引或重解析文档，再测试召回效果。
- `kbIds` 需要替换为你的实际知识库 ID。
- 请求需要携带有效登录令牌（`Authorization: Bearer <token>`）。
