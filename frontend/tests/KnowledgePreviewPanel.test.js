/**
 * @author: caoshuai.cs
 * @date: 2026-08-02 18:36
 * @description: 知识库文件预览面板测试
 */
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import KnowledgePreviewPanel from '../src/components/KnowledgePreviewPanel.vue'

const mocks = vi.hoisted(() => ({
  downloadFile: vi.fn(),
}))

vi.mock('../src/api/knowledge', () => ({
  knowledgeApi: {
    downloadFile: mocks.downloadFile,
  },
}))

const mountPanel = (file) =>
  mount(KnowledgePreviewPanel, {
    props: { file },
    global: {
      directives: {
        tooltip: () => {},
      },
    },
  })

describe('KnowledgePreviewPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    mocks.downloadFile.mockReset()
  })

  it('安全渲染 Markdown 并转义原始 HTML', async () => {
    mocks.downloadFile.mockResolvedValue({
      data: new Blob(
        [
          [
            '---',
            'course_name: "实验课程"',
            'source_url: "https://example.com/course"',
            'license: "MIT"',
            '---',
            '',
            '# 实验说明',
            '',
            '- 用途：LabAgent 实验教学知识库',
            '- 清理：已移除图片、站点导航、构建配置、答案目录和重复内容',
            '',
            '<script>alert("xss")</script>',
          ].join('\n'),
        ],
        {
          type: 'text/markdown',
        },
      ),
    })

    const wrapper = mountPanel({ id: 1, file_name: '实验说明.md' })
    await flushPromises()
    await vi.waitFor(() => {
      expect(wrapper.find('h1').exists()).toBe(true)
    })

    expect(wrapper.find('h1').text()).toBe('实验说明')
    expect(wrapper.html()).not.toContain('<script>')
    expect(wrapper.text()).not.toContain('course_name')
    expect(wrapper.text()).not.toContain('source_url')
    expect(wrapper.text()).not.toContain('LabAgent 实验教学知识库')
    expect(wrapper.text()).not.toContain('已移除图片')
    expect(wrapper.text()).toContain('<script>alert("xss")</script>')
  })

  it('关闭 PDF 预览时回收 Blob URL', async () => {
    const createObjectURL = vi.fn(() => 'blob:knowledge-pdf')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    mocks.downloadFile.mockResolvedValue({
      data: new Blob(['pdf'], { type: 'application/pdf' }),
    })

    const wrapper = mountPanel({ id: 2, file_name: '实验手册.pdf' })
    await flushPromises()

    expect(wrapper.find('iframe').attributes('src')).toBe('blob:knowledge-pdf')
    wrapper.unmount()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:knowledge-pdf')
  })
})
