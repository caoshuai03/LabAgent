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
        <ToolActivityIcon tool-name="tool" />
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
            :class="[`status-${activity.status}`, { expandable: isShell(activity) }]"
            :disabled="!isShell(activity)"
            :aria-expanded="isShell(activity) ? isExpanded(activity.id) : undefined"
            @click="toggleActivity(activity)"
          >
            <span class="activity-item-icon" aria-hidden="true">
              <ToolActivityIcon :tool-name="activity.toolName" />
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
        </div>

        <div v-if="isShell(activity) && isExpanded(activity.id)" class="shell-detail">
          <div class="shell-detail-title">Shell</div>
          <pre>{{ getShellDetail(activity) }}</pre>
        </div>

      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import ToolActivityIcon from './icons/ToolActivityIcon.vue'

const props = defineProps({
  toolEvents: {
    type: Array,
    default: () => [],
  },
  completed: {
    type: Boolean,
    default: false,
  },
})

const READ_TOOL_NAMES = new Set(['list_directory', 'read_file', 'file_search'])
const SKILL_ACTIVATION_TOOL_NAME = 'activate_skill'
const SKILL_RESOURCE_TOOL_NAME = 'read_skill_resource'
const groupExpanded = ref(!props.completed)
const expandedToolCallIds = ref(new Set())

watch(
  () => props.completed,
  (completed) => {
    if (completed) groupExpanded.value = false
  },
)

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
    }
    activeCalls.set(callId, activity)
    list.push(activity)
  }
  return activity
}

const activities = computed(() => {
  const list = []
  const activeCalls = new Map()
  const toolCallsById = new Map(
    props.toolEvents
      .filter((event) => event?.eventType === 'tool_call' && event?.payload?.tool_call_id)
      .map((event) => [event.payload.tool_call_id, event.payload]),
  )

  props.toolEvents.forEach((event, index) => {
    const payload = event?.payload || {}
    const originalCall = toolCallsById.get(payload.tool_call_id) || {}
    const toolName = payload.tool_name || originalCall.tool_name

    if (event?.eventType === 'tool_call') {
      if (toolName === SKILL_RESOURCE_TOOL_NAME) return
      if (toolName === SKILL_ACTIVATION_TOOL_NAME) {
        const skillName = payload.arguments?.name || 'skill'
        const activity = ensureActivity(
          list,
          activeCalls,
          { ...payload, tool_name: `skill:${skillName}` },
          index,
        )
        activity.status = 'running'
        return
      }
      const activity = ensureActivity(list, activeCalls, payload, index)
      activity.arguments = payload.arguments || {}
      activity.description = payload.description || ''
      return
    }

    if (event?.eventType === 'tool_result') {
      const status = payload.status || (payload.success === false ? 'failed' : 'success')
      if (toolName === SKILL_RESOURCE_TOOL_NAME && status === 'success') return
      const skillName = originalCall.arguments?.name || 'skill'
      const activity = ensureActivity(
        list,
        activeCalls,
        {
          ...payload,
          arguments: originalCall.arguments || {},
          tool_name:
            toolName === SKILL_ACTIVATION_TOOL_NAME ? `skill:${skillName}` : toolName,
        },
        index,
      )
      activity.status = status
      activity.resultSummary = payload.result_summary || ''
      activity.outputPreview = payload.output_preview || ''
      activity.errorMessage = payload.error_message || ''
      activity.durationMs = payload.duration_ms ?? null
      if (payload.preview_path) activity.previewPath = payload.preview_path
      return
    }

    if (event?.eventType === 'status') {
      if (payload.stage === 'global_timeout') {
        list.push({
          id: `global-timeout-${index}`,
          toolName: 'global_timeout',
          arguments: {},
          status: 'timeout',
          resultSummary: `Agent执行超时（${payload.timeout_seconds || 1200}秒）`,
          outputPreview: '',
          errorMessage: payload.message || '',
          durationMs: null,
        })
        return
      }
      const status = statusFromStage(payload.stage, payload.success)
      if (toolName === SKILL_RESOURCE_TOOL_NAME && !['failed', 'timeout'].includes(status)) return
      const skillName = originalCall.arguments?.name || 'skill'
      const activity = ensureActivity(
        list,
        activeCalls,
        {
          ...payload,
          arguments: originalCall.arguments || {},
          tool_name:
            toolName === SKILL_ACTIVATION_TOOL_NAME ? `skill:${skillName}` : toolName,
        },
        index,
      )
      activity.status = status || activity.status
      if (payload.message) activity.errorMessage = payload.message
      if (payload.duration_ms !== undefined) activity.durationMs = payload.duration_ms
      return
    }

    if (event?.eventType === 'skill_loaded') {
      ;(payload.skills || []).forEach((skill, skillIndex) => {
        const activity = ensureActivity(
          list,
          activeCalls,
          {
            tool_call_id: payload.tool_call_id || `skill-${index}-${skillIndex}`,
            tool_name: `skill:${skill.name || 'skill'}`,
          },
          index,
        )
        activity.toolName = `skill:${skill.name || 'skill'}`
        activity.status = 'success'
        activity.resultSummary = skill.description || ''
      })
    }
  })

  return [
    ...list.filter((activity) => activity.toolName.startsWith('skill:')),
    ...list.filter((activity) => !activity.toolName.startsWith('skill:')),
  ]
})

const isShell = (activity) => activity.toolName === 'execute_shell'
const isReadActivity = (activity) => READ_TOOL_NAMES.has(activity.toolName)
const isSkillActivity = (activity) => activity.toolName.startsWith('skill:')

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

const groupTitle = computed(() => {
  const shellActivities = activities.value.filter(isShell)
  const readActivities = activities.value.filter(isReadActivity)
  const skillActivities = activities.value.filter(isSkillActivity)
  const onlySkillActivities =
    skillActivities.length > 0 && skillActivities.length === activities.value.length
  const allStatuses = activities.value.map((activity) => activity.status)
  const hasSuccessfulActivity = allStatuses.includes('success')
  const hasUnexecutedActivity = allStatuses.some((status) =>
    ['rejected', 'cancelled'].includes(status),
  )
  const shellCommandCount = shellActivities.reduce(
    (total, activity) => total + Math.max(normalizeCommands(activity).length, 1),
    0,
  )

  if (shellActivities.some((activity) => activity.status === 'pending_approval')) {
    return '等待确认命令'
  }
  if (allStatuses.includes('running') || allStatuses.includes('pending')) {
    if (onlySkillActivities) return '正在加载技能'
    if (shellActivities.length && readActivities.length) return '正在处理文件和命令'
    if (shellActivities.length) return '正在运行命令'
    if (readActivities.length) return '正在查看文件'
    return '正在执行工具操作'
  }
  if (allStatuses.includes('timeout')) {
    return shellActivities.length ? '命令执行超时' : '工具执行超时'
  }
  if (hasUnexecutedActivity) {
    if (hasSuccessfulActivity) return '运行了多个命令'
    const allUnexecuted = allStatuses.every((status) => ['rejected', 'cancelled'].includes(status))
    if (allUnexecuted) {
      return shellActivities.length === activities.value.length
        ? '已拒绝运行命令'
        : '已拒绝工具操作'
    }
    return '部分工具操作未执行'
  }

  const shellTitle = shellCommandCount > 1 ? '运行了多个命令' : '运行了命令'
  if (shellActivities.length && readActivities.length) return `查看了文件，${shellTitle}`
  if (shellActivities.length) return shellTitle
  if (readActivities.length) return '查看了文件'
  if (onlySkillActivities) return '加载了技能'
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
  if (isSkillActivity(activity)) {
    return statusLabel(activity.status, {
      pending: '加载技能',
      running: '加载技能',
      success: '加载技能',
      failed: '加载失败',
    })
  }
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
  box-sizing: border-box;
  width: calc(100% - 16px);
  min-width: 0;
  max-width: calc(100% - 16px);
  margin: 0 0 8px 16px;
  color: var(--text-tertiary, #747682);

  @media (max-width: 768px) {
    width: 100%;
    max-width: 100%;
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
  font-size: 13px;
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
  min-width: 0;
  max-width: 100%;
  margin-top: 3px;
}

.activity-item {
  min-width: 0;
  max-width: 100%;
}

.activity-line {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  max-width: 100%;
}

.activity-line .activity-row {
  flex: 1 1 auto;
  min-width: 0;
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
  color: currentColor;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-chevron {
  margin-left: 6px;
}

.shell-detail {
  min-width: 0;
  max-width: 100%;
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
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  margin: 0;
  padding: 6px 12px 12px;
  overflow-x: auto;
  overflow-y: hidden;
  color: var(--text-primary, #4d4d4d);
  background: transparent;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: normal;
  white-space: pre;
}

@media (hover: none) and (pointer: coarse) {
  .activity-group-header,
  .activity-row {
    min-height: 44px;
  }
}
</style>
