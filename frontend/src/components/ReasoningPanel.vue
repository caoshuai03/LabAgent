<!--
 @author: caoshuai.cs
 @date: 2026-07-26
 @description: 主Agent思考过程的流式展示与折叠面板
-->
<template>
  <section v-if="segments.length" class="reasoning-panel">
    <article v-for="segment in segments" :key="segment.reasoning_id" class="reasoning-segment">
      <button
        type="button"
        class="reasoning-header"
        :aria-expanded="!segment.collapsed"
        @click="$emit('toggle', segment.reasoning_id)"
      >
        <span class="reasoning-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9.5 4.5a3.5 3.5 0 0 0-3.37 4.45A4.5 4.5 0 0 0 7 17.5h1.5"></path>
            <path d="M14.5 4.5a3.5 3.5 0 0 1 3.37 4.45A4.5 4.5 0 0 1 17 17.5h-1.5"></path>
            <path d="M9 12h6M8.5 17.5h7M10 21h4"></path>
          </svg>
        </span>
        <span class="reasoning-title">{{ segment.is_complete ? '已思考完成' : '正在思考' }}</span>
        <span v-if="segments.length > 1" class="reasoning-round">第 {{ segment.round_number }} 轮</span>
        <span v-if="!segment.is_complete" class="reasoning-pulse" aria-hidden="true"></span>
        <svg
          class="reasoning-chevron"
          :class="{ expanded: !segment.collapsed }"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="m9 18 6-6-6-6"></path>
        </svg>
      </button>
      <div v-show="!segment.collapsed" class="reasoning-content">{{ segment.content }}</div>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue'

defineEmits(['toggle'])

const props = defineProps({
  reasoning: {
    type: Array,
    default: () => [],
  },
})

const segments = computed(() => {
  return props.reasoning.filter((segment) => typeof segment?.content === 'string' && segment.content)
})
</script>

<style lang="scss" scoped>
.reasoning-panel {
  box-sizing: border-box;
  width: 100%;
  margin: 0 0 8px;
  padding: 0 16px;
  color: var(--text-tertiary, #747682);

  @media (max-width: 768px) {
    padding: 0 12px;
  }
}

.reasoning-segment + .reasoning-segment {
  margin-top: 4px;
}

.reasoning-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 26px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.reasoning-icon {
  display: inline-flex;
  width: 18px;
  height: 18px;
  margin-right: 7px;

  svg {
    width: 17px;
    height: 17px;
  }
}

.reasoning-title {
  color: var(--text-tertiary, #747682);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
}

.reasoning-round {
  margin-left: 7px;
  color: var(--text-tertiary, #989aa3);
  font-size: 12px;
  line-height: 1.35;
}

.reasoning-pulse {
  width: 5px;
  height: 5px;
  margin-left: 7px;
  border-radius: 50%;
  background: #90138b;
  animation: reasoning-pulse 1.2s ease-in-out infinite;
}

.reasoning-chevron {
  width: 15px;
  height: 15px;
  margin-left: 6px;
  transition: transform 0.18s ease;

  &.expanded {
    transform: rotate(90deg);
  }
}

.reasoning-content {
  width: 100%;
  margin: 3px 0 7px;
  padding: 7px 0;
  color: var(--text-secondary, #626262);
  font-size: 13px;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

@keyframes reasoning-pulse {
  50% {
    opacity: 0.25;
  }
}

@media (prefers-reduced-motion: reduce) {
  .reasoning-pulse {
    animation: none;
  }
}

@media (hover: none) and (pointer: coarse) {
  .reasoning-header {
    min-height: 44px;
  }
}
</style>
