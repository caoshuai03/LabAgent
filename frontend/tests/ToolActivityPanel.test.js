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

  it('写入文件仅展示结果行，不在工具区重复展开文件正文', async () => {
    const wrapper = mount(ToolActivityPanel, {
      props: {
        toolEvents: [
          {
            eventType: 'tool_call',
            payload: {
              tool_call_id: 'call-write',
              tool_name: 'write_file',
              arguments: { file_path: '复习文档/平摊分析复习指南.md' },
            },
          },
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-write',
              tool_name: 'write_file',
              success: true,
              status: 'success',
              preview_path: '复习文档/平摊分析复习指南.md',
              preview_content: '# 平摊分析复习指南',
              preview_language: 'markdown',
            },
          },
        ],
      },
    })

    const activityRow = wrapper.find('.activity-row')
    expect(wrapper.text()).toContain('已写入')
    expect(wrapper.text()).toContain('平摊分析复习指南.md')
    expect(activityRow.classes()).not.toContain('expandable')

    await activityRow.trigger('click')
    expect(wrapper.find('.file-preview').exists()).toBe(false)
  })

  it('部分工具被拒绝时使用汇总标题并在完成后默认折叠', () => {
    const wrapper = mount(ToolActivityPanel, {
      props: {
        completed: true,
        toolEvents: [
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-search',
              tool_name: 'file_search',
              success: true,
              status: 'success',
              result_summary: '命中 3 条知识库资料',
            },
          },
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-write-rejected',
              tool_name: 'write_file',
              success: false,
              status: 'rejected',
              error_message: '用户拒绝覆盖已有文件',
              preview_path: '平摊分析复习指南.md',
            },
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('运行了多个命令')
    expect(wrapper.text()).not.toContain('原因：')
    expect(wrapper.find('.activity-group-header').attributes('aria-expanded')).toBe('false')
  })
})
