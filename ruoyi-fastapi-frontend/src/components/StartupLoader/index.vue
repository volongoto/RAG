<template>
  <transition name="startup-loader-fade">
    <div v-if="visible" class="startup-loader">
      <div class="startup-grid"></div>
      <div class="startup-content">
        <div class="startup-ring"></div>
        <div class="startup-title">{{ title }}</div>
        <div class="startup-subtitle">Booting cyber interface...</div>
      </div>
      <div class="startup-scanline"></div>
    </div>
  </transition>
</template>

<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

const title = import.meta.env.VITE_APP_TITLE || 'Cyber Console'
</script>

<style scoped lang="scss">
.startup-loader {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background:
    radial-gradient(circle at 28% 20%, rgba(20, 227, 255, 0.16), transparent 48%),
    radial-gradient(circle at 76% 78%, rgba(240, 74, 255, 0.14), transparent 44%),
    #020612;
  display: grid;
  place-items: center;
  overflow: hidden;
}

.startup-grid {
  position: absolute;
  inset: -20%;
  background-image:
    linear-gradient(rgba(20, 227, 255, 0.13) 1px, transparent 1px),
    linear-gradient(90deg, rgba(20, 227, 255, 0.13) 1px, transparent 1px);
  background-size: 42px 42px;
  transform: perspective(720px) rotateX(67deg) translateY(12%);
  transform-origin: center;
  opacity: 0.5;
  animation: gridFloat 4.8s linear infinite;
}

.startup-content {
  position: relative;
  text-align: center;
  color: #d7e7ff;
  z-index: 1;
}

.startup-ring {
  width: 110px;
  height: 110px;
  margin: 0 auto 18px;
  border-radius: 50%;
  border: 2px solid rgba(20, 227, 255, 0.26);
  box-shadow: 0 0 25px rgba(20, 227, 255, 0.42), inset 0 0 20px rgba(58, 123, 255, 0.3);
  position: relative;
  animation: ringPulse 1.4s ease-in-out infinite;

  &::before {
    content: "";
    position: absolute;
    inset: 12px;
    border-radius: 50%;
    border: 2px dashed rgba(240, 74, 255, 0.5);
    animation: ringSpin 2.2s linear infinite;
  }
}

.startup-title {
  font-size: 28px;
  letter-spacing: 2.4px;
  font-weight: 700;
  text-transform: uppercase;
  text-shadow: 0 0 14px rgba(20, 227, 255, 0.6);
}

.startup-subtitle {
  margin-top: 10px;
  font-size: 13px;
  letter-spacing: 1.4px;
  color: rgba(192, 213, 245, 0.84);
}

.startup-scanline {
  position: absolute;
  width: 100%;
  height: 132px;
  top: -132px;
  background: linear-gradient(180deg, transparent 0%, rgba(20, 227, 255, 0.22) 42%, transparent 100%);
  animation: scanline 2.4s ease-in-out infinite;
}

.startup-loader-fade-enter-active,
.startup-loader-fade-leave-active {
  transition: opacity 0.36s ease;
}

.startup-loader-fade-enter-from,
.startup-loader-fade-leave-to {
  opacity: 0;
}

@keyframes ringSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes ringPulse {
  0%, 100% { transform: scale(1); filter: brightness(0.95); }
  50% { transform: scale(1.06); filter: brightness(1.14); }
}

@keyframes scanline {
  0% { top: -132px; }
  100% { top: calc(100% + 32px); }
}

@keyframes gridFloat {
  0% { transform: perspective(720px) rotateX(67deg) translateY(12%) translateX(0); }
  100% { transform: perspective(720px) rotateX(67deg) translateY(12%) translateX(-42px); }
}

@media (prefers-reduced-motion: reduce) {
  .startup-grid,
  .startup-ring,
  .startup-ring::before,
  .startup-scanline {
    animation: none !important;
  }
}
</style>
