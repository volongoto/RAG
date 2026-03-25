<template>
  <div class="app-container orchestrator-page">
    <el-tabs v-model="activeTab" class="orchestrator-tabs">
      <el-tab-pane label="会话编排" name="chat">
        <el-row :gutter="20">
          <el-col :xl="6" :lg="7" :md="24">
            <el-card shadow="hover" class="panel-card">
              <template #header>
                <div class="panel-header">
                  <span>参数区</span>
                  <el-tag size="small" effect="plain">已选 {{ selectedKbIds.length }} 个知识库</el-tag>
                </div>
              </template>

              <div class="form-section">
                <div class="section-title">知识库选择</div>
                <el-tree
                  ref="chatKbTreeRef"
                  :data="kbTree"
                  :props="{ children: 'children', label: 'label' }"
                  show-checkbox
                  node-key="id"
                  :check-strictly="false"
                  @check="handleKbCheck(chatKbTreeRef)"
                />
              </div>

              <div class="form-section">
                <div class="section-title">会话配置</div>
                <el-input v-model="chatForm.sessionId" placeholder="会话 ID" class="form-item" />
                <el-input v-model="chatForm.scenario" placeholder="场景标识" class="form-item" />
                <el-input v-model="chatForm.locale" placeholder="语言区域" class="form-item" />
              </div>

              <div class="form-section">
                <div class="section-title">提问内容</div>
                <el-input
                  v-model="chatForm.message"
                  type="textarea"
                  :rows="7"
                  placeholder="请输入要提交给编排器的问题，Ctrl+Enter 可直接发送"
                  @keyup.enter.ctrl="handleChat"
                />
              </div>

              <div class="option-grid">
                <div class="option-item">
                  <span class="option-label">TopK</span>
                  <el-input-number v-model="chatForm.topK" :min="1" :max="50" :controls="false" />
                </div>
                <div class="option-item">
                  <span class="option-label">召回模式</span>
                  <el-select v-model="chatForm.retrievalMode">
                    <el-option label="Hybrid" value="hybrid" />
                    <el-option label="Vector" value="vector" />
                    <el-option label="Lexical" value="lexical" />
                  </el-select>
                </div>
                <div class="option-item">
                  <span class="option-label">返回证据</span>
                  <el-switch v-model="chatForm.includeSource" />
                </div>
                <div class="option-item">
                  <span class="option-label">流式轨迹</span>
                  <el-switch v-model="chatForm.stream" />
                </div>
              </div>

              <div class="action-row">
                <el-button type="primary" :loading="chatLoading" @click="handleChat">
                  <el-icon><Search /></el-icon>
                  执行编排
                </el-button>
                <el-button :disabled="!chatLoading || !chatForm.stream" @click="cancelChat()">
                  <el-icon><SwitchButton /></el-icon>
                  停止
                </el-button>
                <el-button @click="handleNewChat">
                  <el-icon><Refresh /></el-icon>
                  新会话
                </el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :xl="10" :lg="9" :md="24">
            <el-card shadow="hover" class="panel-card">
              <template #header>
                <div class="panel-header">
                  <span>结果区</span>
                  <div class="header-tags">
                    <el-tag size="small" effect="plain">Session {{ chatForm.sessionId }}</el-tag>
                    <el-tag v-if="chatResult.requestId" size="small" effect="plain">Req {{ chatResult.requestId }}</el-tag>
                  </div>
                </div>
              </template>

              <div class="summary-bar">
                <div class="summary-item">
                  <span class="summary-label">Trace ID</span>
                  <span class="summary-value">{{ chatResult.traceId || '--' }}</span>
                </div>
                <div class="summary-item">
                  <span class="summary-label">总耗时</span>
                  <span class="summary-value">{{ chatResult.latencyMs ? `${chatResult.latencyMs} ms` : '--' }}</span>
                </div>
                <div class="summary-item">
                  <span class="summary-label">工具调用</span>
                  <span class="summary-value">{{ chatResult.toolCalls.length }}</span>
                </div>
              </div>

              <div class="answer-block">
                <div class="block-title">最终答案</div>
                <div class="answer-content">{{ chatResult.finalAnswer || '等待执行结果...' }}</div>
              </div>

              <div v-if="chatResult.toolCalls.length" class="tool-call-list">
                <div class="block-title">工具摘要</div>
                <div class="tool-call-tags">
                  <el-tag
                    v-for="item in chatResult.toolCalls"
                    :key="`${item.tool}-${item.status}`"
                    :type="item.status === 'success' ? 'success' : 'danger'"
                    effect="light"
                  >
                    {{ item.tool }} · {{ item.latencyMs }} ms
                  </el-tag>
                </div>
              </div>

              <div class="session-block">
                <div class="block-title">会话消息</div>
                <el-empty v-if="chatSessionMessages.length === 0" description="当前会话暂无消息" :image-size="64" />
                <div v-else class="session-list">
                  <div
                    v-for="(item, index) in chatSessionMessages"
                    :key="`${item.time || index}-${index}`"
                    :class="['session-item', item.role]"
                  >
                    <div class="session-role">{{ item.role === 'user' ? '用户' : '助手' }}</div>
                    <div class="session-text">{{ item.content }}</div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :xl="8" :lg="8" :md="24">
            <TracePanel :trace-events="chatResult.traceEvents" title="执行轨迹" />
          </el-col>
        </el-row>

        <EvidencePanel :citations="chatResult.citations" title="证据面板" />
      </el-tab-pane>

      <el-tab-pane label="异步任务" name="task">
        <el-row :gutter="20">
          <el-col :xl="6" :lg="7" :md="24">
            <el-card shadow="hover" class="panel-card">
              <template #header>
                <div class="panel-header">
                  <span>任务参数</span>
                  <el-tag size="small" effect="plain">已选 {{ selectedKbIds.length }} 个知识库</el-tag>
                </div>
              </template>

              <div class="form-section">
                <div class="section-title">知识库选择</div>
                <el-tree
                  ref="taskKbTreeRef"
                  :data="kbTree"
                  :props="{ children: 'children', label: 'label' }"
                  show-checkbox
                  node-key="id"
                  :check-strictly="false"
                  @check="handleKbCheck(taskKbTreeRef)"
                />
              </div>

              <div class="form-section">
                <div class="section-title">任务配置</div>
                <el-input v-model="taskForm.sessionId" placeholder="会话 ID" class="form-item" />
                <el-input v-model="taskForm.taskType" placeholder="任务类型" class="form-item" />
                <el-input v-model="taskForm.scenario" placeholder="场景标识" class="form-item" />
                <el-input v-model="taskForm.locale" placeholder="语言区域" class="form-item" />
              </div>

              <div class="form-section">
                <div class="section-title">任务内容</div>
                <el-input
                  v-model="taskForm.message"
                  type="textarea"
                  :rows="7"
                  placeholder="请输入需要异步处理的内容"
                />
              </div>

              <div class="option-grid">
                <div class="option-item">
                  <span class="option-label">TopK</span>
                  <el-input-number v-model="taskForm.topK" :min="1" :max="50" :controls="false" />
                </div>
                <div class="option-item">
                  <span class="option-label">召回模式</span>
                  <el-select v-model="taskForm.retrievalMode">
                    <el-option label="Hybrid" value="hybrid" />
                    <el-option label="Vector" value="vector" />
                    <el-option label="Lexical" value="lexical" />
                  </el-select>
                </div>
                <div class="option-item">
                  <span class="option-label">返回证据</span>
                  <el-switch v-model="taskForm.includeSource" />
                </div>
              </div>

              <div class="action-row">
                <el-button type="primary" :loading="taskLoading" @click="handleCreateTask">
                  <el-icon><VideoPlay /></el-icon>
                  提交任务
                </el-button>
                <el-button :disabled="!taskState.taskId" @click="refreshTask">
                  <el-icon><Refresh /></el-icon>
                  立即刷新
                </el-button>
                <el-button @click="handleResetTask">
                  <el-icon><Refresh /></el-icon>
                  重置
                </el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :xl="10" :lg="9" :md="24">
            <el-card shadow="hover" class="panel-card">
              <template #header>
                <div class="panel-header">
                  <span>任务结果</span>
                  <div class="header-tags">
                    <el-tag v-if="taskState.taskId" size="small" effect="plain">Task {{ taskState.taskId }}</el-tag>
                    <el-tag v-if="taskPolling" size="small" type="warning" effect="plain">轮询中</el-tag>
                  </div>
                </div>
              </template>

              <div class="summary-bar">
                <div class="summary-item">
                  <span class="summary-label">状态</span>
                  <el-tag :type="taskStatusTagType(taskState.status)" effect="light">
                    {{ taskStatusText(taskState.status) }}
                  </el-tag>
                </div>
                <div class="summary-item">
                  <span class="summary-label">当前步骤</span>
                  <span class="summary-value">{{ taskState.currentStep || '--' }}</span>
                </div>
                <div class="summary-item">
                  <span class="summary-label">更新时间</span>
                  <span class="summary-value">{{ formatDateTime(taskState.updateTime) }}</span>
                </div>
              </div>

              <el-progress
                :percentage="taskState.progressPercent || 0"
                :status="taskState.status === 'failed' ? 'exception' : taskState.status === 'success' ? 'success' : ''"
                :stroke-width="14"
              />

              <div class="answer-block">
                <div class="block-title">任务输出</div>
                <div class="answer-content">{{ taskAnswer || taskState.error || '等待任务执行结果...' }}</div>
              </div>

              <div class="summary-grid">
                <div class="summary-item">
                  <span class="summary-label">Request ID</span>
                  <span class="summary-value">{{ taskState.requestId || '--' }}</span>
                </div>
                <div class="summary-item">
                  <span class="summary-label">Trace ID</span>
                  <span class="summary-value">{{ taskState.traceId || '--' }}</span>
                </div>
                <div class="summary-item">
                  <span class="summary-label">创建时间</span>
                  <span class="summary-value">{{ formatDateTime(taskState.createTime) }}</span>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :xl="8" :lg="8" :md="24">
            <TracePanel :trace-events="taskTraceEvents" title="任务轨迹" />
          </el-col>
        </el-row>

        <EvidencePanel :citations="taskCitations" title="任务证据" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup name="Orchestrator">
import { getKnowledgeBaseTree } from '@/api/rag/knowledgeBase'
import {
  createOrchestratorTask,
  getOrchestratorSession,
  getOrchestratorTask,
  orchestratorChat,
  streamOrchestratorChat
} from '@/api/rag/orchestrator'
import EvidencePanel from './components/EvidencePanel.vue'
import TracePanel from './components/TracePanel.vue'
import { Refresh, Search, SwitchButton, VideoPlay } from '@element-plus/icons-vue'

const { proxy } = getCurrentInstance()

const activeTab = ref('chat')
const kbTree = ref([])
const selectedKbIds = ref([])
const chatKbTreeRef = ref(null)
const taskKbTreeRef = ref(null)
const chatLoading = ref(false)
const chatAbortController = shallowRef(null)
const chatSessionMessages = ref([])
const taskLoading = ref(false)
const taskPolling = ref(false)

let taskTimer = null

const chatForm = reactive({
  sessionId: buildSessionId('orc-ui'),
  scenario: 'orchestrator-visual',
  locale: 'zh-CN',
  message: '',
  topK: 10,
  retrievalMode: 'hybrid',
  includeSource: true,
  stream: true
})

const taskForm = reactive({
  sessionId: buildSessionId('orc-task'),
  taskType: 'report_generation',
  scenario: 'orchestrator-task',
  locale: 'zh-CN',
  message: '',
  topK: 10,
  retrievalMode: 'hybrid',
  includeSource: true
})

const chatResult = reactive(createEmptyChatResult())
const taskState = reactive(createEmptyTaskState())

const taskAnswer = computed(() => taskState.result?.finalAnswer || '')
const taskCitations = computed(() => taskState.result?.citations || [])
const taskTraceEvents = computed(() => taskState.traceEvents?.length ? taskState.traceEvents : (taskState.result?.traceEvents || []))

function buildSessionId(prefix) {
  return `${prefix}-${Date.now()}`
}

function buildIdempotencyKey() {
  return `${buildSessionId('orc-task-key')}-${Math.random().toString(16).slice(2)}`
}

function createEmptyChatResult() {
  return {
    finalAnswer: '',
    citations: [],
    traceEvents: [],
    toolCalls: [],
    latencyMs: 0,
    requestId: '',
    traceId: ''
  }
}

function createEmptyTaskState() {
  return {
    taskId: '',
    status: '',
    currentStep: '',
    progressPercent: 0,
    error: '',
    requestId: '',
    traceId: '',
    traceEvents: [],
    result: null,
    createTime: '',
    updateTime: ''
  }
}

function resetChatResult() {
  Object.assign(chatResult, createEmptyChatResult())
}

function resetTaskState() {
  Object.assign(taskState, createEmptyTaskState())
}

function getSelectedTreeIds(treeRef) {
  const checkedNodes = treeRef?.getCheckedNodes?.(true) || []
  return checkedNodes.filter(node => typeof node.id === 'number').map(node => node.id)
}

function syncTreeSelection() {
  const checkedKeys = selectedKbIds.value.slice()
  chatKbTreeRef.value?.setCheckedKeys(checkedKeys)
  taskKbTreeRef.value?.setCheckedKeys(checkedKeys)
}

function handleKbCheck(treeRef) {
  selectedKbIds.value = getSelectedTreeIds(treeRef.value)
  nextTick(() => {
    syncTreeSelection()
  })
}

function validateFormMessage(message) {
  if (!message.trim()) {
    proxy.$modal.msgWarning('请输入内容后再执行')
    return false
  }
  if (selectedKbIds.value.length === 0) {
    proxy.$modal.msgWarning('请至少选择一个知识库')
    return false
  }
  return true
}

function applyChatResult(data) {
  Object.assign(chatResult, {
    finalAnswer: data.finalAnswer || '',
    citations: data.citations || [],
    traceEvents: data.traceEvents || [],
    toolCalls: data.toolCalls || [],
    latencyMs: data.latencyMs || 0,
    requestId: data.requestId || '',
    traceId: data.traceId || ''
  })
}

function applyTaskState(data) {
  Object.assign(taskState, {
    taskId: data.taskId || '',
    status: data.status || '',
    currentStep: data.currentStep || '',
    progressPercent: data.progressPercent || 0,
    error: data.error || '',
    requestId: data.requestId || '',
    traceId: data.traceId || '',
    traceEvents: data.traceEvents || [],
    result: data.result || null,
    createTime: data.createTime || '',
    updateTime: data.updateTime || ''
  })
}

async function loadKnowledgeBaseTree() {
  const response = await getKnowledgeBaseTree()
  kbTree.value = response.data || []
  nextTick(() => {
    syncTreeSelection()
  })
}

async function refreshChatSession() {
  if (!chatForm.sessionId) {
    return
  }
  const response = await getOrchestratorSession(chatForm.sessionId)
  chatSessionMessages.value = response.data?.messages || []
}

async function handleChat() {
  if (!validateFormMessage(chatForm.message)) {
    return
  }

  chatLoading.value = true
  resetChatResult()

  const payload = {
    sessionId: chatForm.sessionId,
    scenario: chatForm.scenario,
    locale: chatForm.locale,
    message: chatForm.message,
    kbIds: selectedKbIds.value,
    stream: chatForm.stream,
    topK: chatForm.topK,
    retrievalMode: chatForm.retrievalMode,
    includeSource: chatForm.includeSource
  }

  try {
    if (chatForm.stream) {
      const controller = new AbortController()
      chatAbortController.value = controller
      const result = await streamOrchestratorChat(payload, {
        signal: controller.signal,
        onMessage(event, data) {
          if (event === 'step') {
            chatResult.traceEvents = [...chatResult.traceEvents, data]
            chatResult.requestId = data.requestId || chatResult.requestId
            chatResult.traceId = data.traceId || chatResult.traceId
          }
          if (event === 'answer') {
            chatResult.finalAnswer = data.finalAnswer || ''
            chatResult.citations = data.citations || []
          }
        }
      })
      if (result) {
        applyChatResult(result)
      }
    } else {
      const response = await orchestratorChat(payload)
      applyChatResult(response.data)
    }
    await refreshChatSession()
  } catch (error) {
    if (error?.name !== 'AbortError') {
      proxy.$modal.msgError(`编排执行失败: ${error.message || '未知错误'}`)
    }
  } finally {
    chatLoading.value = false
    chatAbortController.value = null
  }
}

function cancelChat(silent = false) {
  if (!chatAbortController.value) {
    return
  }
  chatAbortController.value.abort()
  chatAbortController.value = null
  if (!silent) {
    proxy.$modal.msgWarning('已停止当前流式会话')
  }
}

function handleNewChat() {
  cancelChat(true)
  chatForm.sessionId = buildSessionId('orc-ui')
  chatForm.message = ''
  resetChatResult()
  chatSessionMessages.value = []
}

async function handleCreateTask() {
  if (!validateFormMessage(taskForm.message)) {
    return
  }

  taskLoading.value = true
  stopTaskPolling()
  resetTaskState()

  try {
    const response = await createOrchestratorTask(
      {
        sessionId: taskForm.sessionId,
        scenario: taskForm.scenario,
        locale: taskForm.locale,
        taskType: taskForm.taskType,
        payload: {
          message: taskForm.message,
          kbIds: selectedKbIds.value,
          topK: taskForm.topK,
          retrievalMode: taskForm.retrievalMode,
          includeSource: taskForm.includeSource
        }
      },
      buildIdempotencyKey()
    )
    applyTaskState(response.data)
    proxy.$modal.msgSuccess('异步任务已提交')
    startTaskPolling()
  } catch (error) {
    proxy.$modal.msgError(`任务提交失败: ${error.message || '未知错误'}`)
  } finally {
    taskLoading.value = false
  }
}

async function refreshTask() {
  if (!taskState.taskId) {
    return
  }

  try {
    const response = await getOrchestratorTask(taskState.taskId)
    applyTaskState(response.data)
    if (['success', 'failed'].includes(taskState.status)) {
      stopTaskPolling()
    }
  } catch (error) {
    stopTaskPolling()
    proxy.$modal.msgError(`任务刷新失败: ${error.message || '未知错误'}`)
  }
}

function startTaskPolling() {
  if (!taskState.taskId) {
    return
  }
  stopTaskPolling()
  taskPolling.value = true
  refreshTask()
  taskTimer = window.setInterval(() => {
    refreshTask()
  }, 2000)
}

function stopTaskPolling() {
  taskPolling.value = false
  if (taskTimer) {
    window.clearInterval(taskTimer)
    taskTimer = null
  }
}

function handleResetTask() {
  stopTaskPolling()
  taskForm.sessionId = buildSessionId('orc-task')
  taskForm.message = ''
  resetTaskState()
}

function taskStatusTagType(status) {
  if (status === 'success') {
    return 'success'
  }
  if (status === 'failed') {
    return 'danger'
  }
  if (status === 'running') {
    return 'warning'
  }
  return 'info'
}

function taskStatusText(status) {
  if (status === 'success') {
    return '成功'
  }
  if (status === 'failed') {
    return '失败'
  }
  if (status === 'running') {
    return '运行中'
  }
  if (status === 'pending') {
    return '排队中'
  }
  return '未启动'
}

function formatDateTime(value) {
  if (!value) {
    return '--'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

watch(activeTab, () => {
  nextTick(() => {
    syncTreeSelection()
  })
})

onMounted(() => {
  loadKnowledgeBaseTree()
})

onBeforeUnmount(() => {
  cancelChat(true)
  stopTaskPolling()
})
</script>

<style scoped>
.orchestrator-page {
  padding-bottom: 12px;
}

.panel-card {
  min-height: 680px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.form-section {
  margin-bottom: 20px;
}

.section-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #303133;
}

.form-item {
  margin-bottom: 10px;
}

.option-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.option-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-label {
  font-size: 12px;
  color: #606266;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.summary-bar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.summary-item {
  padding: 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f7fafc 0%, #eef4ff 100%);
}

.summary-label {
  display: block;
  color: #909399;
  font-size: 12px;
  margin-bottom: 6px;
}

.summary-value {
  color: #303133;
  font-size: 13px;
  word-break: break-all;
}

.answer-block,
.session-block,
.tool-call-list {
  margin-top: 18px;
}

.block-title {
  margin-bottom: 10px;
  font-weight: 700;
  color: #303133;
}

.answer-content {
  min-height: 140px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f7fafc;
  color: #303133;
  line-height: 1.8;
  white-space: pre-wrap;
}

.tool-call-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 280px;
  overflow-y: auto;
  padding-right: 4px;
}

.session-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f5f7fa;
}

.session-item.assistant {
  background: #eef7ff;
}

.session-role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.session-text {
  line-height: 1.7;
  color: #303133;
  white-space: pre-wrap;
}

@media (max-width: 1200px) {
  .panel-card {
    min-height: auto;
    margin-bottom: 20px;
  }
}

@media (max-width: 768px) {
  .option-grid,
  .summary-bar,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
