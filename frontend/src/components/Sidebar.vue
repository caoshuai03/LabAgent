<template>
  <div
    :class="[
      'sidebar',
      {
        collapsed: chatStore.sidebarCollapsed && !isAnimatingCollapse,
        resizing:
          isResizing
          && !chatStore.sidebarCollapsed
          && !isCollapsingByDrag
          && !isExpandingByDrag,
        'collapsing-transition': isAnimatingCollapse,
      },
    ]"
    :style="{ width: chatStore.sidebarCollapsed ? '0px' : `${chatStore.sidebarWidth}px` }"
  >
    <div class="sidebar-header">
      <div class="sidebar-top">
        <div class="logo-area" v-if="showExpandedSidebar" @click="handleNewConversation">
          <img src="../assets/logo.png" alt="JavaLab Logo" class="logo-img" />
        </div>
        <button
          @click="chatStore.toggleSidebar"
          class="toggle-button"
          v-tooltip="chatStore.sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
        >
          <ChevronLeftIcon v-if="showExpandedSidebar" :size="16" />
          <ChevronRightIcon v-else :size="16" />
        </button>
      </div>
      <div class="nav-menu">
        <button
          @click="handleNewConversation"
          :class="['nav-item', { active: isNavActive('/') }]"
          v-tooltip="chatStore.sidebarCollapsed ? '新建对话' : ''"
        >
          <PlusIcon :size="18" />
          <span v-if="showExpandedSidebar">新聊天</span>
        </button>

        <button
          @click="handleKnowledgeManagement"
          :class="['nav-item', { active: isNavActive('/knowledge') }]"
          v-tooltip="chatStore.sidebarCollapsed ? '知识库' : ''"
        >
          <FolderIcon :size="18" />
          <span v-if="showExpandedSidebar">知识库</span>
        </button>

        <button
          @click="handleSkillsManagement"
          :class="['nav-item', { active: isNavActive('/skills') }]"
          v-tooltip="chatStore.sidebarCollapsed ? '技能' : ''"
        >
          <BookIcon :size="18" />
          <span v-if="showExpandedSidebar">技能</span>
        </button>

        <button
          @click="handleMemoryManagement"
          :class="['nav-item', { active: isNavActive('/memory') }]"
          v-tooltip="chatStore.sidebarCollapsed ? '规则与记忆' : ''"
        >
          <RulesMemoryIcon :size="18" />
          <span v-if="showExpandedSidebar">规则与记忆</span>
        </button>
      </div>
    </div>

    <div class="list-header" v-if="showExpandedSidebar">
      <span class="title">历史会话</span>
    </div>

    <ConversationList
      v-if="showExpandedSidebar"
      :is-selection-mode="isSelectionMode"
      :selected-ids="selectedIds"
      @update:selected-ids="(val) => (selectedIds = val)"
      @enterBatchMode="handleEnterBatchModeFromItem"
    />

    <div class="sidebar-bottom" v-if="isSelectionMode && showExpandedSidebar">
      <div class="batch-actions">
        <button class="batch-btn cancel" @click="cancelSelectionMode">取消</button>
        <button
          class="batch-btn delete"
          @click="handleBatchDelete"
          :disabled="selectedIds.length === 0"
        >
          删除 ({{ selectedIds.length }})
        </button>
      </div>
    </div>

    <div class="sidebar-bottom" v-else>
      <UserProfile />
    </div>

    <div
      v-if="showExpandedSidebar"
      class="sidebar-resizer"
      :class="{ resizing: isResizing }"
      @mousedown="startResize"
    ></div>
  </div>
  <button
    v-if="isMobile && !chatStore.sidebarCollapsed"
    type="button"
    class="sidebar-backdrop"
    aria-label="关闭侧边栏"
    @click="chatStore.sidebarCollapsed = true"
  ></button>
  <header v-if="isMobile && chatStore.sidebarCollapsed" class="mobile-page-bar">
    <button
      type="button"
      class="mobile-menu-button"
      aria-label="打开侧边栏"
      @click="chatStore.toggleSidebar"
    >
      <span aria-hidden="true">☰</span>
    </button>
    <strong>{{ mobilePageTitle }}</strong>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useConfirm } from '../composables/useConfirm'
import ConversationList from './ConversationList.vue'
import UserProfile from './UserProfile.vue'
import PlusIcon from './icons/PlusIcon.vue'
import FolderIcon from './icons/FolderIcon.vue'
import BookIcon from './icons/BookIcon.vue'
import RulesMemoryIcon from './icons/RulesMemoryIcon.vue'

import ChevronLeftIcon from './icons/ChevronLeftIcon.vue'
import ChevronRightIcon from './icons/ChevronRightIcon.vue'

const router = useRouter()
const route = useRoute()
const chatStore = useChatStore()
const { confirm } = useConfirm()

defineOptions({ name: 'AppSidebar' })

const isSelectionMode = ref(false)
const selectedIds = ref([])
const isResizing = ref(false)
const isCollapsingByDrag = ref(false)
const isExpandingByDrag = ref(false)
const isAnimatingCollapse = ref(false)
const isMobile = ref(false)
const SIDEBAR_TRANSITION_MS = 340
let collapseAnimationTimer = null
let expandByDragTimer = null
const showExpandedSidebar = computed(() => !chatStore.sidebarCollapsed || isAnimatingCollapse.value)
const mobilePageTitle = computed(() => {
  const titles = {
    '/': 'LabAgent',
    '/knowledge': '知识库',
    '/skills': '技能',
    '/memory': '规则与记忆',
  }
  return titles[route.path] || 'LabAgent'
})

const syncMobileState = () => {
  isMobile.value = window.innerWidth <= 768
  if (isMobile.value) {
    chatStore.sidebarCollapsed = true
  }
}

const closeMobileSidebar = () => {
  if (isMobile.value) {
    chatStore.sidebarCollapsed = true
  }
}

const cancelSelectionMode = () => {
  isSelectionMode.value = false
  selectedIds.value = []
}

// 从会话项菜单进入批量模式
const handleEnterBatchModeFromItem = () => {
  isSelectionMode.value = true
  // 不自动选择任何会话，让用户自己选择
}

const handleBatchDelete = async () => {
  if (selectedIds.value.length === 0) return

  const confirmed = await confirm({
    title: '批量删除对话',
    message: `确定要删除选中的 ${selectedIds.value.length} 个对话吗？`,
    description: '删除后，所选对话内容将无法恢复。',
    confirm_text: '确认删除',
    tone: 'danger',
  })
  if (!confirmed) return

  const success = await chatStore.deleteConversations(selectedIds.value)
  if (success) {
    isSelectionMode.value = false
    selectedIds.value = []
  }
}

/**
 * 创建新对话
 * 新对话的 sessionId 由后端在第一次发送消息时生成
 */
const handleNewConversation = () => {
  // 创建新对话（此时不会生成ID，等待后端返回）
  chatStore.createConversation()

  // 如果当前不在聊天页面，导航回聊天界面
  if (route.path !== '/') {
    router.push('/')
  }
  closeMobileSidebar()
}

const handleKnowledgeManagement = () => {
  router.push('/knowledge')
  closeMobileSidebar()
}

const handleSkillsManagement = () => {
  router.push('/skills')
  closeMobileSidebar()
}

const handleMemoryManagement = () => {
  router.push('/memory')
  closeMobileSidebar()
}

const stopResize = () => {
  isResizing.value = false
  isCollapsingByDrag.value = false
  isExpandingByDrag.value = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  window.removeEventListener('mousemove', handleResizeMove)
  window.removeEventListener('mouseup', stopResize)
}

const clearCollapseAnimationTimer = () => {
  if (!collapseAnimationTimer) return
  window.clearTimeout(collapseAnimationTimer)
  collapseAnimationTimer = null
}

const clearExpandByDragTimer = () => {
  if (!expandByDragTimer) return
  window.clearTimeout(expandByDragTimer)
  expandByDragTimer = null
}

const handleResizeMove = (event) => {
  const collapseThreshold = chatStore.sidebarWidth / 2

  if (event.clientX <= collapseThreshold) {
    isExpandingByDrag.value = false
    clearExpandByDragTimer()
    if (!chatStore.sidebarCollapsed && !isCollapsingByDrag.value) {
      isCollapsingByDrag.value = true
      window.requestAnimationFrame(() => {
        if (isCollapsingByDrag.value) {
          chatStore.sidebarCollapsed = true
        }
      })
    }
    return
  }

  isCollapsingByDrag.value = false
  if (chatStore.sidebarCollapsed && !isExpandingByDrag.value) {
    isExpandingByDrag.value = true
    clearExpandByDragTimer()
    expandByDragTimer = window.setTimeout(() => {
      isExpandingByDrag.value = false
      expandByDragTimer = null
    }, SIDEBAR_TRANSITION_MS)
  }
  chatStore.sidebarCollapsed = false
  chatStore.setSidebarWidth(event.clientX)
}

const startResize = () => {
  isResizing.value = true
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  window.addEventListener('mousemove', handleResizeMove)
  window.addEventListener('mouseup', stopResize)
}

// 判断当前路由是否与某个导航项匹配，便于给选中的入口加背景高亮
// “新聊天”只在新对话状态下高亮，避免和历史会话的选中状态互相覆盖
const isNavActive = (path) => {
  if (path === '/') {
    return route.path === '/' && chatStore.isNewConversation
  }

  return route.path === path
}

watch(
  () => chatStore.sidebarCollapsed,
  (collapsed) => {
    clearCollapseAnimationTimer()
    if (!collapsed) {
      isAnimatingCollapse.value = false
      return
    }

    isAnimatingCollapse.value = true
    collapseAnimationTimer = window.setTimeout(() => {
      isAnimatingCollapse.value = false
      collapseAnimationTimer = null
    }, SIDEBAR_TRANSITION_MS)
  },
)

onMounted(() => {
  syncMobileState()
  window.addEventListener('resize', syncMobileState)
})

onBeforeUnmount(() => {
  stopResize()
  clearCollapseAnimationTimer()
  clearExpandByDragTimer()
  window.removeEventListener('resize', syncMobileState)
})
</script>

<style lang="scss" scoped>
.sidebar {
  --sidebar-transition-duration: 0.34s;
  --sidebar-transition-easing: cubic-bezier(0.2, 0, 0, 1);
  height: var(--app-height, 100vh);
  background-color: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  transition:
    width var(--sidebar-transition-duration) var(--sidebar-transition-easing),
    background-color var(--sidebar-transition-duration) var(--sidebar-transition-easing);
  border-right: none;
  flex-shrink: 0;
  position: relative;
  min-width: 0;

  &.collapsed {
    overflow: visible;
    background-color: transparent;
    border-right: none;
  }

  &.collapsing-transition {
    overflow: hidden;
    background-color: var(--bg-secondary);
  }

  &.resizing {
    transition: none;
  }

  // 移动端响应式
  @media (max-width: 768px) {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 1000;
    transform: translateX(0);
    transition:
      transform var(--sidebar-transition-duration) var(--sidebar-transition-easing),
      background-color var(--sidebar-transition-duration) var(--sidebar-transition-easing),
      width var(--sidebar-transition-duration) var(--sidebar-transition-easing);
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.3);

    &:not(.collapsed) {
      width: min(86vw, 320px) !important;
    }

    &.collapsed {
      transform: translateX(-260px);
      overflow: hidden;
    }

    .sidebar-header .nav-menu .nav-item {
      min-height: 44px;
    }

    .sidebar-header .sidebar-top {
      padding-top: calc(16px + env(safe-area-inset-top));
    }

    .sidebar-bottom {
      padding-bottom: env(safe-area-inset-bottom);
    }
  }

  // 平板响应式
  @media (min-width: 769px) and (max-width: 1024px) {
    &.collapsed {
      overflow: hidden;
    }
  }
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  z-index: 999;
  padding: 0;
  border: 0;
  background: rgba(17, 24, 39, 0.32);
  cursor: default;
  -webkit-tap-highlight-color: transparent;
}

.mobile-page-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 900;
  display: flex;
  align-items: center;
  gap: 10px;
  height: calc(52px + env(safe-area-inset-top));
  padding: env(safe-area-inset-top) 52px 0 12px;
  border-bottom: 1px solid var(--border-color);
  background: var(--app-page-bg);
  background: color-mix(in srgb, var(--app-page-bg) 94%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);

  strong {
    min-width: 0;
    overflow: hidden;
    color: var(--text-primary);
    font-size: 15px;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.mobile-menu-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  padding: 0;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--text-primary);
  font-size: 20px;
  cursor: pointer;

  &:active {
    background: var(--bg-hover);
  }
}

.sidebar-resizer {
  position: absolute;
  top: 0;
  right: -1px;
  z-index: 20;
  width: 2px;
  height: 100%;
  cursor: col-resize;
  background: transparent;
  transition: background 0.2s ease;

  &:hover,
  &.resizing {
    background: var(--primary-color, #90138b);
  }

  @media (max-width: 768px) {
    display: none;
  }
}

.sidebar-header {
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;

  .sidebar-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 12px 12px 12px;

    .logo-area {
      flex: 1;
      cursor: pointer;
      display: flex;
      align-items: center;

      .logo-img {
        height: 32px;
        width: auto;
        object-fit: contain;
      }
    }

    .toggle-button {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      padding: 0;
      background-color: transparent;
      border: 1px solid transparent;
      border-radius: 6px;
      color: var(--text-primary);
      cursor: pointer;
      transition: all 0.2s ease;
      flex-shrink: 0;

      &:hover {
        background-color: var(--bg-hover);
      }

      &:focus {
        outline: none;
      }

      svg {
        flex-shrink: 0;
      }
    }
  }

  .nav-menu {
    display: flex;
    flex-direction: column;
    padding: 0 8px 8px 8px;
    gap: 6px;

    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      background-color: transparent;
      border: none;
      border-radius: 12px;
      color: var(--text-primary);
      cursor: pointer;
      font-size: 14px;
      text-align: left;
      transition: all 0.2s ease;
      min-height: 40px;

      &:hover {
        background-color: var(--nav-bg-hover);
      }

      &.active {
        background-color: var(--nav-bg-active);
        color: var(--primary-color);
      }

      &.active:hover {
        background-color: var(--nav-bg-active);
      }

      &:focus {
        outline: none;
      }

      &:focus-visible {
        outline: none;
        background-color: var(--nav-bg-hover);
      }

      /* 统一侧边栏图标的描边粗细与线帽样式，避免不同图标看起来不一致 */
      svg {
        flex-shrink: 0;
        width: 18px;
        height: 18px;
        stroke: currentColor;
        stroke-width: 1.85;
        stroke-linecap: round;
        stroke-linejoin: round;
      }

      span {
        flex: 1;
        white-space: nowrap;
      }
    }
  }
}

.sidebar.collapsed {
  .sidebar-header {
    position: fixed;
    left: 0;
    top: 0;
    z-index: 1001;

    .sidebar-top {
      padding: 12px;

      .logo-area {
        display: none;
      }

      .toggle-button {
        width: 32px;
        height: 32px;
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        transition: none;
      }
    }

    .nav-menu {
      display: none;
    }
  }

  @media (max-width: 768px) {
    .sidebar-header {
      display: none;
    }
  }
}

.sidebar-bottom {
  margin-top: auto;
  display: flex;
  flex-direction: column;

  .sidebar.collapsed & {
    display: none;
  }
}

.list-header {
  display: flex;
  align-items: center;
  padding: 12px 16px 8px;

  .title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
}

.batch-actions {
  display: flex;
  padding: 12px;
  gap: 12px;

  .batch-btn {
    flex: 1;
    padding: 8px;
    border-radius: 20px;
    font-size: 13px;
    cursor: pointer;
    border: none;
    transition: all 0.2s;

    &.cancel {
      background-color: var(--bg-primary);
      color: var(--text-primary);

      &:hover {
        background-color: var(--bg-hover);
      }
    }

    &.delete {
      background-color: rgba(220, 53, 69, 0.1);
      color: #dc3545;

      &:hover:not(:disabled) {
        background-color: rgba(220, 53, 69, 0.2);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
}
</style>
