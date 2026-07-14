<template>
  <div class="chat-input-container">
    <div class="input-wrapper" :class="{ expanded: isExpanded }">
      <textarea
        ref="inputRef"
        v-model="inputText"
        :disabled="chatStore.isStreaming || chatStore.awaitingApproval"
        :placeholder="
          chatStore.awaitingApproval
            ? '请先处理工具确认'
            : chatStore.isStreaming
              ? 'AI 正在回复...'
              : '输入消息...'
        "
        :class="['chat-input', { 'has-scrollbar': showScrollbar }]"
        rows="1"
        @keydown="handleKeyDown"
        @input="handleInput"
      ></textarea>

      <div class="input-footer">
        <button
          type="button"
          class="action-button attach-button disabled-btn"
          v-tooltip="'附件上传功能开发中'"
          aria-label="附件上传功能开发中"
        >
          <svg
            stroke="currentColor"
            fill="none"
            stroke-width="2.2"
            viewBox="0 0 24 24"
            stroke-linecap="round"
            stroke-linejoin="round"
            height="1em"
            width="1em"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M12 5v14"></path>
            <path d="M5 12h14"></path>
          </svg>
        </button>

        <div class="input-actions">
          <button
            v-if="chatStore.isStreaming"
            class="action-button stop-button"
            v-tooltip="'停止生成'"
            @click="handleStop()"
          >
            <svg
              stroke="currentColor"
              fill="none"
              stroke-width="2"
              viewBox="0 0 24 24"
              stroke-linecap="round"
              stroke-linejoin="round"
              height="1em"
              width="1em"
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            </svg>
          </button>
          <button
            v-else
            class="action-button send-button"
            :class="{ 'disabled-btn': !canSend }"
            v-tooltip="'以 Agent 模式发送(Enter)'"
            @click="handleSend"
          >
            <svg
              stroke="currentColor"
              fill="none"
              stroke-width="2.5"
              viewBox="0 0 24 24"
              stroke-linecap="round"
              stroke-linejoin="round"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path d="M12 20V4M5 11l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { cancelReactAgent, resumeReactAgent, sendReactAgentMessage } from '../api/chat'

const chatStore = useChatStore()

const inputText = ref('')
const inputRef = ref(null)
const showScrollbar = ref(false)
const isExpanded = ref(false)

const MIN_HEIGHT = 24
const MAX_HEIGHT = 320
const EXPAND_TRIGGER_HEIGHT = 84
const COLLAPSE_TRIGGER_HEIGHT = 56

// 将同一帧内的多次高度刷新合并，避免输入过程中出现抖动
let inputVisualSyncFrameId = 0

const canSend = computed(() => {
  return (
    inputText.value.trim().length > 0 &&
    !chatStore.isStreaming &&
    !chatStore.awaitingApproval
  )
})

// 每个会话独立维护自己的流任务，避免切换历史会话时互相覆盖
const streamTasks = new Map()

const getOrCreateActiveConversationKey = () => {
  return chatStore.activeConversationKey || chatStore.createConversation()
}

const getStreamTask = (conversationKey = chatStore.activeConversationKey) => {
  if (!conversationKey) return null
  return streamTasks.get(conversationKey) || null
}

const moveStreamTask = (sourceConversationKey, targetConversationKey) => {
  if (!sourceConversationKey || !targetConversationKey || sourceConversationKey === targetConversationKey) {
    return
  }

  const streamTask = streamTasks.get(sourceConversationKey)
  if (!streamTask) return

  streamTasks.delete(sourceConversationKey)
  streamTask.conversationKey = targetConversationKey
  streamTasks.set(targetConversationKey, streamTask)
}

const bindSessionToStreamTask = (newSessionId, streamTask) => {
  if (!newSessionId || !streamTask || streamTask.sessionIdReceived) {
    return
  }

  const sourceConversationKey = streamTask.conversationKey
  streamTask.sessionIdReceived = true

  if (chatStore.isDraftConversationKey(sourceConversationKey)) {
    chatStore.setCurrentSessionId(newSessionId, sourceConversationKey)
    chatStore.addNewConversationToList(newSessionId, streamTask.currentUserMessage)
    moveStreamTask(sourceConversationKey, newSessionId)
    return
  }

  if (sourceConversationKey !== newSessionId) {
    chatStore.setCurrentSessionId(newSessionId, sourceConversationKey)
    moveStreamTask(sourceConversationKey, newSessionId)
  }
}

const finalizeStreamTask = async (conversationKey, { abort = false, refreshConversations = true } = {}) => {
  if (!conversationKey) return

  const streamTask = streamTasks.get(conversationKey)

  if (abort && streamTask?.abortController) {
    streamTask.abortController.abort()
  }

  chatStore.markLastAssistantMessageComplete(conversationKey)
  chatStore.clearPendingApproval(conversationKey)
  chatStore.setConversationStreaming(conversationKey, false)
  chatStore.setConversationLoading(conversationKey, false)
  streamTasks.delete(conversationKey)

  if (refreshConversations) {
    await chatStore.loadConversationsFromDB()
  }
}

const createStreamCallbacks = (streamTask) => ({
  onMessage: (data) => {
    const lastMessage = chatStore.getLastMessage(streamTask.conversationKey)
    if (!lastMessage) return

    if (typeof data === 'object' && data.event_type) {
      if (data.trace_id) {
        streamTask.traceId = data.trace_id
      }
      handleStreamEvent(data, streamTask, lastMessage)
      return
    }

    if (typeof data !== 'string') return

    if (data.startsWith('[ERROR]')) {
      lastMessage.content = '错误: ' + data.substring(7)
      chatStore.updateLastMessage(lastMessage.content, streamTask.conversationKey)
      void finalizeStreamTask(streamTask.conversationKey, { abort: true })
      return
    }

    if (!streamTask.sessionIdReceived && data.startsWith('[SESSION_ID:')) {
      const match = data.match(/\[SESSION_ID:(.+?)\]/)
      if (match) bindSessionToStreamTask(match[1], streamTask)
      return
    }

    lastMessage.content += data
    chatStore.updateLastMessage(lastMessage.content, streamTask.conversationKey)
  },
  onError: (error) => {
    console.error('请求错误:', error)
    const lastMessage = chatStore.getLastMessage(streamTask.conversationKey)
    if (lastMessage && !lastMessage.content.trim()) {
      lastMessage.content = '连接错误，请重试'
      chatStore.updateLastMessage(lastMessage.content, streamTask.conversationKey)
    }
    void finalizeStreamTask(streamTask.conversationKey)
  },
  onComplete: () => {
    if (streamTask.paused) {
      streamTask.abortController = null
      chatStore.setConversationStreaming(streamTask.conversationKey, false)
      chatStore.setConversationLoading(streamTask.conversationKey, false)
      return
    }
    void finalizeStreamTask(streamTask.conversationKey, { refreshConversations: true })
  },
})

// 长文本输入时切换到更高的编辑态，并通过滞后阈值避免临界高度反复抖动
const updateExpandedState = (contentHeight) => {
  if (isExpanded.value) {
    isExpanded.value = contentHeight > COLLAPSE_TRIGGER_HEIGHT
    return
  }

  isExpanded.value = contentHeight > EXPAND_TRIGGER_HEIGHT
}

// 统一重置输入框的视觉状态，避免发送后仍保持长文本编辑态
const resetInputVisualState = () => {
  if (!inputRef.value) return

  if (inputVisualSyncFrameId) {
    cancelAnimationFrame(inputVisualSyncFrameId)
    inputVisualSyncFrameId = 0
  }

  inputRef.value.style.height = `${MIN_HEIGHT}px`
  inputRef.value.scrollTop = 0
  showScrollbar.value = false
  isExpanded.value = false
}

// 统一使用动画帧同步高度，避免输入事件和侦听器重复更新造成动画不连贯
const scheduleInputVisualSync = () => {
  if (inputVisualSyncFrameId) {
    cancelAnimationFrame(inputVisualSyncFrameId)
  }

  inputVisualSyncFrameId = requestAnimationFrame(() => {
    inputVisualSyncFrameId = 0
    syncInputVisualState()
  })
}

// 在 DOM 完成更新后同步输入框高度与容器状态，避免删减内容后外层仍停留在高态
const syncInputVisualState = () => {
  if (!inputRef.value) return

  if (!inputText.value) {
    resetInputVisualState()
    return
  }

  // 先记录当前像素高度，再过渡到目标高度，确保大段粘贴时也能看到展开动画
  const currentHeight = Math.max(
    MIN_HEIGHT,
    parseFloat(window.getComputedStyle(inputRef.value).height) || MIN_HEIGHT,
  )

  inputRef.value.style.height = 'auto'
  const scrollHeight = inputRef.value.scrollHeight
  const newHeight = Math.max(MIN_HEIGHT, Math.min(scrollHeight, MAX_HEIGHT))
  showScrollbar.value = scrollHeight > MAX_HEIGHT
  updateExpandedState(newHeight)

  if (Math.abs(newHeight - currentHeight) < 1) {
    inputRef.value.style.height = `${newHeight}px`
    return
  }

  inputRef.value.style.height = `${currentHeight}px`
  void inputRef.value.offsetHeight
  inputRef.value.style.height = `${newHeight}px`
}

const handleInput = () => {
  scheduleInputVisualSync()
}

const handleKeyDown = (event) => {
  // 输入法（IME）组字过程中的回车用于确认候选词，不应触发发送。
  // isComposing 为标准属性，keyCode === 229 作为部分浏览器/输入法的兜底判断
  if (event.isComposing || event.keyCode === 229) {
    return
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    if (canSend.value) {
      handleSend()
    }
  }
}

const handleSend = async () => {
  if (!canSend.value) return

  const message = inputText.value.trim()
  if (!message) return

  const conversationKey = getOrCreateActiveConversationKey()
  const streamTask = {
    conversationKey,
    currentUserMessage: message,
    sessionIdReceived: false,
    abortController: null,
    traceId: null,
    paused: false,
  }

  chatStore.addMessage('user', message, conversationKey)

  inputText.value = ''
  resetInputVisualState()

  chatStore.addMessage('assistant', '', conversationKey)
  chatStore.setConversationStreaming(conversationKey, true)
  chatStore.setConversationLoading(conversationKey, true)

  const sessionId = chatStore.isDraftConversationKey(conversationKey) ? '' : conversationKey
  const model = chatStore.selectedModel

  streamTask.abortController = sendReactAgentMessage(
    { message, sessionId, model },
    createStreamCallbacks(streamTask),
  )

  streamTasks.set(conversationKey, streamTask)
}

const handleStreamEvent = (event, streamTask, lastMessage) => {
  const payload = event.payload || {}

  if (event.event_type === 'session') {
    const newSessionId = payload.session_id || event.session_id
    bindSessionToStreamTask(newSessionId, streamTask)
    return
  }

  if (event.event_type === 'token') {
    const content = payload.content || ''
    lastMessage.content += content
    chatStore.updateLastMessage(lastMessage.content, streamTask.conversationKey)
    return
  }

  if (event.event_type === 'sources') {
    chatStore.setLastMessageSources(payload.sources || [], streamTask.conversationKey)
    return
  }

  if (
    event.event_type === 'tool_call' ||
    event.event_type === 'tool_result' ||
    event.event_type === 'status' ||
    event.event_type === 'skill_loaded'
  ) {
    chatStore.addToolEventToLastMessage({
      eventType: event.event_type,
      payload,
      ts: event.ts,
    }, streamTask.conversationKey)
    return
  }

  if (event.event_type === 'tool_approval_required') {
    streamTask.paused = true
    ;(payload.tool_calls || []).forEach((toolCall) => {
      chatStore.addToolEventToLastMessage(
        {
          eventType: 'status',
          payload: {
            stage: 'pending_approval',
            tool_call_id: toolCall.tool_call_id,
            tool_name: toolCall.tool_name,
          },
          ts: event.ts,
        },
        streamTask.conversationKey,
      )
    })
    chatStore.setPendingApproval(payload, streamTask.conversationKey)
    return
  }

  if (event.event_type === 'paused') {
    streamTask.paused = true
    return
  }

  if (event.event_type === 'error') {
    const message = payload.message || '请求失败'
    if (!lastMessage.content) {
      lastMessage.content = `错误: ${message}`
      chatStore.updateLastMessage(lastMessage.content, streamTask.conversationKey)
    }
    return
  }

  if (event.event_type === 'final') {
    streamTask.paused = false
    chatStore.clearPendingApproval(streamTask.conversationKey)
    void finalizeStreamTask(streamTask.conversationKey, { refreshConversations: true })
  }
}

const handleApprovalDecision = (approved) => {
  const conversationKey = chatStore.activeConversationKey
  const streamTask = getStreamTask(conversationKey)
  const approval = chatStore.pendingApproval
  if (!streamTask || !approval?.interrupt_id || !conversationKey) return

  streamTask.paused = false
  chatStore.clearPendingApproval(conversationKey)
  chatStore.setConversationStreaming(conversationKey, true)
  chatStore.setConversationLoading(conversationKey, true)
  streamTask.abortController = resumeReactAgent(
    {
      sessionId: conversationKey,
      interruptId: approval.interrupt_id,
      approved,
    },
    createStreamCallbacks(streamTask),
  )
}

defineExpose({ handleApprovalDecision })

const handleStop = async (conversationKey = chatStore.activeConversationKey) => {
  const streamTask = getStreamTask(conversationKey)
  if (!streamTask && !chatStore.isStreaming) {
    return
  }

  const cancelRequest = streamTask?.traceId && !chatStore.isDraftConversationKey(conversationKey)
    ? cancelReactAgent({ sessionId: conversationKey, traceId: streamTask.traceId }).catch((error) => {
        console.error('服务端停止生成失败:', error)
      })
    : null

  await finalizeStreamTask(conversationKey, { abort: true })
  await cancelRequest
}

watch(
  () => chatStore.shouldFocusInput,
  (shouldFocus) => {
    if (shouldFocus && inputRef.value) {
      nextTick(() => {
        inputRef.value.focus()
        chatStore.shouldFocusInput = false
      })
    }
  },
)

watch(inputText, () => {
  // 无论是新增还是删减内容，都在下一轮渲染后重新同步一次视觉高度
  nextTick(() => {
    scheduleInputVisualSync()
  })
})

onMounted(() => {
  resetInputVisualState()
})

onUnmounted(() => {
  if (inputVisualSyncFrameId) {
    cancelAnimationFrame(inputVisualSyncFrameId)
    inputVisualSyncFrameId = 0
  }

  // 组件卸载时统一清理仍在进行中的流任务，避免留下悬挂状态
  streamTasks.forEach((streamTask, conversationKey) => {
    streamTask.abortController?.abort()
    chatStore.setConversationStreaming(conversationKey, false)
    chatStore.setConversationLoading(conversationKey, false)
  })
  streamTasks.clear()
})
</script>

<style lang="scss" scoped>
.chat-input-container {
  padding: 0 24px 0 24px;
  background-color: var(--bg-primary);
  transition:
    background-color 0.3s ease,
    border-color 0.3s ease;

  .input-wrapper {
    max-width: 952px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: stretch;
    position: relative;
    overflow: hidden;
    background: linear-gradient(
      180deg,
      rgba(255, 255, 255, 0.98) 0%,
      rgba(250, 250, 252, 0.95) 100%
    );
    border: 1px solid rgba(229, 231, 235, 1);
    border-radius: 32px;
    min-height: 96px;
    padding: 16px 18px 12px 18px;
    box-shadow:
      0 8px 22px rgba(17, 24, 39, 0.05),
      0 1px 0 rgba(255, 255, 255, 0.88) inset;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    /* 放慢容器展开与收起的动画，减少突兀感 */
    transition:
      border-color 0.44s ease,
      box-shadow 0.44s ease,
      transform 0.44s ease,
      min-height 0.52s cubic-bezier(0.22, 1, 0.36, 1),
      border-radius 0.52s cubic-bezier(0.22, 1, 0.36, 1),
      padding 0.52s cubic-bezier(0.22, 1, 0.36, 1),
      gap 0.52s cubic-bezier(0.22, 1, 0.36, 1);

    &.expanded {
      min-height: 144px;
      border-radius: 28px;
    }
  }

  @media (max-width: 768px) {
    padding: 0 16px 0 16px;

    .input-wrapper {
      gap: 8px;
      min-height: 88px;
      padding: 14px 14px 10px 14px;
      border-radius: 28px;

      &.expanded {
        min-height: 132px;
        border-radius: 24px;
      }
    }
  }
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 0;

  .action-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    transition: all 0.2s ease;
    color: white;

    &.attach-button {
      width: 24px;
      height: 24px;
      background-color: transparent;
      border: none;
      color: #999;
      cursor: not-allowed;
      flex-shrink: 0;

      &.disabled-btn {
        opacity: 0.8;
      }

      &:hover:not(.disabled-btn) {
        color: #666;
      }

      svg {
        width: 20px;
        height: 20px;
        stroke-width: 2;
      }
    }
  }
}

.chat-input {
  flex: none;
  padding: 0;
  background-color: transparent;
  border: none;
  color: var(--input-text);
  font-size: 16px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  min-height: 24px;
  max-height: 320px;
  overflow-y: hidden;
  outline: none;
  margin-bottom: 2px;
  /* 放慢输入区高度变化，让长文本展开更接近大厂产品的手感 */
  transition: height 0.52s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: height;

  &.has-scrollbar {
    overflow-y: auto;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &::placeholder {
    color: var(--text-secondary);
    opacity: 0.6;
  }

  @media (max-width: 768px) {
    font-size: 15px;
  }

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 3px;

    &:hover {
      background: rgba(0, 0, 0, 0.3);
    }
  }
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;

  .action-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    transition: all 0.2s ease;
    color: white;

    &.send-button {
      width: 32px;
      height: 32px;
      background-color: #90138b;

      svg {
        width: 1.2em;
        height: 1.2em;
      }

      &:hover:not(.disabled-btn) {
        background-color: #9b2a96;
      }

      &.disabled-btn {
        background-color: #e5e5ea;
        color: #8e8e93;
        cursor: not-allowed;
      }
    }

    &.stop-button {
      width: 32px;
      height: 32px;
      background-color: transparent;
      color: var(--text-primary);
      border: 1px solid var(--border-color);

      svg {
        width: 1.2em;
        height: 1.2em;
      }

      &:hover {
        background-color: var(--bg-hover);
      }
    }
  }
}

.chat-tooltip {
  position: fixed;
  transform: translateX(-50%) translateY(-100%);
  background: rgba(17, 24, 39, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: #fff;
  padding: 8px 14px;
  border-radius: 12px; /* 更加圆润 */
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  pointer-events: none;
  z-index: 3000;
  animation: chatTooltipFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.15),
    0 1px 2px rgba(255, 255, 255, 0.1) inset;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

@keyframes chatTooltipFadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-100%) translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(-100%) translateY(0);
  }
}
</style>
