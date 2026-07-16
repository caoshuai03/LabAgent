<!--
 @author: caoshuai.cs
 @date: 2026-07-15 02:11
 @description: Agent命令执行与文件查看活动聚合、折叠和Shell输出展示
-->
<template>
  <section v-if="activities.length" class="tool-activity-panel">
    <button
      type="button"
      class="activity-group-header"
      :aria-expanded="groupExpanded"
      @click="groupExpanded = !groupExpanded"
    >
      <span class="activity-group-icon" aria-hidden="true">
        <svg
          v-if="hasShellActivities"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="3" y="4" width="18" height="16" rx="3"></rect>
          <path d="m7 9 3 3-3 3"></path>
          <path d="M13 15h4"></path>
        </svg>
        <svg
          v-else
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path>
          <path d="M14 2v6h6"></path>
          <path d="M8 13h8"></path>
          <path d="M8 17h6"></path>
        </svg>
      </span>
      <span class="activity-group-title">{{ groupTitle }}</span>
      <svg
        class="activity-chevron"
        :class="{ expanded: groupExpanded }"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="m9 18 6-6-6-6"></path>
      </svg>
    </button>

    <div v-show="groupExpanded" class="activity-list">
      <div v-for="activity in activities" :key="activity.id" class="activity-item">
        <div class="activity-line">
          <button
            type="button"
            class="activity-row"
            :class="[`status-${activity.status}`, { expandable: isShell(activity) || canPreviewFile(activity) }]"
            :disabled="!isShell(activity) && !canPreviewFile(activity)"
            :aria-expanded="isShell(activity) || canPreviewFile(activity) ? isExpanded(activity.id) : undefined"
            @click="toggleActivity(activity)"
          >
            <span class="activity-item-icon" aria-hidden="true">
              <svg
                v-if="isShell(activity)"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <rect x="3" y="4" width="18" height="16" rx="3"></rect>
                <path d="m7 9 3 3-3 3"></path>
                <path d="M13 15h4"></path>
              </svg>
              <svg
                v-else
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"></path>
                <path d="M14 2v6h6"></path>
              </svg>
            </span>
            <span class="activity-status-label">{{ getStatusLabel(activity) }}</span>
            <span
              class="activity-primary-text"
              :title="getPrimaryText(activity)"
            >
              {{ getPrimaryText(activity) }}
            </span>
            <svg
              v-if="isShell(activity) || canPreviewFile(activity)"
              class="item-chevron"
              :class="{ expanded: isExpanded(activity.id) }"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="m9 18 6-6-6-6"></path>
            </svg>
          </button>
        </div>

        <div v-if="isShell(activity) && isExpanded(activity.id)" class="shell-detail">
          <div class="shell-detail-title">Shell</div>
          <pre>{{ getShellDetail(activity) }}</pre>
        </div>

        <div v-if="canPreviewFile(activity) && isExpanded(activity.id)" class="file-preview">
          <div class="file-preview-title">{{ filePathOf(activity) }}</div>
          <div v-if="isPreviewLoading(activity.id)" class="file-preview-loading">正在加载预览…</div>
          <div v-else class="file-preview-body markdown-body" v-html="renderedPreviewHtml(activity)"></div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import { getWorkspaceFilePreview } from '../api/chat'
import { useToast } from '../composables/useToast'

const props = defineProps({
  toolEvents: {
    type: Array,
    default: () => [],
  },
  sessionId: {
    type: String,
    default: '',
  },
})

const toast = useToast()
const READ_TOOL_NAMES = new Set(['list_directory', 'read_file', 'file_search'])
const groupExpanded = ref(true)
const expandedToolCallIds = ref(new Set())
// 按 activity.id 缓存按需拉取的预览内容
const fetchedPreviews = ref({})

const statusFromStage = (stage, success) => {
  const statusMap = {
    pending_approval: 'pending_approval',
    tool_running: 'running',
    tool_done: success === false ? 'failed' : 'success',
    tool_failed: 'failed',
    tool_timeout: 'timeout',
    tool_rejected: 'rejected',
    tool_cancelled: 'cancelled',
    global_timeout: 'timeout',
  }
  return statusMap[stage] || null
}

const ensureActivity = (list, activeCalls, payload, index) => {
  const toolName = payload.tool_name || 'tool'
  const callId = payload.tool_call_id || `${payload.round || 0}:${toolName}:${index}`
  let activity = activeCalls.get(callId)
  if (!activity) {
    activity = {
      id: callId,
      toolName,
      arguments: payload.arguments || {},
      description: payload.description || '',
      status: 'pending',
      resultSummary: '',
      outputPreview: '',
      errorMessage: '',
      durationMs: null,
      previewPath: '',
      previewLanguage: '',
      previewContent: '',
    }
    activeCalls.set(callId, activity)
    list.push(activity)
  }
  return activity
}

const activities = computed(() => {
  const list = []
  const activeCalls = new Map()

  props.toolEvents.forEach((event, index) => {
    const payload = event?.payload || {}

    if (event?.eventType === 'tool_call') {
      const activity = ensureActivity(list, activeCalls, payload, index)
      activity.arguments = payload.arguments || {}
      activity.description = payload.description || ''
      return
    }

    if (event?.eventType === 'tool_result') {
      const activity = ensureActivity(list, activeCalls, payload, index)
      activity.status = payload.status || (payload.success === false ? 'failed' : 'success')
      activity.resultSummary = payload.result_summary || ''
      activity.outputPreview = payload.output_preview || ''
      activity.errorMessage = payload.error_message || ''
      activity.durationMs = payload.duration_ms ?? null
      if (payload.preview_path) activity.previewPath = payload.preview_path
      if (payload.preview_language) activity.previewLanguage = payload.preview_language
      if (payload.preview_content !== undefined) activity.previewContent = payload.preview_content || ''
      return
    }

    if (event?.eventType === 'status') {
      if (payload.stage === 'global_timeout') {
        list.push({
          id: `global-timeout-${index}`,
          toolName: 'global_timeout',
          arguments: {},
          status: 'timeout',
          resultSummary: `Agent执行超时（${payload.timeout_seconds || 180}秒）`,
          outputPreview: '',
          errorMessage: payload.message || '',
          durationMs: null,
        })
        return
      }
      const activity = ensureActivity(list, activeCalls, payload, index)
      activity.status = statusFromStage(payload.stage, payload.success) || activity.status
      if (payload.message) activity.errorMessage = payload.message
      if (payload.duration_ms !== undefined) activity.durationMs = payload.duration_ms
      return
    }

    if (event?.eventType === 'skill_loaded') {
      ;(payload.skills || []).forEach((skill, skillIndex) => {
        list.push({
          id: `skill-${index}-${skillIndex}`,
          toolName: `skill:${skill.name || 'skill'}`,
          arguments: {},
          status: 'success',
          resultSummary: skill.description || '',
          outputPreview: '',
          errorMessage: '',
          durationMs: null,
        })
      })
    }
  })

  return list
})

const isShell = (activity) => activity.toolName === 'execute_shell'
const isReadActivity = (activity) => READ_TOOL_NAMES.has(activity.toolName)
const isWriteFile = (activity) => activity.toolName === 'write_file'
// 写文件成功且拿到路径时，可提供预览/下载入口
const canPreviewFile = (activity) =>
  isWriteFile(activity) && activity.status === 'success' && !!filePathOf(activity)

const filePathOf = (activity) => activity.previewPath || activity.arguments?.file_path || ''

const fileNameOf = (path) => (path ? path.replace(/\\/g, '/').split('/').pop() || path : '')

const normalizeCommands = (activity) => {
  const commands = activity.arguments?.commands
  if (typeof commands === 'string' && commands.trim()) return [commands]
  if (Array.isArray(commands)) {
    return commands.filter((command) => typeof command === 'string' && command.trim())
  }
  return []
}

const hasShellActivities = computed(() => activities.value.some(isShell))

const groupTitle = computed(() => {
  const shellActivities = activities.value.filter(isShell)
  const readActivities = activities.value.filter(isReadActivity)
  const allStatuses = activities.value.map((activity) => activity.status)
  const shellCommandCount = shellActivities.reduce(
    (total, activity) => total + Math.max(normalizeCommands(activity).length, 1),
    0,
  )

  if (shellActivities.some((activity) => activity.status === 'pending_approval')) {
    return '等待确认命令'
  }
  if (allStatuses.includes('running') || allStatuses.includes('pending')) {
    if (shellActivities.length && readActivities.length) return '正在处理文件和命令'
    if (shellActivities.length) return '正在运行命令'
    if (readActivities.length) return '正在查看文件'
    return '正在执行工具操作'
  }
  if (allStatuses.includes('timeout')) {
    return shellActivities.length ? '命令执行超时' : '工具执行超时'
  }
  if (allStatuses.includes('failed')) {
    const hasSuccess = allStatuses.includes('success')
    if (hasSuccess) return '部分工具执行失败'
    if (shellActivities.length) return '命令执行失败'
    if (readActivities.length) return '文件查看失败'
    return '工具执行失败'
  }
  if (allStatuses.includes('rejected')) {
    return shellActivities.length ? '已拒绝运行命令' : '已拒绝工具操作'
  }

  const shellTitle = shellCommandCount > 1 ? '运行了多个命令' : '运行了命令'
  if (shellActivities.length && readActivities.length) return `查看了文件，${shellTitle}`
  if (shellActivities.length) return shellTitle
  if (readActivities.length) return '查看了文件'
  return '执行了工具操作'
})

const statusLabel = (status, labels) => {
  const common = {
    pending: labels.pending,
    pending_approval: labels.approval || labels.pending,
    running: labels.running,
    success: labels.success,
    failed: labels.failed,
    timeout: '执行超时',
    rejected: '已拒绝',
    cancelled: '已取消',
  }
  return common[status] || labels.pending
}

const getStatusLabel = (activity) => {
  if (isShell(activity)) {
    return statusLabel(activity.status, {
      pending: '等待执行',
      approval: '等待确认',
      running: '正在运行',
      success: '已运行',
      failed: '运行失败',
    })
  }
  if (activity.toolName === 'read_file') {
    return statusLabel(activity.status, {
      pending: '等待读取',
      running: '正在读取',
      success: '已读取',
      failed: '读取失败',
    })
  }
  if (activity.toolName === 'file_search') {
    return statusLabel(activity.status, {
      pending: '等待搜索',
      running: '正在搜索',
      success: '已搜索',
      failed: '搜索失败',
    })
  }
  if (activity.toolName === 'list_directory') {
    return statusLabel(activity.status, {
      pending: '等待查看',
      running: '正在查看',
      success: '已查看',
      failed: '查看失败',
    })
  }
  if (activity.toolName === 'write_file') {
    return statusLabel(activity.status, {
      pending: '等待写入',
      running: '正在写入',
      success: '已写入',
      failed: '写入失败',
    })
  }
  return statusLabel(activity.status, {
    pending: '等待执行',
    running: '正在执行',
    success: '已完成',
    failed: '执行失败',
  })
}

const getPrimaryText = (activity) => {
  if (isShell(activity)) {
    const commands = normalizeCommands(activity)
    return commands.length ? commands.join(' ; ') : activity.errorMessage || '未提供命令'
  }
  if (activity.toolName === 'list_directory') return activity.arguments?.dir_path || '.'
  if (activity.toolName === 'read_file') return activity.arguments?.file_path || '未知文件'
  if (activity.toolName === 'write_file') return fileNameOf(filePathOf(activity)) || '未知文件'
  if (activity.toolName === 'file_search') {
    const pattern = activity.arguments?.pattern || '*'
    const dirPath = activity.arguments?.dir_path || '.'
    return `${pattern}（${dirPath}）`
  }
  if (activity.toolName.startsWith('skill:')) return activity.toolName.slice(6)
  return activity.resultSummary || activity.description || activity.toolName
}

const isExpanded = (callId) => expandedToolCallIds.value.has(callId)

const toggleActivity = (activity) => {
  if (isShell(activity)) {
    const next = new Set(expandedToolCallIds.value)
    if (next.has(activity.id)) next.delete(activity.id)
    else next.add(activity.id)
    expandedToolCallIds.value = next
    return
  }
  if (canPreviewFile(activity)) {
    togglePreview(activity)
  }
}

const getShellDetail = (activity) => {
  if (activity.outputPreview) return activity.outputPreview
  if (activity.errorMessage) return activity.errorMessage
  if (activity.status === 'success') {
    const commands = normalizeCommands(activity)
      .map((command) => `$ ${command}`)
      .join('\n')
    return `${commands}\n命令执行成功，无额外输出`.trim()
  }
  const commands = normalizeCommands(activity)
    .map((command) => `$ ${command}`)
    .join('\n')
  return `${commands}\n等待命令执行结果`.trim()
}

// ---- write_file 整文件预览与下载（非 diff）----

const previewLoading = ref(new Set())

const isPreviewLoading = (callId) => previewLoading.value.has(callId)

const previewOf = (activity) => {
  const fetched = fetchedPreviews.value[activity.id]
  if (fetched !== undefined) return { content: fetched.content, language: fetched.language }
  return { content: activity.previewContent, language: activity.previewLanguage || 'text' }
}

const togglePreview = async (activity) => {
  const next = new Set(expandedToolCallIds.value)
  if (next.has(activity.id)) {
    next.delete(activity.id)
    expandedToolCallIds.value = next
    return
  }
  next.add(activity.id)
  expandedToolCallIds.value = next
  // SSE 已带整文件正文时直接用；否则按需拉接口（例如历史消息重放）
  if (activity.previewContent || fetchedPreviews.value[activity.id] !== undefined) return
  await fetchPreview(activity)
}

const fetchPreview = async (activity) => {
  const path = filePathOf(activity)
  if (!path || !props.sessionId) {
    toast.error('缺少会话或文件路径，无法预览')
    return
  }
  const loading = new Set(previewLoading.value)
  loading.add(activity.id)
  previewLoading.value = loading
  try {
    const response = await getWorkspaceFilePreview(props.sessionId, path)
    const data = response.data?.data
    if (data) {
      fetchedPreviews.value = {
        ...fetchedPreviews.value,
        [activity.id]: { content: data.content || '', language: data.language || 'text' },
      }
    } else {
      toast.error(response.data?.message || '预览失败')
    }
  } catch (error) {
    toast.error(error.response?.data?.message || '预览失败，请尝试下载')
  } finally {
    const done = new Set(previewLoading.value)
    done.delete(activity.id)
    previewLoading.value = done
  }
}

// 整文件预览渲染：Markdown 直接渲染富文本，其余按语言走代码块高亮（非 diff）
const renderedPreviewHtml = (activity) => {
  const { content, language } = previewOf(activity)
  if (language === 'markdown') return renderMarkdown(content)
  const fence = language && language !== 'text' ? language : ''
  return renderMarkdown(`\`\`\`${fence}\n${content}\n\`\`\``)
}
</script>

<style lang="scss" scoped>
.tool-activity-panel {
  margin: 0 0 8px 16px;
  color: var(--text-tertiary, #747682);

  @media (max-width: 768px) {
    margin: 0 0 8px;
  }
}

.activity-group-header,
.activity-row {
  width: 100%;
  padding: 0;
  border: 0;
  color: inherit;
  background: transparent;
  font: inherit;
  text-align: left;
}

.activity-group-header {
  display: flex;
  align-items: center;
  min-height: 24px;
  cursor: pointer;
}

.activity-group-icon,
.activity-item-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;

  svg {
    width: 17px;
    height: 17px;
  }
}

.activity-group-icon {
  margin-right: 8px;
}

.activity-group-title {
  min-width: 0;
  color: var(--text-tertiary, #747682);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
}

.activity-chevron,
.item-chevron {
  width: 15px;
  height: 15px;
  margin-left: 6px;
  flex: 0 0 auto;
  transition: transform 0.18s ease;

  &.expanded {
    transform: rotate(90deg);
  }
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 3px;
}

.activity-line {
  display: flex;
  align-items: center;
  gap: 4px;
}

.activity-line .activity-row {
  flex: 1 1 auto;
  min-width: 0;
}

.file-preview {
  margin: 4px 0 8px;
  overflow: hidden;
  border: 1px solid var(--border-color, #dedede);
  border-radius: 10px;
  background: var(--bg-secondary, #f5f5f5);
}

.file-preview-title {
  padding: 8px 12px 5px;
  color: var(--text-secondary, #626262);
  font-size: 13px;
  font-weight: 600;
  word-break: break-all;
}

.file-preview-loading {
  padding: 6px 12px 12px;
  color: var(--text-tertiary, #8a8a8a);
  font-size: 13px;
}

.file-preview-body {
  max-height: 420px;
  padding: 0 12px 12px;
  overflow: auto;
  font-size: 13px;
  line-height: 1.55;
  word-break: break-word;
  overflow-wrap: anywhere;

  :deep(.code-block-wrapper) {
    margin: 0.5em 0;
    border-radius: 10px;
    overflow: hidden;
  }

  :deep(.code-block-wrapper pre) {
    margin: 0;
    padding: 10px 14px;
    overflow-x: auto;
  }

  :deep(pre) {
    max-width: 100%;
  }
}

.activity-row {
  display: flex;
  align-items: center;
  min-height: 24px;
  cursor: default;

  &.expandable {
    cursor: pointer;
  }

  &:disabled {
    opacity: 1;
  }

  &.status-failed,
  &.status-timeout {
    color: #c2410c;
  }

  &.status-rejected,
  &.status-cancelled {
    color: var(--text-tertiary, #8a8a8a);
  }
}

.activity-item-icon {
  width: 19px;
  margin-right: 7px;

  svg {
    width: 16px;
    height: 16px;
  }
}

.activity-status-label {
  flex: 0 0 auto;
  margin-right: 6px;
  color: currentColor;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
}

.activity-primary-text {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  color: var(--text-secondary, #666);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-chevron {
  margin-left: 6px;
}

.shell-detail {
  margin: 4px 0 8px;
  overflow: hidden;
  border: 1px solid var(--border-color, #dedede);
  border-radius: 10px;
  background: var(--bg-secondary, #f5f5f5);
}

.shell-detail-title {
  padding: 8px 12px 5px;
  color: var(--text-secondary, #626262);
  font-size: 13px;
  font-weight: 600;
}

.shell-detail pre {
  max-height: 320px;
  margin: 0;
  padding: 6px 12px 12px;
  overflow: auto;
  color: var(--text-primary, #4d4d4d);
  background: transparent;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: normal;
  white-space: pre-wrap;
}
</style>
