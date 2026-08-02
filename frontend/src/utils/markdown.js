import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import katex from 'katex'
import texmath from 'markdown-it-texmath'
import { escapeHtml } from './html'

// 配置 markdown-it
const md = new MarkdownIt({
  html: true, // 允许 HTML 标签
  linkify: true, // 自动将 URL 转换为链接
  typographer: true, // 启用一些语言中性的替换 + 引号美化
  breaks: false, // 将换行符转换为 <br>
})

md.use(texmath, {
  engine: katex,
  delimiters: ['dollars', 'brackets'],
  katexOptions: {
    throwOnError: false,
    trust: false,
  },
})

// 关闭模糊链接识别：避免把「冒泡排序思考.md」「bubble_sort.py」等文件名（.md/.py 恰是真实顶级域名）
// 误判成外链，从而抢占产物路径超链接并触发错误跳转；仅保留带 http(s):// 协议的显式链接自动识别
md.linkify.set({ fuzzyLink: false, fuzzyEmail: false })

// 表格由外层容器负责横向滚动，保留 table 原生布局，避免窄屏时列宽被破坏
md.renderer.rules.table_open = () => '<div class="markdown-table-wrapper"><table>\n'
md.renderer.rules.table_close = () => '</table></div>\n'

const languageLabels = {
  bash: 'Bash',
  css: 'CSS',
  html: 'HTML',
  java: 'Java',
  javascript: 'JavaScript',
  js: 'JavaScript',
  json: 'JSON',
  py: 'Python',
  python: 'Python',
  sh: 'Shell',
  shell: 'Shell',
  sql: 'SQL',
  text: 'Text',
  ts: 'TypeScript',
  typescript: 'TypeScript',
  txt: 'Text',
  yaml: 'YAML',
  yml: 'YAML',
}

const normalizeFenceLanguage = (info) => {
  const pandocLanguage = info.match(/^\{\s*\.([a-zA-Z0-9_+-]+)/)?.[1]
  const candidate = pandocLanguage || info.split(/\s+/g)[0]?.replace(/^\./, '')
  if (!candidate || !/^[a-zA-Z0-9_+-]+$/.test(candidate)) return ''
  return candidate.toLowerCase()
}

// 自定义代码块渲染规则，避免 markdown-it 自动包裹 <pre>
md.renderer.rules.fence = function (tokens, idx) {
  const token = tokens[idx]
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : ''
  const lang = normalizeFenceLanguage(info)
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

  const langLabel = languageLabels[lang] || lang || 'Text'
  // 添加 highlight.js 的语言类名
  const codeClass = lang ? `language-${lang}` : ''

  return `<div class="code-block-wrapper"><div class="code-block-header"><span class="code-block-lang">${langLabel}</span></div><pre class="hljs"><code class="${codeClass}">${highlighted}</code></pre></div>\n`
}

// 渲染 Markdown 为 HTML
export const renderMarkdown = (content) => {
  if (!content) return ''
  return md.render(content)
}

export const stripMarkdownFrontMatter = (content) => {
  if (!content) return ''
  return content.replace(/^\uFEFF?---[^\S\r\n]*\r?\n[\s\S]*?\r?\n(?:---|\.\.\.)[^\S\r\n]*(?:\r?\n|$)/, '')
}

export const stripKnowledgeDocumentNotes = (content) => {
  if (!content) return ''
  return content
    .replace(/^- 用途：LabAgent 实验教学知识库[^\S\r\n]*(?:\r?\n|$)/gm, '')
    .replace(
      /^- 清理：已移除图片、站点导航、构建配置、答案目录和重复内容[^\S\r\n]*(?:\r?\n|$)/gm,
      '',
    )
}

const normalizeArtifactPath = (path) => String(path || '').replace(/\\/g, '/').replace(/^\.\/+/, '')

const artifactPathCandidates = (path) => {
  const normalized = normalizeArtifactPath(path)
  if (!normalized) return []
  const fileName = normalized.split('/').pop() || normalized
  return [normalized, fileName]
}

// 部分模型在最终回答末尾会把刚生成的文件名再包一层 bash/text 代码块输出。
// 工具事件已经承载了产物路径和预览能力，这类孤立尾块会造成重复展示，渲染前直接移除。
export const stripTrailingArtifactCodeBlock = (content, artifactPaths = []) => {
  if (!content) return ''
  const candidates = new Set()
  ;(Array.from(artifactPaths || [])).forEach((path) => {
    artifactPathCandidates(path).forEach((candidate) => candidates.add(candidate))
  })
  if (candidates.size === 0) return content

  const trailingFencePattern =
    /(?:^|\n)(?:[^\S\r\n]*(?:你可以在工作区中查看文件|可以在工作区中查看文件|文件路径|查看文件|路径)[:：]?[^\S\r\n]*\n+)?[^\S\r\n]*```(?:bash|sh|shell|text|txt)?[^\S\r\n]*\n([^\r\n]+)[^\S\r\n]*\n```[^\S\r\n]*$/i
  const match = content.match(trailingFencePattern)
  if (!match) return content

  const codePath = normalizeArtifactPath(match[1].trim())
  if (!candidates.has(codePath)) return content

  return content.slice(0, match.index).replace(/[ \t]+\n/g, '\n').replace(/\n{3,}$/g, '\n\n').trimEnd()
}
