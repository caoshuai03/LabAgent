<!--
 @author: caoshuai.cs
 @date: 2026-07-30 16:49
 @description: Agent 当前已注册工具及运行超时状态的活动图标映射
-->
<template>
  <svg
    v-if="toolName.startsWith('skill:')"
    class="tool-activity-icon skill-activity-icon tool-icon-sparkles"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path
      d="m12 3-1.15 3.1a4.5 4.5 0 0 1-2.65 2.65L5 10l3.2 1.25a4.5 4.5 0 0 1 2.65 2.65L12 17l1.15-3.1a4.5 4.5 0 0 1 2.65-2.65L19 10l-3.2-1.25a4.5 4.5 0 0 1-2.65-2.65L12 3Z"
    ></path>
    <path
      d="m19 16-.55 1.45A2.5 2.5 0 0 1 17 18.9l-1.5.6 1.5.6a2.5 2.5 0 0 1 1.45 1.45L19 23l.55-1.45A2.5 2.5 0 0 1 21 20.1l1.5-.6-1.5-.6a2.5 2.5 0 0 1-1.45-1.45L19 16Z"
    ></path>
  </svg>

  <svg
    v-else-if="toolName === 'read_skill_resource'"
    class="tool-activity-icon tool-icon-book-open"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M2 4.5A2.5 2.5 0 0 1 4.5 2H10a2 2 0 0 1 2 2v17a3 3 0 0 0-3-3H2V4.5Z"></path>
    <path d="M22 4.5A2.5 2.5 0 0 0 19.5 2H14a2 2 0 0 0-2 2v17a3 3 0 0 1 3-3h7V4.5Z"></path>
  </svg>

  <svg
    v-else-if="toolName === 'search_knowledge_base'"
    class="tool-activity-icon tool-icon-database-search"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <ellipse cx="9" cy="5" rx="6" ry="3"></ellipse>
    <path d="M3 5v5c0 1.65 2.69 3 6 3 1.1 0 2.13-.15 3-.42"></path>
    <path d="M3 10v5c0 1.65 2.69 3 6 3"></path>
    <circle cx="16.5" cy="16.5" r="3.5"></circle>
    <path d="m19 19 2.5 2.5"></path>
  </svg>

  <svg
    v-else-if="toolName === 'write_file'"
    class="tool-activity-icon tool-icon-file-pen"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h8"></path>
    <path d="M14 2v6h6"></path>
    <path d="m14.5 18.5 5-5a1.4 1.4 0 0 1 2 2l-5 5-3 .5.5-3Z"></path>
  </svg>

  <svg
    v-else-if="toolName === 'execute_shell'"
    class="tool-activity-icon tool-icon-terminal"
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
    v-else-if="toolName === 'global_timeout'"
    class="tool-activity-icon tool-icon-clock-alert"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="12" cy="12" r="9"></circle>
    <path d="M12 7v5l3 2"></path>
    <path d="M20 4v4"></path>
    <path d="M20 11h.01"></path>
  </svg>

  <svg
    v-else
    class="tool-activity-icon tool-icon-wrench"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path
      d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-8 8l-7 7a2.1 2.1 0 0 1-3-3l7-7a6 6 0 0 1 8-8l-3.8 3.8Z"
    ></path>
  </svg>
</template>

<script setup>
defineProps({
  toolName: {
    type: String,
    required: true,
  },
})
</script>

<style scoped>
.tool-activity-icon {
  width: 16px;
  height: 16px;
}
</style>
