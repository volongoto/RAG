<template>
  <div :class="{ 'has-logo': showLogo }" class="sidebar-container">
    <logo v-if="showLogo" :collapse="isCollapse" />
    <el-scrollbar wrap-class="scrollbar-wrapper">
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :background-color="getMenuBackground"
        :text-color="getMenuTextColor"
        :unique-opened="true"
        :active-text-color="theme"
        :collapse-transition="false"
        mode="vertical"
        :class="['cyber-menu', sideTheme]"
      >
        <sidebar-item
          v-for="(item, index) in sidebarRouters"
          :key="item.path + index"
          :item="item"
          :base-path="item.path"
        />
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup>
import { gsap } from 'gsap'
import Logo from './Logo'
import SidebarItem from './SidebarItem'
import variables from '@/assets/styles/variables.module.scss'
import useAppStore from '@/store/modules/app'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'

const route = useRoute()
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const permissionStore = usePermissionStore()
const prefersReducedMotion = typeof window !== 'undefined'
  ? window.matchMedia('(prefers-reduced-motion: reduce)')
  : { matches: false }

const sidebarRouters = computed(() => permissionStore.sidebarRouters)
const showLogo = computed(() => settingsStore.sidebarLogo)
const sideTheme = computed(() => settingsStore.sideTheme)
const theme = computed(() => settingsStore.theme)
const isCollapse = computed(() => !appStore.sidebar.opened)

const getMenuBackground = computed(() => {
  if (settingsStore.isDark) {
    return 'var(--sidebar-bg)'
  }
  return sideTheme.value === 'theme-dark' ? variables.menuBg : variables.menuLightBg
})

const getMenuTextColor = computed(() => {
  if (settingsStore.isDark) {
    return 'var(--sidebar-text)'
  }
  return sideTheme.value === 'theme-dark' ? variables.menuText : variables.menuLightText
})

const activeMenu = computed(() => {
  const { meta, path } = route
  if (meta.activeMenu) {
    return meta.activeMenu
  }
  return path
})

watch(
  () => isCollapse.value,
  () => {
    nextTick(() => {
      animateMenu()
    })
  }
)

onMounted(() => {
  animateMenu()
})

function animateMenu() {
  if (!settingsStore.routeFx || settingsStore.motionLevel === 'low' || prefersReducedMotion.matches) {
    return
  }
  const nodes = document.querySelectorAll('.sidebar-container .el-menu-item, .sidebar-container .el-sub-menu__title')
  if (!nodes.length) {
    return
  }
  const duration = settingsStore.motionLevel === 'high' ? 0.44 : 0.26
  gsap.fromTo(
    nodes,
    { autoAlpha: 0, x: isCollapse.value ? -8 : -18 },
    {
      autoAlpha: 1,
      x: 0,
      duration,
      ease: 'power2.out',
      stagger: isCollapse.value ? 0 : 0.018
    }
  )
}
</script>

<style lang="scss" scoped>
.sidebar-container {
  background-color: v-bind(getMenuBackground);

  .scrollbar-wrapper {
    background-color: v-bind(getMenuBackground);
  }

  .el-menu {
    border: none;
    height: 100%;
    width: 100% !important;

    .el-menu-item,
    .el-sub-menu__title {
      position: relative;

      &::before {
        content: "";
        position: absolute;
        left: 8px;
        right: 8px;
        top: 6px;
        bottom: 6px;
        border-radius: 8px;
        pointer-events: none;
        opacity: 0;
        background: linear-gradient(90deg, rgba(20, 227, 255, 0.16), rgba(58, 123, 255, 0.08), rgba(240, 74, 255, 0.16));
        transition: opacity 0.24s ease;
      }

      &:hover::before {
        opacity: 1;
      }
    }

    .el-menu-item {
      color: v-bind(getMenuTextColor);

      &.is-active {
        color: var(--menu-active-text, #14e3ff);
        background-color: var(--menu-active-bg) !important;
      }
    }

    .el-sub-menu__title {
      color: v-bind(getMenuTextColor);
    }
  }
}
</style>
