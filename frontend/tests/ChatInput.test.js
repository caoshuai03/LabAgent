/**
 * @author: caoshuai.cs
 * @date: 2026-07-15 03:30
 * @description: 聊天输入框停止生成功能测试
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChatInput from '../src/components/ChatInput.vue'
import { useChatStore } from '../src/stores/chat'
import { cancelReactAgent, sendReactAgentMessage } from '../src/api/chat'

vi.mock('../src/api/chat', () => ({
  cancelReactAgent: vi.fn(() => Promise.resolve({ data: { data: true } })),
  getUserSessions: vi.fn(() => Promise.resolve({ data: { data: [] } })),
  resumeReactAgent: vi.fn(),
  sendReactAgentMessage: vi.fn(),
}))

describe('ChatInput', () => {
  let pinia

  beforeEach(() => {
    vi.clearAllMocks()
    pinia = createPinia()
    setActivePinia(pinia)
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
      setItem: vi.fn(),
    })
    vi.stubGlobal('requestAnimationFrame', (callback) => {
      callback()
      return 1
    })
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
  })

  it('点击停止按钮会中断当前会话的流式请求', async () => {
    const abort = vi.fn()
    sendReactAgentMessage.mockReturnValue({ abort })

    const chatStore = useChatStore()
    chatStore.createConversation()

    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
        },
      },
    })

    await wrapper.find('textarea').setValue('测试停止生成')
    await wrapper.find('.send-button').trigger('click')
    const callbacks = sendReactAgentMessage.mock.calls[0][1]
    callbacks.onMessage({
      event_type: 'session',
      session_id: 'session-1',
      trace_id: 'trace-1',
      payload: { session_id: 'session-1' },
    })
    await wrapper.find('.stop-button').trigger('click')

    expect(abort).toHaveBeenCalledOnce()
    expect(cancelReactAgent).toHaveBeenCalledWith({ sessionId: 'session-1', traceId: 'trace-1' })
    expect(chatStore.isStreaming).toBe(false)
  })
})
