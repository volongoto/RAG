import request from '@/utils/request'

export function executeQuery(data) {
  return request({
    url: '/rag/query',
    method: 'post',
    data: data
  })
}

export function getQueryLogs(query) {
  return request({
    url: '/rag/query/logs',
    method: 'get',
    params: query
  })
}
