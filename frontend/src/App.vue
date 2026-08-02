<template>
  <!-- 使用 keep-alive 缓存 Chat 组件，
       路由切换到 MCP/Skills/知识库 时不销毁 Chat，
       避免 SSE 流式响应被中断 -->
  <router-view v-slot="{ Component }">
    <keep-alive include="Chat">
      <component :is="Component" />
    </keep-alive>
  </router-view>
  <ConfirmDialog />
  <ToastContainer />
</template>

<script setup>
// 导入 highlight.js 的 CSS
// 使用 github 主题（浅色）
import 'highlight.js/styles/github.css'
import { onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import ConfirmDialog from './components/ConfirmDialog.vue'
import ToastContainer from './components/ToastContainer.vue'
import { useKnowledgeUploadStore } from './stores/knowledgeUpload'

const route = useRoute()
const knowledgeUploadStore = useKnowledgeUploadStore()

watch(
  () => route.fullPath,
  () => {
    if (localStorage.getItem('token')) {
      knowledgeUploadStore.startPolling(true)
    } else {
      knowledgeUploadStore.stopPolling()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  knowledgeUploadStore.stopPolling()
})
</script>

<style>
/* 全局悬停提示 (v-tooltip) */
.global-tooltip {
  position: fixed;
  transform: translateX(-50%) translateY(-100%);
  background: rgba(17, 24, 39, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #fff;
  padding: 8px 14px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  pointer-events: none;
  z-index: 9999;
  animation: globalTooltipFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.15),
    0 1px 2px rgba(255, 255, 255, 0.1) inset;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.global-tooltip.below {
  transform: translateX(-50%);
  animation-name: globalTooltipFadeInBelow;
}

@keyframes globalTooltipFadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-100%) translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(-100%) translateY(0);
  }
}

@keyframes globalTooltipFadeInBelow {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>

<style lang="scss">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body {
  height: 100%;
  width: 100%;
  overflow: hidden;
  overscroll-behavior: none;
  font-family:
    'Inter',
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    'Helvetica Neue',
    Arial,
    'PingFang SC',
    'Microsoft YaHei',
    'Hiragino Sans GB',
    'WenQuanYi Micro Hei',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  transition:
    background-color 0.3s ease,
    color 0.3s ease;
}

#app {
  height: 100%;
  width: 100%;
}

@supports (height: 100dvh) {
  html,
  body,
  #app {
    height: 100dvh;
  }
}

// 浅色主题变量 - ChatGPT风格
:root {
  --app-height: 100vh;
  --bg-primary: #ffffff;
  --bg-secondary: #f7f7f8;
  --bg-tertiary: #f9f9f9;
  --app-page-bg: #fafafc;
  /* 历史会话与通用卡片的灰色悬浮/选中背景 */
  --bg-hover: #e5e5e5;
  --bg-active: #ebebeb;
  /* 导航栏单独保留紫色悬浮/选中背景，避免影响历史会话 */
  --nav-bg-hover: rgba(144, 19, 139, 0.05);
  --nav-bg-active: rgba(144, 19, 139, 0.09);
  --border-color: #e5e5e5;
  --border-color-hover: #d1d1d1;
  --text-primary: #353740;
  --text-secondary: #6e6e80;
  --text-tertiary: #8e8ea0;
  --accent-color: #90138b;
  --primary-color: #90138b;
  --user-message-bg: rgba(144, 19, 139, 0.06);
  --user-message-text: #353740;
  --assistant-message-bg: #ffffff;
  --assistant-message-text: #353740;
  --input-bg: #ffffff;
  --input-text: #353740;
  --input-border: #d1d1d1;
  --scrollbar-thumb: #d1d1d1;
  --scrollbar-thumb-hover: #b0b0b0;
}

@supports (height: 100dvh) {
  :root {
    --app-height: 100dvh;
  }
}

@media (hover: none) and (pointer: coarse) {
  button,
  [role='button'],
  input[type='checkbox'],
  input[type='radio'] {
    touch-action: manipulation;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

// highlight.js 样式
:root {
  .hljs {
    display: block;
    overflow-x: auto;
    padding: 0;
    background: transparent;
    color: inherit;
  }
}
</style>
