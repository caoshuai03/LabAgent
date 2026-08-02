/**
 * @author: caoshuai.cs
 * @date: 2026-07-15 03:30
 * @description: 聊天输入框停止生成功能测试
 */
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ChatInput from '../src/components/ChatInput.vue'
import { useChatStore } from '../src/stores/chat'
import {
  cancelReactAgent,
  compressConversation,
  sendReactAgentMessage,
  uploadChatImage,
} from '../src/api/chat'
import { getSkills } from '../src/api/skills'

vi.mock('../src/api/chat', () => ({
  cancelReactAgent: vi.fn(() => Promise.resolve({ data: { data: true } })),
  compressConversation: vi.fn(),
  getSessionTitle: vi.fn(),
  getUserSessions: vi.fn(() => Promise.resolve({ data: { data: [] } })),
  resumeReactAgent: vi.fn(),
  sendReactAgentMessage: vi.fn(),
  uploadChatImage: vi.fn(),
}))

vi.mock('../src/api/skills', () => ({
  getSkills: vi.fn(),
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
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:chat-image'),
      revokeObjectURL: vi.fn(),
    })
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
          clickOutside: () => {},
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

  it('支持选择图片后随消息上传并发送多模态元数据', async () => {
    sendReactAgentMessage.mockReturnValue({ abort: vi.fn() })
    uploadChatImage.mockResolvedValue({
      data: {
        code: 0,
        data: {
          image_id: 'a'.repeat(32),
          file_name: '实验截图.png',
          content_type: 'image/png',
          size: 8,
        },
      },
    })

    const chatStore = useChatStore()
    chatStore.createConversation()
    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
          clickOutside: () => {},
        },
      },
    })
    const file = new File([new Uint8Array(8)], '实验截图.png', { type: 'image/png' })
    Object.defineProperty(wrapper.find('.image-file-input').element, 'files', {
      configurable: true,
      value: [file],
    })
    await wrapper.find('.image-file-input').trigger('change')
    await wrapper.find('textarea').setValue('分析这张图')
    await wrapper.find('.send-button').trigger('click')

    expect(uploadChatImage).toHaveBeenCalledWith(file)
    expect(sendReactAgentMessage.mock.calls[0][0]).toMatchObject({
      message: '分析这张图',
      images: [
        {
          image_id: 'a'.repeat(32),
          file_name: '实验截图.png',
          content_type: 'image/png',
          size: 8,
        },
      ],
    })
    expect(chatStore.messages[0].images[0].preview_url).toBe('blob:chat-image')
  })

  it('支持从剪贴板粘贴图片', async () => {
    const chatStore = useChatStore()
    chatStore.createConversation()
    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
          clickOutside: () => {},
        },
      },
    })
    const file = new File([new Uint8Array(8)], 'clipboard.png', { type: 'image/png' })
    await wrapper.find('textarea').trigger('paste', {
      clipboardData: {
        items: [
          {
            kind: 'file',
            type: 'image/png',
            getAsFile: () => file,
          },
        ],
      },
    })

    expect(wrapper.findAll('.pending-image')).toHaveLength(1)
    expect(URL.createObjectURL).toHaveBeenCalledWith(file)
  })

  it('第一次回车选择技能，输入任务后再次回车才发送', async () => {
    getSkills.mockResolvedValue({
      data: {
        data: [
          {
            name: 'java-debug-helper',
            description: '分析 Java 异常并给出排查建议',
          },
        ],
      },
    })
    sendReactAgentMessage.mockReturnValue({ abort: vi.fn() })
    const chatStore = useChatStore()
    chatStore.createConversation()
    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
          clickOutside: () => {},
        },
      },
    })

    await wrapper.find('textarea').setValue('已有问题 /')
    await flushPromises()
    expect(getSkills).toHaveBeenCalledOnce()
    expect(wrapper.find('.slash-command-menu').exists()).toBe(true)
    expect(wrapper.find('.compact-button').exists()).toBe(false)
    expect(wrapper.find('.send-button').classes()).toContain('disabled-btn')

    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })

    expect(sendReactAgentMessage).not.toHaveBeenCalled()
    expect(wrapper.find('.selected-skill').text()).toContain('java-debug-helper')
    expect(wrapper.find('.selected-skill .tool-activity-icon').exists()).toBe(true)
    expect(wrapper.find('.input-editor-line').element.lastElementChild.tagName).toBe('TEXTAREA')
    expect(wrapper.find('textarea').element.value).toBe('已有问题')

    await wrapper.find('textarea').setValue('已有问题，分析这个空指针异常')
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })

    expect(sendReactAgentMessage.mock.calls[0][0]).toMatchObject({
      message: '已有问题，分析这个空指针异常',
      skillNames: ['java-debug-helper'],
    })
    expect(chatStore.messages[0].skillNames).toEqual(['java-debug-helper'])
  })

  it('只有输入开头或空白字符后的斜杠才打开命令菜单', async () => {
    getSkills.mockResolvedValue({ data: { data: [] } })
    const chatStore = useChatStore()
    chatStore.createConversation()
    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
          clickOutside: () => {},
        },
      },
    })

    await wrapper.find('textarea').setValue('dha./')
    await flushPromises()
    expect(wrapper.find('.slash-command-menu').exists()).toBe(false)

    await wrapper.find('textarea').setValue('dha. /')
    await flushPromises()
    expect(wrapper.find('.slash-command-menu').exists()).toBe(true)
  })

  it('从斜杠菜单选择压缩会调用现有主动压缩接口', async () => {
    getSkills.mockResolvedValue({ data: { data: [] } })
    compressConversation.mockResolvedValue({
      data: {
        data: {
          compressed: false,
          before_tokens: 10,
          after_tokens: 10,
        },
      },
    })
    const chatStore = useChatStore()
    const draftKey = chatStore.createConversation()
    const sessionId = '00000000-0000-0000-0000-000000000001'
    chatStore.setCurrentSessionId(sessionId, draftKey)
    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
          clickOutside: () => {},
        },
      },
    })

    await wrapper.find('textarea').setValue('/')
    await flushPromises()
    const compressButton = wrapper
      .findAll('.menu-item')
      .find((button) => button.text().includes('压缩上下文'))
    await compressButton.trigger('click')
    await flushPromises()

    expect(compressConversation).toHaveBeenCalledWith(sessionId)
    expect(wrapper.find('textarea').element.value).toBe('')
    expect(chatStore.compactionStatus).toBe('')
  })

  it('主动压缩期间和成功后更新当前会话的压缩状态', async () => {
    getSkills.mockResolvedValue({ data: { data: [] } })
    let resolveCompression
    compressConversation.mockReturnValue(
      new Promise((resolve) => {
        resolveCompression = resolve
      }),
    )
    const chatStore = useChatStore()
    const draftKey = chatStore.createConversation()
    const sessionId = '00000000-0000-0000-0000-000000000002'
    chatStore.setCurrentSessionId(sessionId, draftKey)
    chatStore.addMessage('assistant', '待压缩的历史消息', sessionId)
    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
          clickOutside: () => {},
        },
      },
    })

    await wrapper.find('textarea').setValue('/')
    await flushPromises()
    const compressButton = wrapper
      .findAll('.menu-item')
      .find((button) => button.text().includes('压缩上下文'))
    await compressButton.trigger('click')

    expect(chatStore.compactionStatus).toBe('compressing')
    expect(chatStore.compactionAfterMessageId).toBe(chatStore.messages[0].id)

    resolveCompression({
      data: {
        data: {
          compressed: true,
          before_tokens: 12000,
          after_tokens: 3000,
        },
      },
    })
    await flushPromises()

    expect(chatStore.compactionStatus).toBe('compressed')
  })

  it('技能加载期间按回车不会把斜杠作为普通消息发送', async () => {
    let resolveSkills
    getSkills.mockReturnValue(
      new Promise((resolve) => {
        resolveSkills = resolve
      }),
    )
    const chatStore = useChatStore()
    chatStore.createConversation()
    const wrapper = mount(ChatInput, {
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
          clickOutside: () => {},
        },
      },
    })

    await wrapper.find('textarea').setValue('/')
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' })

    expect(sendReactAgentMessage).not.toHaveBeenCalled()
    resolveSkills({ data: { data: [] } })
    await flushPromises()
  })
})
