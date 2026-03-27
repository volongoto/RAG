import request from '@/utils/request'

export function listDocument(query) {
  return request({
    url: '/rag/doc/list',
    method: 'get',
    params: query
  })
}

export function getDocument(docId) {
  return request({
    url: '/rag/doc/' + docId,
    method: 'get'
  })
}

export function uploadDocument(kbId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/rag/doc/upload',
    method: 'post',
    params: { kbId: kbId },
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
      repeatSubmit: false,
      showLoading: false
    }
  })
}

export function delDocument(docIds) {
  return request({
    url: '/rag/doc/' + docIds,
    method: 'delete'
  })
}

export function reparseDocument(docId) {
  return request({
    url: '/rag/doc/reparse/' + docId,
    method: 'post'
  })
}
