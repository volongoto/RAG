import request from '@/utils/request'

export function executeQuery(data) {
  return request({
    url: '/rag/query',
    method: 'post',
    data: data,
    // RAG query may include embedding retrieval + LLM generation, which can exceed the global 10s timeout.
    timeout: 120000
  })
}

export function getQueryLogs(query) {
  return request({
    url: '/rag/query/logs',
    method: 'get',
    params: query
  })
}
