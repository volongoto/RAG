<template>
  <div class="hamburger-wrap" @click="toggleClick">
    <svg
      :class="{ 'is-active': isActive }"
      class="hamburger"
      viewBox="0 0 1024 1024"
      xmlns="http://www.w3.org/2000/svg"
      width="64"
      height="64"
      fill="currentColor"
    >
      <path d="M408 442h480c4.4 0 8-3.6 8-8v-56c0-4.4-3.6-8-8-8H408c-4.4 0-8 3.6-8 8v56c0 4.4 3.6 8 8 8zm-8 204c0 4.4 3.6 8 8 8h480c4.4 0 8-3.6 8-8v-56c0-4.4-3.6-8-8-8H408c-4.4 0-8 3.6-8 8v56zm504-486H120c-4.4 0-8 3.6-8 8v56c0 4.4 3.6 8 8 8h784c4.4 0 8-3.6 8-8v-56c0-4.4-3.6-8-8-8zm0 632H120c-4.4 0-8 3.6-8 8v56c0 4.4 3.6 8 8 8h784c4.4 0 8-3.6 8-8v-56c0-4.4-3.6-8-8-8zM142.4 642.1L298.7 519a8.84 8.84 0 0 0 0-13.9L142.4 381.9c-5.8-4.6-14.4-.5-14.4 6.9v246.3a8.9 8.9 0 0 0 14.4 7z" />
    </svg>
  </div>
</template>

<script setup>
defineProps({
  isActive: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggleClick'])
const toggleClick = () => {
  emit('toggleClick')
}
</script>

<style scoped>
.hamburger-wrap {
  padding: 0 15px;
}

.hamburger {
  display: inline-block;
  vertical-align: middle;
  width: 20px;
  height: 20px;
  color: var(--navbar-text);
  transition: transform 0.38s cubic-bezier(0.22, 1, 0.36, 1), filter 0.28s ease, color 0.28s ease;
}

.hamburger.is-active {
  transform: rotate(180deg) scale(1.04);
  color: var(--accent-cyan);
  filter: drop-shadow(0 0 8px rgba(20, 227, 255, 0.7));
}

.hamburger-wrap:hover .hamburger {
  color: var(--accent-cyan);
  filter: drop-shadow(0 0 6px rgba(20, 227, 255, 0.5));
}
</style>
