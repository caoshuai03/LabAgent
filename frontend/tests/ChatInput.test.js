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
import { cancelReactAgent, sendReactAgentMessage, uploadChatImage } from '../src/api/chat'

vi.mock('../src/api/chat', () => ({
  cancelReactAgent: vi.fn(() => Promise.resolve({ data: { data: true } })),
  getUserSessions: vi.fn(() => Promise.resolve({ data: { data: [] } })),
  resumeReactAgent: vi.fn(),
  sendReactAgentMessage: vi.fn(),
  uploadChatImage: vi.fn(),
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
})
