# Agent Orchestrator and RAG Runtime Boundary Checklist (v1)

## Architecture

Target layers:

1. Business App
2. Agent Orchestrator
3. RAG Runtime

Current implementation keeps Orchestrator and Runtime as separate modules in the same backend service, with independent APIs and contracts.

## Boundary Matrix

| Domain | Owner | Input | Output | Boundary Rule |
|---|---|---|---|---|
| Session/task state, multi-turn memory | Agent Orchestrator | user message, sessionId, scenario, locale | final answer, task state, tool traces | Business app should not mutate orchestrator internal state |
| Intent routing, tool plan, retry/degrade | Agent Orchestrator | conversation context, tool registry | tool call traces, synthesized answer | Runtime should not implement generic planner logic |
| KB/doc/index lifecycle | RAG Runtime | documents, kb config, index instructions | index job status, document parse status | Orchestrator should not touch runtime storage directly |
| Retrieve/rerank/citation | RAG Runtime | query, kbIds, tenant/user context | evidence chunks and scores | Business app should not bypass runtime access checks |
| Business response shaping and UI | Business App | user request | UI/API response | Business app should not implement core agent orchestration |

## Public API Contracts

Business -> Orchestrator:

- `POST /orchestrator/chat` (supports `stream=true`, SSE)
- `POST /orchestrator/tasks` (requires `Idempotency-Key`)
- `GET /orchestrator/tasks/{taskId}`
- `GET /orchestrator/sessions/{sessionId}`

Orchestrator/Business -> Runtime:

- `POST /rag/retrieve` (retrieve only)
- `POST /rag/query` (retrieve + generation)
- `POST /rag/index/jobs` (requires `Idempotency-Key`)
- `GET /rag/index/jobs/{jobId}`

Headers propagated across layers:

- `Authorization`
- `X-Tenant-Id`
- `X-User-Id`
- `X-Request-Id`
- `X-Trace-Id`

Required body context:

- `sessionId`
- `scenario`
- `locale`

Runtime evidence fields:

- `kbId`
- `docId`
- `fileName`
- `filePath`
- `chunkId`
- `section`
- `page`
- `paragraph`
- `snippet`
- `retrievalScore`
- `rerankScore`
- `retrievalChannel`

## Auth and Permission Boundaries

1. Business app performs login and business pre-checks.
2. Orchestrator validates request/auth context and propagates metadata.
3. Runtime enforces final KB/document data scope checks.

## Reliability Defaults

1. Business -> Orchestrator timeout: 30s (stream mode stays open)
2. Orchestrator -> Runtime retrieve timeout: 8s
3. Orchestrator -> Runtime query timeout: 20s
4. `POST /orchestrator/tasks` and `POST /rag/index/jobs` require `Idempotency-Key`

Current orchestrator degrades gracefully on retrieve/query timeout by returning explainable fallback output and tool call failure traces.

## Delivery Notes (v1)

Implemented:

1. Orchestrator module and APIs
2. Runtime retrieve and index-job APIs
3. Hybrid retrieval (`vector`, `lexical`, `hybrid`) and citation schema
4. Request metadata normalization and idempotency guard
5. Timeout/degrade behavior in orchestrator chat

Known limitations for next version:

1. Orchestrator session/task storage is in-memory (move to Redis/DB for production)
2. Orchestrator calls runtime services in-process; can be replaced with HTTP client adapter to enforce network boundary
3. Index job status currently tracks job orchestration lifecycle, not full downstream parse completion per document
