<template>
  <div :class="['message-item', `message-${message.sender}`]">
    <div class="message-container">
      <div class="message-content">
        <ReasoningPanel
          v-if="message.sender === 'assistant' && message.reasoning?.length"
          :reasoning="message.reasoning"
          @toggle="handleReasoningToggle"
        />

        <ToolActivityPanel
          v-if="message.sender === 'assistant' && message.toolEvents?.length"
          :tool-events="message.toolEvents"
          :completed="message.isComplete"
        />

        <div v-if="messageImages.length" class="message-images">
          <button
            v-for="image in messageImages"
            :key="image.image_id || image.preview_url"
            type="button"
            class="message-image-link"
            :disabled="!image.preview_url"
            :aria-label="`在右侧预览 ${image.file_name || '聊天图片'}`"
            @click="openImagePreview(image)"
          >
            <img
              v-if="image.preview_url"
              class="message-image"
              :src="image.preview_url"
              :alt="image.file_name || '聊天图片'"
            />
            <span v-else class="message-image-error">
              {{ image.load_error ? '图片加载失败' : '图片加载中…' }}
            </span>
          </button>
        </div>

        <div
          v-if="message.sender === 'user' && (userSkillNames.length || message.content)"
          class="user-message-body"
        >
          <span v-for="skillName in userSkillNames" :key="skillName" class="message-skill">
            <ToolActivityIcon :tool-name="`skill:${skillName}`" />
            <span>{{ skillName }}</span>
          </span>
          <div
            v-if="message.content"
            ref="messageTextRef"
            class="message-text"
            v-html="formatContent(message.content)"
            @click="handleCodeBlockClick"
          ></div>
        </div>

        <div
          v-else-if="message.content"
          ref="messageTextRef"
          class="message-text"
          v-html="formatContent(message.content)"
          @click="handleCodeBlockClick"
        ></div>

        <ToolApprovalInline
          v-if="showInlineApproval"
          :approval="chatStore.pendingApproval"
          @decision="emit('approval-decision', $event)"
        />

        <div
          v-if="message.sender === 'assistant' && sources.length > 0"
          ref="sourcesPanelRef"
          class="sources-panel"
        >
          <div class="sources-title">引用来源</div>
          <div class="sources-list">
            <button
              v-for="(source, idx) in visibleSources"
              :key="source.citation_id || `source-${idx}`"
              type="button"
              class="source-item"
              :data-source-index="idx + 1"
              @click="openSource(source)"
            >
              <div class="source-header">
                <span class="source-index">[{{ idx + 1 }}]</span>
                <span class="source-name" v-tooltip="formatSourceName(source)">
                  {{ formatSourceName(source) }}
                </span>
                <span v-if="source.score !== undefined && source.score !== null" class="source-score">
                  {{ formatScore(source.score) }}
                </span>
              </div>
              <div v-if="source.snippet" class="source-snippet">{{ source.snippet }}</div>
            </button>
          </div>
          <button
            v-if="hasCollapsedSources"
            type="button"
            class="sources-toggle"
            :aria-expanded="sourcesExpanded"
            :aria-label="sourcesExpanded ? '收起引用' : `展开 ${hiddenSourceCount} 条引用`"
            @click="sourcesExpanded = !sourcesExpanded"
          >
            <svg
              :class="{ expanded: sourcesExpanded }"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>

        <div class="message-footer">
          <div v-if="showMessageActions" class="message-actions">
            <span v-if="message.sender === 'user' && messageTime" class="message-time">
              {{ messageTime }}
            </span>
            <button
              @click="handleCopy"
              :class="['action-button', { copied: copied }]"
              v-tooltip="copied ? '已复制' : '复制'"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            </button>
            <span v-if="message.sender === 'assistant' && messageTime" class="message-time">
              {{ messageTime }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import router from '../router'
import { useChatStore } from '../stores/chat'
import { renderMarkdown, stripTrailingArtifactCodeBlock } from '../utils/markdown'
import { escapeHtml } from '../utils/html'
import ReasoningPanel from './ReasoningPanel.vue'
import ToolActivityPanel from './ToolActivityPanel.vue'
import ToolApprovalInline from './ToolApprovalInline.vue'
import ToolActivityIcon from './icons/ToolActivityIcon.vue'

const emit = defineEmits(['approval-decision'])

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const chatStore = useChatStore()
const messageTextRef = ref(null)
const sourcesPanelRef = ref(null)
const copied = ref(false)
const sourcesExpanded = ref(false)
const DEFAULT_VISIBLE_SOURCE_COUNT = 5

const showMessageActions = computed(() => {
  return (
    props.message.sender === 'user' ||
    (props.message.sender === 'assistant' && props.message.isComplete)
  )
})

const messageTime = computed(() => {
  if (!props.message.timestamp) return ''

  const timestampValue = String(props.message.timestamp)
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestampValue)
  const timestamp = new Date(hasTimezone ? timestampValue : `${timestampValue}Z`)
  if (Number.isNaN(timestamp.getTime())) return ''

  const timeParts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: 'numeric',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(timestamp)
  const hour = timeParts.find(({ type }) => type === 'hour')?.value
  const minute = timeParts.find(({ type }) => type === 'minute')?.value

  return hour && minute ? `${Number(hour)}:${minute}` : ''
})

const sources = computed(() => {
  return Array.isArray(props.message.sources) ? props.message.sources : []
})

const visibleSources = computed(() => {
  return sourcesExpanded.value ? sources.value : sources.value.slice(0, DEFAULT_VISIBLE_SOURCE_COUNT)
})

const hiddenSourceCount = computed(() => {
  return Math.max(0, sources.value.length - DEFAULT_VISIBLE_SOURCE_COUNT)
})

const hasCollapsedSources = computed(() => {
  return sources.value.length > DEFAULT_VISIBLE_SOURCE_COUNT
})

const messageImages = computed(() => {
  return Array.isArray(props.message.images) ? props.message.images : []
})

const userSkillNames = computed(() => {
  return Array.isArray(props.message.skillNames) ? props.message.skillNames : []
})

const openImagePreview = (image) => {
  if (!image?.preview_url) return
  chatStore.openPreview({
    path: `chat-image/${image.image_id || image.file_name}`,
    preview_type: 'image',
    image_url: image.preview_url,
    download_name: image.file_name || '聊天图片',
  })
}

const handleReasoningToggle = () => {
  chatStore.toggleMessageReasoning(props.message.id)
}

const showInlineApproval = computed(() => {
  if (!chatStore.pendingApproval || props.message.sender !== 'assistant') return false
  const messages = chatStore.messages || []
  return messages.length > 0 && messages[messages.length - 1]?.id === props.message.id
})

const formatScore = (score) => {
  const value = Number(score)
  if (Number.isNaN(value)) return ''
  return value.toFixed(2)
}

const formatSourceName = (source) => {
  const titlePath = [source.file_name, source.chapter_name, source.section_name].filter(Boolean)
  return titlePath.length > 0 ? titlePath.join(' / ') : '未知来源'
}

const openSource = (source) => {
  if (!source.file_name) return
  void router.push({
    name: 'Knowledge',
    query: { file_name: source.file_name },
  })
}

const formatContent = (content) => {
  if (!content) return ''

  if (props.message.sender === 'assistant') {
    return renderMarkdown(stripTrailingArtifactCodeBlock(content, messageArtifactPaths.value))
  }

  return escapeHtml(content).replace(/\n/g, '<br>').replace(/ {2}/g, '&nbsp;&nbsp;')
}

const messageArtifactPaths = computed(() => {
  const paths = new Set()
  ;(props.message.toolEvents || []).forEach((event) => {
    const payload = event?.payload || {}
    if (payload.tool_name !== 'write_file') return
    const path = payload.preview_path || payload.arguments?.file_path
    if (path) paths.add(path)
  })
  return paths
})

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (error) {
    console.error('复制失败:', error)
    const textArea = document.createElement('textarea')
    textArea.value = props.message.content
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  }
}

const handleCodeBlockClick = async (event) => {
  const citationLink = event.target.closest('.citation-index')
  if (citationLink) {
    event.preventDefault()
    await scrollToCitationSource(Number(citationLink.dataset.citationIndex))
    return
  }

  // 正文中的产物超链接：点击在右侧预览侧栏打开对应文件
  const artifactLink = event.target.closest('.artifact-link')
  if (artifactLink) {
    event.preventDefault()
    const path = artifactLink.getAttribute('data-path')
    if (path) {
      chatStore.openPreview({ ...findArtifactPreview(path) })
    }
    return
  }

  const copyButton = event.target.closest('.code-block-copy')
  if (!copyButton) return

  const codeBlock = copyButton.closest('.code-block-wrapper')
  const codeElement = codeBlock?.querySelector('code')
  if (!codeElement) return

  const codeText = codeElement.textContent || codeElement.innerText
  try {
    await navigator.clipboard.writeText(codeText)
    copyButton.classList.add('copied')
    copyButton.setAttribute('data-tooltip', '已复制')

    if (copyButton._tooltipEl) {
      copyButton._tooltipEl.textContent = '已复制'
    }

    setTimeout(() => {
      copyButton.classList.remove('copied')
      copyButton.setAttribute('data-tooltip', '复制代码')
      if (copyButton._tooltipEl) {
        copyButton._tooltipEl.textContent = '复制代码'
      }
    }, 2000)
  } catch (error) {
    console.error('复制代码失败:', error)
  }
}

const scrollToCitationSource = async (sourceIndex) => {
  if (!Number.isInteger(sourceIndex) || sourceIndex < 1 || sourceIndex > sources.value.length) return
  if (sourceIndex > DEFAULT_VISIBLE_SOURCE_COUNT && !sourcesExpanded.value) {
    sourcesExpanded.value = true
    await nextTick()
  }

  const sourceItem = sourcesPanelRef.value?.querySelector(`[data-source-index="${sourceIndex}"]`)
  if (!sourceItem) return
  sourceItem.scrollIntoView({ behavior: 'smooth', block: 'center' })
  sourceItem.classList.remove('source-item-guided')
  requestAnimationFrame(() => sourceItem.classList.add('source-item-guided'))
  setTimeout(() => sourceItem.classList.remove('source-item-guided'), 1400)
}

const decorateCitationLinks = () => {
  if (!messageTextRef.value || props.message.sender !== 'assistant') return
  const citationIndexes = new Map(
    sources.value
      .map((source, index) => [source.citation_id, index + 1])
      .filter(([citationId]) => citationId),
  )
  if (citationIndexes.size === 0) return

  const walker = document.createTreeWalker(messageTextRef.value, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.parentElement?.closest('a, button, code, pre')) return NodeFilter.FILTER_REJECT
      return Array.from(citationIndexes.keys()).some((id) =>
        node.nodeValue?.includes(`[资料${id}]`),
      )
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT
    },
  })
  const targets = []
  let current = walker.nextNode()
  while (current) {
    targets.push(current)
    current = walker.nextNode()
  }

  targets.forEach((textNode) => {
    const pattern = /\[资料([^\]]+)\]/g
    const fragment = document.createDocumentFragment()
    let lastIndex = 0
    let match
    while ((match = pattern.exec(textNode.nodeValue)) !== null) {
      const sequence = citationIndexes.get(match[1])
      if (!sequence) continue
      fragment.appendChild(document.createTextNode(textNode.nodeValue.slice(lastIndex, match.index)))
      const index = document.createElement('button')
      index.type = 'button'
      index.className = 'citation-index'
      index.dataset.citationIndex = String(sequence)
      index.setAttribute('aria-label', `查看引用来源 ${sequence}`)
      index.textContent = String(sequence)
      fragment.appendChild(index)
      lastIndex = match.index + match[0].length
    }
    if (lastIndex === 0) return
    fragment.appendChild(document.createTextNode(textNode.nodeValue.slice(lastIndex)))
    textNode.parentNode.replaceChild(fragment, textNode)
  })
}

// 从本条消息的 write_file 工具事件里取回产物的整文件正文与语言（若 SSE 已带），
// 供点击超链接时直接展示，避免再次请求接口
const findArtifactPreview = (path) => {
  const events = props.message.toolEvents || []
  for (const event of events) {
    const payload = event?.payload || {}
    if (payload.tool_name !== 'write_file') continue
    const eventPath = payload.preview_path || payload.arguments?.file_path
    if (eventPath === path) {
      return {
        path,
        language: payload.preview_language || '',
        content: payload.preview_content ?? null,
      }
    }
  }
  return { path, language: '', content: null }
}

// 正文渲染后，把命中「本会话产物路径集合」的纯文本路径替换为可点击超链接（DOM 安全，不破坏已有标签）
const decorateArtifactLinks = () => {
  if (!messageTextRef.value || props.message.sender !== 'assistant') return
  const paths = Array.from(chatStore.artifactPaths || [])
  if (paths.length === 0) return
  // 长路径优先匹配，避免子串误替换
  paths.sort((a, b) => b.length - a.length)

  const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const pattern = new RegExp(`(${paths.map(escapeRegExp).join('|')})`, 'g')

  const walker = document.createTreeWalker(messageTextRef.value, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      // 只跳过已处理的链接内文本；代码块（含 ```text）里的产物路径同样需要可点击
      if (node.parentElement?.closest('a')) {
        return NodeFilter.FILTER_REJECT
      }
      // 带 g 标志的正则跨节点复用会累积 lastIndex，每次判定前必须重置，避免误判
      pattern.lastIndex = 0
      return pattern.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
    },
  })

  const targets = []
  let current = walker.nextNode()
  while (current) {
    targets.push(current)
    current = walker.nextNode()
  }

  targets.forEach((textNode) => {
    const text = textNode.nodeValue
    pattern.lastIndex = 0
    const fragment = document.createDocumentFragment()
    let lastIndex = 0
    let match
    while ((match = pattern.exec(text)) !== null) {
      if (match.index > lastIndex) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)))
      }
      const link = document.createElement('a')
      link.className = 'artifact-link'
      // data-path 保留完整相对路径（供右侧预览定位并展示完整路径），正文仅显示文件名以免影响阅读体验
      link.setAttribute('data-path', match[0])
      link.setAttribute('href', '#')
      link.textContent = match[0].replace(/\\/g, '/').split('/').pop() || match[0]
      fragment.appendChild(link)
      lastIndex = match.index + match[0].length
    }
    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex)))
    }
    textNode.parentNode.replaceChild(fragment, textNode)
  })
}

const addCopyButtons = () => {
  if (!messageTextRef.value) return

  const codeBlocks = messageTextRef.value.querySelectorAll('.code-block-wrapper')
  codeBlocks.forEach((block) => {
    if (block.querySelector('.code-block-copy')) return

    const copyButton = document.createElement('button')
    copyButton.className = 'code-block-copy'
    copyButton.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
    `
    copyButton.setAttribute('data-tooltip', '复制代码')

    copyButton.addEventListener('mouseenter', () => {
      const tooltipText = copyButton.getAttribute('data-tooltip')
      if (!tooltipText) return

      const tooltipTimer = setTimeout(() => {
        const tooltipEl = document.createElement('div')
        tooltipEl.className = 'global-tooltip'
        tooltipEl.textContent = tooltipText
        tooltipEl.style.visibility = 'hidden'
        document.body.appendChild(tooltipEl)

        const rect = copyButton.getBoundingClientRect()
        const padding = 12
        const gap = 8

        requestAnimationFrame(() => {
          if (!tooltipEl) return

          const tooltipRect = tooltipEl.getBoundingClientRect()
          const halfWidth = tooltipRect.width / 2

          let x = rect.left + rect.width / 2
          x = Math.max(padding + halfWidth, x)
          x = Math.min(window.innerWidth - padding - halfWidth, x)

          const hasEnoughTopSpace = rect.top - tooltipRect.height - gap >= padding
          const y = hasEnoughTopSpace ? rect.top - gap : rect.bottom + gap

          tooltipEl.classList.toggle('below', !hasEnoughTopSpace)
          tooltipEl.style.top = `${y}px`
          tooltipEl.style.left = `${x}px`
          tooltipEl.style.visibility = 'visible'
        })

        copyButton._tooltipEl = tooltipEl
      }, 400)

      copyButton._tooltipTimer = tooltipTimer
    })

    copyButton.addEventListener('mouseleave', () => {
      if (copyButton._tooltipTimer) clearTimeout(copyButton._tooltipTimer)
      if (copyButton._tooltipEl) {
        copyButton._tooltipEl.remove()
        copyButton._tooltipEl = null
      }
    })

    const header = block.querySelector('.code-block-header')
    if (header) {
      header.appendChild(copyButton)
    }
  })
}

onMounted(() => {
  nextTick(() => {
    addCopyButtons()
    decorateArtifactLinks()
    decorateCitationLinks()
  })
})

watch(
  () => props.message.content,
  () => {
    nextTick(() => {
      addCopyButtons()
      decorateArtifactLinks()
      decorateCitationLinks()
    })
  },
  { flush: 'post' },
)

watch(
  () => sources.value.map((source) => source.citation_id || '').join(','),
  () => nextTick(decorateCitationLinks),
  { flush: 'post' },
)

// 产物集合在流式过程中会新增（如先写文件后回答），集合变化后重新装饰正文超链接
watch(
  () => chatStore.artifactPaths,
  () => {
    nextTick(() => {
      decorateArtifactLinks()
    })
  },
  { flush: 'post' },
)

</script>

<style lang="scss" scoped>
.message-item {
  min-width: 0;
  width: 100%;
  padding: 24px 0;

  &.message-user {
    background-color: transparent;
    transition: background-color 0.3s ease;

    .message-container {
      width: var(--chat-content-track-width, min(100%, 880px));
      margin: 0 auto;
      display: flex;
      gap: 12px;
      justify-content: flex-end;
    }

    .message-content {
      flex: 0 1 auto;
      width: fit-content;
      max-width: 100%;
      align-items: flex-end;
    }

    .message-footer {
      align-self: stretch;
      width: auto;
      justify-content: flex-end;
      padding-left: 0;
    }

    .message-actions {
      justify-content: flex-end;
    }

    .action-button {
      opacity: 0;
      pointer-events: none;
    }

    &:hover .action-button,
    &:focus-within .action-button {
      opacity: 1;
      pointer-events: auto;
    }

    .user-message-body {
      background-color: var(--user-message-bg);
      color: var(--user-message-text);
    }

    .message-text {
      background-color: transparent;
      color: var(--user-message-text);
      white-space: pre-wrap;
    }

    @media (hover: none) and (pointer: coarse) {
      .action-button {
        opacity: 1;
        pointer-events: auto;
      }
    }
  }

  &.message-assistant {
    background-color: transparent;
    transition: background-color 0.3s ease;

    .message-container {
      width: var(--chat-content-track-width, min(100%, 880px));
      margin: 0 auto;
      display: flex;
      gap: 12px;
    }

    .message-content {
      align-items: flex-start;
    }

    .message-text {
      background-color: transparent;
      color: var(--assistant-message-text);
    }
  }

  @media (max-width: 768px) {
    padding: 16px 0;

    .message-container {
      width: var(--chat-content-track-width, calc(100% - 32px));
    }
  }
}

.message-container {
  display: flex;
  min-width: 0;
  max-width: 100%;
}

.message-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.user-message-body {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px 7px;
  max-width: 100%;
  padding: 10px 16px 8px;
  border-radius: 12px;
}

.message-skill {
  position: relative;
  display: inline-block;
  min-width: 0;
  padding-left: 22px;
  color: var(--primary-color, #90138b);
  font-size: 15px;
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;

  :deep(.tool-activity-icon) {
    position: absolute;
    top: 50%;
    left: 0;
    width: 17px;
    height: 17px;
    transform: translateY(-50%);
  }
}

.user-message-body .message-text {
  display: inline;
  padding: 0;
  border-radius: 0;
}

.message-images {
  display: flex;
  flex-direction: row-reverse;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 100%;
  margin-bottom: 8px;
}

.message-image-link {
  display: flex;
  width: 72px;
  height: 72px;
  flex: 0 0 72px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--border-color, rgba(229, 231, 235, 1));
  border-radius: 10px;
  background: #f7f7f8;
  align-items: center;
  justify-content: center;
  cursor: zoom-in;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;

  &:hover:not(:disabled) {
    border-color: rgba(144, 19, 139, 0.4);
    box-shadow: 0 4px 14px rgba(17, 24, 39, 0.08);
    transform: translateY(-1px);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color, #90138b);
    outline-offset: 2px;
  }

  &:disabled {
    cursor: default;
  }
}

.message-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.message-image-error {
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 768px) {
  .user-message-body {
    padding: 8px 12px 6px;
    border-radius: 10px;
  }

  .message-skill {
    font-size: 14px;
  }

  .message-image-link {
    width: 56px;
    height: 56px;
    flex-basis: 56px;
  }
}

.message-text {
  min-width: 0;
  max-width: 100%;
  padding: 10px 16px 8px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 15px;
  overflow-wrap: anywhere;
  white-space: normal;

  @media (max-width: 768px) {
    padding: 8px 12px 6px;
    font-size: 14px;
    border-radius: 10px;
  }

  :deep(> *:last-child) {
    margin-bottom: 0 !important;
  }

  :deep(p) {
    margin: 0.25em 0;

    &:first-child {
      margin-top: 0;
    }

    &:last-child {
      margin-bottom: 0;
    }
  }

  :deep(ul),
  :deep(ol) {
    margin: 0.5em 0;
    padding-left: 1.5em;
  }

  :deep(li) {
    margin: 0.25em 0;
  }

  :deep(blockquote) {
    margin: 0.75em 0;
    padding: 0.1em 0 0.1em 1em;
    border-left: 2px solid var(--border-color, #d0d7de);
    background-color: transparent;
    border-radius: 0;
    color: var(--text-secondary);
    font-style: normal;
  }

  :deep(blockquote > :first-child) {
    margin-top: 0;
  }

  :deep(blockquote > :last-child) {
    margin-bottom: 0;
  }

  :deep(code:not(pre code)) {
    padding: 2px 7px;
    border-radius: 6px;
    font-family:
      'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', 'Monaco', 'Courier New', monospace;
    font-size: 0.88em;
    background-color: rgba(175, 184, 193, 0.24);
    color: var(--text-primary, #242424);
  }

  // 正文中的产物路径超链接：点击在右侧预览侧栏打开
  :deep(.artifact-link) {
    color: #90138b;
    text-decoration: none;
    cursor: pointer;
    border-bottom: 1px solid transparent;
    transition: border-color 0.2s ease;
    word-break: break-all;

    &:hover {
      border-bottom-color: #90138b;
    }
  }

  :deep(.code-block-wrapper) {
    width: 100%;
    min-width: 0;
    max-width: 100%;
    margin: 1em 0;
    border-radius: 14px;
    overflow: hidden;
    background-color: var(--bg-secondary, #f4f4f4);
    border: none;
    position: relative;
    box-shadow: none;

    .code-block-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 42px;
      padding: 10px 16px 2px;
      background-color: transparent;
      border-bottom: none;

      .code-block-lang {
        color: var(--text-secondary, #626262);
        font-family: inherit;
        font-size: 14px;
        font-weight: 400;
        letter-spacing: 0;
        text-transform: lowercase;
      }

      .code-block-copy {
        padding: 5px;
        background-color: transparent;
        border: none;
        color: var(--text-tertiary, #858585);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
        border-radius: 6px;

        svg {
          width: 18px;
          height: 18px;
        }

        &:hover {
          color: var(--text-primary);
          background-color: var(--bg-hover, rgba(0, 0, 0, 0.05));
        }

        &.copied {
          color: #90138b;
        }
      }
    }

    pre {
      width: 100%;
      max-width: 100%;
      margin: 0;
      padding: 14px 16px 18px;
      border-radius: 0;
      overflow-x: auto;
      overflow-y: hidden;
      background-color: transparent;

      code {
        width: max-content;
        min-width: 100%;
        padding: 0;
        background-color: transparent;
        font-size: 0.92em;
        line-height: 1.55;
        color: var(--text-primary, #242424);
        font-family:
          'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', 'Monaco', 'Courier New',
          monospace;
        display: block;
        white-space: pre;
      }
    }
  }

  :deep(pre:not(.code-block-wrapper pre)) {
    margin: 1em 0;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
    background-color: #f6f8fa;
    border: 1px solid rgba(0, 0, 0, 0.1);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);

    code {
      padding: 0;
      background-color: transparent;
      font-size: 0.875em;
      line-height: 1.6;
      color: #24292f;
      font-family:
        'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', 'Monaco', 'Courier New', monospace;
    }
  }

  :deep(.markdown-table-wrapper) {
    max-width: 100%;
    margin: 1em 0;
    width: 100%;
    overflow-x: auto;
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 10px;
    background: transparent;
  }

  :deep(table) {
    width: 100%;
    min-width: 560px;
    margin: 0;
    border-spacing: 0;
    border-collapse: separate;
    font-size: 14px;

    th,
    td {
      padding: 10px 12px;
      border: 0;
      border-bottom: 1px solid var(--border-color, #e5e5e5);
      text-align: left;
      vertical-align: top;

      & + th,
      & + td {
        border-left: 1px solid var(--border-color, #e5e5e5);
      }
    }

    th {
      background-color: rgba(0, 0, 0, 0.025);
      font-weight: 600;
      color: var(--text-primary);
    }

    tbody tr:last-child td {
      border-bottom: 0;
    }
  }

  :deep(a) {
    color: #90138b;
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color 0.2s ease;

    &:hover {
      border-bottom-color: #90138b;
    }
  }

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4),
  :deep(h5),
  :deep(h6) {
    margin: 0.8em 0 0.4em 0;
    font-weight: 600;

    &:first-child {
      margin-top: 0;
    }
  }

  :deep(hr) {
    margin: 1em 0;
    border: none;
    border-top: 1px solid var(--border-color);
  }
}

.message-footer {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  margin-top: 12px;
  padding-left: 16px;

  @media (max-width: 768px) {
    padding-left: 12px;
  }
}

.sources-panel {
  margin: 12px 0 0 16px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 12px;
  padding: 12px 16px;
  max-width: 600px;

  @media (max-width: 768px) {
    margin: 12px 0 0 0;
    max-width: 100%;
  }
}

.sources-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #6b7280);
  margin-bottom: 10px;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  padding: 4px 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.2s ease;

  &:hover {
    background: var(--hover-bg, #f3f4f6);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color, #90138b);
    outline-offset: 2px;
  }

  &.source-item-guided {
    background: var(--bg-hover, #e5e5e5);
  }
}

.source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}

.source-index {
  flex-shrink: 0;
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
  text-align: center;
}

.source-name {
  font-size: 13px;
  color: var(--text-primary, #374151);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-score {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-tertiary, #9ca3af);
}

.source-snippet {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  line-height: 1.5;
  padding-left: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.message-text :deep(.citation-index) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  margin: 0 2px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: var(--bg-hover, #e5e5e5);
  color: inherit;
  font: inherit;
  font-size: 12px;
  line-height: 1;
  vertical-align: 0.08em;
  cursor: pointer;

  &:hover {
    background: var(--bg-active, #ebebeb);
  }

  &:focus-visible {
    outline: 2px solid var(--text-secondary, #6e6e80);
    outline-offset: 2px;
  }
}

.sources-toggle {
  width: 28px;
  height: 24px;
  margin: 8px auto 0;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;

  &:hover {
    background: var(--hover-bg, #f3f4f6);
    color: var(--text-primary, #374151);
  }

  &:focus-visible {
    outline: 2px solid rgba(144, 19, 139, 0.25);
    outline-offset: 2px;
  }

  svg {
    transition: transform 0.2s ease;

    &.expanded {
      transform: rotate(180deg);
    }
  }
}

.message-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
}

.message-time {
  color: var(--text-tertiary, #9ca3af);
  font-size: 13px;
  line-height: 28px;
  opacity: 0;
  visibility: hidden;
  transition:
    opacity 0.18s ease,
    visibility 0.18s ease;
}

.message-item:hover .message-time,
.message-item:focus-within .message-time {
  opacity: 1;
  visibility: visible;
}

.action-button {
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    color 0.18s ease,
    background-color 0.18s ease,
    transform 0.18s ease;

  svg {
    width: 18px;
    height: 18px;
  }

  &:hover {
    color: var(--text-primary);
    background-color: var(--bg-hover);
  }

  &.copied {
    color: #90138b;
  }
}
</style>
