<template>
  <div
    class="chat-main"
    :class="{ 'is-empty': chatStore.messages.length === 0 }"
    @click="handleMainClick"
  >
    <!-- 移动端顶部菜单入口 -->
    <div v-if="showMobileMenuButton" class="top-bar">
      <button
        @click.stop="toggleSidebar"
        class="mobile-menu-button"
        v-tooltip="'打开菜单'"
      >
        ☰
      </button>
    </div>

    <MessageList
      v-show="chatStore.messages.length > 0"
      @approval-decision="handleApprovalDecision"
    />

    <div v-if="chatStore.messages.length === 0" class="welcome-container">
      <div class="welcome-content">
        <h2>你的实验助手</h2>
        <p>我可以为您解答实验相关的问题，请把您的任务交给我吧~</p>
      </div>
    </div>

    <ChatInput ref="chatInputRef" />

    <div class="footer-container">
      <p>以上内容均由AI生成, 仅供参考和借鉴。版权所有 © shuaicao01@163.com</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '../stores/chat'
import MessageList from './MessageList.vue'
import ChatInput from './ChatInput.vue'

const chatStore = useChatStore()
const chatInputRef = ref(null)
const isMobile = ref(false)

const showMobileMenuButton = computed(() => {
  return isMobile.value && chatStore.sidebarCollapsed
})

const toggleSidebar = () => {
  chatStore.toggleSidebar()
}

const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
  if (isMobile.value && !chatStore.sidebarCollapsed) {
    chatStore.sidebarCollapsed = true
  }
}

const handleMainClick = () => {
  if (isMobile.value && !chatStore.sidebarCollapsed) {
    chatStore.sidebarCollapsed = true
  }
}

const handleApprovalDecision = (approved) => {
  chatInputRef.value?.handleApprovalDecision(approved)
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style lang="scss" scoped>
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-width: 0;
  position: relative;
  overflow: hidden;

  // 侧边栏折叠时给悬浮按钮留出空间
  .sidebar.collapsed + &,
  .sidebar.collapsed ~ & {
    .top-bar {
      padding-left: 60px;
    }
  }

  &.is-empty {
    justify-content: center;

    .welcome-container {
      display: flex;
      justify-content: center;
      margin-bottom: 40px;

      .welcome-content {
        text-align: center;
        color: var(--text-secondary);

        h2 {
          color: var(--text-primary);
          font-size: 24px;
          margin-bottom: 16px;
          font-weight: 600;
        }

        p {
          font-size: 16px;
          line-height: 1.5;
        }
      }
    }

    :deep(.chat-input-container) {
      border-top: none;
      background-color: transparent;
    }
  }

  .footer-container {
    text-align: center;
    color: var(--text-tertiary, #999);
    font-size: 12px;
    padding: 8px 0 12px 0;
    width: 100%;
    flex-shrink: 0; // 防止被压缩

    p {
      margin: 0;
      opacity: 0.8;
    }
  }

  @media (max-width: 768px) {
    width: 100%;
    position: relative;
  }
}

.top-bar {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  background-color: transparent;
  flex-shrink: 0;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 100;
  pointer-events: none;

  .mobile-menu-button {
    pointer-events: auto;
    width: 32px;
    height: 32px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 18px;
    cursor: pointer;
    display: none;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    flex-shrink: 0;
    margin-right: 8px;

    &:hover {
      background-color: var(--bg-hover);
    }

    @media (max-width: 768px) {
      display: flex;
    }
  }

  @media (max-width: 768px) {
    position: relative;
    top: 0;
    left: 0;
    padding: 12px 16px;
    pointer-events: auto;
  }
}
</style>
