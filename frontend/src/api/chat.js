import apiClient, { buildApiUrl, handleAuthExpired, isAuthExpiredResponse } from './index'

/**
 * 聊天相关 API
 * 使用数据库持久化存储会话和消息
 */

/**
 * 获取用户的会话列表
 * @param {number} userId - 用户ID
 * @returns {Promise} 会话列表
 */
export const getUserSessions = () => {
  return apiClient.post('/v1/ai/rag/sessions')
}

/**
 * 获取单个会话的标题
 * @param {string} sessionId - 会话ID
 * @param {AbortSignal} signal - 取消轮询信号
 * @returns {Promise} 会话标题
 */
export const getSessionTitle = (sessionId, signal) => {
  return apiClient.get(`/v1/ai/rag/sessions/${sessionId}/title`, { signal })
}

/**
 * 获取会话的历史消息
 * @param {string} sessionId - 会话ID
 * @param {number} userId - 用户ID（用于权限校验）
 * @returns {Promise} 消息列表
 */
export const getSessionHistory = (sessionId) => {
  return apiClient.post('/v1/ai/rag/history', { session_id: sessionId })
}

/**
 * 删除会话（逻辑删除）
 * @param {string} sessionId - 会话ID
 * @param {number} userId - 用户ID（用于权限校验）
 * @returns {Promise} 删除结果，true表示成功
 */
export const deleteSession = (sessionId) => {
  return apiClient.post('/v1/ai/rag/sessions/delete', { session_id: sessionId })
}

/**
 * 批量删除会话（逻辑删除）
 * @param {Array<string>} sessionIds - 会话ID列表
 * @param {number} userId - 用户ID（用于权限校验）
 * @returns {Promise} 删除结果，true表示成功
 */
export const deleteSessions = (sessionIds) => {
  return apiClient.post('/v1/ai/rag/sessions/delete', { session_ids: sessionIds })
}

/**
 * 发送 Agent 对话消息（POST 方式，支持 SSE 流式响应）
 *
 * 使用 fetch + ReadableStream 处理 SSE 流式响应，
 * 相比 EventSource（仅支持GET），POST方式更安全且支持更长的消息内容。
 *
 * @param {Object} params - 请求参数
 * @param {string} params.message - 用户消息
 * @param {string} [params.sessionId] - 会话ID，新会话时为空
 * @param {string} [params.model] - 大模型名称
 * @param {string[]} [params.skillNames] - 本轮主动激活的技能名称
 * @param {Object} callbacks - 回调函数集合
 * @param {Function} callbacks.onMessage - 收到消息时的回调 (data: string) => void
 * @param {Function} callbacks.onError - 发生错误时的回调 (error: Error) => void
 * @param {Function} callbacks.onComplete - 完成时的回调 () => void
 * @returns {AbortController} 用于取消请求的控制器
 */
export const sendReactAgentMessage = (params, callbacks) => {
  const { message, sessionId = '', model, images = [], skillNames = [] } = params
  return sendSseRequest(
    buildApiUrl('/v1/ai/react-agent'),
    { message, session_id: sessionId, model, images, skill_names: skillNames },
    callbacks,
  )
}

export const uploadChatImage = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post('/v1/ai/images', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getChatImage = (imageId) => {
  return apiClient.get(`/v1/ai/images/${imageId}`, { responseType: 'blob' })
}

export const resumeReactAgent = (params, callbacks) => {
  const { sessionId, interruptId, approved } = params
  return sendSseRequest(
    buildApiUrl('/v1/ai/react-agent/resume'),
    { session_id: sessionId, interrupt_id: interruptId, approved },
    callbacks,
  )
}

export const cancelReactAgent = ({ sessionId, traceId }) => {
  return apiClient.post('/v1/ai/react-agent/cancel', {
    session_id: sessionId,
    trace_id: traceId,
  })
}

export const compressConversation = (sessionId) => {
  return apiClient.post(`/v1/ai/sessions/${sessionId}/compress`)
}

export const getAgentTools = () => {
  return apiClient.get('/v1/ai/tools')
}

/**
 * 预览工作区文件（整文件内容，非 diff）
 * @param {string} sessionId - 会话ID
 * @param {string} path - 工作区相对路径
 * @returns {Promise} { path, language, content, truncated }
 */
export const getWorkspaceFilePreview = (sessionId, path) => {
  return apiClient.get('/v1/ai/workspace/file', {
    params: { session_id: sessionId, path, disposition: 'inline' },
  })
}

/**
 * 下载工作区文件
 * @param {string} sessionId - 会话ID
 * @param {string} path - 工作区相对路径
 * @returns {Promise} 文件 blob 数据
 */
export const downloadWorkspaceFile = (sessionId, path) => {
  return apiClient.get('/v1/ai/workspace/file', {
    params: { session_id: sessionId, path, disposition: 'attachment' },
    responseType: 'blob',
  })
}

const sendSseRequest = (url, body, callbacks) => {
  const { onMessage, onError, onComplete } = callbacks

  const controller = new AbortController()

  const token = localStorage.getItem('token')

  const headers = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }

  // 仅在 token 存在时携带 Authorization，避免发送 "Bearer null"
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        if (response.status === 401) {
          handleAuthExpired()
          throw new Error('未登录或无权限，请先登录后再重试')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        const data = await response.json()
        if (isAuthExpiredResponse(data)) {
          handleAuthExpired()
          throw new Error(data.message || '登录已过期或无效')
        }
        if (data?.code && data.code !== 0) {
          throw new Error(data.message || '请求失败')
        }
        throw new Error('服务响应格式异常')
      }

      if (!response.body) {
        throw new Error('服务响应为空')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let eventBuffer = []

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          if (buffer) {
            processLine(buffer, eventBuffer, onMessage)
          }
          if (eventBuffer.length > 0) {
            onMessage?.(eventBuffer.join(''))
          }
          onComplete?.()
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          processLine(line, eventBuffer, onMessage)
        }
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        console.error('SSE请求错误:', error)
        onError?.(error)
      }
    })

  return controller
}

/**
 * 处理 SSE 数据行
 * @param {string} line - 数据行
 * @param {string[]} eventBuffer - 事件数据缓存
 * @param {Function} onMessage - 消息回调
 */
function processLine(line, eventBuffer, onMessage) {
  const cleanLine = line.endsWith('\r') ? line.slice(0, -1) : line

  if (!cleanLine) {
    if (eventBuffer.length > 0) {
      const fullMessage = eventBuffer.join('')
      onMessage?.(fullMessage)
      eventBuffer.length = 0
    }
    return
  }

  if (cleanLine.startsWith('data:')) {
    let data = cleanLine.slice(5)

    try {
      const parsed = JSON.parse(data)

      if (parsed.event_type) {
        onMessage?.(parsed)
        return
      }

      if (parsed.session_id) {
        eventBuffer.push(`[SESSION_ID:${parsed.session_id}]`)
      } else if (parsed.content !== undefined) {
        eventBuffer.push(parsed.content)
      }
    } catch {
      if (data.length === 0) {
        data = '\n'
      }
      eventBuffer.push(data)
    }
  }
}
