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
})
