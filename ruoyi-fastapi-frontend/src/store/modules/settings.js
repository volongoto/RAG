import defaultSettings from '@/settings'
import { useDark, useToggle } from '@vueuse/core'
import { useDynamicTitle } from '@/utils/dynamicTitle'

const isDark = useDark()
const toggleDark = useToggle(isDark)

const {
  sideTheme,
  showSettings,
  navType,
  tagsView,
  tagsIcon,
  fixedHeader,
  sidebarLogo,
  dynamicTitle,
  footerVisible,
  footerContent
} = defaultSettings

function getStorageSetting() {
  try {
    return JSON.parse(localStorage.getItem('layout-setting') || '{}')
  } catch (error) {
    console.warn('invalid layout-setting payload', error)
    return {}
  }
}

const storageSetting = getStorageSetting()

const useSettingsStore = defineStore('settings', {
  state: () => ({
    title: '',
    theme: storageSetting.theme || '#14E3FF',
    sideTheme: storageSetting.sideTheme || sideTheme,
    showSettings,
    navType: storageSetting.navType === undefined ? navType : storageSetting.navType,
    tagsView: storageSetting.tagsView === undefined ? tagsView : storageSetting.tagsView,
    tagsIcon: storageSetting.tagsIcon === undefined ? tagsIcon : storageSetting.tagsIcon,
    fixedHeader: storageSetting.fixedHeader === undefined ? fixedHeader : storageSetting.fixedHeader,
    sidebarLogo: storageSetting.sidebarLogo === undefined ? sidebarLogo : storageSetting.sidebarLogo,
    dynamicTitle: storageSetting.dynamicTitle === undefined ? dynamicTitle : storageSetting.dynamicTitle,
    footerVisible: storageSetting.footerVisible === undefined ? footerVisible : storageSetting.footerVisible,
    footerContent,
    isDark: isDark.value,
    motionLevel: storageSetting.motionLevel || 'high',
    routeFx: storageSetting.routeFx === undefined ? true : storageSetting.routeFx,
    requestFx: storageSetting.requestFx === undefined ? true : storageSetting.requestFx
  }),
  actions: {
    changeSetting(data) {
      const { key, value } = data
      if (Object.prototype.hasOwnProperty.call(this, key)) {
        this[key] = value
      }
    },
    setTitle(title) {
      this.title = title
      useDynamicTitle()
    },
    toggleTheme() {
      this.isDark = !this.isDark
      toggleDark()
    }
  }
})

export default useSettingsStore
