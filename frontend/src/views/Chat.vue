<template>
  <div class="chat-container">
    <Sidebar />
    <ChatMain />

    <!-- 正文与预览侧栏之间的可拖拽分隔条：拖动同时调节两栏宽度 -->
    <div
      v-if="chatStore.previewPanelOpen"
      class="preview-resizer"
      :class="{ dragging: isDragging }"
      @mousedown="startDrag"
    ></div>

    <WorkspacePreviewPanel
      class="preview-panel-shell"
      :class="{
        open: chatStore.previewPanelOpen,
        dragging: isDragging,
        'switching-collapse': chatStore.previewPanelSwitchingCollapse,
      }"
      :aria-hidden="!chatStore.previewPanelOpen"
      :style="{ width: chatStore.previewPanelOpen ? `${chatStore.previewPanelWidth}px` : '0px' }"
    />

    <!-- 侧栏收起后的展开按钮：始终可点，重新打开预览侧栏 -->
    <button
      v-if="!chatStore.previewPanelOpen"
      type="button"
      class="preview-expand-button"
      v-tooltip="'展开预览侧栏'"
      @click="chatStore.openPreviewPanel()"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <rect x="3" y="3" width="18" height="18" rx="2"></rect>
        <line x1="15" y1="3" x2="15" y2="21"></line>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { onMounted, onActivated, onBeforeUnmount, ref, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import Sidebar from '../components/Sidebar.vue'
import ChatMain from '../components/ChatMain.vue'
import WorkspacePreviewPanel from '../components/WorkspacePreviewPanel.vue'

// 声明组件名称，配合 App.vue 的 keep-alive 使用，
// 确保路由切换到 MCP/Skills/知识库 时 Chat 组件不被销毁
defineOptions({ name: 'Chat' })

const chatStore = useChatStore()

// 拖拽分隔条调节预览侧栏宽度（侧栏在右侧，向左拖变宽）
const isDragging = ref(false)
const MAIN_CONTENT_MIN_WIDTH = 480
const PREVIEW_RESIZER_WIDTH = 2
const PREVIEW_PANEL_MIN_WIDTH = 260

const getSidebarReservedWidth = () => {
  if (chatStore.sidebarCollapsed || window.innerWidth <= 768) {
    return 0
  }

  return chatStore.sidebarWidth
}

const getPreviewPanelMaxWidth = () => {
  const remainingWidth = window.innerWidth
    - getSidebarReservedWidth()
    - MAIN_CONTENT_MIN_WIDTH
    - PREVIEW_RESIZER_WIDTH
  return Math.max(PREVIEW_PANEL_MIN_WIDTH, remainingWidth)
}

const keepPreviewPanelWithinViewport = () => {
  if (!chatStore.previewPanelOpen) return

  chatStore.setPreviewPanelWidth(
    Math.min(chatStore.previewPanelWidth, getPreviewPanelMaxWidth()),
  )
}

const onDragMove = (event) => {
  // 侧栏宽度 = 视口右边界 - 鼠标位置
  chatStore.setPreviewPanelWidth(
    Math.min(window.innerWidth - event.clientX, getPreviewPanelMaxWidth()),
  )
}

const stopDrag = () => {
  isDragging.value = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', stopDrag)
}

const startDrag = () => {
  isDragging.value = true
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', stopDrag)
}

/**
 * 初始化聊天页面
 * 从数据库加载会话列表和历史消息
 */
onMounted(async () => {
  // 移动端默认折叠侧边栏
  if (window.innerWidth <= 768) {
    chatStore.sidebarCollapsed = true
  }

  // 从数据库加载会话（异步操作）
  await chatStore.initialize()
  keepPreviewPanelWithinViewport()
  window.addEventListener('resize', keepPreviewPanelWithinViewport)
})

/**
 * keep-alive 缓存下，切换用户后组件被复用而非重建，onMounted 不会再触发。
 * 通过 onActivated + needsReload 标记，在重新激活时按新用户重新加载会话列表。
 */
onActivated(async () => {
  if (chatStore.needsReload) {
    await chatStore.initialize()
  }
})

onBeforeUnmount(() => {
  stopDrag()
  window.removeEventListener('resize', keepPreviewPanelWithinViewport)
})

watch(
  () => [chatStore.previewPanelOpen, chatStore.sidebarCollapsed, chatStore.sidebarWidth],
  () => {
    window.requestAnimationFrame(keepPreviewPanelWithinViewport)
  },
)
</script>

<style lang="scss" scoped>
.chat-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: var(--app-page-bg);
  transition: background-color 0.3s ease;
}

.preview-resizer {
  flex: 0 0 auto;
  width: 2px;
  cursor: col-resize;
  background: transparent;
  transition: background 0.2s ease;

  &:hover,
  &.dragging {
    background: var(--primary-color, #90138b);
  }

  @media (max-width: 768px) {
    display: none;
  }
}

.preview-panel-shell {
  overflow: hidden;
  visibility: hidden;
  pointer-events: none;
  transition:
    width 0.3s ease,
    visibility 0s linear 0.3s;

  &.open {
    visibility: visible;
    pointer-events: auto;
    transition:
      width 0.3s ease,
      visibility 0s linear 0s;
  }

  &.dragging {
    transition: none;
  }

  &.switching-collapse {
    transition:
      width 0.16s ease,
      visibility 0s linear 0.16s;
  }
}

.preview-expand-button {
  position: fixed;
  top: 8px;
  right: 8px;
  z-index: 200;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  color: var(--text-secondary, #666);
  background: transparent;
  cursor: pointer;

  &:hover {
    color: var(--text-primary, #333);
    background: var(--bg-secondary, #f0f0f0);
  }

  svg {
    width: 18px;
    height: 18px;
  }
}
</style>
