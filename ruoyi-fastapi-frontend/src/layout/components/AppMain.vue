<template>
  <section class="app-main">
    <router-view v-slot="{ Component, route: currentRoute }">
      <transition
        :name="settingsStore.routeFx ? 'fade-transform' : 'fade'"
        mode="out-in"
        @enter="handleEnter"
        @leave="handleLeave"
      >
        <keep-alive :include="tagsViewStore.cachedViews">
          <div v-if="!currentRoute.meta.link" class="app-main-route">
            <component :is="Component" :key="currentRoute.path" />
          </div>
        </keep-alive>
      </transition>
    </router-view>
    <IframeToggle />
    <Copyright />
  </section>
</template>

<script setup>
import { gsap } from 'gsap'
import Copyright from './Copyright/index'
import IframeToggle from './IframeToggle/index'
import useTagsViewStore from '@/store/modules/tagsView'
import useSettingsStore from '@/store/modules/settings'

const route = useRoute()
const tagsViewStore = useTagsViewStore()
const settingsStore = useSettingsStore()

const prefersReducedMotion = typeof window !== 'undefined'
  ? window.matchMedia('(prefers-reduced-motion: reduce)')
  : { matches: false }

onMounted(() => {
  addIframe()
})

watchEffect(() => {
  addIframe()
})

function isMotionDisabled() {
  return !settingsStore.routeFx || settingsStore.motionLevel === 'low' || prefersReducedMotion.matches
}

function handleEnter(el, done) {
  if (isMotionDisabled()) {
    done()
    return
  }

  const duration = settingsStore.motionLevel === 'high' ? 0.54 : 0.34
  gsap.fromTo(
    el,
    { autoAlpha: 0, x: -20, y: 10, filter: 'blur(4px)' },
    {
      autoAlpha: 1,
      x: 0,
      y: 0,
      filter: 'blur(0px)',
      duration,
      ease: 'power3.out',
      onComplete: done
    }
  )
}

function handleLeave(el, done) {
  if (isMotionDisabled()) {
    done()
    return
  }

  const duration = settingsStore.motionLevel === 'high' ? 0.42 : 0.26
  gsap.to(el, {
    autoAlpha: 0,
    x: 20,
    y: -6,
    filter: 'blur(2px)',
    duration,
    ease: 'power2.inOut',
    onComplete: done
  })
}

function addIframe() {
  if (route.meta.link) {
    tagsViewStore.addIframeView(route)
  }
}
</script>

<style lang="scss" scoped>
.app-main {
  min-height: calc(100vh - 50px);
  width: 100%;
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(160deg, rgba(4, 10, 21, 0.03), rgba(4, 10, 21, 0)),
    transparent;
}

.app-main-route {
  min-height: inherit;
}

.fixed-header + .app-main {
  overflow-y: auto;
  scrollbar-gutter: auto;
  height: calc(100vh - 50px);
  min-height: 0;
}

.app-main:has(.copyright) {
  padding-bottom: 36px;
}

.fixed-header + .app-main {
  margin-top: 50px;
}

.hasTagsView {
  .app-main {
    min-height: calc(100vh - 84px);
  }

  .fixed-header + .app-main {
    margin-top: 84px;
    height: calc(100vh - 84px);
    min-height: 0;
  }
}

@media screen and (max-width: 991px) {
  .fixed-header + .app-main {
    padding-bottom: max(60px, calc(constant(safe-area-inset-bottom) + 40px));
    padding-bottom: max(60px, calc(env(safe-area-inset-bottom) + 40px));
    overscroll-behavior-y: none;
  }

  .hasTagsView .fixed-header + .app-main {
    padding-bottom: max(60px, calc(constant(safe-area-inset-bottom) + 40px));
    padding-bottom: max(60px, calc(env(safe-area-inset-bottom) + 40px));
    overscroll-behavior-y: none;
  }
}

@supports (-webkit-touch-callout: none) {
  @media screen and (max-width: 991px) {
    .fixed-header + .app-main {
      padding-bottom: max(17px, calc(constant(safe-area-inset-bottom) + 10px));
      padding-bottom: max(17px, calc(env(safe-area-inset-bottom) + 10px));
      height: calc(100svh - 50px);
      height: calc(100dvh - 50px);
    }

    .hasTagsView .fixed-header + .app-main {
      padding-bottom: max(17px, calc(constant(safe-area-inset-bottom) + 10px));
      padding-bottom: max(17px, calc(env(safe-area-inset-bottom) + 10px));
      height: calc(100svh - 84px);
      height: calc(100dvh - 84px);
    }
  }
}
</style>
