import request from '@/utils/request'
import { getToken } from '@/utils/auth'

const ORCHESTRATOR_BASE_URL = import.meta.env.VITE_APP_BASE_API || ''

function buildTraceId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `trace-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function parseSseChunk(chunk, onMessage) {
  const lines = chunk
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)

  let dataLine = ''
  lines.forEach(line => {
    if (line.startsWith('data:')) {
      dataLine += line.slice(5).trim()
    }
  })

  if (!dataLine) {
    return null
  }

  const payload = JSON.parse(dataLine)
  if (typeof onMessage === 'function') {
    onMessage(payload.event, payload.data)
  }
  if (payload.event === 'error') {
    throw new Error(payload.data?.message || 'Orchestrator stream failed')
  }
  return payload
}

export function orchestratorChat(data) {
  return request({
    url: '/orchestrator/chat',
    method: 'post',
    data,
    timeout: 120000
  })
}

export function createOrchestratorTask(data, idempotencyKey) {
  return request({
    url: '/orchestrator/tasks',
    method: 'post',
    data,
    timeout: 120000,
    headers: {
      'Idempotency-Key': idempotencyKey
    }
  })
}

export function getOrchestratorTask(taskId) {
  return request({
    url: `/orchestrator/tasks/${taskId}`,
    method: 'get'
  })
}

export function getOrchestratorSession(sessionId) {
  return request({
    url: `/orchestrator/sessions/${sessionId}`,
    method: 'get'
  })
}

export async function streamOrchestratorChat(data, options = {}) {
  const { signal, onMessage } = options
  const token = getToken()
  const requestId = buildTraceId()
  const traceId = buildTraceId()
  const response = await fetch(`${ORCHESTRATOR_BASE_URL}/orchestrator/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json;charset=utf-8',
      Authorization: token ? `Bearer ${token}` : '',
      'X-Request-Id': requestId,
      'X-Trace-Id': traceId
    },
    body: JSON.stringify({ ...data, stream: true }),
    signal
  })

  const contentType = response.headers.get('content-type') || ''
  if (!response.ok || contentType.includes('application/json')) {
    let errorMessage = `Request failed with status ${response.status}`
    try {
      const body = await response.json()
      errorMessage = body.msg || body.message || errorMessage
    } catch (error) {
      console.error(error)
    }
    throw new Error(errorMessage)
  }

  if (!response.body) {
    throw new Error('Readable stream is not available')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let donePayload = null

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() || ''

    chunks.forEach(chunk => {
      const payload = parseSseChunk(chunk, onMessage)
      if (payload?.event === 'done') {
        donePayload = payload.data
      }
    })
  }

  if (buffer.trim()) {
    const payload = parseSseChunk(buffer, onMessage)
    if (payload?.event === 'done') {
      donePayload = payload.data
    }
  }

  return donePayload
}
