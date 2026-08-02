<template>
  <div class="message-list-wrapper">
    <div
      class="message-list"
      :class="{ 'is-scrolling': isScrolling }"
      ref="messageListRef"
      @scroll="handleScroll"
    >
      <template v-for="message in chatStore.messages" :key="message.id">
        <MessageItem
          :message="message"
          @approval-decision="$emit('approval-decision', $event)"
        />
        <div
          v-if="
            chatStore.compactionStatus
              && chatStore.compactionAfterMessageId === message.id
          "
          class="compaction-divider"
          :class="`is-${chatStore.compactionStatus}`"
          role="status"
          aria-live="polite"
        >
          <span>
            {{
              chatStore.compactionStatus === 'compressing'
                ? '历史对话压缩中'
                : '历史对话已被压缩'
            }}
          </span>
        </div>
      </template>

      <div
        v-if="chatStore.compactionStatus && !chatStore.compactionAfterMessageId"
        class="compaction-divider"
        :class="`is-${chatStore.compactionStatus}`"
        role="status"
        aria-live="polite"
      >
        <span>
          {{
            chatStore.compactionStatus === 'compressing'
              ? '历史对话压缩中'
              : '历史对话已被压缩'
          }}
        </span>
      </div>

      <div v-if="chatStore.isStreaming" class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>

    <!-- 到底部按钮 -->
    <button
      v-if="showScrollToBottomButton"
      @click="handleScrollToBottom"
      class="scroll-to-bottom-button"
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <polyline points="19 12 12 19 5 12"></polyline>
      </svg>
    </button>
  </div>
</template>

<script setup>
import {
  ref,
  watch,
  nextTick,
  onMounted,
  onBeforeUnmount,
  onActivated,
  onDeactivated,
} from 'vue'
import { useChatStore } from '../stores/chat'
import MessageItem from './MessageItem.vue'

defineEmits(['approval-decision'])

const chatStore = useChatStore()
const messageListRef = ref(null)

// 用户是否主动向上滚动过（离开底部区域）
const userHasScrolledUp = ref(false)
const showScrollToBottomButton = ref(false)

// 正文滚动条默认隐藏，滚动时才显示，停止后延时淡出
const isScrolling = ref(false)
let scrollbarHideTimer = null
const flashScrollbar = () => {
  isScrolling.value = true
  if (scrollbarHideTimer) clearTimeout(scrollbarHideTimer)
  scrollbarHideTimer = setTimeout(() => {
    isScrolling.value = false
  }, 800)
}

const BOTTOM_THRESHOLD = 1
const conversationScrollPositions = new Map()
let contentMutationObserver = null
let containerResizeObserver = null
let restoringConversationKey = null
let lastScrollTop = 0
let isComponentActive = true

// 检查当前是否在底部区域
const checkIsAtBottom = () => {
  if (!messageListRef.value) return false

  const { scrollTop, scrollHeight, clientHeight } = messageListRef.value
  return scrollHeight - scrollTop - clientHeight <= BOTTOM_THRESHOLD
}

// 根据距离底部的位置同步自动跟随和置底按钮状态
const syncScrollState = () => {
  if (!messageListRef.value) return

  const isAtBottom = checkIsAtBottom()
  if (isAtBottom) {
    userHasScrolledUp.value = false
  }
  showScrollToBottomButton.value = !isAtBottom
  lastScrollTop = messageListRef.value.scrollTop
}

const saveConversationScrollPosition = (conversationKey) => {
  if (!conversationKey || !messageListRef.value) return

  const { clientHeight, scrollHeight } = messageListRef.value
  // keep-alive 停用后容器可能已脱离布局，不能用失效尺寸覆盖已保存位置
  if (clientHeight <= 0 || scrollHeight < clientHeight) return

  conversationScrollPositions.set(conversationKey, {
    scrollTop: messageListRef.value.scrollTop,
    isAtBottom: checkIsAtBottom(),
  })
}

const restoreConversationScrollPosition = (conversationKey, previousConversationKey) => {
  if (!messageListRef.value) return

  let savedPosition = conversationScrollPositions.get(conversationKey)

  // 草稿首次收到后端会话 ID 时仍是同一会话，沿用草稿的阅读位置
  if (
    !savedPosition &&
    chatStore.isDraftConversationKey(previousConversationKey) &&
    conversationScrollPositions.has(previousConversationKey)
  ) {
    savedPosition = conversationScrollPositions.get(previousConversationKey)
    conversationScrollPositions.set(conversationKey, savedPosition)
  }

  if (savedPosition?.isAtBottom) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  } else if (savedPosition) {
    const maxScrollTop = Math.max(
      messageListRef.value.scrollHeight - messageListRef.value.clientHeight,
      0,
    )
    messageListRef.value.scrollTop = Math.min(savedPosition.scrollTop, maxScrollTop)
  } else {
    // 首次打开会话仍默认展示最新消息
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }

  userHasScrolledUp.value = !checkIsAtBottom()
  syncScrollState()
}

/**
 * scroll 事件同步检查距底部的位置，不做防抖。
 */
const handleScroll = () => {
  if (!messageListRef.value) return

  flashScrollbar()
  if (messageListRef.value.scrollTop < lastScrollTop) {
    userHasScrolledUp.value = true
  }
  syncScrollState()
  saveConversationScrollPosition(chatStore.activeConversationKey)
}

// 滚动到底部
const scrollToBottom = (force = false) => {
  if (!messageListRef.value || restoringConversationKey || !isComponentActive) return

  // 只有在强制滚动或用户未主动上滑时才自动滚动
  if (force || !userHasScrolledUp.value) {
    nextTick(() => {
      if (messageListRef.value) {
        messageListRef.value.scrollTop = messageListRef.value.scrollHeight
        syncScrollState()
      }
    })
  }
}

// 点击"到底部"按钮
const handleScrollToBottom = () => {
  userHasScrolledUp.value = false // 清除上滑标记，恢复自动跟随
  scrollToBottom(true)
}

// 监听消息列表长度变化（新消息添加时）
watch(
  () => chatStore.messages.length,
  () => {
    scrollToBottom()
  },
)

watch(
  () => chatStore.compactionStatus,
  () => {
    scrollToBottom()
  },
)

// 监听最后一条消息的内容变化（流式输出文本时）
watch(
  () => {
    const messages = chatStore.messages
    if (messages.length === 0) return ''
    const lastMessage = messages[messages.length - 1]
    return lastMessage ? lastMessage.content : ''
  },
  () => {
    scrollToBottom()
  },
)

// 监听最后一条消息的思考内容变化，思考流式展开时保持置底
watch(
  () => {
    const messages = chatStore.messages
    if (messages.length === 0) return ''
    const lastMessage = messages[messages.length - 1]
    return lastMessage?.reasoning?.map((segment) => segment.content).join('') || ''
  },
  () => {
    scrollToBottom()
  },
)

// 监听最后一条消息中的工具事件变化，确保工具列表流式渲染时也能自动跟随到底部
watch(
  () => {
    const messages = chatStore.messages
    if (messages.length === 0) return 0
    const lastMessage = messages[messages.length - 1]
    return lastMessage?.toolEvents?.length || 0
  },
  () => {
    scrollToBottom()
  },
)

// 切换会话时保存离开位置，并恢复目标会话上次停留的阅读位置
watch(
  () => chatStore.activeConversationKey,
  (conversationKey, previousConversationKey) => {
    if (!isComponentActive) {
      restoringConversationKey = conversationKey
      return
    }

    saveConversationScrollPosition(previousConversationKey)
    restoringConversationKey = conversationKey
    userHasScrolledUp.value = false
    showScrollToBottomButton.value = false
    nextTick(() => {
      if (chatStore.activeConversationKey !== conversationKey) return

      restoreConversationScrollPosition(conversationKey, previousConversationKey)
      if (restoringConversationKey === conversationKey) {
        restoringConversationKey = null
      }
    })
  },
  { flush: 'sync' },
)

// 初始化：检查初始位置
onMounted(() => {
  nextTick(() => {
    syncScrollState()

    if (messageListRef.value && typeof MutationObserver !== 'undefined') {
      contentMutationObserver = new MutationObserver(() => {
        nextTick(syncScrollState)
      })
      contentMutationObserver.observe(messageListRef.value, {
        childList: true,
        characterData: true,
        subtree: true,
      })
    }

    if (messageListRef.value && typeof ResizeObserver !== 'undefined') {
      containerResizeObserver = new ResizeObserver(() => {
        syncScrollState()
      })
      containerResizeObserver.observe(messageListRef.value)
    }
  })
})

onDeactivated(() => {
  isComponentActive = false
  saveConversationScrollPosition(chatStore.activeConversationKey)
})

onActivated(() => {
  isComponentActive = true
  const conversationKey = chatStore.activeConversationKey
  restoringConversationKey = conversationKey
  nextTick(() => {
    window.requestAnimationFrame(() => {
      if (!isComponentActive || chatStore.activeConversationKey !== conversationKey) return

      restoreConversationScrollPosition(conversationKey)
      if (restoringConversationKey === conversationKey) {
        restoringConversationKey = null
      }
    })
  })
})

onBeforeUnmount(() => {
  saveConversationScrollPosition(chatStore.activeConversationKey)
  contentMutationObserver?.disconnect()
  containerResizeObserver?.disconnect()
  if (scrollbarHideTimer) clearTimeout(scrollbarHideTimer)
})
</script>

<style lang="scss" scoped>
.message-list-wrapper {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  width: 100%;
  overflow: hidden;
}

.message-list {
  flex: 1;
  min-width: 0;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 60px 0 32px 0;

  &::-webkit-scrollbar {
    width: 8px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: transparent;
    border-radius: 4px;
    transition: background 0.3s ease;
  }

  // 仅在滚动时显示滚动条，停止后淡出
  &.is-scrolling::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);

    &:hover {
      background: var(--scrollbar-thumb-hover);
    }
  }

  .typing-indicator {
    display: flex;
    gap: 4px;
    padding: 20px;
    justify-content: center;

    span {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: var(--text-secondary);
      animation: typing 1.4s infinite;

      &:nth-child(2) {
        animation-delay: 0.2s;
      }

      &:nth-child(3) {
        animation-delay: 0.4s;
      }
    }
  }
}

.compaction-divider {
  display: flex;
  align-items: center;
  gap: 20px;
  width: var(--chat-content-track-width, min(100%, 880px));
  margin: 16px auto;
  color: #6f6f73;
  font-size: 14px;
  line-height: 1.5;

  &::before,
  &::after {
    content: '';
    height: 1px;
    flex: 1;
    background: #e4e4e7;
  }

  span {
    flex-shrink: 0;
  }

  &.is-compressing {
    color: color-mix(in srgb, var(--primary-color, #90138b) 42%, white);

    span {
      animation: compactionStatusPulse 1.6s ease-in-out infinite;
    }
  }
}

@media (max-width: 768px) {
  .message-list {
    padding-top: calc(68px + env(safe-area-inset-top));
    padding-bottom: 20px;
    overscroll-behavior-y: contain;
  }

}

.scroll-to-bottom-button {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background-color: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: #333333;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 10;

  svg {
    transition: transform 0.2s ease;
  }

  &:hover {
    background-color: #ffffff;
    border-color: rgba(0, 0, 0, 0.12);
    transform: translateX(-50%) translateY(-2px);

    svg {
      transform: translateY(1px);
    }
  }

  &:active {
    transform: translateX(-50%) translateY(0);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

@media (max-width: 768px) {
  .scroll-to-bottom-button {
    width: 44px;
    height: 44px;
    bottom: 16px;
  }
}

@keyframes typing {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.7;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}

@keyframes compactionStatusPulse {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}
</style>
