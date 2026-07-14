/**
 * @author: caoshuai.cs
 * @date: 2026-07-15 02:11
 * @description: Agent删除操作消息内联审批卡片测试
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ToolApprovalInline from '../src/components/ToolApprovalInline.vue'

const approval = {
  interrupt_id: 'int-1',
  risk_level: 'high',
  tool_calls: [
    {
      tool_call_id: 'call-1',
      tool_name: 'execute_shell',
      arguments: { commands: ['rm output/test.txt'] },
      risk_level: 'high',
    },
  ],
}

describe('ToolApprovalInline', () => {
  it('在消息内展示待批准的删除命令', () => {
    const wrapper = mount(ToolApprovalInline, { props: { approval } })

    expect(wrapper.text()).toContain('允许执行删除命令吗')
    expect(wrapper.text()).toContain('rm output/test.txt')
  })

  it('允许和拒绝按钮返回对应决策', async () => {
    const wrapper = mount(ToolApprovalInline, { props: { approval } })
    const buttons = wrapper.findAll('button')

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(wrapper.emitted('decision')).toEqual([[false], [true]])
  })
})
