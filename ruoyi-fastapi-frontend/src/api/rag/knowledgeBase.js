import request from '@/utils/request'

export function listKnowledgeBase(query) {
  return request({
    url: '/rag/kb/list',
    method: 'get',
    params: query
  })
}

export function getKnowledgeBaseTree() {
  return request({
    url: '/rag/kb/tree',
    method: 'get'
  })
}

export function getKnowledgeBase(kbId) {
  return request({
    url: '/rag/kb/' + kbId,
    method: 'get'
  })
}

export function addKnowledgeBase(data) {
  return request({
    url: '/rag/kb',
    method: 'post',
    data: data
  })
}

export function updateKnowledgeBase(data) {
  return request({
    url: '/rag/kb',
    method: 'put',
    data: data
  })
}

export function delKnowledgeBase(kbIds) {
  return request({
    url: '/rag/kb/' + kbIds,
    method: 'delete'
  })
}
