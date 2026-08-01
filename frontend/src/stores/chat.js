import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  deleteSession,
  deleteSessions,
  getChatImage,
  getSessionHistory,
  getUserSessions,
} from '../api/chat'
import { DEFAULT_MODEL } from '../constants/models'

const CURRENT_CONVERSATION_STORAGE_KEY = 'chat_current_conversation_id'
const DRAFT_CONVERSATION_PREFIX = '__draft_conversation__'

export const useChatStore = defineStore('chat', () => {
  // 会话列表
  const conversations = ref([])

  // 当前选中的会话 key：历史会话直接使用 sessionId，新会话使用前端草稿 key
  const activeConversationKey = ref(null)

  // 每个会话单独维护自己的消息、加载、流式和右侧预览状态，避免历史会话切换时串流/串预览
  const conversationStates = ref({})

  // 侧边栏折叠状态
  const sidebarCollapsed = ref(false)
  const SIDEBAR_MIN_WIDTH = 240
  const SIDEBAR_MAX_WIDTH = 360
  const sidebarWidth = ref(280)

  // 切换用户后需要重新加载会话列表：logout 时置 true，Chat 视图 onActivated 时据此重载，
  // 避免 keep-alive 缓存导致上一个用户的会话残留
  const needsReload = ref(false)

  // 是否需要聚焦输入框
  const shouldFocusInput = ref(false)

  // 侧栏宽度（像素），由正文/侧栏之间的分隔条拖拽调节
  const PREVIEW_PANEL_MIN_WIDTH = 260
  const PREVIEW_PANEL_MAX_WIDTH = 900
  const previewPanelWidth = ref(460)
  const previewPanelSwitchingCollapse = ref(false)
  let previewPanelSwitchingCollapseTimer = null

  const setPreviewPanelWidth = (width) => {
    const clamped = Math.min(PREVIEW_PANEL_MAX_WIDTH, Math.max(PREVIEW_PANEL_MIN_WIDTH, width))
    previewPanelWidth.value = clamped
  }

  const createConversationState = () => ({
    messages: [],
    isLoading: false,
    isStreaming: false,
    awaitingApproval: false,
    pendingApproval: null,
    hasLoadedMessages: false,
    historyLoadError: '',
    previewPanelOpen: false,
    previewTabs: [],
    previewActivePath: '',
    selectedModel: DEFAULT_MODEL,
  })

  const generateDraftConversationKey = () => {
    return `${DRAFT_CONVERSATION_PREFIX}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  const generateMessageId = () => {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  const isDraftConversationKey = (conversationKey) => {
    return typeof conversationKey === 'string' && conversationKey.startsWith(DRAFT_CONVERSATION_PREFIX)
  }

  const ensureConversationDisplayState = (state) => {
    if (!state) return null
    if (typeof state.previewPanelOpen !== 'boolean') {
      state.previewPanelOpen = false
    }
    if (!Array.isArray(state.previewTabs)) {
      state.previewTabs = []
    }
    if (typeof state.previewActivePath !== 'string') {
      state.previewActivePath = ''
    }
    if (typeof state.selectedModel !== 'string' || !state.selectedModel) {
      state.selectedModel = DEFAULT_MODEL
    }
    if (typeof state.historyLoadError !== 'string') {
      state.historyLoadError = ''
    }
    return state
  }

  const ensureConversationState = (conversationKey) => {
    if (!conversationKey) return null

    if (!conversationStates.value[conversationKey]) {
      conversationStates.value[conversationKey] = createConversationState()
    } else {
      ensureConversationDisplayState(conversationStates.value[conversationKey])
    }

    return conversationStates.value[conversationKey]
  }

  const getConversationState = (conversationKey = activeConversationKey.value, createIfMissing = false) => {
    if (!conversationKey) return null

    if (createIfMissing) {
      return ensureConversationState(conversationKey)
    }

    return conversationStates.value[conversationKey] || null
  }

  const markPreviewPanelSwitchingCollapse = () => {
    previewPanelSwitchingCollapse.value = true
    if (previewPanelSwitchingCollapseTimer) {
      globalThis.clearTimeout(previewPanelSwitchingCollapseTimer)
    }
    previewPanelSwitchingCollapseTimer = globalThis.setTimeout(() => {
      previewPanelSwitchingCollapse.value = false
      previewPanelSwitchingCollapseTimer = null
    }, 180)
  }

  const selectConversationKey = (conversationKey) => {
    activeConversationKey.value = conversationKey

    if (!conversationKey || isDraftConversationKey(conversationKey)) {
      localStorage.removeItem(CURRENT_CONVERSATION_STORAGE_KEY)
      return
    }

    localStorage.setItem(CURRENT_CONVERSATION_STORAGE_KEY, conversationKey)
  }

  const createDraftConversation = ({ focus = true } = {}) => {
    const currentState = getConversationState(activeConversationKey.value, false)
    if (currentState?.previewPanelOpen) {
      markPreviewPanelSwitchingCollapse()
    }

    const draftConversationKey = generateDraftConversationKey()
    const state = ensureConversationState(draftConversationKey)

    // 新建草稿会话时重置该草稿自己的显示状态，不影响其他会话中的流式任务
    state.messages = []
    state.isLoading = false
    state.isStreaming = false
    state.hasLoadedMessages = false

    selectConversationKey(draftConversationKey)

    if (focus) {
      focusInput()
    }

    return draftConversationKey
  }

  const currentConversationId = computed(() => {
    return isDraftConversationKey(activeConversationKey.value) ? null : activeConversationKey.value
  })

  const messages = computed(() => {
    return getConversationState(activeConversationKey.value)?.messages || []
  })

  const previewPanelOpen = computed(() => {
    return getConversationState(activeConversationKey.value)?.previewPanelOpen || false
  })

  const previewTabs = computed(() => {
    return getConversationState(activeConversationKey.value)?.previewTabs || []
  })

  const previewActivePath = computed(() => {
    return getConversationState(activeConversationKey.value)?.previewActivePath || ''
  })

  const selectedModel = computed(() => {
    return getConversationState(activeConversationKey.value)?.selectedModel || DEFAULT_MODEL
  })

  // 当前会话的「产物路径集合」：所有 write_file 工具调用的目标路径，
  // 供正文渲染判定「哪些路径可点击预览」（等价于产物注册，无需新建表）
  const artifactPaths = computed(() => {
    const paths = new Set()
    const list = getConversationState(activeConversationKey.value)?.messages || []
    list.forEach((message) => {
      ;(message.toolEvents || []).forEach((event) => {
        const payload = event?.payload || {}
        if (payload.tool_name !== 'write_file') return
        const path = payload.preview_path || payload.arguments?.file_path
        if (path) paths.add(path)
      })
    })
    return paths
  })

  const isLoading = computed(() => {
    return getConversationState(activeConversationKey.value)?.isLoading || false
  })

  const isStreaming = computed(() => {
    return getConversationState(activeConversationKey.value)?.isStreaming || false
  })

  const awaitingApproval = computed(() => {
    return getConversationState(activeConversationKey.value)?.awaitingApproval || false
  })

  const pendingApproval = computed(() => {
    return getConversationState(activeConversationKey.value)?.pendingApproval || null
  })

  const historyLoadError = computed(() => {
    return getConversationState(activeConversationKey.value)?.historyLoadError || ''
  })

  const isNewConversation = computed(() => {
    return isDraftConversationKey(activeConversationKey.value)
  })

  const currentConversation = computed(() => {
    return conversations.value.find((conv) => conv.id === currentConversationId.value)
  })

  const setSelectedModel = (model, conversationKey = activeConversationKey.value) => {
    if (!model) return

    const state = ensureConversationState(conversationKey)
    if (state) {
      state.selectedModel = model
    }
  }

  /**
   * 打开工作区文件预览（正文超链接点击触发）
   * @param {object} payload - { path, language?, content? }；content 为空时由预览面板按需拉取
   */
  const openPreview = ({
    path,
    language = '',
    content = null,
    preview_type = 'text',
    image_url = '',
    download_name = '',
  } = {}) => {
    if (!path) return

    const state = ensureConversationState(activeConversationKey.value)
    if (!state) return

    const existing = state.previewTabs.find((tab) => tab.path === path)
    if (existing) {
      // 已有 tab：若之前没拿到正文而这次带来了正文，则补上
      if (content !== null && !existing.content) {
        existing.content = content
        existing.language = language || existing.language
      }
      if (image_url) {
        existing.image_url = image_url
      }
      existing.preview_type = preview_type || existing.preview_type
      existing.download_name = download_name || existing.download_name
    } else {
      state.previewTabs.push({
        path,
        language,
        content,
        preview_type,
        image_url,
        download_name,
        loading: false,
        error: '',
      })
    }
    state.previewActivePath = path
    state.previewPanelOpen = true
  }

  const setPreviewActive = (path) => {
    const state = getConversationState(activeConversationKey.value, true)
    if (state?.previewTabs.some((tab) => tab.path === path)) {
      state.previewActivePath = path
    }
  }

  const closePreviewTab = (path) => {
    const state = getConversationState(activeConversationKey.value, true)
    if (!state) return

    const index = state.previewTabs.findIndex((tab) => tab.path === path)
    if (index === -1) return

    state.previewTabs.splice(index, 1)
    if (state.previewActivePath === path) {
      const next = state.previewTabs[index] || state.previewTabs[index - 1] || null
      state.previewActivePath = next ? next.path : ''
    }
    // 关闭最后一个 tab 后保留面板（显示空状态提示），由收起按钮显式关闭
  }

  // 显式展开当前会话侧栏（即使没有任何文件，也展示空状态提示）
  const openPreviewPanel = () => {
    const state = ensureConversationState(activeConversationKey.value)
    if (state) {
      state.previewPanelOpen = true
    }
  }

  const closePreviewPanel = () => {
    const state = getConversationState(activeConversationKey.value, true)
    if (state) {
      state.previewPanelOpen = false
    }
  }

  /**
   * 创建新对话
   * 注意：新对话的 ID 由后端在第一次发送消息时生成
   */
  const createConversation = () => {
    return createDraftConversation()
  }

  /**
   * 设置当前会话ID（由后端返回的 sessionId）
   * @param {string} sessionId - 后端返回的会话ID
   * @param {string} [sourceConversationKey] - 流式开始时所属的会话 key
   */
  const setCurrentSessionId = (sessionId, sourceConversationKey = activeConversationKey.value) => {
    if (!sessionId) return

    const sourceState = getConversationState(sourceConversationKey, false)

    if (sourceConversationKey && sourceConversationKey !== sessionId && sourceState) {
      conversationStates.value[sessionId] = sourceState
      delete conversationStates.value[sourceConversationKey]
    } else {
      ensureConversationState(sessionId)
    }

    // 只有当前正在看的就是这条流时，才切换当前选中项，避免后台流式输出打断当前页面
    if (activeConversationKey.value === sourceConversationKey || !activeConversationKey.value) {
      selectConversationKey(sessionId)
    }
  }

  const setConversationLoading = (conversationKey, loading) => {
    const state = ensureConversationState(conversationKey)
    if (state) {
      state.isLoading = loading
    }
  }

  const setConversationStreaming = (conversationKey, streaming) => {
    const state = ensureConversationState(conversationKey)
    if (state) {
      state.isStreaming = streaming
    }
  }

  const getConversationMessages = (conversationKey = activeConversationKey.value) => {
    return getConversationState(conversationKey)?.messages || []
  }

  const getLastMessage = (conversationKey = activeConversationKey.value) => {
    const conversationMessages = getConversationMessages(conversationKey)
    return conversationMessages.length > 0 ? conversationMessages[conversationMessages.length - 1] : null
  }

  /**
   * 切换到指定会话，优先展示内存缓存；仅在首次进入且本地没有缓存时才从数据库加载
   * @param {string} conversationId - 会话ID
   */
  const switchConversation = async (conversationId) => {
    const currentState = getConversationState(activeConversationKey.value, false)
    const targetState = getConversationState(conversationId, false)
    if (currentState?.previewPanelOpen && !targetState?.previewPanelOpen) {
      markPreviewPanelSwitchingCollapse()
    }

    selectConversationKey(conversationId)

    const conversation = conversations.value.find((conv) => conv.id === conversationId)
    const state = getConversationState(conversationId, false)

    if (conversation && !(state?.isStreaming || state?.hasLoadedMessages || state?.messages.length > 0)) {
      await loadConversationMessagesFromDB(conversationId)
    } else {
      ensureConversationState(conversationId)
    }

    // 触发输入框聚焦
    focusInput()
  }

  const removeConversationState = (conversationKey) => {
    if (conversationKey && conversationStates.value[conversationKey]) {
      delete conversationStates.value[conversationKey]
    }
  }

  /**
   * 删除对话（调用后端API进行逻辑删除）
   * @param {string} conversationId - 会话ID
   * @returns {Promise<boolean>} 删除是否成功
   */
  const deleteConversation = async (conversationId) => {
    try {
      // 调用后端API删除会话，传递 userId 进行权限校验
      const response = await deleteSession(conversationId)

      // 删除成功后更新本地状态
      if (response.data.data === true) {
        const index = conversations.value.findIndex((conv) => conv.id === conversationId)
        if (index !== -1) {
          conversations.value.splice(index, 1)
        }

        removeConversationState(conversationId)

        // 如果删除的是当前会话，切换到其他会话
        if (conversationId === currentConversationId.value) {
          if (conversations.value.length > 0) {
            await switchConversation(conversations.value[0].id)
          } else {
            createDraftConversation({ focus: false })
          }
        }

        console.log('会话删除成功:', conversationId)
        return true
      } else {
        console.error('删除会话失败: 后端返回false')
        return false
      }
    } catch (error) {
      console.error('删除会话失败:', error)
      return false
    }
  }

  /**
   * 批量删除对话
   * @param {Array<string>} conversationIds - 会话ID列表
   * @returns {Promise<boolean>} 删除是否成功
   */
  const deleteConversations = async (conversationIds) => {
    try {
      if (!conversationIds || conversationIds.length === 0) return false

      // 调用后端API批量删除会话
      const response = await deleteSessions(conversationIds)

      // 删除成功后更新本地状态
      if (response.data.data === true) {
        // 过滤掉已删除的会话
        conversations.value = conversations.value.filter(
          (conv) => !conversationIds.includes(conv.id),
        )

        conversationIds.forEach((conversationId) => {
          removeConversationState(conversationId)
        })

        // 如果当前会话被删除了，切换到其他会话
        if (conversationIds.includes(currentConversationId.value)) {
          if (conversations.value.length > 0) {
            await switchConversation(conversations.value[0].id)
          } else {
            createDraftConversation({ focus: false })
          }
        }

        console.log('批量删除会话成功:', conversationIds)
        return true
      } else {
        console.error('批量删除会话失败: 后端返回false')
        return false
      }
    } catch (error) {
      console.error('批量删除会话失败:', error)
      return false
    }
  }

  /**
   * 重命名会话
   * 注意：仅更新前端显示标题，不修改 updatedAt（时间由数据库管理）
   * TODO: 后续可以添加后端更新接口
   */
  const renameConversation = (conversationId, newTitle) => {
    const conversation = conversations.value.find((conv) => conv.id === conversationId)
    if (conversation) {
      conversation.title = newTitle || '新对话'
      // 不更新 updatedAt，保持数据库时间
    }
  }

  /**
   * 更新会话标题（根据第一条消息）
   * 注意：仅更新前端显示标题，不修改 updatedAt（时间由数据库管理）
   */
  const updateConversationTitle = (conversationId, firstMessage) => {
    const conversation = conversations.value.find((conv) => conv.id === conversationId)
    if (conversation && conversation.title === '新对话') {
      const title = firstMessage.length > 30 ? firstMessage.substring(0, 30) + '...' : firstMessage
      conversation.title = title
      // 不更新 updatedAt，保持数据库时间
    }
  }

  /**
   * 添加消息到指定会话
   * @param {string} sender - 发送者类型（'user' 或 'assistant'）
   * @param {string} content - 消息内容
   * @param {string} [conversationKey] - 会话 key
   * @param {Array} [images] - 图片附件及本地预览地址
   * @param {Array<string>} [skillNames] - 用户主动选择的技能名称
   * @returns {object|null} 消息对象
   */
  const addMessage = (
    sender,
    content,
    conversationKey = activeConversationKey.value,
    images = [],
    skillNames = [],
  ) => {
    const state = ensureConversationState(conversationKey)
    if (!state) return null

    const message = {
      id: generateMessageId(),
      sender: sender,
      content: content,
      images,
      skillNames,
      timestamp: new Date().toISOString(),
      toolEvents: [],
      sources: [],
      reasoning: [],
      isComplete: sender !== 'assistant',
      feedbackState: null,
    }

    state.messages.push(message)

    return message
  }

  /**
   * 将当前新对话添加到会话列表
   * 注意：时间使用null占位，会在下次刷新会话列表时从数据库同步
   * @param {string} sessionId - 后端返回的会话ID
   * @param {string} title - 会话标题（通常是第一条消息）
   */
  const addNewConversationToList = (sessionId, title) => {
    const existingConversation = conversations.value.find((conversation) => conversation.id === sessionId)

    if (existingConversation) {
      existingConversation.title = title.length > 30 ? title.substring(0, 30) + '...' : title
      return
    }

    const newConversation = {
      id: sessionId,
      title: title.length > 30 ? title.substring(0, 30) + '...' : title,
      createdAt: null, // 时间由数据库管理，下次刷新会话列表时同步
      updatedAt: null, // 时间由数据库管理，下次刷新会话列表时同步
    }

    // 添加到列表顶部
    conversations.value.unshift(newConversation)
  }

  /**
   * 更新指定会话最后一条消息内容（用于流式响应）
   * @param {string} content - 最新消息内容
   * @param {string} [conversationKey] - 会话 key
   */
  const updateLastMessage = (content, conversationKey = activeConversationKey.value) => {
    const lastMessage = getLastMessage(conversationKey)
    if (lastMessage && lastMessage.sender === 'assistant') {
      lastMessage.content = content
    }
  }

  const markLastAssistantMessageComplete = (conversationKey = activeConversationKey.value) => {
    const lastMessage = getLastMessage(conversationKey)
    if (lastMessage && lastMessage.sender === 'assistant') {
      lastMessage.isComplete = true
    }
  }

  const appendReasoningToLastMessage = (payload, conversationKey = activeConversationKey.value) => {
    const lastMessage = getLastMessage(conversationKey)
    const content = typeof payload?.content === 'string' ? payload.content : ''
    if (!lastMessage || lastMessage.sender !== 'assistant' || !content) return

    if (!Array.isArray(lastMessage.reasoning)) {
      lastMessage.reasoning = []
    }
    const reasoningId = payload.reasoning_id || `agent-${payload.round_number || lastMessage.reasoning.length + 1}`
    let segment = lastMessage.reasoning.find((item) => item.reasoning_id === reasoningId)
    if (!segment) {
      lastMessage.reasoning.forEach((item) => {
        if (!item.is_complete && !item.user_toggled) item.collapsed = true
      })
      segment = {
        reasoning_id: reasoningId,
        phase: payload.phase || 'agent',
        round_number: payload.round_number || lastMessage.reasoning.length + 1,
        content: '',
        is_complete: false,
        collapsed: false,
        user_toggled: false,
      }
      lastMessage.reasoning.push(segment)
    }
    segment.content += content
  }

  const completeLastMessageReasoning = (
    reasoningId = null,
    conversationKey = activeConversationKey.value,
  ) => {
    const lastMessage = getLastMessage(conversationKey)
    if (!lastMessage || lastMessage.sender !== 'assistant' || !Array.isArray(lastMessage.reasoning)) return

    lastMessage.reasoning.forEach((segment) => {
      if (reasoningId && segment.reasoning_id !== reasoningId) return
      segment.is_complete = true
      if (!segment.user_toggled) segment.collapsed = true
    })
  }

  const toggleMessageReasoning = (
    messageId,
    reasoningId,
    conversationKey = activeConversationKey.value,
  ) => {
    const state = getConversationState(conversationKey)
    const message = state?.messages.find((item) => item.id === messageId)
    const segment = message?.reasoning?.find((item) => item.reasoning_id === reasoningId)
    if (!segment) return

    segment.collapsed = !segment.collapsed
    segment.user_toggled = true
  }

  const setMessageFeedbackState = (
    messageId,
    feedbackState,
    conversationKey = activeConversationKey.value,
  ) => {
    const state = getConversationState(conversationKey)
    if (!state) return

    const targetMessage = state.messages.find((message) => message.id === messageId)
    if (targetMessage) {
      targetMessage.feedbackState = feedbackState
    }
  }

  const addToolEventToLastMessage = (toolEvent, conversationKey = activeConversationKey.value) => {
    const lastMessage = getLastMessage(conversationKey)
    if (lastMessage && lastMessage.sender === 'assistant') {
      if (!Array.isArray(lastMessage.toolEvents)) {
        lastMessage.toolEvents = []
      }
      lastMessage.toolEvents.push(toolEvent)
    }
  }

  const setPendingApproval = (approval, conversationKey = activeConversationKey.value) => {
    const state = ensureConversationState(conversationKey)
    if (!state) return
    state.pendingApproval = approval
    state.awaitingApproval = Boolean(approval)
  }

  const clearPendingApproval = (conversationKey = activeConversationKey.value) => {
    const state = ensureConversationState(conversationKey)
    if (!state) return
    state.pendingApproval = null
    state.awaitingApproval = false
  }

  /**
   * 追加合并指定会话最后一条助手消息的引用来源（RAG 检索命中的来源）
   * 检索即工具后一次对话可能多次下发 sources，按 file_name + snippet 去重合并，保留全部来源
   * @param {Array} sources - 本次检索的来源列表，每项含 file_name/snippet/score（全蛇形）
   * @param {string} [conversationKey] - 会话 key
   */
  const setLastMessageSources = (sources, conversationKey = activeConversationKey.value) => {
    const lastMessage = getLastMessage(conversationKey)
    if (!lastMessage || lastMessage.sender !== 'assistant') return
    const incoming = Array.isArray(sources) ? sources : []
    const existing = Array.isArray(lastMessage.sources) ? lastMessage.sources : []
    const seen = new Set(existing.map((item) => `${item.file_name}|${item.snippet}`))
    const merged = [...existing]
    incoming.forEach((item) => {
      const key = `${item.file_name}|${item.snippet}`
      if (seen.has(key)) return
      seen.add(key)
      merged.push(item)
    })
    lastMessage.sources = merged
  }

  /**
   * 从数据库加载会话的历史消息
   * @param {string} sessionId - 会话ID
   * @param {boolean} [force=false] - 是否强制刷新
   */
  const loadConversationMessagesFromDB = async (sessionId, force = false) => {
    const state = ensureConversationState(sessionId)

    if (!force && (state.isStreaming || state.hasLoadedMessages || state.messages.length > 0)) {
      return state.messages
    }

    try {
      state.isLoading = true

      const response = await getSessionHistory(sessionId)
      const dbMessages = response.data.data || []
      state.historyLoadError = ''

      // 转换后端消息格式为前端格式
      state.messages = dbMessages.map((msg) => {
        const content = msg.content || ''
        const toolEvents = []
        ;(msg.tool_calls || []).forEach((toolCall) => {
          toolEvents.push({
            eventType: 'tool_call',
            payload: {
              tool_call_id: toolCall.tool_call_id,
              tool_name: toolCall.tool_name,
              arguments: toolCall.arguments || {},
              round: toolCall.round,
              risk_level: toolCall.risk_level,
            },
            ts: toolCall.created_at,
          })
          toolEvents.push({
            eventType: 'tool_result',
            payload: {
              tool_call_id: toolCall.tool_call_id,
              tool_name: toolCall.tool_name,
              success: toolCall.status === 'success',
              status: toolCall.status,
              result_summary: toolCall.result_summary,
              output_preview: toolCall.output_preview,
              error_message: toolCall.error_message,
              duration_ms: toolCall.duration_ms,
              round: toolCall.round,
              // 历史消息不带整文件正文，仅保留路径供正文超链接判定与按需预览
              preview_path:
                toolCall.tool_name === 'write_file' ? toolCall.arguments?.file_path : undefined,
            },
            ts: toolCall.created_at,
          })
        })

        return {
          id: msg.id || generateMessageId(),
          sender: msg.role === 'user' ? 'user' : 'assistant',
          content,
          images: Array.isArray(msg.images)
            ? msg.images.map((image) => ({ ...image, preview_url: '' }))
            : [],
          skillNames: Array.isArray(msg.skill_names) ? msg.skill_names : [],
          timestamp: msg.created_at || new Date().toISOString(),
          toolEvents,
          sources: Array.isArray(msg.sources) ? msg.sources : [],
          reasoning: Array.isArray(msg.reasoning)
            ? msg.reasoning.map((segment) => ({
                ...segment,
                is_complete: true,
                collapsed: true,
                user_toggled: false,
              }))
            : [],
          isComplete: true,
          feedbackState: null,
        }
      })
      const historyImages = state.messages.flatMap((message) => message.images || [])
      await Promise.all(
        historyImages.map(async (image) => {
          try {
            const imageResponse = await getChatImage(image.image_id)
            image.preview_url = URL.createObjectURL(imageResponse.data)
          } catch (error) {
            console.error('加载聊天图片失败:', error)
            image.load_error = true
          }
        }),
      )
      state.hasLoadedMessages = true

      return state.messages
    } catch (error) {
      console.error('加载会话历史失败:', error)
      state.messages = []
      state.hasLoadedMessages = false
      state.historyLoadError = error?.response?.data?.message || error?.message || '会话历史加载失败'
      return []
    } finally {
      state.isLoading = false
    }
  }

  /**
   * 从数据库加载用户的会话列表
   */
  const loadConversationsFromDB = async () => {
    try {
      const response = await getUserSessions()
      const dbSessions = response.data.data || []

      // 转换后端会话格式为前端格式
      // 注意：后端字段名是 created_at/updated_at（蛇形命名）
      conversations.value = dbSessions.map((session) => ({
        id: session.id,
        title: session.title || '新对话',
        createdAt: session.created_at || null,
        updatedAt: session.updated_at || null,
      }))
    } catch (error) {
      console.error('加载会话列表失败:', error)
      conversations.value = []
    }
  }

  /**
   * 清空当前会话的消息
   */
  const clearMessages = (conversationKey = activeConversationKey.value) => {
    const state = ensureConversationState(conversationKey)
    if (state) {
      state.messages = []
      state.hasLoadedMessages = false
    }
  }

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const setSidebarWidth = (width) => {
    sidebarWidth.value = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, width))
  }

  const focusInput = () => {
    shouldFocusInput.value = true
  }

  /**
   * 初始化：从数据库加载会话列表
   */
  const initialize = async () => {
    needsReload.value = false
    await loadConversationsFromDB()

    // 如果当前已经是新对话状态（比如从其他页面点击“新对话”跳转过来时），则不自动加载历史会话
    if (isDraftConversationKey(activeConversationKey.value)) {
      return
    }

    // 如果有保存的当前会话ID，尝试切换到该会话
    const currentId = localStorage.getItem(CURRENT_CONVERSATION_STORAGE_KEY)
    if (currentId && conversations.value.find((conv) => conv.id === currentId)) {
      await switchConversation(currentId)
    } else if (conversations.value.length > 0) {
      // 否则选择第一个会话
      await switchConversation(conversations.value[0].id)
    } else {
      // 没有会话，准备新建一个前端草稿会话
      createDraftConversation({ focus: false })
    }
  }

  /**
   * 重置会话状态：切换用户（登出）时调用，清空当前用户的会话数据与本地当前会话记录，
   * 并标记 needsReload，让 Chat 视图重新激活时按新用户重新加载
   */
  const reset = () => {
    if (previewPanelSwitchingCollapseTimer) {
      globalThis.clearTimeout(previewPanelSwitchingCollapseTimer)
      previewPanelSwitchingCollapseTimer = null
    }
    previewPanelSwitchingCollapse.value = false
    conversations.value = []
    conversationStates.value = {}
    activeConversationKey.value = null
    localStorage.removeItem(CURRENT_CONVERSATION_STORAGE_KEY)
    needsReload.value = true
  }

  return {
    conversations,
    currentConversationId,
    activeConversationKey,
    messages,
    isLoading,
    isStreaming,
    awaitingApproval,
    pendingApproval,
    historyLoadError,
    sidebarCollapsed,
    sidebarWidth,
    needsReload,
    shouldFocusInput,
    isNewConversation,
    selectedModel,
    setSelectedModel,
    currentConversation,
    previewPanelOpen,
    previewTabs,
    previewActivePath,
    previewPanelWidth,
    previewPanelSwitchingCollapse,
    artifactPaths,
    openPreview,
    setPreviewActive,
    closePreviewTab,
    openPreviewPanel,
    closePreviewPanel,
    setSidebarWidth,
    setPreviewPanelWidth,
    createConversation,
    setCurrentSessionId,
    setConversationLoading,
    setConversationStreaming,
    getConversationMessages,
    getLastMessage,
    addNewConversationToList,
    switchConversation,
    deleteConversation,
    deleteConversations,
    renameConversation,
    updateConversationTitle,
    addMessage,
    updateLastMessage,
    markLastAssistantMessageComplete,
    appendReasoningToLastMessage,
    completeLastMessageReasoning,
    toggleMessageReasoning,
    setMessageFeedbackState,
    addToolEventToLastMessage,
    setPendingApproval,
    clearPendingApproval,
    setLastMessageSources,
    clearMessages,
    toggleSidebar,
    focusInput,
    initialize,
    reset,
    loadConversationsFromDB,
    loadConversationMessagesFromDB,
    isDraftConversationKey,
  }
})
