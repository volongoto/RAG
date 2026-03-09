<template>
  <div class="app-container">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <span>知识库选择</span>
          </template>
          <el-tree
            ref="kbTreeRef"
            :data="kbTree"
            :props="{ children: 'children', label: 'label' }"
            show-checkbox
            node-key="id"
            :check-strictly="false"
            @check="handleKbCheck"
          />
        </el-card>
      </el-col>
      <el-col :span="18">
        <el-card shadow="hover">
          <template #header>
            <span>知识查询</span>
          </template>
          <div class="query-container">
            <div class="query-input">
              <el-input
                v-model="queryText"
                type="textarea"
                :rows="3"
                placeholder="请输入您的问题，Ctrl+Enter 发送"
                @keyup.enter.ctrl="handleQuery"
              />
              <div class="query-options">
                <div class="query-option-item">
                  <span class="query-option-label">TopK</span>
                  <el-input-number v-model="queryOptions.topK" :min="1" :max="50" :step="1" :controls="false" />
                </div>
                <div class="query-option-item">
                  <span class="query-option-label">召回模式</span>
                  <el-select v-model="queryOptions.retrievalMode" style="width: 130px">
                    <el-option label="Hybrid" value="hybrid" />
                    <el-option label="Vector" value="vector" />
                    <el-option label="Lexical" value="lexical" />
                  </el-select>
                </div>
                <div class="query-option-item">
                  <span class="query-option-label">返回来源</span>
                  <el-switch v-model="queryOptions.includeSource" />
                </div>
                <div class="query-option-item">
                  <span class="query-option-label">回答模式</span>
                  <el-select v-model="queryOptions.answerMode" style="width: 130px">
                    <el-option label="详细" value="detailed" />
                    <el-option label="精简" value="concise" />
                  </el-select>
                </div>
              </div>
              <div class="query-actions">
                <el-button type="primary" :loading="queryLoading" @click="handleQuery">
                  <el-icon><Search /></el-icon>
                  查询
                </el-button>
                <el-button @click="handleClear">
                  <el-icon><Refresh /></el-icon>
                  清空
                </el-button>
              </div>
            </div>

            <div v-if="answerText" class="answer-container">
              <el-divider content-position="left">回答结果</el-divider>
              <div class="answer-content">
                <div class="answer-text">{{ answerText }}</div>
                <div v-if="responseTime" class="response-time">响应时间: {{ responseTime }}ms</div>
              </div>
            </div>

            <div v-if="sourceChunks.length > 0" class="source-container">
              <el-divider content-position="left">参考来源</el-divider>
              <el-collapse v-model="activeChunks">
                <el-collapse-item
                  v-for="(chunk, index) in sourceChunks"
                  :key="chunk.chunkId || chunk.chunk_id || index"
                  :name="index"
                >
                  <template #title>
                    <div class="source-title">
                      <el-tag size="small" type="primary">文档 {{ index + 1 }}</el-tag>
                      <span class="doc-name">{{ chunk.docName || chunk.fileName || '未命名文档' }}</span>
                      <span v-if="chunk.pageNum || chunk.page" class="page-info">第 {{ chunk.pageNum || chunk.page }} 页</span>
                      <el-tag size="small" type="success" v-if="chunk.similarity || chunk.retrievalScore">
                        相似度 {{ (((chunk.similarity || chunk.retrievalScore) || 0) * 100).toFixed(1) }}%
                      </el-tag>
                    </div>
                  </template>
                  <div class="source-content">{{ chunk.content || chunk.snippet }}</div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="Query">
import { executeQuery } from "@/api/rag/query";
import { getKnowledgeBaseTree } from "@/api/rag/knowledgeBase";
import { Search, Refresh } from "@element-plus/icons-vue";

const { proxy } = getCurrentInstance();

const kbTree = ref([]);
const selectedKbIds = ref([]);
const queryText = ref("");
const queryLoading = ref(false);
const answerText = ref("");
const responseTime = ref(0);
const sourceChunks = ref([]);
const activeChunks = ref([]);
const sessionId = ref(`rag-ui-${Date.now()}`);
const queryOptions = reactive({
  topK: 10,
  retrievalMode: "hybrid",
  includeSource: true,
  answerMode: "detailed",
});

function getKbTree() {
  getKnowledgeBaseTree().then((response) => {
    kbTree.value = response.data || [];
  });
}

function handleKbCheck() {
  const checkedNodes = proxy.$refs.kbTreeRef.getCheckedNodes(true);
  selectedKbIds.value = checkedNodes
    .filter((node) => typeof node.id === "number")
    .map((node) => node.id);
}

async function handleQuery() {
  if (!queryText.value.trim()) {
    proxy.$modal.msgWarning("请输入查询内容");
    return;
  }
  if (selectedKbIds.value.length === 0) {
    proxy.$modal.msgWarning("请选择至少一个知识库");
    return;
  }

  queryLoading.value = true;
  answerText.value = "";
  sourceChunks.value = [];
  activeChunks.value = [];

  try {
    const response = await executeQuery({
      kbIds: selectedKbIds.value,
      queryText: queryText.value,
      topK: queryOptions.topK,
      includeSource: queryOptions.includeSource,
      sessionId: sessionId.value,
      scenario: "rag-query-ui",
      locale: "zh-CN",
      retrievalMode: queryOptions.retrievalMode,
      answerMode: queryOptions.answerMode,
    });

    answerText.value = response.data.answerText;
    responseTime.value = response.data.responseTime;
    sourceChunks.value = queryOptions.includeSource ? (response.data.sourceChunks || []) : [];

    if (sourceChunks.value.length > 0) {
      activeChunks.value = [0];
    }
  } catch (error) {
    proxy.$modal.msgError("查询失败: " + (error.message || "未知错误"));
  } finally {
    queryLoading.value = false;
  }
}

function handleClear() {
  queryText.value = "";
  answerText.value = "";
  responseTime.value = 0;
  sourceChunks.value = [];
  activeChunks.value = [];
}

getKbTree();
</script>

<style scoped>
.query-container {
  min-height: 400px;
}

.query-input {
  margin-bottom: 20px;
}

.query-options {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.query-option-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.query-option-label {
  color: #606266;
  font-size: 13px;
}

.query-actions {
  margin-top: 10px;
  text-align: right;
}

.answer-container {
  margin-top: 20px;
}

.answer-content {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}

.answer-text {
  line-height: 1.8;
  white-space: pre-wrap;
}

.response-time {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  text-align: right;
}

.source-container {
  margin-top: 20px;
}

.source-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-name {
  font-weight: 500;
}

.page-info {
  color: #909399;
  font-size: 12px;
}

.source-content {
  background-color: #fafafa;
  padding: 10px;
  border-radius: 4px;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}
</style>
