import Cookies from 'js-cookie'
import { SidebarStatusKey, SizeKey } from '@/utils/auth'

const useAppStore = defineStore(
  'app',
  {
    state: () => ({
      sidebar: {
        opened: Cookies.get(SidebarStatusKey) ? !!+Cookies.get(SidebarStatusKey) : true,
        withoutAnimation: false,
        hide: false
      },
      device: 'desktop',
      size: Cookies.get(SizeKey) || 'default'
    }),
    actions: {
      toggleSideBar(withoutAnimation) {
        if (this.sidebar.hide) {
          return false;
        }
        this.sidebar.opened = !this.sidebar.opened
        this.sidebar.withoutAnimation = withoutAnimation
        if (this.sidebar.opened) {
          Cookies.set(SidebarStatusKey, 1)
        } else {
          Cookies.set(SidebarStatusKey, 0)
        }
      },
      closeSideBar({ withoutAnimation }) {
        Cookies.set(SidebarStatusKey, 0)
        this.sidebar.opened = false
        this.sidebar.withoutAnimation = withoutAnimation
      },
      toggleDevice(device) {
        this.device = device
      },
      setSize(size) {
        this.size = size;
        Cookies.set(SizeKey, size)
      },
      toggleSideBarHide(status) {
        this.sidebar.hide = status
      }
    }
  })

export default useAppStore
