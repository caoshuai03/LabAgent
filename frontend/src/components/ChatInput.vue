<template>
  <div class="chat-input-container">
    <div class="input-wrapper" :class="{ expanded: isExpanded }">
      <SlashCommandMenu
        ref="slashMenuRef"
        :open="showSlashMenu"
        :query="slashQuery || ''"
        :skills="skillSummaries"
        :selected-skill-names="selectedSkillNames"
        :can-compress="canCompress"
        :is-compressing="isCompressing"
        :loading-skills="isLoadingSkills"
        @select="handleSlashCommandSelect"
        @close="closeSlashMenu"
      />

      <div v-if="pendingImages.length" class="pending-images">
        <div
          v-for="(image, index) in pendingImages"
          :key="image.preview_url"
          class="pending-image"
        >
          <img :src="image.preview_url" :alt="image.file.name" />
          <button
            type="button"
            class="remove-image-button"
            :aria-label="`移除图片 ${image.file.name}`"
            @click="removePendingImage(index)"
          >
            ×
          </button>
        </div>
      </div>

      <div class="input-editor-line">
        <div v-if="selectedSkills.length" ref="selectedSkillsRef" class="selected-skills">
          <span v-for="skill in selectedSkills" :key="skill.name" class="selected-skill">
            <ToolActivityIcon :tool-name="`skill:${skill.name}`" />
            <span class="selected-skill-name">{{ skill.name }}</span>
          </span>
        </div>

        <textarea
          ref="inputRef"
          v-model="inputText"
          :disabled="chatStore.isStreaming || chatStore.awaitingApproval"
          :placeholder="
            chatStore.awaitingApproval
              ? '请先处理工具确认'
              : chatStore.isStreaming
                ? 'AI 正在回复...'
                : selectedSkills.length
                  ? '输入任务...'
                  : '询问实验、论文、代码或数据分析问题...'
          "
          :class="['chat-input', { 'has-scrollbar': showScrollbar }]"
          :style="{ '--selected-skills-indent': `${selectedSkillsIndent}px` }"
          rows="1"
          @keydown="handleKeyDown"
          @input="handleInput"
          @paste="handlePaste"
        ></textarea>
      </div>

      <div class="input-footer">
        <div class="input-left-actions">
          <button
            type="button"
            class="action-button attach-button"
            :class="{ 'disabled-btn': !canSelectImages }"
            :disabled="!canSelectImages"
            v-tooltip="'上传图片'"
            aria-label="上传图片"
            @click="imageInputRef?.click()"
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
          <input
            ref="imageInputRef"
            class="image-file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            @change="handleImageSelection"
          />
        </div>

        <div class="input-actions">
          <div class="input-model-selector" v-click-outside="closeModelDropdown">
            <button
              type="button"
              class="model-selector-button"
              :class="{ disabled: chatStore.isStreaming || chatStore.awaitingApproval }"
              :disabled="chatStore.isStreaming || chatStore.awaitingApproval"
              @click="toggleModelDropdown"
            >
              <span>{{ currentModelLabel }}</span>
              <ChevronDownIcon
                :size="14"
                class="model-selector-icon"
                :class="{ 'is-open': showModelDropdown }"
              />
            </button>

            <transition name="model-dropdown-fade">
              <div v-show="showModelDropdown" class="model-dropdown-menu">
                <button
                  v-for="model in availableModels"
                  :key="model.value"
                  type="button"
                  class="model-option"
                  :class="{ active: chatStore.selectedModel === model.value }"
                  @click="selectModel(model.value)"
                >
                  <span class="model-option-content">
                    <ModelIcon :name="model.icon" />
                    <span class="model-option-label">{{ model.label }}</span>
                  </span>
                  <svg
                    v-if="chatStore.selectedModel === model.value"
                    class="model-option-check"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.4"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </button>
              </div>
            </transition>
          </div>

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
import {
  cancelReactAgent,
  compressConversation,
  getSessionTitle,
  resumeReactAgent,
  sendReactAgentMessage,
  uploadChatImage,
} from '../api/chat'
import { getSkills } from '../api/skills'
import { AVAILABLE_MODELS } from '../constants/models'
import ChevronDownIcon from './icons/ChevronDownIcon.vue'
import ModelIcon from './icons/ModelIcon.vue'
import SlashCommandMenu from './SlashCommandMenu.vue'
import ToolActivityIcon from './icons/ToolActivityIcon.vue'
import { useToast } from '../composables/useToast'

const chatStore = useChatStore()
const toast = useToast()

const inputText = ref('')
const inputRef = ref(null)
const selectedSkillsRef = ref(null)
const imageInputRef = ref(null)
const slashMenuRef = ref(null)
const pendingImages = ref([])
const skillSummaries = ref([])
const selectedSkills = ref([])
const showScrollbar = ref(false)
const isExpanded = ref(false)
const showModelDropdown = ref(false)
const slashMenuDismissed = ref(false)
const isCompressing = ref(false)
const isLoadingSkills = ref(false)
const skillsLoaded = ref(false)
const isUploadingImages = ref(false)
const selectedSkillsIndent = ref(0)

const MIN_HEIGHT = 24
const MAX_HEIGHT = 320
const EXPAND_TRIGGER_HEIGHT = 84
const COLLAPSE_TRIGGER_HEIGHT = 56
const MAX_IMAGE_COUNT = 10
const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
const MAX_SELECTED_SKILLS = 3
const SUPPORTED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
const TOOL_FAILURE_STAGES = new Set([
  'tool_failed',
  'tool_timeout',
  'tool_rejected',
  'tool_cancelled',
])
const TITLE_POLL_INTERVAL_MS = 1000
const TITLE_POLL_MAX_ATTEMPTS = 65

const availableModels = AVAILABLE_MODELS

const currentModel = computed(() => {
  return (
    availableModels.find((item) => item.value === chatStore.selectedModel) ||
    availableModels[0]
  )
})

const currentModelLabel = computed(() => {
  return currentModel.value.label
})

const slashCommandMatch = computed(() => {
  const match = inputText.value.match(/(?:^|\s)\/([^\s/]*)$/)
  if (!match) return null
  const leadingWhitespaceLength = match[0].startsWith('/') ? 0 : 1
  return {
    query: match[1],
    start: inputText.value.length - match[0].length + leadingWhitespaceLength,
  }
})

const slashQuery = computed(() => slashCommandMatch.value?.query ?? null)

const showSlashMenu = computed(() => {
  return (
    slashQuery.value !== null &&
    !slashMenuDismissed.value &&
    !chatStore.isStreaming &&
    !chatStore.awaitingApproval
  )
})

const selectedSkillNames = computed(() => selectedSkills.value.map((skill) => skill.name))

// 将同一帧内的多次高度刷新合并，避免输入过程中出现抖动
let inputVisualSyncFrameId = 0

const updateSelectedSkillsIndent = () => {
  selectedSkillsIndent.value = selectedSkillsRef.value
    ? Math.ceil(selectedSkillsRef.value.getBoundingClientRect().width) + 6
    : 0
  scheduleInputVisualSync()
}

const canSend = computed(() => {
  return (
    (inputText.value.trim().length > 0 || pendingImages.value.length > 0) &&
    !chatStore.isStreaming &&
    !chatStore.awaitingApproval &&
    !showSlashMenu.value &&
    !isUploadingImages.value
  )
})

const canSelectImages = computed(() => {
  return (
    !chatStore.isStreaming &&
    !chatStore.awaitingApproval &&
    !isUploadingImages.value &&
    pendingImages.value.length < MAX_IMAGE_COUNT
  )
})

const addPendingImages = (files) => {
  const fileList = Array.from(files)
  const availableCount = MAX_IMAGE_COUNT - pendingImages.value.length
  const candidates = fileList.slice(0, availableCount)
  if (fileList.length > availableCount) {
    toast.info(`单次最多上传 ${MAX_IMAGE_COUNT} 张图片`)
  }
  candidates.forEach((file) => {
    if (!SUPPORTED_IMAGE_TYPES.has(file.type)) {
      toast.error(`不支持图片类型：${file.name || file.type}`)
      return
    }
    if (file.size <= 0 || file.size > MAX_IMAGE_SIZE_BYTES) {
      toast.error(`图片 ${file.name || ''} 需小于 10MB`)
      return
    }
    pendingImages.value.push({
      file,
      preview_url: URL.createObjectURL(file),
    })
  })
}

const handleImageSelection = (event) => {
  addPendingImages(event.target.files || [])
  event.target.value = ''
}

const handlePaste = (event) => {
  if (!canSelectImages.value) return
  const imageFiles = Array.from(event.clipboardData?.items || [])
    .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
    .map((item) => item.getAsFile())
    .filter(Boolean)
  if (!imageFiles.length) return
  event.preventDefault()
  addPendingImages(imageFiles)
}

const removePendingImage = (index) => {
  const [removed] = pendingImages.value.splice(index, 1)
  if (removed?.preview_url) URL.revokeObjectURL(removed.preview_url)
}

const canCompress = computed(() => {
  return Boolean(
    chatStore.currentConversationId
      && !chatStore.isStreaming
      && !chatStore.awaitingApproval
      && !isCompressing.value,
  )
})

const handleCompress = async () => {
  if (!canCompress.value) return
  isCompressing.value = true
  try {
    const response = await compressConversation(chatStore.currentConversationId)
    const result = response.data.data
    if (!result?.compressed) {
      toast.info('当前上下文无需压缩')
      return
    }
    toast.success(
      `上下文已压缩：${result.before_tokens} → ${result.after_tokens} tokens`,
      5000,
    )
  } catch (error) {
    toast.error(error.response?.data?.message || '上下文压缩失败')
  } finally {
    isCompressing.value = false
  }
}

const loadSkills = async () => {
  if (skillsLoaded.value || isLoadingSkills.value) return
  isLoadingSkills.value = true
  try {
    const response = await getSkills()
    skillSummaries.value = response.data.data || []
    skillsLoaded.value = true
  } catch (error) {
    toast.error(error.response?.data?.message || '加载技能失败')
  } finally {
    isLoadingSkills.value = false
  }
}

const closeSlashMenu = () => {
  slashMenuDismissed.value = true
}

const removeSlashCommand = () => {
  if (!slashCommandMatch.value) return
  inputText.value = inputText.value.slice(0, slashCommandMatch.value.start).trimEnd()
}

const handleSlashCommandSelect = async (item) => {
  if (item.type === 'compress') {
    removeSlashCommand()
    slashMenuDismissed.value = true
    scheduleInputVisualSync()
    await handleCompress()
    inputRef.value?.focus()
    return
  }

  if (item.type !== 'skill' || !item.skill) return
  if (selectedSkills.value.length >= MAX_SELECTED_SKILLS) {
    toast.info(`单次最多选择 ${MAX_SELECTED_SKILLS} 个技能`)
    return
  }
  if (!selectedSkillNames.value.includes(item.skill.name)) {
    selectedSkills.value.push(item.skill)
  }
  removeSlashCommand()
  slashMenuDismissed.value = true
  scheduleInputVisualSync()
  inputRef.value?.focus()
}

const toggleModelDropdown = () => {
  if (chatStore.isStreaming || chatStore.awaitingApproval) return
  closeSlashMenu()
  showModelDropdown.value = !showModelDropdown.value
}

const closeModelDropdown = () => {
  showModelDropdown.value = false
}

const selectModel = (model) => {
  chatStore.setSelectedModel(model)
  closeModelDropdown()
}

// 每个会话独立维护自己的流任务，避免切换历史会话时互相覆盖
const streamTasks = new Map()
const titlePollControllers = new Map()

const waitForTitlePoll = (signal) => {
  return new Promise((resolve) => {
    const timeoutId = window.setTimeout(resolve, TITLE_POLL_INTERVAL_MS)
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timeoutId)
        resolve()
      },
      { once: true },
    )
  })
}

const pollConversationTitle = async (sessionId, fallbackTitle) => {
  if (!sessionId) return

  titlePollControllers.get(sessionId)?.abort()
  const controller = new AbortController()
  titlePollControllers.set(sessionId, controller)

  try {
    for (let attempt = 0; attempt < TITLE_POLL_MAX_ATTEMPTS; attempt += 1) {
      await waitForTitlePoll(controller.signal)
      if (controller.signal.aborted) return

      try {
        const response = await getSessionTitle(sessionId, controller.signal)
        const titleResult = response.data.data
        if (titleResult?.title) {
          chatStore.renameConversation(sessionId, titleResult.title)
          if (titleResult.title !== fallbackTitle) {
            return
          }
        }
      } catch {
        if (controller.signal.aborted) return
      }
    }
  } finally {
    if (titlePollControllers.get(sessionId) === controller) {
      titlePollControllers.delete(sessionId)
    }
  }
}

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
  chatStore.completeLastMessageReasoning(null, conversationKey)
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
  slashMenuDismissed.value = false
  closeModelDropdown()
  scheduleInputVisualSync()
}

const handleKeyDown = (event) => {
  // 输入法（IME）组字过程中的回车用于确认候选词，不应触发发送。
  // isComposing 为标准属性，keyCode === 229 作为部分浏览器/输入法的兜底判断
  if (event.isComposing || event.keyCode === 229) {
    return
  }
  if (event.key === 'Backspace' && !inputText.value && selectedSkills.value.length) {
    selectedSkills.value.pop()
    return
  }
  if (showSlashMenu.value && slashMenuRef.value?.handleKeyDown(event)) {
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

  closeModelDropdown()
  closeSlashMenu()

  const message = inputText.value.trim()
  if (!message && !pendingImages.value.length) return

  isUploadingImages.value = true
  let uploadedImages
  try {
    uploadedImages = await Promise.all(
      pendingImages.value.map(async ({ file, preview_url }) => {
        const response = await uploadChatImage(file)
        if (response.data?.code !== 0 || !response.data?.data) {
          throw new Error(response.data?.message || '图片上传失败')
        }
        return { ...response.data.data, preview_url }
      }),
    )
  } catch (error) {
    toast.error(error.response?.data?.message || error.message || '图片上传失败')
    return
  } finally {
    isUploadingImages.value = false
  }

  const conversationKey = getOrCreateActiveConversationKey()
  const titleMessage = message || '[图片]'
  const skillNames = [...selectedSkillNames.value]
  const streamTask = {
    conversationKey,
    currentUserMessage: titleMessage,
    sessionIdReceived: false,
    shouldPollTitle: chatStore.isDraftConversationKey(conversationKey),
    fallbackTitle: titleMessage.slice(0, 30),
    abortController: null,
    traceId: null,
    paused: false,
  }

  chatStore.addMessage('user', message, conversationKey, uploadedImages, skillNames)

  inputText.value = ''
  pendingImages.value = []
  selectedSkills.value = []
  resetInputVisualState()

  chatStore.addMessage('assistant', '', conversationKey)
  chatStore.setConversationStreaming(conversationKey, true)
  chatStore.setConversationLoading(conversationKey, true)

  const sessionId = chatStore.isDraftConversationKey(conversationKey) ? '' : conversationKey
  const model = chatStore.selectedModel

  streamTask.abortController = sendReactAgentMessage(
    {
      message,
      sessionId,
      model,
      skillNames,
      images: uploadedImages.map((image) => ({
        image_id: image.image_id,
        file_name: image.file_name,
        content_type: image.content_type,
        size: image.size,
      })),
    },
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

  if (event.event_type === 'reasoning_token') {
    chatStore.appendReasoningToLastMessage(payload, streamTask.conversationKey)
    return
  }

  if (event.event_type === 'reasoning_done') {
    chatStore.completeLastMessageReasoning(payload.reasoning_id || null, streamTask.conversationKey)
    return
  }

  if (event.event_type === 'sources') {
    chatStore.setLastMessageSources(payload.sources || [], streamTask.conversationKey)
    return
  }

  if (event.event_type === 'session_title') {
    const sessionId = payload.session_id || event.session_id || streamTask.conversationKey
    chatStore.renameConversation(sessionId, payload.title)
    return
  }

  if (
    event.event_type === 'tool_call' ||
    event.event_type === 'tool_result' ||
    event.event_type === 'status' ||
    event.event_type === 'skill_loaded'
  ) {
    if (event.event_type === 'status' && TOOL_FAILURE_STAGES.has(payload.stage)) {
      const toolError = new Error(
        payload.message || `${payload.tool_name || 'tool'} 执行异常：${payload.stage}`,
      )
      toolError.name = 'ToolExecutionError'
      console.error('[LabAgent 工具异常]', toolError, {
        event,
        payload,
        conversationKey: streamTask.conversationKey,
      })
    }
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
    chatStore.completeLastMessageReasoning(null, streamTask.conversationKey)
    return
  }

  if (event.event_type === 'error') {
    chatStore.completeLastMessageReasoning(null, streamTask.conversationKey)
    const message = payload.message || '请求失败'
    if (!lastMessage.content) {
      lastMessage.content = `错误: ${message}`
    } else if (!lastMessage.content.includes(`错误: ${message}`)) {
      lastMessage.content = `${lastMessage.content}\n\n错误: ${message}`
    }
    chatStore.updateLastMessage(lastMessage.content, streamTask.conversationKey)
    return
  }

  if (event.event_type === 'final') {
    streamTask.paused = false
    chatStore.clearPendingApproval(streamTask.conversationKey)
    if (streamTask.shouldPollTitle) {
      void pollConversationTitle(streamTask.conversationKey, streamTask.fallbackTitle)
    }
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

watch(showSlashMenu, (open) => {
  if (open) {
    void loadSkills()
  }
})

watch(selectedSkillNames, () => {
  nextTick(updateSelectedSkillsIndent)
})

watch(
  () => [chatStore.isStreaming, chatStore.awaitingApproval],
  ([isStreaming, awaitingApproval]) => {
    if (isStreaming || awaitingApproval) {
      closeModelDropdown()
    }
  },
)

onMounted(() => {
  resetInputVisualState()
  window.addEventListener('resize', updateSelectedSkillsIndent)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateSelectedSkillsIndent)

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
  titlePollControllers.forEach((controller) => controller.abort())
  titlePollControllers.clear()
  pendingImages.value.forEach((image) => URL.revokeObjectURL(image.preview_url))
})
</script>

<style lang="scss" scoped>
.chat-input-container {
  padding: 0;
  background-color: var(--app-page-bg);
  transition:
    background-color 0.3s ease,
    border-color 0.3s ease;

  .input-wrapper {
    width: var(--chat-content-track-width, min(100%, 880px));
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: stretch;
    position: relative;
    overflow: visible;
    background: var(--app-page-bg);
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
    padding: 0;

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

  .input-left-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }

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
      cursor: pointer;
      flex-shrink: 0;

      &.disabled-btn {
        opacity: 0.45;
        cursor: not-allowed;
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

.input-editor-line {
  position: relative;
  min-width: 0;
}

.selected-skills {
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 6px;
  max-width: calc(100% - 120px);
  min-height: 24px;
  overflow: hidden;
}

.selected-skill {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  max-width: 220px;
  height: 24px;
  flex-shrink: 1;
  color: var(--primary-color, #90138b);
  font-size: 14px;
  font-weight: 600;

  :deep(.tool-activity-icon) {
    width: 17px;
    height: 17px;
    margin-right: 5px;
  }
}

.selected-skill-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pending-images {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  overscroll-behavior-x: contain;
  scroll-behavior: smooth;
  scrollbar-width: none;
  touch-action: pan-x;
  -webkit-overflow-scrolling: touch;

  &::-webkit-scrollbar {
    display: none;
  }
}

.pending-image {
  position: relative;
  width: 72px;
  height: 72px;
  flex: 0 0 72px;

  img {
    width: 100%;
    height: 100%;
    border: 1px solid rgba(229, 231, 235, 1);
    border-radius: 12px;
    background: #f7f7f8;
    object-fit: contain;
  }
}

.remove-image-button {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  background: rgba(31, 41, 55, 0.88);
  color: #fff;
  font-size: 15px;
  line-height: 18px;
  cursor: pointer;
}

.image-file-input {
  display: none;
}

.chat-input {
  width: 100%;
  min-width: 0;
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
  text-indent: var(--selected-skills-indent, 0);
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

  .input-model-selector {
    position: relative;
    flex-shrink: 0;
  }

  .model-selector-button {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    max-width: 150px;
    height: 32px;
    padding: 0 10px;
    border: 0;
    border-radius: 999px;
    background: transparent;
    color: var(--text-primary, #242424);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition:
      background-color 0.2s ease,
      color 0.2s ease;

    &:hover:not(.disabled) {
      background: var(--bg-hover, rgba(0, 0, 0, 0.05));
      color: var(--text-primary, #242424);
    }

    &.disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }

    span {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .model-selector-icon {
    flex-shrink: 0;
    color: currentColor;
    transition: transform 0.2s ease;

    &.is-open {
      transform: rotate(180deg);
    }
  }

  .model-dropdown-menu {
    position: absolute;
    right: 0;
    bottom: calc(100% + 10px);
    width: 220px;
    max-height: min(280px, calc(100vh - 180px));
    padding: 6px;
    border: 1px solid rgba(229, 231, 235, 0.95);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.98);
    box-shadow:
      0 18px 42px rgba(17, 24, 39, 0.14),
      0 1px 0 rgba(255, 255, 255, 0.9) inset;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    overflow-y: auto;
    z-index: 1200;

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: rgba(0, 0, 0, 0.16);
      border-radius: 999px;
    }
  }

  .model-option {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 16px;
    column-gap: 8px;
    align-items: center;
    width: 100%;
    min-height: 34px;
    padding: 0 10px;
    border: 0;
    border-radius: 12px;
    background: transparent;
    color: var(--text-primary, #353740);
    font-size: 13px;
    font-weight: 500;
    text-align: left;
    cursor: pointer;
    transition: background-color 0.16s ease;

    &:hover {
      background: var(--bg-hover, rgba(0, 0, 0, 0.05));
    }

  }

  .model-option-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .model-option-content {
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 0;
  }

  .model-option-check {
    width: 14px;
    height: 14px;
    color: var(--primary-color, #90138b);
    justify-self: end;
  }

  .model-dropdown-fade-enter-active,
  .model-dropdown-fade-leave-active {
    transition:
      opacity 0.16s ease,
      transform 0.16s ease;
  }

  .model-dropdown-fade-enter-from,
  .model-dropdown-fade-leave-to {
    opacity: 0;
    transform: translateY(4px) scale(0.98);
  }

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
      background-color: var(--primary-color, #90138b);
      color: #fff;
      border: none;

      svg {
        width: 1em;
        height: 1em;
        fill: currentColor;
        stroke: none;
      }

      &:hover {
        background-color: #9b2a96;
      }
    }
  }

  @media (max-width: 768px) {
    .model-selector-button {
      max-width: 118px;
      padding: 0 8px;
      font-size: 12px;
    }

    .model-dropdown-menu {
      width: 200px;
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
