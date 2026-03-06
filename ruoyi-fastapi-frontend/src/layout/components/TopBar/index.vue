<template>
  <el-menu class="topbar-menu" :ellipsis="false" :default-active="activeMenu" :active-text-color="theme" mode="horizontal">
    <sidebar-item v-for="(item, index) in topMenus" :key="item.path + index" :item="item" :base-path="item.path" />

    <el-sub-menu v-if="moreRoutes.length > 0" index="more" class="el-sub-menu__hide-arrow">
      <template #title>
        <span>更多菜单</span>
      </template>
      <sidebar-item v-for="(item, index) in moreRoutes" :key="item.path + index" :item="item" :base-path="item.path" />
    </el-sub-menu>
  </el-menu>
</template>

<script setup>
import SidebarItem from '../Sidebar/SidebarItem'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'

const route = useRoute()
const settingsStore = useSettingsStore()
const permissionStore = usePermissionStore()

const theme = computed(() => settingsStore.theme)
const activeMenu = computed(() => {
  const { meta, path } = route
  return meta.activeMenu || path
})

const visibleNumber = ref(5)
const topMenus = computed(() => permissionStore.sidebarRouters.filter((item) => !item.hidden).slice(0, visibleNumber.value))
const moreRoutes = computed(() => permissionStore.sidebarRouters.filter((item) => !item.hidden).slice(visibleNumber.value))

function setVisibleNumber() {
  const width = document.body.getBoundingClientRect().width / 3
  visibleNumber.value = Math.max(1, Math.floor(width / 85))
}

onMounted(() => {
  setVisibleNumber()
  window.addEventListener('resize', setVisibleNumber)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', setVisibleNumber)
})
</script>

<style lang="scss">
.topbar-menu.el-menu--horizontal .el-submenu__title,
.topbar-menu.el-menu--horizontal .el-menu-item {
  padding: 0 10px !important;
}

.topbar-menu.el-menu--horizontal > .el-menu-item {
  float: left;
  height: 50px !important;
  line-height: 50px !important;
  color: var(--navbar-text) !important;
  padding: 0 8px !important;
  margin: 0 8px !important;
  border-radius: 8px;
}

.topbar-menu.el-menu--horizontal > .el-menu-item:hover {
  background: var(--navbar-hover) !important;
}

.el-sub-menu.is-active .svg-icon,
.el-menu-item.is-active .svg-icon + span,
.el-sub-menu.is-active .svg-icon + span,
.el-sub-menu.is-active .el-sub-menu__title span {
  color: v-bind(theme);
  text-shadow: 0 0 10px rgba(20, 227, 255, 0.45);
}

.topbar-menu.el-menu--horizontal > .el-sub-menu .el-sub-menu__title {
  float: left;
  line-height: 50px !important;
  color: var(--navbar-text) !important;
  margin: 0 15px -3px !important;
  border-radius: 8px;
}

.topbar-menu.el-menu--horizontal > .el-sub-menu .el-sub-menu__title:hover {
  background: var(--navbar-hover) !important;
}

.topbar-menu .el-sub-menu .el-sub-menu__icon-arrow {
  position: static;
  margin-left: 8px;
  margin-top: 0;
  display: block !important;
}

.topbar-menu.el-menu--horizontal .el-sub-menu__title,
.topbar-menu.el-menu--horizontal .el-menu-item {
  height: 50px;
}
</style>
