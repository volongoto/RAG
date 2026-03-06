<template>
  <startup-loader :visible="showStartupLoader" />
  <router-view />
</template>

<script setup>
import router from '@/router'
import StartupLoader from '@/components/StartupLoader'
import useSettingsStore from '@/store/modules/settings'
import { handleThemeStyle } from '@/utils/theme'

const showStartupLoader = ref(true)

onMounted(() => {
  const settingsStore = useSettingsStore()
  const minVisibleMs = 900
  const startedAt = Date.now()

  nextTick(() => {
    handleThemeStyle(settingsStore.theme)
  })

  router.isReady().then(() => {
    const elapsed = Date.now() - startedAt
    const delay = Math.max(0, minVisibleMs - elapsed)
    setTimeout(() => {
      showStartupLoader.value = false
    }, delay)
  })
})
</script>
