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

  it('使用 KaTeX 渲染行内公式和块级公式', () => {
    const html = renderMarkdown(
      '注意力权重为 $\\alpha_{ij}=\\frac{\\exp(a_{ij})}{\\sum_l\\exp(a_{il})}$。\n\n$$\\text{MultiHead}(Q,K,V)=\\text{Concat}(head_1,\\ldots,head_h)W^O$$',
    )

    expect(html).toContain('<eq><span class="katex">')
    expect(html).toContain('<eqn><span class="katex-display">')
    expect(html).not.toContain('$\\alpha_{ij}')
  })

  it('支持括号形式的公式分隔符', () => {
    const html = renderMarkdown('行内公式 \\(x_i\\)，块级公式：\n\n\\[x^2+y^2=z^2\\]')

    expect(html).toContain('<eq><span class="katex">')
    expect(html).toContain('<eqn><span class="katex-display">')
  })

  it('规范化 Pandoc 风格的代码块语言并启用语法高亮', () => {
    const html = renderMarkdown('```{.python}\nprint("LabAgent")\n```')

    expect(html).toContain('<span class="code-block-lang">Python</span>')
    expect(html).toContain('<code class="language-python">')
    expect(html).toContain('<span class="hljs-built_in">print</span>')
    expect(html).not.toContain('{.python}')
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
