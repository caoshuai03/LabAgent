/**
 * @author: caoshuai.cs
 * @date: 2026-07-31 01:30
 * @description: 用户消息操作按钮测试
 */
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MessageItem from '../src/components/MessageItem.vue'
import router from '../src/router'
import { useChatStore } from '../src/stores/chat'

describe('MessageItem', () => {
  let pinia
  let writeText
  let scrollIntoView

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
    scrollIntoView = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
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

  it('引用来源显示文件名和章节路径并保留摘要原文', () => {
    const wrapper = mount(MessageItem, {
      props: {
        message: {
          id: 'assistant-message-source-path',
          sender: 'assistant',
          content: '回答内容',
          sources: [
            {
              file_name: '04-线性神经网络.md',
              course_name: '动手学深度学习',
              chapter_name: '线性回归',
              section_name: '损失函数',
              snippet: '## 平方损失用于衡量预测值与真实值之间的误差。',
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

    expect(wrapper.find('.source-index').text()).toBe('[1]')
    expect(wrapper.find('.source-name').text()).toBe('04-线性神经网络.md / 线性回归 / 损失函数')
    expect(wrapper.find('.source-snippet').text()).toBe(
      '## 平方损失用于衡量预测值与真实值之间的误差。',
    )
  })

  it('正文以圆形序号展示引用，点击后滚动到对应引用来源', async () => {
    const routerPush = vi.spyOn(router, 'push').mockResolvedValue()
    const wrapper = mount(MessageItem, {
      props: {
        message: {
          id: 'assistant-message-citation-link',
          sender: 'assistant',
          content: '动量法可以加速收敛。[资料S026e0624]',
          sources: [
            {
              citation_id: 'S026e0624',
              file_name: '11-优化算法.md',
              snippet: '实际实验让我们来看看动量法如何运作。',
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

    await vi.waitFor(() => expect(wrapper.find('.citation-index').exists()).toBe(true))
    expect(wrapper.find('.citation-index').text()).toBe('1')
    expect(wrapper.find('.citation-index').attributes('aria-label')).toBe('查看引用来源 1')

    await wrapper.find('.citation-index').trigger('click')
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    expect(routerPush).not.toHaveBeenCalled()

    await wrapper.find('.source-item').trigger('click')
    expect(routerPush).toHaveBeenCalledWith({
      name: 'Knowledge',
      query: { file_name: '11-优化算法.md' },
    })
  })
})
