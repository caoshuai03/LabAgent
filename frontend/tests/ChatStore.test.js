/**
 * @author: caoshuai.cs
 * @date: 2026-07-26
 * @description: 对话思考过程状态管理测试
 */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/api/chat', () => ({
  deleteSession: vi.fn(),
  deleteSessions: vi.fn(),
  getSessionHistory: vi.fn(),
  getUserSessions: vi.fn(),
}))

import { useChatStore } from '../src/stores/chat'

describe('chat store reasoning', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
      setItem: vi.fn(),
    })
  })

  it('思考结束后自动折叠，但保留用户手动折叠选择', () => {
    const chatStore = useChatStore()
    const conversationKey = chatStore.createConversation()
    chatStore.addMessage('assistant', '', conversationKey)

    chatStore.appendReasoningToLastMessage(
      {
        reasoning_id: 'agent-1',
        round_number: 1,
        content: '分析题目约束。',
      },
      conversationKey,
    )
    let segment = chatStore.getLastMessage(conversationKey).reasoning[0]
    expect(segment.collapsed).toBe(false)

    chatStore.completeLastMessageReasoning('agent-1', conversationKey)
    expect(segment.collapsed).toBe(true)

    chatStore.appendReasoningToLastMessage(
      {
        reasoning_id: 'agent-2',
        round_number: 2,
        content: '整理最终回答。',
      },
      conversationKey,
    )
    chatStore.toggleMessageReasoning(chatStore.getLastMessage(conversationKey).id, 'agent-2', conversationKey)
    chatStore.completeLastMessageReasoning('agent-2', conversationKey)

    segment = chatStore.getLastMessage(conversationKey).reasoning[1]
    expect(segment.collapsed).toBe(true)
    expect(segment.user_toggled).toBe(true)
  })

  it('统一切换同一消息内的全部思考分段', () => {
    const chatStore = useChatStore()
    const conversationKey = chatStore.createConversation()
    chatStore.addMessage('assistant', '', conversationKey)

    chatStore.appendReasoningToLastMessage(
      { reasoning_id: 'agent-1', content: '第一段思考。' },
      conversationKey,
    )
    chatStore.appendReasoningToLastMessage(
      { reasoning_id: 'agent-2', content: '第二段思考。' },
      conversationKey,
    )

    const message = chatStore.getLastMessage(conversationKey)
    chatStore.toggleMessageReasoning(message.id, null, conversationKey)

    expect(message.reasoning.every((segment) => segment.collapsed)).toBe(true)
    expect(message.reasoning.every((segment) => segment.user_toggled)).toBe(true)
  })

  it('同一路径再次预览时使用最新文件内容', () => {
    const chatStore = useChatStore()
    chatStore.createConversation()

    chatStore.openPreview({
      path: '快速排序_实验报告.md',
      language: 'markdown',
      content: '旧内容',
    })
    chatStore.openPreview({
      path: '快速排序_实验报告.md',
      language: 'markdown',
      content: '修改后的内容',
    })

    expect(chatStore.previewTabs).toHaveLength(1)
    expect(chatStore.previewTabs[0].content).toBe('修改后的内容')
  })

  it('已打开文件被工具修改后实时更新预览内容', () => {
    const chatStore = useChatStore()
    const conversationKey = chatStore.createConversation()
    chatStore.addMessage('assistant', '', conversationKey)
    chatStore.openPreview({
      path: '快速排序_实验报告.md',
      language: 'markdown',
      content: '旧内容',
    })

    chatStore.addToolEventToLastMessage(
      {
        eventType: 'tool_result',
        payload: {
          tool_name: 'write_file',
          success: true,
          preview_path: '快速排序_实验报告.md',
          preview_language: 'markdown',
          preview_content: '修改后的内容',
        },
      },
      conversationKey,
    )

    expect(chatStore.previewTabs[0].content).toBe('修改后的内容')
  })

  it('后台对话输出完成后保留提示，进入对话时清除', async () => {
    const chatStore = useChatStore()
    const conversationKey = 'conversation-1'

    chatStore.setConversationStreaming(conversationKey, true)
    expect(chatStore.isConversationStreaming(conversationKey)).toBe(true)

    chatStore.markConversationComplete(conversationKey)
    chatStore.setConversationStreaming(conversationKey, false)
    expect(chatStore.hasConversationUnreadCompletion(conversationKey)).toBe(true)

    await chatStore.switchConversation(conversationKey)
    expect(chatStore.hasConversationUnreadCompletion(conversationKey)).toBe(false)
  })
})
