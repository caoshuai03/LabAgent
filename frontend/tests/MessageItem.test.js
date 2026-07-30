/**
 * @author: caoshuai.cs
 * @date: 2026-07-31 01:30
 * @description: 用户消息操作按钮测试
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MessageItem from '../src/components/MessageItem.vue'
import { useChatStore } from '../src/stores/chat'

describe('MessageItem', () => {
  let pinia
  let writeText

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
      setItem: vi.fn(),
    })
    writeText = vi.fn(() => Promise.resolve())
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
  })

  it('用户消息提供右侧操作区的复制按钮', async () => {
    const wrapper = mount(MessageItem, {
      props: {
        message: {
          id: 'user-message-1',
          sender: 'user',
          content: '需要复制的用户消息',
          timestamp: '2026-07-31T01:30:00Z',
        },
      },
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
        },
      },
    })

    const copyButton = wrapper.find('.message-actions .action-button')
    expect(copyButton.exists()).toBe(true)
    expect(wrapper.find('.message-time').exists()).toBe(false)

    await copyButton.trigger('click')
    expect(writeText).toHaveBeenCalledWith('需要复制的用户消息')
  })

  it('点击正文图片会在右侧预览面板打开', async () => {
    const chatStore = useChatStore()
    chatStore.createConversation()
    const wrapper = mount(MessageItem, {
      props: {
        message: {
          id: 'user-message-image',
          sender: 'user',
          content: '查看图片',
          images: [
            {
              image_id: 'image-1',
              file_name: '实验截图.png',
              preview_url: 'blob:experiment-image',
            },
          ],
        },
      },
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
        },
      },
    })

    await wrapper.find('.message-image-link').trigger('click')

    expect(chatStore.previewPanelOpen).toBe(true)
    expect(chatStore.previewTabs[0]).toMatchObject({
      path: 'chat-image/image-1',
      preview_type: 'image',
      image_url: 'blob:experiment-image',
      download_name: '实验截图.png',
    })
  })
})
