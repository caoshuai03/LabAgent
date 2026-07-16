import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { escapeHtml } from './html'

// 配置 markdown-it
const md = new MarkdownIt({
  html: true, // 允许 HTML 标签
  linkify: true, // 自动将 URL 转换为链接
  typographer: true, // 启用一些语言中性的替换 + 引号美化
  breaks: false, // 将换行符转换为 <br>
})

// 关闭模糊链接识别：避免把「冒泡排序思考.md」「bubble_sort.py」等文件名（.md/.py 恰是真实顶级域名）
// 误判成外链，从而抢占产物路径超链接并触发错误跳转；仅保留带 http(s):// 协议的显式链接自动识别
md.linkify.set({ fuzzyLink: false, fuzzyEmail: false })

// 自定义代码块渲染规则，避免 markdown-it 自动包裹 <pre>
md.renderer.rules.fence = function (tokens, idx) {
  const token = tokens[idx]
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : ''
  const lang = info.split(/\s+/g)[0]
  const content = token.content

  let highlighted = ''
  if (lang && hljs.getLanguage(lang)) {
    try {
      highlighted = hljs.highlight(content, { language: lang, ignoreIllegals: true }).value
    } catch {
      highlighted = ''
    }
  }

  if (!highlighted) {
    highlighted = escapeHtml(content)
  }

  const langLabel = lang || 'text'
  // 添加 highlight.js 的语言类名
  const codeClass = lang ? `language-${lang}` : ''

  return `<div class="code-block-wrapper"><div class="code-block-header"><span class="code-block-lang">${langLabel}</span></div><pre class="hljs"><code class="${codeClass}">${highlighted}</code></pre></div>\n`
}

// 渲染 Markdown 为 HTML
export const renderMarkdown = (content) => {
  if (!content) return ''
  return md.render(content)
}
