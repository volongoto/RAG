import router from './router'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { getToken } from '@/utils/auth'
import { isHttp, isPathMatch } from '@/utils/validate'
import { isRelogin } from '@/utils/request'
import useUserStore from '@/store/modules/user'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'

NProgress.configure({ showSpinner: false, trickleSpeed: 110, minimum: 0.12, easing: 'ease' })

const whiteList = ['/login', '/register']

const isWhiteList = (path) => whiteList.some((pattern) => isPathMatch(pattern, path))

router.beforeEach((to, from, next) => {
  const settingsStore = useSettingsStore()
  if (settingsStore.routeFx) {
    NProgress.start()
  }

  if (getToken()) {
    to.meta.title && settingsStore.setTitle(to.meta.title)

    if (to.path === '/login') {
      next({ path: '/' })
      settingsStore.routeFx && NProgress.done()
      return
    }

    if (isWhiteList(to.path)) {
      next()
      return
    }

    if (useUserStore().roles.length === 0) {
      isRelogin.show = true
      useUserStore()
        .getInfo()
        .then(() => {
          isRelogin.show = false
          usePermissionStore().generateRoutes().then((accessRoutes) => {
            accessRoutes.forEach((route) => {
              if (!isHttp(route.path)) {
                router.addRoute(route)
              }
            })
            next({ ...to, replace: true })
          })
        })
        .catch((err) => {
          useUserStore().logOut().then(() => {
            ElMessage.error(err)
            next({ path: '/' })
          })
        })
    } else {
      next()
    }
  } else if (isWhiteList(to.path)) {
    next()
  } else {
    next(`/login?redirect=${to.fullPath}`)
    settingsStore.routeFx && NProgress.done()
  }
})

router.afterEach(() => {
  if (useSettingsStore().routeFx) {
    NProgress.done()
  }
})
