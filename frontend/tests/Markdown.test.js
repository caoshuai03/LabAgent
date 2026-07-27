/**
 * @author: caoshuai.cs
 * @date: 2026-07-26 01:32
 * @description: Markdown 渲染工具测试
 */
import { describe, expect, it } from 'vitest'
import { renderMarkdown, stripTrailingArtifactCodeBlock } from '../src/utils/markdown'

describe('renderMarkdown', () => {
  it('使用独立容器包裹表格以支持横向滚动', () => {
    const html = renderMarkdown(
      '| 特性 | 传统版 | 增强版 |\n| --- | --- | --- |\n| 最坏情况 | O(n²) | O(n log n) |',
    )

    expect(html).toContain('<div class="markdown-table-wrapper"><table>')
    expect(html).toContain('</table></div>')
  })

  it('移除末尾重复展示产物路径的代码块', () => {
    const content = [
      '已按要求完成：',
      '',
      '文件名：`enhanced_quicksort.md`',
      '',
      '你可以在工作区中查看文件：',
      '',
      '```bash',
      'enhanced_quicksort.md',
      '```',
    ].join('\n')

    expect(stripTrailingArtifactCodeBlock(content, ['enhanced_quicksort.md'])).toBe(
      '已按要求完成：\n\n文件名：`enhanced_quicksort.md`',
    )
  })

  it('产物带子目录时允许按文件名清理尾部代码块', () => {
    const content = '已生成文档。\n\n```text\n平摊分析复习指南.md\n```'

    expect(stripTrailingArtifactCodeBlock(content, ['复习文档/平摊分析复习指南.md'])).toBe(
      '已生成文档。',
    )
  })

  it('不移除非产物路径的普通代码块', () => {
    const content = '示例命令：\n\n```bash\npytest\n```'

    expect(stripTrailingArtifactCodeBlock(content, ['enhanced_quicksort.md'])).toBe(content)
  })
})
