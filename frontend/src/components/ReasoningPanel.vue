<!--
 @author: caoshuai.cs
 @date: 2026-07-26
 @description: 主Agent思考过程的流式展示与折叠面板
-->
<template>
  <section v-if="segments.length" class="reasoning-panel">
    <article class="reasoning-segment">
      <button
        type="button"
        class="reasoning-header"
        :aria-expanded="!collapsed"
        @click="$emit('toggle')"
      >
        <span class="reasoning-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9.5 4.5a3.5 3.5 0 0 0-3.37 4.45A4.5 4.5 0 0 0 7 17.5h1.5"></path>
            <path d="M14.5 4.5a3.5 3.5 0 0 1 3.37 4.45A4.5 4.5 0 0 1 17 17.5h-1.5"></path>
            <path d="M9 12h6M8.5 17.5h7M10 21h4"></path>
          </svg>
        </span>
        <span class="reasoning-title">{{ isComplete ? '已思考完成' : '正在思考' }}</span>
        <svg
          class="reasoning-chevron"
          :class="{ expanded: !collapsed }"
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
      <div v-show="!collapsed" class="reasoning-content">
        <template v-for="(segment, index) in segments" :key="segment.reasoning_id">
          <hr v-if="index > 0" class="reasoning-divider" />
          <div class="reasoning-text">{{ segment.content }}</div>
        </template>
      </div>
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

const isComplete = computed(() => segments.value.every((segment) => segment.is_complete))
const collapsed = computed(() => segments.value.every((segment) => segment.collapsed))
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
}

.reasoning-text {
  white-space: pre-wrap;
}

.reasoning-divider {
  margin: 8px 0;
  border: 0;
  border-top: 1px solid #d9d9d9;
}

@media (hover: none) and (pointer: coarse) {
  .reasoning-header {
    min-height: 44px;
  }
}
</style>
