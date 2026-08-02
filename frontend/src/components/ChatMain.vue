<template>
  <div
    class="chat-main"
    :class="{ 'is-empty': chatStore.messages.length === 0 && !isHistorySwitching }"
    @click="handleMainClick"
  >
    <MessageList
      v-show="chatStore.messages.length > 0 || isHistorySwitching"
      @approval-decision="handleApprovalDecision"
    />

    <div v-if="chatStore.messages.length === 0 && !isHistorySwitching" class="welcome-container">
      <div class="welcome-content">
        <template v-if="chatStore.historyLoadError">
          <h2>
            <span>会话加载失败</span>
          </h2>
          <p>{{ chatStore.historyLoadError }}</p>
        </template>
        <template v-else-if="chatStore.currentConversationId && !chatStore.isLoading">
          <h2>
            <span>暂无会话内容</span>
          </h2>
          <p>这条会话没有可展示的历史消息</p>
        </template>
        <template v-else>
          <h2>
            <span>{{ displayedWelcomeTitle }}</span>
            <span class="typewriter-cursor" aria-hidden="true"></span>
          </h2>
          <p>可以向我提问实验设计、数据分析、论文理解、代码实现等问题</p>
        </template>
      </div>
    </div>

    <ChatInput ref="chatInputRef" />

    <div class="footer-container">
      <p>以上内容均由 AI 生成, 仅供参考和借鉴。版权所有 © shuaicao01@163.com</p>
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
const welcomeTitleIndex = ref(0)
const displayedWelcomeTitle = ref('')
const welcomeTitles = ['今天想研究什么？', '我可以帮你完成实验相关任务', '让我们开始一个新问题']
let welcomeTitleTimer = 0
let welcomeTitleCharIndex = 0
let isDeletingWelcomeTitle = false

const TYPE_DELAY = 72
const DELETE_DELAY = 34
const HOLD_DELAY = 1400
const SWITCH_DELAY = 260

const isHistorySwitching = computed(() => {
  return Boolean(chatStore.currentConversationId && chatStore.isLoading && chatStore.messages.length === 0)
})

const scheduleWelcomeTitleTyping = (delay) => {
  welcomeTitleTimer = window.setTimeout(updateWelcomeTitleTyping, delay)
}

const updateWelcomeTitleTyping = () => {
  const title = welcomeTitles[welcomeTitleIndex.value]

  if (!isDeletingWelcomeTitle && welcomeTitleCharIndex < title.length) {
    welcomeTitleCharIndex += 1
    displayedWelcomeTitle.value = title.slice(0, welcomeTitleCharIndex)
    scheduleWelcomeTitleTyping(TYPE_DELAY)
    return
  }

  if (!isDeletingWelcomeTitle) {
    isDeletingWelcomeTitle = true
    scheduleWelcomeTitleTyping(HOLD_DELAY)
    return
  }

  if (welcomeTitleCharIndex > 0) {
    welcomeTitleCharIndex -= 1
    displayedWelcomeTitle.value = title.slice(0, welcomeTitleCharIndex)
    scheduleWelcomeTitleTyping(DELETE_DELAY)
    return
  }

  isDeletingWelcomeTitle = false
  welcomeTitleIndex.value = (welcomeTitleIndex.value + 1) % welcomeTitles.length
  scheduleWelcomeTitleTyping(SWITCH_DELAY)
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
  updateWelcomeTitleTyping()
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  window.clearTimeout(welcomeTitleTimer)
})
</script>

<style lang="scss" scoped>
.chat-main {
  flex: 1 0 min(480px, 100vw);
  display: flex;
  flex-direction: column;
  height: var(--app-height, 100vh);
  min-width: min(480px, 100vw);
  position: relative;
  overflow: hidden;
  --chat-content-max-width: 720px;
  --chat-content-gutter: clamp(24px, 6%, 72px);
  --chat-content-track-width: min(
    var(--chat-content-max-width),
    calc(100% - (var(--chat-content-gutter) * 2))
  );
  background-color: var(--app-page-bg);

  // 侧边栏折叠时给悬浮按钮留出空间
  .sidebar.collapsed + &,
  .sidebar.collapsed ~ & {
    .top-bar {
      padding-left: 60px;
    }
  }

  &.is-empty {
    justify-content: flex-start;
    padding-top: clamp(148px, 27vh, 252px);

    .welcome-container {
      display: flex;
      justify-content: center;
      margin-bottom: 34px;

      .welcome-content {
        text-align: center;
        color: var(--text-secondary);
        max-width: 640px;
        padding: 0 24px;

        h2 {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 35px;
          color: var(--text-primary);
          font-size: 28px;
          line-height: 1.24;
          margin-bottom: 12px;
          font-weight: 650;
          letter-spacing: -0.02em;
        }

        .typewriter-cursor {
          width: 2px;
          height: 0.92em;
          margin-left: 3px;
          border-radius: 999px;
          background: var(--primary-color);
          animation: typewriterCursorBlink 1.05s steps(2, start) infinite;
        }

        p {
          color: #737889;
          font-size: 15px;
          line-height: 1.5;
        }
      }
    }

    :deep(.chat-input-container) {
      border-top: none;
      background-color: transparent;
    }

    .footer-container {
      color: rgba(110, 110, 128, 0.52);
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
    --chat-content-gutter: 16px;

    &.is-empty {
      padding-top: 120px;

      .welcome-container {
        margin-bottom: 28px;

        .welcome-content {
          h2 {
            font-size: 24px;
          }

          p {
            font-size: 14px;
          }
        }
      }
    }

    .footer-container {
      display: none;
    }
  }
}

@keyframes typewriterCursorBlink {
  0%,
  45% {
    opacity: 1;
  }

  46%,
  100% {
    opacity: 0;
  }
}

</style>
