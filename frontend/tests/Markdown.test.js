/**
 * @author: caoshuai.cs
 * @date: 2026-07-26 01:32
 * @description: Markdown 渲染工具测试
 */
import { describe, expect, it } from 'vitest'
import { renderMarkdown } from '../src/utils/markdown'

describe('renderMarkdown', () => {
  it('使用独立容器包裹表格以支持横向滚动', () => {
    const html = renderMarkdown(
      '| 特性 | 传统版 | 增强版 |\n| --- | --- | --- |\n| 最坏情况 | O(n²) | O(n log n) |',
    )

    expect(html).toContain('<div class="markdown-table-wrapper"><table>')
    expect(html).toContain('</table></div>')
  })
})
