/**
 * @author: caoshuai.cs
 * @date: 2026-07-15 02:11
 * @description: Agent命令执行与文件查看活动面板组件测试
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ToolActivityPanel from '../src/components/ToolActivityPanel.vue'
import ToolActivityIcon from '../src/components/icons/ToolActivityIcon.vue'

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
  it.each([
    ['skill:lab-report-writer', '.tool-icon-sparkles'],
    ['read_skill_resource', '.tool-icon-book-open'],
    ['search_knowledge_base', '.tool-icon-database-search'],
    ['write_file', '.tool-icon-file-pen'],
    ['execute_shell', '.tool-icon-terminal'],
    ['global_timeout', '.tool-icon-clock-alert'],
    ['unknown_tool', '.tool-icon-wrench'],
  ])('%s 使用对应的工具活动图标', (toolName, iconSelector) => {
    const wrapper = mount(ToolActivityIcon, { props: { toolName } })

    expect(wrapper.find(iconSelector).exists()).toBe(true)
  })

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

  it('Skill 激活置顶、使用专属图标并隐藏成功的资源读取', () => {
    const wrapper = mount(ToolActivityPanel, {
      props: {
        toolEvents: [
          {
            eventType: 'tool_call',
            payload: {
              tool_call_id: 'call-search',
              tool_name: 'search_knowledge_base',
              arguments: { query: '快速排序实验' },
            },
          },
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-search',
              tool_name: 'search_knowledge_base',
              success: false,
              status: 'failed',
              result_summary: '知识库检索失败，已降级',
            },
          },
          {
            eventType: 'tool_call',
            payload: {
              tool_call_id: 'call-activate-skill',
              tool_name: 'activate_skill',
              arguments: { name: 'lab-report-writer' },
            },
          },
          {
            eventType: 'status',
            payload: {
              tool_call_id: 'call-activate-skill',
              tool_name: 'activate_skill',
              stage: 'tool_running',
            },
          },
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-activate-skill',
              tool_name: 'activate_skill',
              success: true,
              status: 'success',
              result_summary: 'Skill lab-report-writer 已激活',
            },
          },
          {
            eventType: 'skill_loaded',
            payload: {
              tool_call_id: 'call-activate-skill',
              skills: [{ name: 'lab-report-writer', description: '实验报告写作' }],
            },
          },
          {
            eventType: 'tool_call',
            payload: {
              tool_call_id: 'call-read-skill-resource',
              tool_name: 'read_skill_resource',
              arguments: {
                name: 'lab-report-writer',
                resource_path: 'references/report-checklist.md',
              },
            },
          },
          {
            eventType: 'tool_result',
            payload: {
              tool_call_id: 'call-read-skill-resource',
              tool_name: 'read_skill_resource',
              success: true,
              status: 'success',
              result_summary: '已读取 Skill 资源 references/report-checklist.md',
            },
          },
        ],
      },
    })

    const activityItems = wrapper.findAll('.activity-item')
    expect(activityItems).toHaveLength(2)
    expect(activityItems[0].text()).toContain('加载 Skill')
    expect(activityItems[0].text()).toContain('lab-report-writer')
    expect(activityItems[0].find('.skill-activity-icon').exists()).toBe(true)
    expect(activityItems[1].text()).toContain('知识库检索失败，已降级')
    expect(wrapper.find('.activity-group-title').text()).toBe('执行了工具操作')
    expect(wrapper.find('.activity-group-title').text()).not.toContain('失败')
    expect(wrapper.text()).toContain('加载 Skill')
    expect(wrapper.text()).toContain('lab-report-writer')
    expect(wrapper.text()).not.toContain('已完成')
    expect(wrapper.text()).not.toContain('report-checklist.md')
  })
})
