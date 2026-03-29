<template>
  <el-drawer v-model="showSettings" :with-header="false" :lock-scroll="false" direction="rtl" size="320px">
    <div class="setting-drawer-title">
      <h3 class="drawer-title">菜单导航设置</h3>
    </div>
    <div class="nav-wrap">
      <el-tooltip content="左侧菜单" placement="bottom">
        <div class="item left" :class="{ activeItem: navType === 1 }" @click="handleNavType(1)">
          <b></b><b></b>
        </div>
      </el-tooltip>

      <el-tooltip content="混合菜单" placement="bottom">
        <div class="item mix" :class="{ activeItem: navType === 2 }" @click="handleNavType(2)">
          <b></b><b></b>
        </div>
      </el-tooltip>

      <el-tooltip content="顶部菜单" placement="bottom">
        <div class="item top" :class="{ activeItem: navType === 3 }" @click="handleNavType(3)">
          <b></b><b></b>
        </div>
      </el-tooltip>
    </div>

    <div class="setting-drawer-title">
      <h3 class="drawer-title">主题风格</h3>
      <small class="drawer-tip">深色模式已升级为赛博高对比风格</small>
    </div>
    <div class="setting-drawer-block-checbox">
      <div class="setting-drawer-block-checbox-item" @click="handleTheme('theme-dark')">
        <img src="@/assets/images/dark.svg" alt="dark" />
        <div v-if="sideTheme === 'theme-dark'" class="setting-drawer-block-checbox-selectIcon">
          <el-icon><Check /></el-icon>
        </div>
      </div>
      <div class="setting-drawer-block-checbox-item" @click="handleTheme('theme-light')">
        <img src="@/assets/images/light.svg" alt="light" />
        <div v-if="sideTheme === 'theme-light'" class="setting-drawer-block-checbox-selectIcon">
          <el-icon><Check /></el-icon>
        </div>
      </div>
    </div>
    <div class="drawer-item">
      <span>主题色</span>
      <span class="comp-style">
        <el-color-picker v-model="theme" :predefine="predefineColors" @change="themeChange" />
      </span>
    </div>
    <el-divider />

    <h3 class="drawer-title">系统布局配置</h3>

    <div class="drawer-item">
      <span>开启 Tags-Views</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.tagsView" class="drawer-switch" />
      </span>
    </div>

    <div class="drawer-item">
      <span>显示页签图标</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.tagsIcon" :disabled="!settingsStore.tagsView" class="drawer-switch" />
      </span>
    </div>

    <div class="drawer-item">
      <span>固定 Header</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.fixedHeader" class="drawer-switch" />
      </span>
    </div>

    <div class="drawer-item">
      <span>显示 Logo</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.sidebarLogo" class="drawer-switch" />
      </span>
    </div>

    <div class="drawer-item">
      <span>动态标题</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.dynamicTitle" @change="dynamicTitleChange" class="drawer-switch" />
      </span>
    </div>

    <div class="drawer-item">
      <span>底部版权</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.footerVisible" class="drawer-switch" />
      </span>
    </div>

    <el-divider />
    <h3 class="drawer-title">动效配置</h3>

    <div class="drawer-item">
      <span>动效档位</span>
      <span class="comp-style">
        <el-select v-model="settingsStore.motionLevel" style="width: 120px">
          <el-option label="强" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="轻" value="low" />
        </el-select>
      </span>
    </div>

    <div class="drawer-item">
      <span>路由过渡动效</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.routeFx" class="drawer-switch" />
      </span>
    </div>

    <div class="drawer-item">
      <span>请求加载蒙层</span>
      <span class="comp-style">
        <el-switch v-model="settingsStore.requestFx" class="drawer-switch" />
      </span>
    </div>

    <el-divider />

    <el-button type="primary" plain icon="DocumentAdd" @click="saveSetting">保存配置</el-button>
    <el-button plain icon="Refresh" @click="resetSetting">重置配置</el-button>
  </el-drawer>
</template>

<script setup>
import { Check } from '@element-plus/icons-vue'
import { LayoutSettingKey } from '@/utils/auth'
import useAppStore from '@/store/modules/app'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'
import { handleThemeStyle } from '@/utils/theme'

const { proxy } = getCurrentInstance()
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const permissionStore = usePermissionStore()

const showSettings = ref(false)
const navType = ref(settingsStore.navType)
const theme = ref(settingsStore.theme)
const sideTheme = ref(settingsStore.sideTheme)

const predefineColors = ref(['#14E3FF', '#3A7BFF', '#F04AFF', '#20B2AA', '#67C23A', '#E6A23C', '#F56C6C', '#8F9BB3'])

function dynamicTitleChange() {
  settingsStore.setTitle(settingsStore.title)
}

function themeChange(val) {
  settingsStore.theme = val
  handleThemeStyle(val)
}

function handleTheme(val) {
  settingsStore.sideTheme = val
  sideTheme.value = val
}

function handleNavType(val) {
  settingsStore.navType = val
  navType.value = val
}

watch(
  () => navType.value,
  (val) => {
    if (val === 1) {
      appStore.sidebar.opened = true
      appStore.toggleSideBarHide(false)
    }
    if (val === 2) {
      appStore.sidebar.opened = true
    }
    if (val === 3) {
      appStore.sidebar.opened = false
      appStore.toggleSideBarHide(true)
    }
    if ([1, 3].includes(val)) {
      permissionStore.setSidebarRouters(permissionStore.defaultRoutes)
    }
  },
  { immediate: true }
)

function saveSetting() {
  proxy.$modal.loading('正在保存到本地，请稍候...')
  const layoutSetting = {
    navType: settingsStore.navType,
    tagsView: settingsStore.tagsView,
    tagsIcon: settingsStore.tagsIcon,
    fixedHeader: settingsStore.fixedHeader,
    sidebarLogo: settingsStore.sidebarLogo,
    dynamicTitle: settingsStore.dynamicTitle,
    footerVisible: settingsStore.footerVisible,
    sideTheme: settingsStore.sideTheme,
    theme: settingsStore.theme,
    motionLevel: settingsStore.motionLevel,
    routeFx: settingsStore.routeFx,
    requestFx: settingsStore.requestFx
  }
  localStorage.setItem(LayoutSettingKey, JSON.stringify(layoutSetting))
  setTimeout(() => proxy.$modal.closeLoading(), 320)
}

function resetSetting() {
  proxy.$modal.loading('正在清除设置缓存并刷新，请稍候...')
  localStorage.removeItem(LayoutSettingKey)
  setTimeout(() => {
    window.location.reload()
  }, 360)
}

function openSetting() {
  showSettings.value = true
}

defineExpose({
  openSetting
})
</script>

<style lang="scss" scoped>
.setting-drawer-title {
  margin-bottom: 12px;
  color: var(--el-text-color-primary, rgba(0, 0, 0, 0.85));
  line-height: 22px;
  font-weight: 700;

  .drawer-title {
    margin: 0;
    font-size: 14px;
  }

  .drawer-tip {
    color: var(--text-secondary);
    display: block;
    margin-top: 4px;
  }
}

.setting-drawer-block-checbox {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  margin-top: 10px;
  margin-bottom: 20px;

  .setting-drawer-block-checbox-item {
    position: relative;
    margin-right: 16px;
    border-radius: 4px;
    cursor: pointer;
    border: 1px solid var(--panel-border);
    overflow: hidden;

    img {
      width: 48px;
      height: 48px;
    }

    .setting-drawer-block-checbox-selectIcon {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      color: var(--accent-cyan);
      background: rgba(2, 8, 24, 0.25);
      font-size: 16px;
    }
  }
}

.drawer-item {
  color: var(--el-text-color-regular, rgba(0, 0, 0, 0.65));
  padding: 12px 0;
  font-size: 14px;

  .comp-style {
    float: right;
    margin: -3px 8px 0 0;
  }
}

.nav-wrap {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  margin-top: 10px;
  margin-bottom: 20px;

  .activeItem {
    border: 2px solid var(--el-color-primary) !important;
    box-shadow: 0 0 12px rgba(20, 227, 255, 0.35);
  }

  .item {
    position: relative;
    margin-right: 16px;
    cursor: pointer;
    width: 56px;
    height: 48px;
    border-radius: 4px;
    background: color-mix(in srgb, var(--panel-bg) 88%, transparent);
    border: 2px solid transparent;
  }

  .left {
    b:first-child {
      display: block;
      height: 30%;
      background: #fff;
    }

    b:last-child {
      width: 30%;
      background: #122544;
      position: absolute;
      height: 100%;
      top: 0;
      border-radius: 4px 0 0 4px;
    }
  }

  .mix {
    b:first-child {
      border-radius: 4px 4px 0 0;
      display: block;
      height: 30%;
      background: #122544;
    }

    b:last-child {
      width: 30%;
      background: #122544;
      position: absolute;
      height: 70%;
      border-radius: 0 0 0 4px;
    }
  }

  .top {
    b:first-child {
      display: block;
      height: 30%;
      background: #122544;
      border-radius: 4px 4px 0 0;
    }
  }
}
</style>
