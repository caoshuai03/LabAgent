/**
 * @author: caoshuai.cs
 * @date: 2026-07-31 00:00
 * @description: 消息列表会话滚动位置与置底按钮测试
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MessageList from '../src/components/MessageList.vue'
import { useChatStore } from '../src/stores/chat'

vi.mock('../src/api/chat', () => ({
  deleteSession: vi.fn(),
  deleteSessions: vi.fn(),
  getSessionHistory: vi.fn(),
  getUserSessions: vi.fn(),
}))

describe('MessageList', () => {
  let pinia

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
      setItem: vi.fn(),
    })
  })

  const setScrollMetrics = (element, { scrollHeight, clientHeight, scrollTop }) => {
    Object.defineProperty(element, 'scrollHeight', {
      configurable: true,
      value: scrollHeight,
    })
    Object.defineProperty(element, 'clientHeight', {
      configurable: true,
      value: clientHeight,
    })
    element.scrollTop = scrollTop
  }

  it('切换会话后恢复该会话上次的阅读位置并立即显示置底按钮', async () => {
    const chatStore = useChatStore()
    const firstConversationKey = chatStore.createConversation()
    chatStore.addMessage({
      id: 'first-message',
      sender: 'assistant',
      content: '第一条会话消息',
    })

    const wrapper = mount(MessageList, {
      global: {
        plugins: [pinia],
        stubs: {
          MessageItem: {
            props: ['message'],
            template: '<div>{{ message.content }}</div>',
          },
        },
      },
    })
    const messageList = wrapper.find('.message-list')
    setScrollMetrics(messageList.element, {
      scrollHeight: 1200,
      clientHeight: 400,
      scrollTop: 260,
    })
    await messageList.trigger('scroll')

    const secondConversationKey = chatStore.createConversation()
    await nextTick()
    await chatStore.switchConversation(firstConversationKey)
    await nextTick()

    expect(secondConversationKey).not.toBe(firstConversationKey)
    expect(messageList.element.scrollTop).toBe(260)
    expect(wrapper.find('.scroll-to-bottom-button').exists()).toBe(true)
  })
})
