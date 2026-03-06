import axios from 'axios'
import { ElNotification, ElMessageBox, ElMessage, ElLoading } from 'element-plus'
import { getToken } from '@/utils/auth'
import errorCode from '@/utils/errorCode'
import { tansParams, blobValidate } from '@/utils/ruoyi'
import cache from '@/plugins/cache'
import { saveAs } from 'file-saver'
import useUserStore from '@/store/modules/user'
import useSettingsStore from '@/store/modules/settings'

let downloadLoadingInstance
let globalLoadingInstance
let loadingRequestCount = 0

export let isRelogin = { show: false }

axios.defaults.headers['Content-Type'] = 'application/json;charset=utf-8'

const service = axios.create({
  baseURL: import.meta.env.VITE_APP_BASE_API,
  timeout: 10000
})

function shouldShowGlobalLoading(config) {
  if ((config.headers || {}).showLoading === false) {
    return false
  }
  return useSettingsStore().requestFx
}

function openGlobalLoading() {
  if (loadingRequestCount === 0) {
    globalLoadingInstance = ElLoading.service({
      lock: true,
      text: '数据链路同步中...',
      background: 'rgba(2, 8, 24, 0.68)',
      customClass: 'cyber-loading-mask'
    })
  }
  loadingRequestCount += 1
}

function closeGlobalLoading() {
  if (loadingRequestCount > 0) {
    loadingRequestCount -= 1
  }
  if (loadingRequestCount === 0 && globalLoadingInstance) {
    globalLoadingInstance.close()
    globalLoadingInstance = null
  }
}

service.interceptors.request.use(
  (config) => {
    const isToken = (config.headers || {}).isToken === false
    const isRepeatSubmit = (config.headers || {}).repeatSubmit === false

    if (getToken() && !isToken) {
      config.headers.Authorization = `Bearer ${getToken()}`
    }

    if (config.method === 'get' && config.params) {
      let url = `${config.url}?${tansParams(config.params)}`
      url = url.slice(0, -1)
      config.params = {}
      config.url = url
    }

    if (!isRepeatSubmit && (config.method === 'post' || config.method === 'put')) {
      const requestObj = {
        url: config.url,
        data: typeof config.data === 'object' ? JSON.stringify(config.data) : config.data,
        time: new Date().getTime()
      }
      const requestSize = Object.keys(JSON.stringify(requestObj)).length
      const limitSize = 5 * 1024 * 1024
      if (requestSize >= limitSize) {
        console.warn(`[${config.url}] request payload is too large for repeat-submit cache`)
        return config
      }
      const sessionObj = cache.session.getJSON('sessionObj')
      if (!sessionObj) {
        cache.session.setJSON('sessionObj', requestObj)
      } else {
        const interval = 1000
        if (sessionObj.data === requestObj.data && requestObj.time - sessionObj.time < interval && sessionObj.url === requestObj.url) {
          const message = '数据正在处理中，请勿重复提交'
          console.warn(`[${sessionObj.url}] ${message}`)
          return Promise.reject(new Error(message))
        }
        cache.session.setJSON('sessionObj', requestObj)
      }
    }

    if (shouldShowGlobalLoading(config)) {
      openGlobalLoading()
    }

    return config
  },
  (error) => {
    closeGlobalLoading()
    return Promise.reject(error)
  }
)

service.interceptors.response.use(
  (res) => {
    if (shouldShowGlobalLoading(res.config || {})) {
      closeGlobalLoading()
    }

    const code = res.data.code || 200
    const msg = errorCode[code] || res.data.msg || errorCode.default

    if (res.request.responseType === 'blob' || res.request.responseType === 'arraybuffer') {
      return res.data
    }

    if (code === 401) {
      if (!isRelogin.show) {
        isRelogin.show = true
        ElMessageBox.confirm('登录状态已过期，您可以继续留在该页面，或者重新登录', '系统提示', {
          confirmButtonText: '重新登录',
          cancelButtonText: '取消',
          type: 'warning'
        })
          .then(() => {
            isRelogin.show = false
            useUserStore().logOut().then(() => {
              location.href = '/index'
            })
          })
          .catch(() => {
            isRelogin.show = false
          })
      }
      return Promise.reject(new Error('无效会话或会话已过期，请重新登录'))
    }

    if (code === 500) {
      ElMessage({ message: msg, type: 'error' })
      return Promise.reject(new Error(msg))
    }

    if (code === 601) {
      ElMessage({ message: msg, type: 'warning' })
      return Promise.reject(new Error(msg))
    }

    if (code !== 200) {
      ElNotification.error({ title: msg })
      return Promise.reject(new Error(msg))
    }

    return Promise.resolve(res.data)
  },
  (error) => {
    closeGlobalLoading()

    let { message } = error
    if (message === 'Network Error') {
      message = '后端接口连接异常'
    } else if (message.includes('timeout')) {
      message = '系统接口请求超时'
    } else if (message.includes('Request failed with status code')) {
      message = `系统接口${message.slice(-3)}异常`
    }
    ElMessage({ message, type: 'error', duration: 5000 })
    return Promise.reject(error)
  }
)

export function download(url, params, filename, config) {
  downloadLoadingInstance = ElLoading.service({
    text: '正在下载数据，请稍候',
    background: 'rgba(2, 8, 24, 0.68)',
    customClass: 'cyber-loading-mask'
  })
  return service
    .post(url, params, {
      transformRequest: [(data) => tansParams(data)],
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', showLoading: false },
      responseType: 'blob',
      ...config
    })
    .then(async (data) => {
      const isBlob = blobValidate(data)
      if (isBlob) {
        const blob = new Blob([data])
        saveAs(blob, filename)
      } else {
        const resText = await data.text()
        const rspObj = JSON.parse(resText)
        const errMsg = errorCode[rspObj.code] || rspObj.msg || errorCode.default
        ElMessage.error(errMsg)
      }
      downloadLoadingInstance.close()
    })
    .catch((error) => {
      console.error(error)
      ElMessage.error('下载文件出现错误，请联系管理员')
      downloadLoadingInstance.close()
    })
}

export default service
