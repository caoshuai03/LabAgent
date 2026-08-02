<!--
 @author: caoshuai.cs
 @date: 2026-08-02 18:32
 @description: 知识库文件预览面板，支持 Markdown、TXT 与 PDF
-->
<template>
  <aside class="knowledge-preview-panel" aria-label="文件预览">
    <header class="preview-header">
      <div class="preview-title">
        <span :class="['file-type-mark', `type-${fileType.toLowerCase()}`]">
          {{ fileType }}
        </span>
        <div>
          <h2 :title="file.file_name">{{ file.file_name }}</h2>
          <p>文件预览</p>
        </div>
      </div>
      <div class="preview-actions">
        <button type="button" v-tooltip="'下载文件'" @click="emit('download', file.id)">
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
        <button type="button" aria-label="关闭预览" v-tooltip="'关闭预览'" @click="emit('close')">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <path d="M18 6 6 18M6 6l12 12"></path>
          </svg>
        </button>
      </div>
    </header>

    <div class="preview-content">
      <div v-if="loading" class="preview-state" role="status">
        <span class="preview-spinner"></span>
        <span>正在加载预览...</span>
      </div>
      <div v-else-if="errorMessage" class="preview-state preview-error">
        <span>{{ errorMessage }}</span>
        <button type="button" @click="loadPreview">重新加载</button>
      </div>
      <iframe
        v-else-if="fileType === 'PDF'"
        class="pdf-preview"
        :src="objectUrl"
        :title="`${file.file_name} 预览`"
      ></iframe>
      <article
        v-else-if="fileType === 'MD'"
        class="markdown-preview"
        v-html="renderedMarkdown"
      ></article>
      <pre v-else class="text-preview">{{ textContent }}</pre>
    </div>
  </aside>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { knowledgeApi } from '../api/knowledge'
import { assertDownloadableBlob, readBlobText } from '../utils/blobResponse'
import { escapeHtml } from '../utils/html'
import {
  renderMarkdown,
  stripKnowledgeDocumentNotes,
  stripMarkdownFrontMatter,
} from '../utils/markdown'

const props = defineProps({
  file: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['close', 'download'])

const loading = ref(false)
const errorMessage = ref('')
const textContent = ref('')
const objectUrl = ref('')
let requestVersion = 0

const fileType = computed(() => {
  const extension = String(props.file?.file_name || '').split('.').pop()?.toLowerCase()
  if (extension === 'pdf') return 'PDF'
  if (extension === 'md' || extension === 'markdown') return 'MD'
  return 'TXT'
})

const renderedMarkdown = computed(() =>
  renderMarkdown(
    escapeHtml(
      stripKnowledgeDocumentNotes(
        stripMarkdownFrontMatter(textContent.value),
      ),
    ),
  ),
)

const releaseObjectUrl = () => {
  if (!objectUrl.value) return
  window.URL.revokeObjectURL(objectUrl.value)
  objectUrl.value = ''
}

const loadPreview = async () => {
  const fileId = props.file?.id
  if (fileId == null) return

  const currentRequest = ++requestVersion
  loading.value = true
  errorMessage.value = ''
  textContent.value = ''
  releaseObjectUrl()

  try {
    const response = await knowledgeApi.downloadFile(fileId)
    if (currentRequest !== requestVersion) return
    const blob = await assertDownloadableBlob(response.data)
    if (currentRequest !== requestVersion) return
    if (fileType.value === 'PDF') {
      const pdfBlob =
        blob.type === 'application/pdf' ? blob : new Blob([blob], { type: 'application/pdf' })
      objectUrl.value = window.URL.createObjectURL(pdfBlob)
    } else {
      const content = await readBlobText(blob)
      if (currentRequest !== requestVersion) return
      textContent.value = content
    }
  } catch (error) {
    if (currentRequest !== requestVersion) return
    errorMessage.value = error?.response?.data?.message || '预览加载失败，请下载后查看'
  } finally {
    if (currentRequest === requestVersion) {
      loading.value = false
    }
  }
}

watch(
  () => props.file?.id,
  () => loadPreview(),
  { immediate: true },
)

onBeforeUnmount(() => {
  requestVersion += 1
  releaseObjectUrl()
})
</script>

<style lang="scss" scoped>
.knowledge-preview-panel {
  display: flex;
  flex: 0 0 clamp(380px, 42%, 620px);
  flex-direction: column;
  min-width: 0;
  height: 100%;
  border-left: 1px solid var(--border-color);
  background: var(--bg-primary);
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 64px;
  padding: 8px 12px 8px 16px;
  border-bottom: 1px solid var(--border-color);
}

.preview-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;

  > div {
    min-width: 0;
  }

  h2 {
    margin: 0;
    color: var(--text-primary);
    font-size: 13px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  p {
    margin: 3px 0 0;
    color: var(--text-tertiary);
    font-size: 11px;
  }
}

.file-type-mark {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 29px;
  height: 34px;
  border: 1px solid var(--border-color);
  border-radius: 5px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 8px;
  font-weight: 700;
}

.preview-actions {
  display: flex;
  flex-shrink: 0;
  gap: 2px;

  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;

    &:hover {
      background: var(--bg-hover);
      color: var(--text-primary);
    }

    &:focus-visible {
      outline: 2px solid var(--border-color-hover);
      outline-offset: 1px;
    }
  }

  svg {
    width: 17px;
    height: 17px;
  }
}

.preview-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.preview-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 180px;
  color: var(--text-secondary);
  font-size: 13px;
}

.preview-error {
  flex-direction: column;

  button {
    padding: 5px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    cursor: pointer;

    &:hover {
      background: var(--bg-secondary);
    }
  }
}

.preview-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-color);
  border-top-color: var(--text-secondary);
  border-radius: 50%;
  animation: preview-spin 0.8s linear infinite;
}

.pdf-preview {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  background: var(--bg-secondary);
}

.text-preview {
  box-sizing: border-box;
  min-width: 100%;
  min-height: 100%;
  width: max-content;
  margin: 0;
  padding: 24px 28px 40px;
  background: transparent;
  color: var(--text-primary);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.markdown-preview {
  padding: 24px 28px 40px;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.75;
  overflow-wrap: anywhere;

  :deep(> *:first-child) {
    margin-top: 0;
  }

  :deep(h1),
  :deep(h2),
  :deep(h3) {
    margin: 1.1em 0 0.5em;
    color: var(--text-primary);
    font-weight: 600;
  }

  :deep(h1) {
    font-size: 20px;
  }

  :deep(h2) {
    font-size: 17px;
  }

  :deep(h3) {
    font-size: 15px;
  }

  :deep(p),
  :deep(ul),
  :deep(ol) {
    margin: 0.8em 0;
  }

  :deep(blockquote) {
    margin: 1em 0;
    padding-left: 12px;
    border-left: 3px solid var(--border-color-hover);
    color: var(--text-secondary);
  }

  :deep(.markdown-table-wrapper) {
    margin: 1em 0;
    border: 1px solid var(--border-color);
    border-radius: 7px;
    overflow-x: auto;
  }

  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  :deep(th),
  :deep(td) {
    padding: 7px 9px;
    border-bottom: 1px solid var(--border-color);
    text-align: left;
  }

  :deep(th) {
    background: var(--bg-secondary);
  }

  :deep(.code-block-wrapper) {
    position: relative;
    margin: 1em 0;
    border: 1px solid var(--border-color);
    border-radius: 7px;
    background: var(--bg-secondary);
    overflow: hidden;
  }

  :deep(.code-block-header) {
    position: absolute;
    top: 8px;
    right: 10px;
    color: var(--text-tertiary);
    font-size: 10px;
  }

  :deep(pre) {
    margin: 0;
    padding: 22px 14px 14px;
    overflow-x: auto;
    background: transparent;
  }

  :deep(code:not(pre code)) {
    padding: 0.1em 0.35em;
    border-radius: 4px;
    background: var(--bg-secondary);
  }

  :deep(a) {
    color: var(--text-primary);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
}

@keyframes preview-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 900px) {
  .knowledge-preview-panel {
    position: fixed;
    inset: 0;
    z-index: 100;
    width: 100%;
    height: var(--app-height, 100vh);
    border-left: 0;
  }
}
</style>
