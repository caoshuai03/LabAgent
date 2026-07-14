/**
 * @author: caoshuai.cs
 * @date: 2026-07-15 02:11
 * @description: Agent命令执行与文件查看活动面板组件测试
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ToolActivityPanel from '../src/components/ToolActivityPanel.vue'

const shellEvents = [
  {
    eventType: 'tool_call',
    payload: {
      tool_call_id: 'call-shell',
      tool_name: 'execute_shell',
      arguments: { commands: 'ls -la' },
    },
  },
  {
    eventType: 'tool_result',
    payload: {
      tool_call_id: 'call-shell',
      tool_name: 'execute_shell',
      success: true,
      status: 'success',
      output_preview: '$ ls -la\ninput\noutput\ntmp',
    },
  },
]

describe('ToolActivityPanel', () => {
  it('展示命令活动标题和实际命令', () => {
    const wrapper = mount(ToolActivityPanel, { props: { toolEvents: shellEvents } })

    expect(wrapper.text()).toContain('运行了命令')
    expect(wrapper.text()).toContain('已运行')
    expect(wrapper.text()).toContain('ls -la')
  })

  it('点击Shell行后展开执行输出', async () => {
    const wrapper = mount(ToolActivityPanel, { props: { toolEvents: shellEvents } })

    expect(wrapper.find('.shell-detail').exists()).toBe(false)
    await wrapper.find('.activity-row.expandable').trigger('click')

    expect(wrapper.find('.shell-detail').exists()).toBe(true)
    expect(wrapper.find('.shell-detail').text()).toContain('input')
    expect(wrapper.find('.shell-detail').text()).toContain('output')
  })

  it('聚合文件查看和多条命令标题', () => {
    const wrapper = mount(ToolActivityPanel, {
      props: {
        toolEvents: [
          ...shellEvents,
          {
            eventType: 'tool_call',
            payload: {
              tool_call_id: 'call-shell-2',
              tool_name: 'execute_shell',
              arguments: { commands: 'pwd' },
            },
          },
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-shell-2',
              tool_name: 'execute_shell',
              success: true,
              status: 'success',
            },
          },
          {
            eventType: 'tool_call',
            payload: {
              tool_call_id: 'call-list',
              tool_name: 'list_directory',
              arguments: { dir_path: '.' },
            },
          },
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-list',
              tool_name: 'list_directory',
              success: true,
              status: 'success',
            },
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('查看了文件，运行了多个命令')
  })
})
