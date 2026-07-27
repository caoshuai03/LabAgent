/**
 * @author: caoshuai.cs
 * @date: 2026-07-26
 * @description: 主Agent思考过程展示与折叠组件测试
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ReasoningPanel from '../src/components/ReasoningPanel.vue'

describe('ReasoningPanel', () => {
  it('展示当前思考内容，并允许用户手动折叠', async () => {
    const wrapper = mount(ReasoningPanel, {
      props: {
        reasoning: [
          {
            reasoning_id: 'agent-2',
            round_number: 2,
            content: '正在比对知识库中的实验要求。',
            is_complete: false,
            collapsed: false,
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('正在思考')
    expect(wrapper.text()).toContain('正在比对知识库中的实验要求。')
    await wrapper.find('.reasoning-header').trigger('click')
    expect(wrapper.emitted('toggle')).toEqual([['agent-2']])
  })

  it('已完成的思考保留折叠状态', () => {
    const wrapper = mount(ReasoningPanel, {
      props: {
        reasoning: [
          {
            reasoning_id: 'agent-1',
            round_number: 1,
            content: '已完成分析。',
            is_complete: true,
            collapsed: true,
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('已思考完成')
    expect(wrapper.find('.reasoning-header').attributes('aria-expanded')).toBe('false')
  })
})
