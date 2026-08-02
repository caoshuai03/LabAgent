<!--
 @author: caoshuai.cs
 @date: 2026-07-15 15:20
 @description: 右侧工作区文件预览侧栏，支持多 tab 切换、路径展示、下载、收起（整文件预览，无行号，非 diff）
-->
<template>
  <aside class="workspace-preview-panel">
    <div class="preview-header">
      <div class="preview-tabs">
        <button
          v-for="tab in chatStore.previewTabs"
          :key="tab.path"
          type="button"
          class="preview-tab"
          :class="{ active: tab.path === chatStore.previewActivePath }"
          :title="tab.path"
          @click="chatStore.setPreviewActive(tab.path)"
        >
          <span class="preview-tab-name">{{ tabNameOf(tab) }}</span>
          <span
            class="preview-tab-close"
            role="button"
            aria-label="关闭"
            @click.stop="chatStore.closePreviewTab(tab.path)"
          >
            ×
          </span>
        </button>
      </div>
      <button
        type="button"
        class="preview-collapse"
        v-tooltip="'收起侧栏'"
        @click="chatStore.closePreviewPanel()"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <rect x="3" y="3" width="18" height="18" rx="2"></rect>
          <line x1="15" y1="3" x2="15" y2="21"></line>
        </svg>
      </button>
    </div>

    <div v-if="activeTab" class="preview-toolbar">
      <span class="preview-path" :title="previewPathOf(activeTab)">
        {{ previewPathOf(activeTab) }}
      </span>
      <button
        type="button"
        class="preview-download"
        v-tooltip="'下载文件'"
        @click="handleDownload(activeTab)"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
      </button>
    </div>

    <div v-if="activeTab" class="preview-content">
      <div v-if="activeTab.loading" class="preview-hint">正在加载预览…</div>
      <div v-else-if="activeTab.error" class="preview-hint preview-error">{{ activeTab.error }}</div>
      <div
        v-else-if="isMarkdownTab(activeTab)"
        class="preview-body markdown-body"
        v-html="renderedMarkdownHtml(activeTab)"
      ></div>
      <div
        v-else-if="isImageTab(activeTab)"
        ref="imageStage"
        class="preview-image-stage"
        :class="{ dragging: imageDragging }"
        @wheel.prevent="handleImageWheel"
        @pointerdown="startImageDrag"
        @pointermove="moveImage"
        @pointerup="stopImageDrag"
        @pointercancel="stopImageDrag"
      >
        <div class="preview-image-position" :style="imagePositionStyle">
          <img
            ref="previewImage"
            class="preview-image"
            :src="activeTab.image_url"
            :alt="activeTab.download_name || fileNameOf(activeTab.path)"
            :style="imageStyle"
            draggable="false"
            @load="handleImageLoad"
          />
        </div>
        <div class="preview-image-controls" @pointerdown.stop>
          <button
            type="button"
            class="preview-image-control"
            aria-label="缩小图片"
            v-tooltip="'缩小'"
            @click="changeImageZoom(-IMAGE_ZOOM_STEP)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <circle cx="10.5" cy="10.5" r="6.5"></circle>
              <line x1="6.5" y1="10.5" x2="14.5" y2="10.5"></line>
              <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
            </svg>
          </button>
          <input
            class="preview-image-range"
            type="range"
            :min="IMAGE_ZOOM_MIN"
            :max="IMAGE_ZOOM_MAX"
            :step="IMAGE_ZOOM_STEP"
            :value="imageZoom"
            aria-label="图片缩放比例"
            @input="setImageZoom($event.target.value)"
          />
          <button
            type="button"
            class="preview-image-control"
            aria-label="放大图片"
            v-tooltip="'放大'"
            @click="changeImageZoom(IMAGE_ZOOM_STEP)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <circle cx="10.5" cy="10.5" r="6.5"></circle>
              <line x1="6.5" y1="10.5" x2="14.5" y2="10.5"></line>
              <line x1="10.5" y1="6.5" x2="10.5" y2="14.5"></line>
              <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
            </svg>
          </button>
          <span class="preview-image-zoom">{{ imageZoom }}%</span>
          <span class="preview-image-divider" aria-hidden="true"></span>
          <button type="button" class="preview-image-action" @click="fitImage">适应窗口</button>
          <button type="button" class="preview-image-action" @click="showActualImageSize">1:1</button>
        </div>
      </div>
      <pre v-else class="preview-code hljs"><code
        :class="codeLanguageClass(activeTab)"
        v-html="renderedCodeHtml(activeTab)"
      ></code></pre>
    </div>
    <div v-else class="preview-empty">暂无可预览的文件</div>
  </aside>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import hljs from 'highlight.js'
import { useChatStore } from '../stores/chat'
import { renderMarkdown } from '../utils/markdown'
import { downloadWorkspaceFile, getWorkspaceFilePreview } from '../api/chat'
import { useToast } from '../composables/useToast'
import { escapeHtml } from '../utils/html'

const chatStore = useChatStore()
const toast = useToast()
const IMAGE_ZOOM_MIN = 10
const IMAGE_ZOOM_MAX = 300
const IMAGE_ZOOM_STEP = 1

const imageStage = ref(null)
const previewImage = ref(null)
const imageZoom = ref(100)
const imageOffset = ref({ x: 0, y: 0 })
const imageNaturalSize = ref({ width: 0, height: 0 })
const imageDragging = ref(false)
const imageFitMode = ref(true)
let imageDragStart = null
let observedImageStage = null
let imageStageResizeObserver = null

const activeTab = computed(() => {
  return chatStore.previewTabs.find((tab) => tab.path === chatStore.previewActivePath) || null
})

const fileNameOf = (path) => (path ? path.replace(/\\/g, '/').split('/').pop() || path : '')
const tabNameOf = (tab) => tab?.download_name || fileNameOf(tab?.path)

const workspacePathOf = (path) => {
  if (!path) return '/'
  const normalized = path.replace(/\\/g, '/').replace(/^\/+/, '')
  return `/${normalized}`
}

const previewPathOf = (tab) => {
  return isImageTab(tab) ? `聊天图片 / ${tabNameOf(tab)}` : workspacePathOf(tab?.path)
}

const isMarkdownTab = (tab) => (tab?.language || '').toLowerCase() === 'markdown'
const isImageTab = (tab) => tab?.preview_type === 'image'

const imagePositionStyle = computed(() => ({
  transform: `translate(${imageOffset.value.x}px, ${imageOffset.value.y}px)`,
}))

const imageStyle = computed(() => ({
  transform: `translate(-50%, -50%) scale(${imageZoom.value / 100})`,
}))

const clampImageZoom = (value) => {
  const zoom = Number(value)
  return Math.min(IMAGE_ZOOM_MAX, Math.max(IMAGE_ZOOM_MIN, Number.isFinite(zoom) ? zoom : 100))
}

const clampImageOffset = () => {
  if (!imageStage.value || !imageNaturalSize.value.width || !imageNaturalSize.value.height) return
  const scale = imageZoom.value / 100
  const overflowX = Math.max(
    0,
    (imageNaturalSize.value.width * scale - imageStage.value.clientWidth) / 2,
  )
  const overflowY = Math.max(
    0,
    (imageNaturalSize.value.height * scale - imageStage.value.clientHeight) / 2,
  )
  imageOffset.value = {
    x: Math.min(overflowX, Math.max(-overflowX, imageOffset.value.x)),
    y: Math.min(overflowY, Math.max(-overflowY, imageOffset.value.y)),
  }
}

const setImageZoom = (value) => {
  imageFitMode.value = false
  imageZoom.value = clampImageZoom(value)
  clampImageOffset()
}

const changeImageZoom = (change) => {
  setImageZoom(imageZoom.value + change)
}

const fitImage = () => {
  if (!imageStage.value || !imageNaturalSize.value.width || !imageNaturalSize.value.height) return
  const availableWidth = Math.max(1, imageStage.value.clientWidth - 48)
  const availableHeight = Math.max(1, imageStage.value.clientHeight - 96)
  const scale = Math.min(
    1,
    availableWidth / imageNaturalSize.value.width,
    availableHeight / imageNaturalSize.value.height,
  )
  imageZoom.value = clampImageZoom(Math.floor(scale * 100))
  imageOffset.value = { x: 0, y: 0 }
  imageFitMode.value = true
}

const showActualImageSize = () => {
  imageZoom.value = 100
  imageOffset.value = { x: 0, y: 0 }
  imageFitMode.value = false
}

const handleImageLoad = (event) => {
  imageNaturalSize.value = {
    width: event.target.naturalWidth,
    height: event.target.naturalHeight,
  }
  fitImage()
}

const handleImageWheel = (event) => {
  if (event.ctrlKey || event.metaKey) {
    changeImageZoom(event.deltaY < 0 ? IMAGE_ZOOM_STEP : -IMAGE_ZOOM_STEP)
    return
  }
  const deltaX = event.shiftKey && event.deltaX === 0 ? event.deltaY : event.deltaX
  const deltaY = event.shiftKey ? 0 : event.deltaY
  imageOffset.value = {
    x: imageOffset.value.x - deltaX,
    y: imageOffset.value.y - deltaY,
  }
  clampImageOffset()
}

const startImageDrag = (event) => {
  if (event.button !== 0) return
  imageDragging.value = true
  imageDragStart = {
    pointerId: event.pointerId,
    clientX: event.clientX,
    clientY: event.clientY,
    offsetX: imageOffset.value.x,
    offsetY: imageOffset.value.y,
  }
  event.currentTarget.setPointerCapture(event.pointerId)
}

const moveImage = (event) => {
  if (!imageDragging.value || !imageDragStart || event.pointerId !== imageDragStart.pointerId) return
  imageOffset.value = {
    x: imageDragStart.offsetX + event.clientX - imageDragStart.clientX,
    y: imageDragStart.offsetY + event.clientY - imageDragStart.clientY,
  }
  clampImageOffset()
}

const stopImageDrag = (event) => {
  if (!imageDragStart || event.pointerId !== imageDragStart.pointerId) return
  if (event.currentTarget.hasPointerCapture(event.pointerId)) {
    event.currentTarget.releasePointerCapture(event.pointerId)
  }
  imageDragging.value = false
  imageDragStart = null
}

const observeImageStage = () => {
  if (typeof ResizeObserver === 'undefined') return
  if (!imageStageResizeObserver) {
    imageStageResizeObserver = new ResizeObserver(() => {
      if (imageFitMode.value) {
        fitImage()
      } else {
        clampImageOffset()
      }
    })
  }
  if (observedImageStage) imageStageResizeObserver.unobserve(observedImageStage)
  observedImageStage = imageStage.value
  if (observedImageStage) imageStageResizeObserver.observe(observedImageStage)
}

const normalizedCodeLanguage = (tab) => {
  const language = (tab?.language || '').toLowerCase()
  return language && language !== 'text' ? language : ''
}

const codeLanguageClass = (tab) => {
  const language = normalizedCodeLanguage(tab)
  return language ? `language-${language}` : ''
}

// Markdown 文件按富文本预览；代码文件直接渲染高亮代码，不复用聊天代码块卡片样式
const renderedMarkdownHtml = (tab) => {
  const content = tab.content || ''
  return renderMarkdown(content)
}

const renderedCodeHtml = (tab) => {
  const content = tab.content || ''
  const language = normalizedCodeLanguage(tab)
  if (language && hljs.getLanguage(language)) {
    try {
      return hljs.highlight(content, { language, ignoreIllegals: true }).value
    } catch {
      return escapeHtml(content)
    }
  }
  return escapeHtml(content)
}

// tab 首次激活且没有正文时（例如历史消息重放），按需拉取整文件内容
const fetchPreviewIfNeeded = async (tab) => {
  if (!tab || isImageTab(tab) || tab.content !== null || tab.loading) return
  const sessionId = chatStore.currentConversationId
  if (!sessionId) {
    tab.error = '缺少会话信息，无法预览'
    return
  }
  tab.loading = true
  tab.error = ''
  try {
    const response = await getWorkspaceFilePreview(sessionId, tab.path)
    const data = response.data?.data
    if (data) {
      tab.content = data.content || ''
      tab.language = data.language || tab.language
    } else {
      tab.error = response.data?.message || '预览失败'
    }
  } catch (error) {
    tab.error = error.response?.data?.message || '预览失败，请尝试下载'
  } finally {
    tab.loading = false
  }
}

const handleDownload = async (tab) => {
  if (isImageTab(tab) && tab.image_url) {
    const link = document.createElement('a')
    link.href = tab.image_url
    link.download = tab.download_name || fileNameOf(tab.path) || 'image'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    return
  }
  const sessionId = chatStore.currentConversationId
  if (!tab?.path || !sessionId) {
    toast.error('缺少会话或文件路径，无法下载')
    return
  }
  try {
    const response = await downloadWorkspaceFile(sessionId, tab.path)
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileNameOf(tab.path) || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    toast.error(error.response?.data?.message || '下载失败')
  }
}

watch(
  activeTab,
  (tab) => {
    if (tab) fetchPreviewIfNeeded(tab)
    imageZoom.value = 100
    imageOffset.value = { x: 0, y: 0 }
    imageNaturalSize.value = { width: 0, height: 0 }
    imageFitMode.value = true
    nextTick(() => {
      observeImageStage()
      if (isImageTab(tab) && previewImage.value?.complete) {
        imageNaturalSize.value = {
          width: previewImage.value.naturalWidth,
          height: previewImage.value.naturalHeight,
        }
        fitImage()
      }
    })
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  imageStageResizeObserver?.disconnect()
})
</script>

<style lang="scss" scoped>
.workspace-preview-panel {
  display: flex;
  flex-direction: column;
  height: var(--app-height, 100vh);
  flex-shrink: 0;
  border-left: 1px solid var(--border-color, #e5e5e5);
  background: var(--app-page-bg, #fafafc);
  overflow: hidden;
}

.workspace-preview-panel.switching-collapse {
  .preview-header,
  .preview-toolbar,
  .preview-content,
  .preview-empty {
    visibility: hidden;
  }
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px 8px 12px;
  flex-shrink: 0;
}

.preview-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1 1 auto;
  min-width: 0;
  overflow-x: auto;
}

.preview-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 180px;
  padding: 5px 8px 5px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary, #666);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    background: var(--bg-secondary, #f0f0f0);
  }

  &.active {
    background: var(--bg-secondary, #f0f0f0);
    border-color: var(--border-color, #ddd);
    color: var(--text-primary, #333);
    font-weight: 500;
  }
}

.preview-tab-name {
  overflow: hidden;
  text-overflow: ellipsis;
}

.preview-tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  font-size: 15px;
  line-height: 1;
  color: var(--text-tertiary, #999);

  &:hover {
    background: rgba(0, 0, 0, 0.08);
    color: var(--text-primary, #333);
  }
}

.preview-collapse {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  color: var(--text-secondary, #666);
  background: transparent;
  cursor: pointer;

  &:hover {
    background: var(--bg-secondary, #f0f0f0);
    color: var(--text-primary, #333);
  }

  svg {
    width: 18px;
    height: 18px;
  }
}

.preview-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color, #eee);
  flex-shrink: 0;
}

.preview-path {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  color: var(--text-secondary, #626262);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-download {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  color: var(--text-secondary, #666);
  background: transparent;
  cursor: pointer;

  &:hover {
    background: var(--bg-secondary, #f0f0f0);
    color: var(--text-primary, #333);
  }

  svg {
    width: 17px;
    height: 17px;
  }
}

.preview-content {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
}

.preview-image-stage {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  min-height: 100%;
  overflow: hidden;
  background: var(--bg-secondary, #f3f4f6);
  container-type: inline-size;
  cursor: grab;
  touch-action: none;
  user-select: none;

  &.dragging {
    cursor: grabbing;
  }
}

.preview-image-position {
  position: absolute;
  top: 50%;
  left: 50%;
}

.preview-image {
  position: absolute;
  top: 0;
  left: 0;
  display: block;
  max-width: none;
  max-height: none;
  border-radius: 8px;
  transform-origin: center;
  box-shadow: 0 10px 32px rgba(17, 24, 39, 0.12);
  pointer-events: none;
}

.preview-image-controls {
  position: absolute;
  bottom: 16px;
  left: 50%;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 10px;
  background: var(--app-page-bg, #fafafc);
  box-shadow: 0 8px 24px rgba(17, 24, 39, 0.12);
  transform: translateX(-50%);
  cursor: default;
}

.preview-image-control,
.preview-image-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  color: var(--text-secondary, #666);
  background: transparent;
  cursor: pointer;

  &:hover {
    color: var(--text-primary, #333);
    background: var(--bg-secondary, #f0f0f0);
  }
}

.preview-image-control {
  width: 30px;
  flex-shrink: 0;

  svg {
    width: 17px;
    height: 17px;
  }
}

.preview-image-action {
  padding: 0 8px;
  white-space: nowrap;
  font-size: 12px;
}

.preview-image-range {
  width: 92px;
  accent-color: var(--primary-color, #4f46e5);
  cursor: pointer;
}

.preview-image-zoom {
  width: 42px;
  color: var(--text-primary, #333);
  font-size: 12px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.preview-image-divider {
  width: 1px;
  height: 18px;
  margin: 0 4px;
  background: var(--border-color, #ddd);
}

@container (max-width: 360px) {
  .preview-image-range {
    display: none;
  }
}

.preview-body {
  padding: 28px 32px 48px;
  color: #1f2328;
  font-size: 15px;
  line-height: 1.75;
  word-break: break-word;
  overflow-wrap: anywhere;

  :deep(> *:first-child) {
    margin-top: 0;
  }

  :deep(> *:last-child) {
    margin-bottom: 0;
  }

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4),
  :deep(h5),
  :deep(h6) {
    margin: 0.8em 0 0.4em 0;
    color: #202124;
    font-weight: 600;

    &:first-child {
      margin-top: 0;
    }
  }

  :deep(h1) {
    font-size: 20px;
  }

  :deep(h2) {
    font-size: 17px;
  }

  :deep(h3) {
    font-size: 16px;
  }

  :deep(h4),
  :deep(h5),
  :deep(h6) {
    font-size: 15px;
  }

  :deep(p) {
    margin: 0.8em 0;
  }

  :deep(ul),
  :deep(ol) {
    margin: 0.8em 0;
    padding-left: 1.45em;
  }

  :deep(li) {
    margin: 0.28em 0;
    padding-left: 0.15em;
  }

  :deep(blockquote) {
    margin: 1.1em 0;
    padding: 0.15em 0 0.15em 1em;
    border-left: 4px solid #e3e5e7;
    color: #6b7280;
  }

  :deep(code:not(pre code)) {
    padding: 0.12em 0.42em;
    border-radius: 5px;
    background: #f1f3f5;
    color: #343a40;
    font-family:
      'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Monaco, 'Courier New', monospace;
    font-size: 0.88em;
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

  :deep(hr) {
    margin: 1.6em 0;
    border: 0;
    border-top: 1px solid #e5e7eb;
  }

  :deep(.markdown-table-wrapper) {
    width: 100%;
    margin: 1.1em 0;
    overflow-x: auto;
    border: 1px solid #e3e5e8;
    border-radius: 10px;
  }

  :deep(table) {
    width: 100%;
    min-width: 520px;
    margin: 0;
    border-spacing: 0;
    border-collapse: separate;
    font-size: 13px;
  }

  :deep(th),
  :deep(td) {
    padding: 9px 11px;
    border: 0;
    border-bottom: 1px solid #e3e5e8;
    text-align: left;
    vertical-align: top;

    & + th,
    & + td {
      border-left: 1px solid #e3e5e8;
    }
  }

  :deep(th) {
    background: rgba(0, 0, 0, 0.025);
    font-weight: 600;
  }

  :deep(tbody tr:last-child td) {
    border-bottom: 0;
  }

  :deep(.code-block-wrapper) {
    position: relative;
    margin: 1.1em 0;
    border: 1px solid #eff1f3;
    border-radius: 12px;
    overflow: hidden;
    background: var(--app-page-bg, #fafafc);
  }

  :deep(.code-block-header) {
    position: absolute;
    top: 10px;
    right: 12px;
    z-index: 1;
    min-height: 0;
    padding: 0;
    border: 0;
    background: transparent;
  }

  :deep(.code-block-lang) {
    color: #8a8f98;
    font-family: inherit;
    font-size: 12px;
    line-height: 1;
  }

  :deep(.code-block-wrapper pre) {
    margin: 0;
    padding: 24px 18px 18px;
    overflow-x: auto;
    background: transparent;
    color: #24292f;
    font-size: 13px;
    line-height: 1.65;
  }

  :deep(pre) {
    max-width: 100%;
  }

  :deep(pre code) {
    font-family:
      'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Monaco, 'Courier New', monospace;
  }
}

.preview-content > .preview-code {
  box-sizing: border-box;
  min-width: 100%;
  width: max-content;
  margin: 0;
  padding: 28px 32px 48px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: #24292f;
  font-family:
    'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre;
  word-break: normal;
  overflow: visible;
  overflow-wrap: normal;
  tab-size: 2;

  code {
    display: block;
    padding: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    white-space: inherit;
  }
}

.preview-hint {
  padding: 16px;
  color: var(--text-tertiary, #8a8a8a);
  font-size: 13px;
}

.preview-error {
  color: #c2410c;
}

.preview-empty {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #8a8a8a);
  font-size: 13px;
}

@media (max-width: 768px) {
  .workspace-preview-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 100vw !important;
    max-width: none;
    height: var(--app-height, 100vh);
    border-left: 0;
    z-index: 1200;
    box-shadow: none;
  }

  .preview-header {
    min-height: calc(52px + env(safe-area-inset-top));
    padding-top: calc(8px + env(safe-area-inset-top));
  }

  .preview-collapse,
  .preview-download {
    width: 40px;
    height: 40px;
  }

  .preview-tab {
    min-height: 40px;
  }

  .preview-tab-close {
    width: 28px;
    height: 28px;
    margin: -4px -4px -4px 0;
  }

  .preview-body {
    padding: 22px 20px 36px;
    font-size: 14px;
  }

  .preview-content > .preview-code {
    padding: 22px 20px 36px;
    font-size: 13px;
  }
}
</style>
