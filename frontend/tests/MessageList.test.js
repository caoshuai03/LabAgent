/**
 * @author: caoshuai.cs
 * @date: 2026-07-31 00:00
 * @description: 消息列表会话滚动位置与置底按钮测试
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, KeepAlive, nextTick, ref } from 'vue'
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

  it('切换到其他组件后暂停自动滚动，返回时恢复原阅读位置', async () => {
    const chatStore = useChatStore()
    chatStore.createConversation()
    chatStore.addMessage('assistant', '初始回答')
    const showChat = ref(true)
    const KeepAliveHarness = defineComponent({
      setup() {
        return () => h(
          KeepAlive,
          null,
          () => (showChat.value ? h(MessageList) : h('div', '知识库')),
        )
      },
    })
    const wrapper = mount(KeepAliveHarness, {
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

    showChat.value = false
    await nextTick()
    messageList.element.scrollTop = 0
    chatStore.updateLastMessage('初始回答，后台继续输出')
    await nextTick()

    showChat.value = true
    await nextTick()
    await new Promise((resolve) => window.requestAnimationFrame(resolve))

    expect(wrapper.find('.message-list').element.scrollTop).toBe(260)
    expect(wrapper.find('.scroll-to-bottom-button').exists()).toBe(true)
  })

  it('在其他组件选择历史会话后，返回时恢复目标会话的阅读位置', async () => {
    const chatStore = useChatStore()
    const firstConversationKey = chatStore.createConversation()
    chatStore.addMessage('assistant', '第一条会话')
    const showChat = ref(true)
    const KeepAliveHarness = defineComponent({
      setup() {
        return () => h(
          KeepAlive,
          null,
          () => (showChat.value ? h(MessageList) : h('div', '知识库')),
        )
      },
    })
    const wrapper = mount(KeepAliveHarness, {
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
      scrollHeight: 1400,
      clientHeight: 400,
      scrollTop: 260,
    })
    await messageList.trigger('scroll')

    const secondConversationKey = chatStore.createConversation()
    chatStore.addMessage('assistant', '第二条会话')
    await nextTick()
    setScrollMetrics(messageList.element, {
      scrollHeight: 1600,
      clientHeight: 400,
      scrollTop: 430,
    })
    await messageList.trigger('scroll')
    await chatStore.switchConversation(firstConversationKey)
    await nextTick()

    showChat.value = false
    await nextTick()
    setScrollMetrics(messageList.element, {
      scrollHeight: 0,
      clientHeight: 0,
      scrollTop: 0,
    })
    await chatStore.switchConversation(secondConversationKey)
    await nextTick()

    showChat.value = true
    await nextTick()
    setScrollMetrics(messageList.element, {
      scrollHeight: 1600,
      clientHeight: 400,
      scrollTop: 0,
    })
    await new Promise((resolve) => window.requestAnimationFrame(resolve))
    await nextTick()

    expect(wrapper.find('.message-list').element.scrollTop).toBe(430)
    expect(wrapper.find('.scroll-to-bottom-button').exists()).toBe(true)
  })

  it('流式输出时离开底部超过阈值后停止自动置底', async () => {
    const chatStore = useChatStore()
    chatStore.createConversation()
    chatStore.addMessage('assistant', '初始回答')

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
      scrollTop: 800,
    })
    await messageList.trigger('scroll')

    messageList.element.scrollTop = 798
    await messageList.trigger('scroll')

    Object.defineProperty(messageList.element, 'scrollHeight', {
      configurable: true,
      value: 1400,
    })
    chatStore.updateLastMessage('初始回答，继续输出')
    await nextTick()
    await nextTick()

    expect(messageList.element.scrollTop).toBe(798)
    expect(wrapper.find('.scroll-to-bottom-button').exists()).toBe(true)
  })

  it('思考内容流式增长时保持置底，直到用户主动向上滚动', async () => {
    const chatStore = useChatStore()
    chatStore.createConversation()
    chatStore.addMessage('assistant', '')

    const wrapper = mount(MessageList, {
      global: {
        plugins: [pinia],
        stubs: {
          MessageItem: {
            props: ['message'],
            template: '<div>{{ message.reasoning?.[0]?.content }}</div>',
          },
        },
      },
    })
    const messageList = wrapper.find('.message-list')
    setScrollMetrics(messageList.element, {
      scrollHeight: 1200,
      clientHeight: 400,
      scrollTop: 800,
    })
    await messageList.trigger('scroll')

    Object.defineProperty(messageList.element, 'scrollHeight', {
      configurable: true,
      value: 1400,
    })
    chatStore.appendReasoningToLastMessage({
      reasoning_id: 'agent-1',
      content: '正在分析截图内容。',
    })
    await nextTick()
    await nextTick()

    expect(messageList.element.scrollTop).toBe(1400)
    expect(wrapper.find('.scroll-to-bottom-button').exists()).toBe(false)

    messageList.element.scrollTop = 998
    await messageList.trigger('scroll')
    Object.defineProperty(messageList.element, 'scrollHeight', {
      configurable: true,
      value: 1600,
    })
    chatStore.appendReasoningToLastMessage({
      reasoning_id: 'agent-1',
      content: '继续分析。',
    })
    await nextTick()
    await nextTick()

    expect(messageList.element.scrollTop).toBe(998)
    expect(wrapper.find('.scroll-to-bottom-button').exists()).toBe(true)
  })

  it('压缩期间显示状态，并在完成后将分隔线保留在压缩边界', async () => {
    const chatStore = useChatStore()
    const conversationKey = chatStore.createConversation()
    const historyMessage = chatStore.addMessage('assistant', '较早的历史消息')
    chatStore.setConversationCompactionStatus(
      conversationKey,
      'compressing',
      historyMessage.id,
    )

    const wrapper = mount(MessageList, {
      global: {
        plugins: [pinia],
        stubs: {
          MessageItem: {
            props: ['message'],
            template: '<div class="stub-message">{{ message.content }}</div>',
          },
        },
      },
    })

    expect(wrapper.find('.compaction-divider').text()).toBe('历史对话压缩中')
    expect(wrapper.find('.compaction-divider').classes()).toContain('is-compressing')

    chatStore.setConversationCompactionStatus(conversationKey, 'compressed')
    chatStore.addMessage('user', '压缩完成后的新消息')
    await nextTick()

    const children = wrapper.find('.message-list').element.children
    expect(wrapper.find('.compaction-divider').text()).toBe('历史对话已被压缩')
    expect(wrapper.find('.compaction-divider').classes()).toContain('is-compressed')
    expect(children[1].classList).toContain('compaction-divider')
    expect(children[2].textContent).toContain('压缩完成后的新消息')
  })
})
