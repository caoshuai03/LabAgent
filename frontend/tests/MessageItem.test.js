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

  it('用户消息在复制按钮左侧显示时间', async () => {
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
    const messageTime = wrapper.find('.message-actions .message-time')
    expect(copyButton.exists()).toBe(true)
    expect(messageTime.text()).toBe('9:30')
    expect(messageTime.element.nextElementSibling).toBe(copyButton.element)

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

  it('用户消息显示主动选择的技能和正文', () => {
    const wrapper = mount(MessageItem, {
      props: {
        message: {
          id: 'user-message-skill',
          sender: 'user',
          content: '分析这个空指针异常',
          skillNames: ['java-debug-helper'],
        },
      },
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
        },
      },
    })

    expect(wrapper.find('.message-skill').text()).toContain('java-debug-helper')
    expect(wrapper.find('.message-skill .tool-activity-icon').exists()).toBe(true)
    expect(wrapper.find('.user-message-body .message-text').text()).toBe('分析这个空指针异常')
  })

  it('引用来源超过五条时默认折叠并支持展开和收起', async () => {
    const wrapper = mount(MessageItem, {
      props: {
        message: {
          id: 'assistant-message-sources',
          sender: 'assistant',
          content: '回答内容',
          sources: Array.from({ length: 7 }, (_, index) => ({
            file_name: `source-${index + 1}.md`,
            snippet: `引用片段 ${index + 1}`,
          })),
        },
      },
      global: {
        plugins: [pinia],
        directives: {
          tooltip: () => {},
        },
      },
    })

    expect(wrapper.findAll('.source-item')).toHaveLength(5)
    expect(wrapper.find('.sources-toggle').text()).toBe('')
    expect(wrapper.find('.sources-toggle').attributes('aria-label')).toBe('展开 2 条引用')
    expect(wrapper.find('.sources-toggle').attributes('aria-expanded')).toBe('false')

    await wrapper.find('.sources-toggle').trigger('click')
    expect(wrapper.findAll('.source-item')).toHaveLength(7)
    expect(wrapper.find('.sources-toggle').attributes('aria-label')).toBe('收起引用')
    expect(wrapper.find('.sources-toggle').attributes('aria-expanded')).toBe('true')

    await wrapper.find('.sources-toggle').trigger('click')
    expect(wrapper.findAll('.source-item')).toHaveLength(5)
  })
})
