# RAG 能力外部调用接口文档

> **版本**: v1.0  
> **更新日期**: 2025-04-02  
> **基础路径**: `http://{host}:{port}/dev-api`  
> **协议**: HTTPS (生产环境) / HTTP (开发环境)

---

## 目录

1. [概述](#1-概述)
2. [认证机制](#2-认证机制)
3. [接口列表](#3-接口列表)
4. [数据模型](#4-数据模型)
5. [错误码说明](#5-错误码说明)
6. [调用示例（完整 Demo）](#6-调用示例完整-demo)

---

## 1. 概述

本系统提供 **RAG（检索增强生成）能力** 的外部调用接口，支持第三方系统集成知识库检索与问答功能。

### 1.1 核心能力

| 能力 | 说明 |
|------|------|
| **RAG 查询** | 基于知识库的智能问答（检索 + LLM 生成） |
| **纯检索** | 仅返回相关文档片段，不生成答案 |
| **知识库可见性查询** | 查询指定用户/部门可访问的知识库列表 |
| **文档上传** | 向知识库上传文档（Base64 编码） |
| **文档管理** | 查询、删除知识库中的文档 |

### 1.2 接口分类

| 分类 | 路径前缀 | 认证方式 | 用途 |
|------|----------|----------|------|
| **内部桥接 API** | `/internal/rag/*` | HMAC 签名 | 供外部系统集成调用 |
| **用户 API** | `/rag/*` | JWT Token | 供前端用户使用 |

> **本文档重点介绍内部桥接 API，供第三方系统集成。**

---

## 2. 认证机制

### 2.1 HMAC-SHA256 签名验证

所有 `/internal/rag/*` 接口均采用 **HMAC-SHA256** 签名机制进行身份认证。

#### 2.1.1 必需的请求头

| Header 名称 | 类型 | 必填 | 说明 |
|-------------|------|------|------|
| `X-Service-Source-System` | String | ✅ | 调用方系统标识码 |
| `X-Service-Timestamp` | String | ✅ | 当前 Unix 时间戳（秒） |
| `X-Service-Signature` | String | ✅ | HMAC-SHA256 签名字符串 |
| `X-Service-Path` | String | ✅ | 规范化请求路径 |
| `X-Service-Request-Id` | String | ❌ | 请求唯一标识（用于追踪） |

#### 2.1.2 签名算法

```
签名输入 = 方法(大写) + \n + 路径 + \n + source_system + \n + timestamp + \n + payload_json
签名结果 = HMAC-SHA256(签名输入, shared_secret) → hex字符串
```

**详细步骤**：

1. 将请求体（payload）按 JSON 格式序列化（key 排序、无空格）
2. 拼接签名字符串：`{METHOD}\n{PATH}\n{SOURCE_SYSTEM}\n{TIMESTAMP}\n{PAYLOAD}`
3. 使用 HMAC-SHA256 算法计算签名
4. 将签名放入请求头 `X-Service-Signature`

#### 2.1.3 时间戳容差

签名时间戳与服务器时间差不能超过配置的 TTL（默认 **300 秒**），否则视为过期。

### 2.2 配置项

在 `.env.dev` 文件中配置：

```env
# 内部服务共享密钥（必须与调用方协商一致）
RAG_INTERNAL_SHARED_SECRET=your-shared-secret-here

# 允许的来源系统列表（逗号分隔）
RAG_INTERNAL_ALLOWED_SOURCE_SYSTEMS=ksguoaj-google,external-system-a

# 签名有效期（秒）
RAG_INTERNAL_SIGNATURE_TTL_SECONDS=300
```

---

## 3. 接口列表

### 3.1 RAG 智能查询

执行基于知识库的智能问答，自动进行向量检索并调用 LLM 生成答案。

**端点**: `POST /dev-api/internal/rag/query`

#### 请求参数

**Header**:
```
Content-Type: application/json
X-Service-Source-System: {source_system}
X-Service-Timestamp: {timestamp}
X-Service-Signature: {signature}
X-Service-Path: /internal/rag/query
```

**Body (JSON)**:

```json
{
    "principal": {
        "sourceSystem": "ksguoaj-google",
        "externalUserId": "ext_user_001",
        "externalUserName": "张三",
        "externalDeptId": "dept_100"
    },
    "query": {
        "kbIds": [1, 2],
        "queryText": "什么是RAG技术？",
        "topK": 5,
        "includeSource": true,
        "sessionId": "sess_20250402_001",
        "scenario": "general_qa",
        "locale": "zh-CN",
        "retrievalMode": "hybrid",
        "answerMode": "detailed"
    }
}
```

**principal 字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sourceSystem` | String | ✅ | 来源系统标识（需在允许列表内） |
| `externalUserId` | String | ❌ | 外部用户 ID（用于映射本地用户） |
| `externalUserName` | String | ❌ | 外部用户名称（用于映射或回退查找） |
| `externalDeptId` | String | ❌ | 外部部门 ID |

**query 字段说明**:

| 字段 | 类型 | 默认值 | 必填 | 说明 |
|------|------|--------|------|------|
| `kbIds` | Array\<int\> | - | ❌ | 目标知识库 ID 列表（为空则查所有可见 KB） |
| `queryText` | String | - | ✅ | 用户问题文本 |
| `topK` | int | 10 | ❌ | 返回 Top-K 结果（1~50） |
| `includeSource` | bool | true | ❌ | 是否包含参考来源片段 |
| `sessionId` | String | - | ✅ | 会话 ID（用于上下文关联） |
| `scenario` | String | - | ✅ | 场景标识 |
| `locale` | String | - | ✅ | 语言区域 |
| `retrievalMode` | string | hybrid | ❌ | 检索模式：`vector` / `lexical` / `hybrid` |
| `answerMode` | string | detailed | ❌ | 回答模式：`concise` / `detailed` |

#### 响应示例

**成功响应 (200)**:

```json
{
    "code": 200,
    "msg": "操作成功",
    "data": {
        "answerText": "RAG（Retrieval-Augmented Generation）是一种结合了信息检索和文本生成的AI技术框架...",
        "sourceChunks": [
            {
                "kbId": 1,
                "chunkId": 1001,
                "docId": 201,
                "fileName": "RAG技术白皮书.pdf",
                "filePath": "/upload/docs/RAG技术白皮书.pdf",
                "section": "第一章 概述",
                "page": 3,
                "paragraph": 2,
                "snippet": "RAG（Retrieval-Augmented Generation）是一种将大型语言模型与外部知识库相结合的技术...",
                "retrievalScore": 0.92,
                "rerankScore": 0.88,
                "retrievalChannel": "vector"
            }
        ],
        "responseTime": 1250
    }
}
```

**失败响应 (401)** — 签名校验失败：

```json
{
    "code": 401,
    "msg": "内部服务签名校验失败"
}
```

**失败响应 (400)** — 无可访问知识库：

```json
{
    "code": 500,
    "msg": "当前主体在知识库系统中没有可访问的知识库"
}
```

---

### 3.2 获取可见知识库列表

查询指定外部用户在当前系统中可访问的所有知识库。

**端点**: `POST /dev-api/internal/rag/kbs/visible`

#### 请求参数

**Header**:
```
Content-Type: application/json
X-Service-Source-System: {source_system}
X-Service-Timestamp: {timestamp}
X-Service-Signature: {signature}
X-Service-Path: /internal/rag/kbs/visible
```

**Body (JSON)**:

```json
{
    "principal": {
        "sourceSystem": "ksguoaj-google",
        "externalUserId": "ext_user_001",
        "externalUserName": "张三",
        "externalDeptId": "dept_100"
    }
}
```

#### 响应示例

**成功响应 (200)**:

```json
{
    "code": 200,
    "msg": "操作成功",
    "data": {
        "principal": {
            "sourceSystem": "ksguoaj-google",
            "externalUserId": "ext_user_001",
            "externalUserName": "张三",
            "externalDeptId": "dept_100",
            "mappedUserId": 5,
            "mappedUserName": "zhangsan",
            "mappedDeptId": 10,
            "mappedDeptName": "研发部",
            "isAdmin": false,
            "resolutionMode": "user_name_map"
        },
        "kbIds": [1, 3, 5],
        "knowledgeBases": [
            {
                "kbId": 1,
                "kbName": "产品技术文档库",
                "kbType": "dept",
                "description": "公司产品相关的技术文档",
                "deptId": 10,
                "userId": null,
                "embeddingModel": "BAAI/bge-m3",
                "status": "0",
                "createTime": "2025-01-15T10:30:00"
            },
            {
                "kbId": 3,
                "kbName": "个人知识库-张三",
                "kbType": "personal",
                "description": "个人收藏的技术资料",
                "deptId": null,
                "userId": 5,
                "embeddingModel": "BAAI/bge-m3",
                "status": "0",
                "createTime": "2025-02-20T14:00:00"
            }
        ]
    }
}
```

**principal 解析策略说明** (`resolution_mode`)：

| 模式 | 说明 |
|------|------|
| `user_id_map` | 通过用户 ID 映射表匹配 |
| `user_name_map` | 通过用户名映射表匹配 |
| `direct_user_id` | 直接使用外部用户 ID 作为本地用户 ID |
| `username_lookup` | 通过用户名直接查找本地用户 |
| `dept_id_map` | 通过部门 ID 映射表匹配 |
| `direct_dept_id` | 直接使用外部部门 ID |
| `unresolved` | 未解析到任何本地用户 |

---

## 4. 数据模型

### 4.1 ExternalPrincipalModel（外部调用方身份）

```typescript
interface ExternalPrincipalModel {
    /** 来源系统标识 */
    sourceSystem: string;
    /** 外部用户ID */
    externalUserId?: string;
    /** 外部用户名称 */
    externalUserName?: string;
    /** 外部部门ID */
    externalDeptId?: string;
}
```

### 4.2 QueryRequestModel（查询请求）

```typescript
interface QueryRequestModel {
    /** 知识库ID列表 */
    kbIds?: number[];
    /** 查询文本 */
    queryText: string;
    /** 返回Top-K数量 (1-50) */
    topK?: number; // 默认 10
    /** 是否包含来源片段 */
    includeSource?: boolean; // 默认 true
    /** 会话ID */
    sessionId: string;
    /** 场景标识 */
    scenario: string;
    /** 语言区域 */
    locale: string;
    /** 检索模式 */
    retrievalMode?: 'vector' | 'lexical' | 'hybrid'; // 默认 'hybrid'
    /** 回答模式 */
    answerMode?: 'concise' | 'detailed'; // 默认 'detailed'
}
```

### 4.3 SourceChunkModel（来源片段）

```typescript
interface SourceChunkModel {
    /** 知识库ID */
    kbId?: number;
    /** 片段ID */
    chunkId: number;
    /** 文档ID */
    docId: number;
    /** 文件名 */
    fileName?: string;
    /** 文件路径 */
    filePath?: string;
    /** 章节/节标题 */
    section?: string;
    /** 页码 */
    page?: number;
    /** 段落索引 */
    paragraph?: number;
    /** 匹配内容片段 */
    snippet: string;
    /** 检索得分 */
    retrievalScore?: number;
    /** 重排序得分 */
    rerankScore?: number;
    /** 检索渠道 */
    retrievalChannel?: string;
}
```

### 4.4 QueryResponseModel（查询响应）

```typescript
interface QueryResponseModel {
    /** 生成的答案文本 */
    answerText: string;
    /** 参考来源片段列表 */
    sourceChunks?: SourceChunkModel[];
    /** 响应耗时（毫秒） */
    responseTime?: number;
}
```

### 4.5 KnowledgeBaseModel（知识库模型）

```typescript
interface KnowledgeBaseModel {
    /** 知识库ID */
    kbId?: number;
    /** 知识库名称 */
    kbName?: string;
    /** 知识库类型: dept=部门级, personal=个人级 */
    kbType?: 'dept' | 'personal';
    /** 描述 */
    description?: string;
    /** 部门ID */
    deptId?: number;
    /** 所属用户ID */
    userId?: number;
    /** Embedding模型 */
    embeddingModel?: string;
    /** 状态: 0=启用, 1=禁用 */
    status?: '0' | '1';
    /** 创建时间 */
    createTime?: string;
}
```

---

## 5. 错误码说明

| HTTP Code | 业务 Code | 说明 | 解决方案 |
|-----------|-----------|------|----------|
| 200 | 200 | 成功 | - |
| 401 | 401 | 认证失败 | 检查签名算法和密钥配置 |
| 401 | - | 签名头缺失 | 补全 X-Service-* 头信息 |
| 401 | - | 来源系统不在允许列表 | 联系管理员添加系统标识 |
| 401 | - | 签名已过期 | 检查客户端时间同步 |
| 401 | - | 签名路径不匹配 | 确保 X-Service-Path 与实际路径一致 |
| 401 | - | 共享密钥未配置 | 服务端配置 RAG_INTERNAL_SHARED_SECRET |
| 500 | 500 | 无可访问知识库 | 检查用户/部门的权限和知识库分配 |
| 500 | 500 | 映射配置不是合法JSON | 检查 .env 中的映射配置格式 |

---

## 6. 调用示例（完整 Demo）

### 6.1 Python 完整调用示例

```python
"""
RAG 外部调用完整示例 - Python
===============================
演示如何调用 Cradle RAG 系统的外部接口
"""

import hashlib
import hmac
import json
import time
from typing import Any

import requests


class RagClient:
    """Cradle RAG 外部调用客户端"""
    
    def __init__(
        self,
        base_url: str,
        shared_secret: str,
        source_system: str,
        timeout: int = 30,
    ):
        """
        初始化 RAG 客户端
        
        Args:
            base_url: RAG服务地址，如 http://192.168.1.100:29099/dev-api
            shared_secret: 与RAG服务协商的共享密钥
            source_system: 本系统的标识码（需在RAG服务允许列表中）
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.shared_secret = shared_secret
        self.source_system = source_system
        self.timeout = timeout
        self.session = requests.Session()
    
    def _build_signature(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> tuple[str, str]:
        """
        构建签名和时间戳
        
        Returns:
            (timestamp, signature) 元组
        """
        timestamp = str(int(time.time()))
        
        # 序列化 payload（key 排序，紧凑格式）
        canonical_payload = json.dumps(
            payload or {},
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True,
        )
        
        # 拼接签名字符串
        canonical_message = '\n'.join([
            method.upper(),
            path,
            self.source_system,
            timestamp,
            canonical_payload,
        ])
        
        # 计算 HMAC-SHA256 签名
        signature = hmac.new(
            self.shared_secret.encode('utf-8'),
            canonical_message.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        
        return timestamp, signature
    
    def _build_headers(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, str]:
        """构建带签名的请求头"""
        timestamp, signature = self._build_signature(method, path, payload)
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Service-Source-System': self.source_system,
            'X-Service-Timestamp': timestamp,
            'X-Service-Signature': signature,
            'X-Service-Path': path,
        }
        
        if request_id:
            headers['X-Service-Request-Id'] = request_id
        
        return headers
    
    def query_knowledge_base(
        self,
        query_text: str,
        *,
        kb_ids: list[int] | None = None,
        external_user_id: str | None = None,
        external_user_name: str | None = None,
        external_dept_id: str | None = None,
        top_k: int = 5,
        session_id: str | None = None,
        scenario: str = 'general_qa',
        locale: str = 'zh-CN',
        retrieval_mode: str = 'hybrid',
        answer_mode: str = 'detailed',
        include_source: bool = True,
    ) -> dict[str, Any]:
        """
        执行 RAG 智能查询
        
        Args:
            query_text: 用户问题
            kb_ids: 目标知识库ID列表（None则查询所有可见KB）
            external_user_id: 外部用户ID
            external_user_name: 外部用户名
            external_dept_id: 外部部门ID
            top_k: 返回结果数
            session_id: 会话ID
            scenario: 场景标识
            locale: 语言区域
            retrieval_mode: 检索模式 vector/lexical/hybrid
            answer_mode: 回答模式 concise/detailed
            include_source: 是否包含来源片段
            
        Returns:
            API 响应字典
        """
        path = '/internal/rag/query'
        
        payload = {
            'principal': {
                'sourceSystem': self.source_system,
                'externalUserId': external_user_id,
                'externalUserName': external_user_name,
                'externalDeptId': external_dept_id,
            },
            'query': {
                'kbIds': kb_ids or [],
                'queryText': query_text,
                'topK': top_k,
                'includeSource': include_source,
                'sessionId': session_id or f'sess_{int(time.time())}',
                'scenario': scenario,
                'locale': locale,
                'retrievalMode': retrieval_mode,
                'answerMode': answer_mode,
            },
        }
        
        headers = self._build_headers('POST', path, payload)
        url = f'{self.base_url}{path}'
        
        response = self.session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        
        return response.json()
    
    def get_visible_knowledge_bases(
        self,
        *,
        external_user_id: str | None = None,
        external_user_name: str | None = None,
        external_dept_id: str | None = None,
    ) -> dict[str, Any]:
        """
        获取可见知识库列表
        
        Returns:
            API 响应字典，包含可访问的知识库列表
        """
        path = '/internal/rag/kbs/visible'
        
        payload = {
            'principal': {
                'sourceSystem': self.source_system,
                'externalUserId': external_user_id,
                'externalUserName': external_user_name,
                'externalDeptId': external_dept_id,
            },
        }
        
        headers = self._build_headers('POST', path, payload)
        url = f'{self.base_url}{path}'
        
        response = self.session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        
        return response.json()


# ==================== 使用示例 ====================

if __name__ == '__main__':
    # 初始化客户端
    client = RagClient(
        base_url='http://192.168.1.100:29099/dev-api',
        shared_secret='your-negotiated-secret-key',
        source_system='ksguoaj-google',  # 需在 RAG 服务的允许列表中
    )
    
    print("=" * 60)
    print("示例1: 查询可见知识库")
    print("=" * 60)
    
    kbs_result = client.get_visible_knowledge_bases(
        external_user_name='zhangsan',
        external_dept_id='dept_100',
    )
    
    if kbs_result.get('code') == 200:
        data = kbs_result['data']
        print(f"✅ 解析到本地用户: {data['principal']['mappedUserName']}")
        print(f"✅ 可访问知识库数量: {len(data['kbIds'])}")
        for kb in data['knowledgeBases']:
            print(f"   - [{kb['kbId']}] {kb['kbName']} ({kb['kbType']})")
    else:
        print(f"❌ 请求失败: {kbs_result}")
    
    print("\n" + "=" * 60)
    print("示例2: 执行 RAG 智能查询")
    print("=" * 60)
    
    query_result = client.query_knowledge_base(
        query_text="什么是RAG技术？它有哪些应用场景？",
        kb_ids=[1],  # 指定知识库
        external_user_name='zhangsan',
        top_k=5,
        retrieval_mode='hybrid',
        answer_mode='detailed',
        include_source=True,
    )
    
    if query_result.get('code') == 200:
        data = query_result['data']
        print(f"📝 答案:\n{data['answerText']}\n")
        print(f"⏱️  响应耗时: {data['responseTime']}ms")
        print(f"📚 参考来源 ({len(data.get('sourceChunks', []))} 条):")
        for i, chunk in enumerate(data.get('sourceChunks', []), 1):
            print(f"   [{i}] 得分={chunk.get('retrievalScore', 'N/A'):.2f} "
                  f"| 文档={chunk.get('fileName')} "
                  f"| 页码={chunk.get('page', 'N/A')}")
            print(f"       片段: {chunk.get('snippet', '')[:80]}...")
    else:
        print(f"❌ 请求失败: {query_result}")
```

---

### 6.2 Java (Spring Boot) 完整调用示例

```java
/**
 * RAG 外部调用完整示例 - Java
 * ===============================
 * 演示如何从 Spring Boot 应用调用 Cradle RAG 系统
 */

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;

public class RagClient {

    private final String baseUrl;
    private final String sharedSecret;
    private final String sourceSystem;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public RagClient(String baseUrl, String sharedSecret, String sourceSystem) {
        this.baseUrl = baseUrl.replaceAll("/$", "");
        this.sharedSecret = sharedSecret;
        this.sourceSystem = sourceSystem;
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper();
    }

    /**
     * 构建 HMAC-SHA256 签名
     */
    private String buildSignature(String method, String path, 
                                   String timestamp, String payloadJson) throws Exception {
        String canonicalMessage = String.join("\n",
            method.toUpperCase(),
            path,
            sourceSystem,
            timestamp,
            payloadJson
        );
        
        Mac mac = Mac.getInstance("HmacSHA256");
        SecretKeySpec secretKey = new SecretKeySpec(
            sharedSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
        mac.init(secretKey);
        byte[] hash = mac.doFinal(canonicalMessage.getBytes(StandardCharsets.UTF_8));
        
        return bytesToHex(hash);
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }

    /**
     * 构建请求头
     */
    private Map<String, String> buildHeaders(String method, String path, 
                                              Map<String, Object> payload) throws Exception {
        String timestamp = String.valueOf(Instant.now().getEpochSecond());
        String payloadJson = objectMapper.writeValueAsString(payload);
        String signature = buildSignature(method, path, timestamp, payloadJson);

        Map<String, String> headers = new HashMap<>();
        headers.put("Content-Type", "application/json");
        headers.put("Accept", "application/json");
        headers.put("X-Service-Source-System", sourceSystem);
        headers.put("X-Service-Timestamp", timestamp);
        headers.put("X-Service-Signature", signature);
        headers.put("X-Service-Path", path);
        headers.put("X-Service-Request-Id", UUID.randomUUID().toString());
        
        return headers;
    }

    /**
     * 执行 RAG 查询
     */
    public JsonNode queryKnowledgeBase(String queryText, List<Integer> kbIds,
                                        String externalUserName) throws Exception {
        String path = "/internal/rag/query";
        
        Map<String, Object> principal = new HashMap<>();
        principal.put("sourceSystem", sourceSystem);
        principal.put("externalUserName", externalUserName);
        
        Map<String, Object> query = new HashMap<>();
        query.put("kbIds", kbIds != null ? kbIds : Collections.emptyList());
        query.put("queryText", queryText);
        query.put("topK", 5);
        query.put("includeSource", true);
        query.put("sessionId", "sess_" + Instant.now().getEpochSecond());
        query.put("scenario", "general_qa");
        query.put("locale", "zh-CN");
        query.put("retrievalMode", "hybrid");
        query.put("answerMode", "detailed");
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("principal", principal);
        payload.put("query", query);

        Map<String, String> headers = buildHeaders("POST", path, payload);
        String body = objectMapper.writeValueAsString(payload);

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(baseUrl + path))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .headers(headers.entrySet().stream()
                .flatMap(e -> List.of(e.getKey(), e.getValue()).stream())
                .toArray(String[]::new))
            .build();

        HttpResponse<String> response = httpClient.send(request, 
            HttpResponse.BodyHandlers.ofString());
        
        return objectMapper.readTree(response.body());
    }

    /**
     * 获取可见知识库
     */
    public JsonNode getVisibleKnowledgeBases(String externalUserName) throws Exception {
        String path = "/internal/rag/kbs/visible";
        
        Map<String, Object> principal = new HashMap<>();
        principal.put("sourceSystem", sourceSystem);
        principal.put("externalUserName", externalUserName);
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("principal", principal);

        Map<String, String> headers = buildHeaders("POST", path, payload);
        String body = objectMapper.writeValueAsString(payload);

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(baseUrl + path))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .headers(headers.entrySet().stream()
                .flatMap(e -> List.of(e.getKey(), e.getValue()).stream())
                .toArray(String[]::new))
            .build();

        HttpResponse<String> response = httpClient.send(request, 
            HttpResponse.BodyHandlers.ofString());
        
        return objectMapper.readTree(response.body());
    }

    // ==================== 使用示例 ====================
    public static void main(String[] args) {
        try {
            RagClient client = new RagClient(
                "http://192.168.1.100:29099/dev-api",
                "your-negotiated-secret-key",
                "ksguoaj-google"
            );

            System.out.println("=".repeat(60));
            System.out.println("示例1: 查询可见知识库");
            System.out.println("=".repeat(60));

            JsonNode kbsResult = client.getVisibleKnowledgeBases("zhangsan");
            
            if (kbsResult.has("code") && kbsResult.get("code").asInt() == 200) {
                JsonNode data = kbsResult.get("data");
                System.out.println("✅ 解析到本地用户: " + 
                    data.get("principal").get("mappedUserName").asText());
                
                JsonNode kbList = data.get("knowledgeBases");
                System.out.println("✅ 可访问知识库数量: " + kbList.size());
                for (JsonNode kb : kbList) {
                    System.out.printf("   - [%d] %s (%s)%n",
                        kb.get("kbId").asInt(),
                        kb.get("kbName").asText(),
                        kb.get("kbType").asText());
                }
            } else {
                System.out.println("❌ 请求失败: " + kbsResult);
            }

            System.out.println("\n" + "=".repeat(60));
            System.out.println("示例2: 执行 RAG 智能查询");
            System.out.println("=".repeat(60));

            JsonNode queryResult = client.queryKnowledgeBase(
                "什么是RAG技术？",
                List.of(1),
                "zhangsan"
            );

            if (queryResult.has("code") && queryResult.get("code").asInt() == 200) {
                JsonNode data = queryResult.get("data");
                System.out.println("📝 答答:\n" + data.get("answerText").asText() + "\n");
                System.out.println("⏱️  响应耗时: " + data.get("responseTime").asLong() + "ms");
                
                JsonNode chunks = data.get("sourceChunks");
                if (chunks != null && chunks.isArray()) {
                    System.out.println("📚 参考来源 (" + chunks.size() + " 条):");
                    for (int i = 0; i < chunks.size(); i++) {
                        JsonNode chunk = chunks.get(i);
                        double score = chunk.has("retrievalScore") ? 
                            chunk.get("retrievalScore").asDouble() : 0;
                        System.out.printf("   [%d] 得分=%.2f | 文档=%s%n",
                            i + 1, score, chunk.get("fileName").asText());
                    }
                }
            } else {
                System.out.println("❌ 请求失败: " + queryResult);
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

---

### 6.3 JavaScript / Node.js 完整调用示例

```javascript
/**
 * RAG 外部调用完整示例 - JavaScript/Node.js
 * =============================================
 * 演示如何从 Node.js 应用调用 Cradle RAG 系统
 */

const crypto = require('crypto');

class RagClient {
    constructor({ baseUrl, sharedSecret, sourceSystem }) {
        this.baseUrl = baseUrl.replace(/\/+$/, '');
        this.sharedSecret = sharedSecret;
        this.sourceSystem = sourceSystem;
    }

    /**
     * 构建 HMAC-SHA256 签名
     */
    _buildSignature(method, path, payload) {
        const timestamp = Math.floor(Date.now() / 1000).toString();
        const canonicalPayload = JSON.stringify(payload || {}, Object.keys(payload || {}).sort());
        
        const canonicalMessage = [
            method.toUpperCase(),
            path,
            this.sourceSystem,
            timestamp,
            canonicalPayload,
        ].join('\n');

        const signature = crypto
            .createHmac('sha256', this.sharedSecret)
            .update(canonicalMessage)
            .digest('hex');

        return { timestamp, signature };
    }

    /**
     * 构建请求头
     */
    _buildHeaders(method, path, payload, requestId = null) {
        const { timestamp, signature } = this._buildSignature(method, path, payload);
        
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Service-Source-System': this.sourceSystem,
            'X-Service-Timestamp': timestamp,
            'X-Service-Signature': signature,
            'X-Service-Path': path,
        };
        
        if (requestId) {
            headers['X-Service-Request-Id'] = requestId;
        }
        
        return headers;
    }

    /**
     * 发送 HTTP 请求
     */
    async _request(method, path, payload) {
        const headers = this._buildHeaders(method, path, payload);
        const url = `${this.baseUrl}${path}`;

        const response = await fetch(url, {
            method: method,
            headers: headers,
            body: JSON.stringify(payload),
        });

        return await response.json();
    }

    /**
     * 执行 RAG 智能查询
     */
    async queryKnowledgeBase({
        queryText,
        kbIds = [],
        externalUserName = null,
        externalUserId = null,
        externalDeptId = null,
        topK = 5,
        sessionId = null,
        scenario = 'general_qa',
        locale = 'zh-CN',
        retrievalMode = 'hybrid',
        answerMode = 'detailed',
        includeSource = true,
    }) {
        const path = '/internal/rag/query';

        const payload = {
            principal: {
                sourceSystem: this.sourceSystem,
                externalUserId: externalUserId,
                externalUserName: externalUserName,
                externalDeptId: externalDeptId,
            },
            query: {
                kbIds: kbIds,
                queryText: queryText,
                topK: topK,
                includeSource: includeSource,
                sessionId: sessionId || `sess_${Date.now()}`,
                scenario: scenario,
                locale: locale,
                retrievalMode: retrievalMode,
                answerMode: answerMode,
            },
        };

        return await this._request('POST', path, payload);
    }

    /**
     * 获取可见知识库列表
     */
    async getVisibleKnowledgeBases({
        externalUserName = null,
        externalUserId = null,
        externalDeptId = null,
    }) {
        const path = '/internal/rag/kbs/visible';

        const payload = {
            principal: {
                sourceSystem: this.sourceSystem,
                externalUserId: externalUserId,
                externalUserName: externalUserName,
                externalDeptId: externalDeptId,
            },
        };

        return await this._request('POST', path, payload);
    }
}

// ==================== 使用示例 ====================

(async () => {
    const client = new RagClient({
        baseUrl: 'http://192.168.1.100:29099/dev-api',
        sharedSecret: 'your-negotiated-secret-key',
        sourceSystem: 'ksguoaj-google',
    });

    console.log('='.repeat(60));
    console.log('示例1: 查询可见知识库');
    console.log('='.repeat(60));

    const kbsResult = await client.getVisibleKnowledgeBases({
        externalUserName: 'zhangsan',
        externalDeptId: 'dept_100',
    });

    if (kbsResult.code === 200) {
        const { principal, knowledgeBases } = kbsResult.data;
        console.log(`✅ 解析到本地用户: ${principal.mappedUserName}`);
        console.log(`✅ 可访问知识库数量: ${knowledgeBases.length}`);
        knowledgeBases.forEach(kb => {
            console.log(`   - [${kb.kbId}] ${kb.kbName} (${kb.kbType})`);
        });
    } else {
        console.log(`❌ 请求失败: ${JSON.stringify(kbsResult)}`);
    }

    console.log('\n' + '='.repeat(60));
    console.log('示例2: 执行 RAG 智能查询');
    console.log('='.repeat(60));

    const queryResult = await client.queryKnowledgeBase({
        queryText: '什么是RAG技术？它有哪些应用场景？',
        kbIds: [1],
        externalUserName: 'zhangsan',
        topK: 5,
        retrievalMode: 'hybrid',
        answerMode: 'detailed',
        includeSource: true,
    });

    if (queryResult.code === 200) {
        const { answerText, sourceChunks, responseTime } = queryResult.data;
        console.log(`📝 答案:\n${answerText}\n`);
        console.log(`⏱️  响应耗时: ${responseTime}ms`);
        console.log(`📚 参考来源 (${sourceChunks.length} 条):`);
        sourceChunks.forEach((chunk, i) => {
            console.log(`   [${i + 1}] 得分=${chunk.retrievalScore?.toFixed(2)} | 文档=${chunk.fileName}`);
            console.log(`       片段: ${chunk.snippet?.substring(0, 80)}...`);
        });
    } else {
        console.log(`❌ 请求失败: ${JSON.stringify(queryResult)}`);
    }
})();
```

---

### 6.4 cURL 快速测试命令

```bash
# ========================================
# 配置变量（请替换为实际值）
# ========================================

BASE_URL="http://192.168.1.100:29099/dev-api"
SHARED_SECRET="your-negotiated-secret-key"
SOURCE_SYSTEM="ksguoaj-google"

# ========================================
# 示例1: 获取可见知识库
# ========================================

TIMESTAMP=$(date +%s)
PAYLOAD='{"principal":{"sourceSystem":"'"$SOURCE_SYSTEM"'","externalUserName":"zhangsan"}}'
CANONICAL_PAYLOAD=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.dumps(json.loads(sys.stdin.read()), ensure_ascii=False, separators=(',', ':'), sort_keys=True))")
CANONICAL_MESSAGE=$(printf '%s\n%s\n%s\n%s\n%s' "POST" "/internal/rag/kbs/visible" "$SOURCE_SYSTEM" "$TIMESTAMP" "$CANONICAL_PAYLOAD")
SIGNATURE=$(echo -n "$CANONICAL_MESSAGE" | openssl dgst -sha256 -hmac "$SHARED_SECRET" | awk '{print $NF}')

curl -X POST "$BASE_URL/internal/rag/kbs/visible" \
  -H "Content-Type: application/json" \
  -H "X-Service-Source-System: $SOURCE_SYSTEM" \
  -H "X-Service-Timestamp: $TIMESTAMP" \
  -H "X-Service-Signature: $SIGNATURE" \
  -H "X-Service-Path: /internal/rag/kbs/visible" \
  -d "$PAYLOAD" | python3 -m json.tool

# ========================================
# 示例2: 执行 RAG 查询
# ========================================

TIMESTAMP=$(date +%s)
PAYLOAD='{"principal":{"sourceSystem":"'"$SOURCE_SYSTEM"'","externalUserName":"zhangsan"},"query":{"kbIds":[1],"queryText":"什么是RAG技术？","topK":5,"includeSource":true,"sessionId":"test_session_001","scenario":"general_qa","locale":"zh-CN","retrievalMode":"hybrid","answerMode":"detailed"}}'
CANONICAL_PAYLOAD=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.dumps(json.loads(sys.stdin.read()), ensure_ascii=False, separators=(',', ':'), sort_keys=True))")
CANONICAL_MESSAGE=$(printf '%s\n%s\n%s\n%s\n%s' "POST" "/internal/rag/query" "$SOURCE_SYSTEM" "$TIMESTAMP" "$CANONICAL_PAYLOAD")
SIGNATURE=$(echo -n "$CANONICAL_MESSAGE" | openssl dgst -sha256 -hmac "$SHARED_SECRET" | awk '{print $NF}')

curl -X POST "$BASE_URL/internal/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-Service-Source-System: $SOURCE_SYSTEM" \
  -H "X-Service-Timestamp: $TIMESTAMP" \
  -H "X-Service-Signature: $SIGNATURE" \
  -H "X-Service-Path: /internal/rag/query" \
  -d "$PAYLOAD" | python3 -m json.tool
```

---

## 附录

### A. 用户映射配置说明

在 RAG 服务端的 `.env.dev` 中配置外部用户到本地用户的映射关系：

```env
# 外部用户ID → 本地用户ID 映射（JSON对象）
RAG_EXTERNAL_USER_MAP={"ext_user_001": 5, "ext_user_002": 8}

# 外部用户名 → 本地用户ID 映射（JSON对象）
RAG_EXTERNAL_USER_NAME_MAP={"张三": 5, "李四": 8}

# 外部部门ID → 本地部门ID 映射（JSON对象）
RAG_EXTERNAL_DEPT_MAP={"dept_100": 10, "dept_200": 20}

# 是否允许直接用外部用户ID作为本地用户ID查找（开发环境可开启）
RAG_INTERNAL_ALLOW_DIRECT_USER_ID_FALLBACK=true
RAG_INTERNAL_ALLOW_DIRECT_DEPT_ID_FALLBACK=true
```

### B. 权限控制逻辑

| 知识库类型 | 访问条件 |
|-----------|----------|
| **公共/部门级** (`kb_type=dept`) | 用户所属部门匹配 `dept_id` 或用户为管理员 |
| **个人级** (`kb_type=personal`) | 用户 `user_id` 匹配或用户为管理员 |
| **管理员** (`is_admin=true`) | 可访问所有已启用的知识库 |

### C. 性能建议

1. **缓存策略**: 对同一用户的可见知识库列表做客户端缓存（TTL 建议 5 分钟）
2. **批量查询**: 多个相关问题可在同一 `session_id` 下发送，便于后端优化
3. **超时设置**: 建议客户端超时设置为 30~60 秒（含 LLM 生成时间）
4. **重试机制**: 网络异常时可重试一次，但需重新生成签名（时间戳变化）

---

> **文档维护**: 如有接口变更，请联系 RAG 服务团队更新本文档。
