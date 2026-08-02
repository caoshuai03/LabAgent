<!--
 @author: caoshuai.cs
 @date: 2026-07-15 02:11
 @description: Agent高风险删除操作的消息内联审批卡片
-->
<template>
  <section class="tool-approval-inline">
    <div class="approval-heading">{{ heading }}</div>
    <div class="approval-description">此操作可能删除工作区内容，需要你的确认。</div>

    <div class="approval-call-list">
      <div
        v-for="toolCall in approval.tool_calls || []"
        :key="toolCall.tool_call_id"
        class="approval-call"
      >
        <div class="approval-call-label">{{ getCallLabel(toolCall) }}</div>
        <pre>{{ getCallDetail(toolCall) }}</pre>
      </div>
    </div>

    <div class="approval-actions">
      <button type="button" class="approval-button reject" @click="$emit('decision', false)">
        拒绝
      </button>
      <button type="button" class="approval-button allow" @click="$emit('decision', true)">
        允许
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  approval: {
    type: Object,
    required: true,
  },
})

defineEmits(['decision'])

const heading = computed(() => {
  const calls = props.approval.tool_calls || []
  if (calls.some((call) => call.tool_name === 'execute_shell')) return '允许执行删除命令吗？'
  if (calls.some((call) => call.tool_name === 'file_delete')) return '允许删除文件吗？'
  return '允许执行此操作吗？'
})

const getCallLabel = (toolCall) => {
  if (toolCall.tool_name === 'execute_shell') return 'Shell'
  if (toolCall.tool_name === 'file_delete') return '删除文件'
  return toolCall.tool_name || '工具操作'
}

const getCallDetail = (toolCall) => {
  const argumentsValue = toolCall.arguments || {}
  if (toolCall.tool_name === 'execute_shell') {
    const commands = argumentsValue.commands
    if (Array.isArray(commands)) return commands.join('\n')
    return String(commands || '')
  }
  if (toolCall.tool_name === 'file_delete') {
    return String(argumentsValue.file_path || '')
  }
  try {
    return JSON.stringify(argumentsValue, null, 2)
  } catch {
    return String(argumentsValue)
  }
}
</script>

<style lang="scss" scoped>
.tool-approval-inline {
  box-sizing: border-box;
  width: min(calc(100% - 16px), 760px);
  min-width: 0;
  max-width: calc(100% - 16px);
  margin: 10px 0 16px 16px;
  padding: 16px;
  border: 1px solid var(--border-color, #dedede);
  border-radius: 12px;
  color: var(--text-primary, #333);
  background: var(--bg-secondary, #f7f7f7);

  @media (max-width: 768px) {
    width: 100%;
    max-width: 100%;
    margin: 8px 0 12px;
  }
}

.approval-heading {
  font-size: 15px;
  font-weight: 600;
}

.approval-description {
  margin-top: 5px;
  color: var(--text-secondary, #666);
  font-size: 13px;
  line-height: 1.5;
}

.approval-call-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  margin-top: 12px;
}

.approval-call {
  min-width: 0;
  max-width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color, #e1e1e1);
  border-radius: 9px;
  background: var(--bg-primary, #fff);
}

.approval-call-label {
  margin-bottom: 6px;
  color: var(--text-secondary, #666);
  font-size: 12px;
  font-weight: 600;
}

.approval-call pre {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  margin: 0;
  overflow-x: auto;
  overflow-y: hidden;
  color: var(--text-primary, #333);
  background: transparent;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: normal;
  white-space: pre;
}

.approval-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.approval-button {
  min-width: 72px;
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
}

.approval-button.reject {
  border: 1px solid var(--border-color, #d8d8d8);
  color: var(--text-primary, #333);
  background: var(--bg-primary, #fff);
}

.approval-button.allow {
  border: 1px solid #90138b;
  color: #fff;
  background: #90138b;
}

@media (hover: none) and (pointer: coarse) {
  .approval-button {
    min-height: 44px;
    flex: 1;
  }
}
</style>
