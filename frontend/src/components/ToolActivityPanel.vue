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
        <button
          type="button"
          class="activity-row"
          :class="[`status-${activity.status}`, { expandable: isShell(activity) }]"
          :disabled="!isShell(activity)"
          :aria-expanded="isShell(activity) ? isExpanded(activity.id) : undefined"
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
          <span class="activity-primary-text" :title="getPrimaryText(activity)">
            {{ getPrimaryText(activity) }}
          </span>
          <svg
            v-if="isShell(activity)"
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

        <div v-if="isShell(activity) && isExpanded(activity.id)" class="shell-detail">
          <div class="shell-detail-title">Shell</div>
          <pre>{{ getShellDetail(activity) }}</pre>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  toolEvents: {
    type: Array,
    default: () => [],
  },
})

const READ_TOOL_NAMES = new Set(['list_directory', 'read_file', 'file_search'])
const groupExpanded = ref(true)
const expandedToolCallIds = ref(new Set())

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
  if (!isShell(activity)) return
  const next = new Set(expandedToolCallIds.value)
  if (next.has(activity.id)) next.delete(activity.id)
  else next.add(activity.id)
  expandedToolCallIds.value = next
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
</script>

<style lang="scss" scoped>
.tool-activity-panel {
  width: min(100%, 760px);
  margin: 0 0 16px 16px;
  color: var(--text-secondary, #626262);

  @media (max-width: 768px) {
    margin: 0 0 12px;
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
  min-height: 32px;
  cursor: pointer;
}

.activity-group-icon,
.activity-item-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;

  svg {
    width: 20px;
    height: 20px;
  }
}

.activity-group-icon {
  margin-right: 10px;
}

.activity-group-title {
  min-width: 0;
  color: var(--text-secondary, #666);
  font-size: 15px;
  font-weight: 600;
}

.activity-chevron,
.item-chevron {
  width: 17px;
  height: 17px;
  margin-left: 8px;
  flex: 0 0 auto;
  transition: transform 0.18s ease;

  &.expanded {
    transform: rotate(90deg);
  }
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}

.activity-row {
  display: flex;
  align-items: center;
  min-height: 32px;
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
  width: 24px;
  margin-right: 8px;

  svg {
    width: 19px;
    height: 19px;
  }
}

.activity-status-label {
  flex: 0 0 auto;
  margin-right: 7px;
  color: currentColor;
  font-size: 14px;
  font-weight: 500;
}

.activity-primary-text {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  color: var(--text-secondary, #666);
  font-family: inherit;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-chevron {
  margin-left: 8px;
}

.shell-detail {
  margin: 4px 0 10px;
  overflow: hidden;
  border: 1px solid var(--border-color, #dedede);
  border-radius: 10px;
  background: var(--bg-secondary, #f5f5f5);
}

.shell-detail-title {
  padding: 10px 14px 6px;
  color: var(--text-secondary, #626262);
  font-size: 13px;
  font-weight: 600;
}

.shell-detail pre {
  max-height: 320px;
  margin: 0;
  padding: 8px 14px 14px;
  overflow: auto;
  color: var(--text-primary, #4d4d4d);
  background: transparent;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: normal;
  white-space: pre-wrap;
}
</style>
