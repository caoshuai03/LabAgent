<!--
 @author: caoshuai.cs
 @date: 2026-07-30 00:00
 @description: 用户 AGENTS.md 与个性化记忆管理页面
-->
<template>
  <div class="memory-page">
    <Sidebar />
    <main class="memory-main">
      <header class="page-header">
        <div>
          <h1>规则与记忆</h1>
        </div>
      </header>

      <div class="memory-layout">
        <section class="memory-panel">
          <div class="section-heading">
            <div>
              <h2>AGENTS.md</h2>
            </div>
            <div class="editor-actions">
              <button
                class="text-button"
                :disabled="agentsSaving || agentsContent === savedAgentsContent"
                @click="cancelAgentsEdit"
              >
                取消
              </button>
              <button
                class="primary-button"
                :disabled="agentsSaving || agentsContent === savedAgentsContent"
                @click="saveAgents"
              >
                {{ agentsSaving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
          <textarea
            v-model="agentsContent"
            class="memory-editor"
            spellcheck="false"
            aria-label="编辑我的 AGENTS.md"
          ></textarea>
        </section>

        <section class="memory-panel profile-panel">
          <div class="section-heading">
            <div>
              <h2>个性化信息</h2>
              <p>系统会从对话中了解你的稳定偏好、背景与协作方式，用于提供更贴合你的回答。</p>
            </div>
            <label class="memory-switch">
              <span>个性化记忆</span>
              <input
                v-model="longTermMemoryEnabled"
                type="checkbox"
                role="switch"
                :aria-checked="longTermMemoryEnabled"
                :disabled="settingsSaving"
                @change="saveSettings"
              />
              <span class="switch-track" aria-hidden="true">
                <span class="switch-thumb"></span>
              </span>
            </label>
          </div>
          <textarea
            v-model="profileContent"
            class="memory-editor profile-editor"
            spellcheck="false"
            readonly
            aria-label="查看我的个性化信息"
          ></textarea>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import { useChatStore } from '../stores/chat'
import { useToast } from '../composables/useToast'
import {
  getAgentsMemory,
  getMemorySettings,
  getUserProfileMemory,
  updateAgentsMemory,
  updateMemorySettings,
} from '../api/memory'

defineOptions({ name: 'MemoryManagement' })

const chatStore = useChatStore()
const toast = useToast()
const agentsContent = ref('')
const savedAgentsContent = ref('')
const agentsSaving = ref(false)
const profileContent = ref('')
const longTermMemoryEnabled = ref(true)
const settingsSaving = ref(false)

const loadAgents = async () => {
  try {
    const response = await getAgentsMemory()
    const content = response.data.data?.content ?? ''
    agentsContent.value = content
    savedAgentsContent.value = content
  } catch (error) {
    toast.error(error.response?.data?.message || '加载 AGENTS.md 失败')
  }
}

const saveAgents = async () => {
  agentsSaving.value = true
  try {
    const response = await updateAgentsMemory(agentsContent.value)
    const content = response.data.data?.content ?? agentsContent.value
    agentsContent.value = content
    savedAgentsContent.value = content
    toast.success('AGENTS.md 已保存')
  } catch (error) {
    toast.error(error.response?.data?.message || '保存 AGENTS.md 失败')
  } finally {
    agentsSaving.value = false
  }
}

const cancelAgentsEdit = () => {
  agentsContent.value = savedAgentsContent.value
}

const loadProfile = async () => {
  try {
    const response = await getUserProfileMemory()
    const content = response.data.data?.content ?? ''
    profileContent.value = content
  } catch (error) {
    toast.error(error.response?.data?.message || '加载 USER_PROFILE.md 失败')
  }
}

const loadSettings = async () => {
  try {
    const response = await getMemorySettings()
    longTermMemoryEnabled.value = response.data.data?.long_term_memory_enabled ?? true
  } catch (error) {
    toast.error(error.response?.data?.message || '加载个性化记忆设置失败')
  }
}

const saveSettings = async () => {
  settingsSaving.value = true
  const nextValue = longTermMemoryEnabled.value
  try {
    const response = await updateMemorySettings(nextValue)
    longTermMemoryEnabled.value = response.data.data?.long_term_memory_enabled ?? nextValue
    toast.success(longTermMemoryEnabled.value ? '个性化记忆已开启' : '个性化记忆已关闭')
  } catch (error) {
    longTermMemoryEnabled.value = !nextValue
    toast.error(error.response?.data?.message || '保存个性化记忆设置失败')
  } finally {
    settingsSaving.value = false
  }
}

onMounted(() => {
  chatStore.initialize()
  loadAgents()
  loadProfile()
  loadSettings()
})
</script>

<style lang="scss" scoped>
.memory-page {
  display: flex;
  width: 100vw;
  height: var(--app-height, 100vh);
  overflow: hidden;
  background: var(--app-page-bg);
}

.memory-main {
  flex: 1;
  min-width: 0;
  padding: 48px 40px 72px;
  overflow: auto;
}

.page-header {
  max-width: 900px;
  margin: 0 auto 40px;

  h1 {
    margin: 0;
    color: var(--text-primary);
    font-size: 28px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
}

.memory-layout {
  display: flex;
  flex-direction: column;
  gap: 52px;
  max-width: 900px;
  margin: 0 auto;
}

.memory-panel {
  min-width: 0;
}

.profile-panel {
  padding-top: 44px;
  border-top: 1px solid var(--border-color);
}

.section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;

  h2 {
    margin: 0 0 6px;
    color: var(--text-primary);
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.01em;
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 13px;
    line-height: 1.6;
  }
}

.editor-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.memory-editor {
  width: 100%;
  min-height: 420px;
  padding: 20px 22px;
  resize: vertical;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  outline: none;
  background: var(--bg-primary);
  color: var(--text-primary);
  font:
    13px/1.75 ui-monospace,
    SFMono-Regular,
    Menlo,
    Monaco,
    Consolas,
    monospace;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;

  &:focus {
    border-color: rgba(144, 19, 139, 0.5);
    box-shadow: 0 0 0 3px rgba(144, 19, 139, 0.07);
  }
}

.profile-editor {
  min-height: 360px;
  color: var(--text-secondary);
}

.memory-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
  cursor: pointer;

  input {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    opacity: 0;
    pointer-events: none;
  }

  .switch-track {
    position: relative;
    width: 36px;
    height: 20px;
    flex: 0 0 36px;
    border-radius: 999px;
    background: var(--border-color);
    transition: background 0.2s ease;
  }

  .switch-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
    transition: transform 0.2s ease;
  }

  input:checked + .switch-track {
    background: var(--primary-color);
  }

  input:checked + .switch-track .switch-thumb {
    transform: translateX(16px);
  }

  input:focus-visible + .switch-track {
    box-shadow: 0 0 0 3px rgba(144, 19, 139, 0.16);
  }

  &:has(input:disabled) {
    cursor: not-allowed;
    opacity: 0.55;
  }
}

.primary-button,
.text-button {
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  font: inherit;
}

.primary-button {
  min-height: 34px;
  padding: 7px 14px;
  background: rgba(144, 19, 139, 0.12);
  color: var(--primary-color);
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s ease;

  &:not(:disabled):hover {
    background: rgba(144, 19, 139, 0.18);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.text-button {
  padding: 5px 7px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;

  &:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  &:disabled:hover {
    background: transparent;
    color: var(--text-secondary);
  }
}

@media (max-width: 900px) {
  .memory-main {
    padding: 32px 24px 56px;
  }

  .page-header {
    margin-bottom: 34px;
  }

  .memory-editor {
    min-height: 400px;
  }
}

@media (max-width: 768px) {
  .memory-main {
    padding-top: calc(68px + env(safe-area-inset-top));
  }

  .page-header {
    display: none;
  }
}

@media (max-width: 600px) {
  .memory-main {
    padding: calc(68px + env(safe-area-inset-top)) 16px max(48px, env(safe-area-inset-bottom));
    overscroll-behavior-y: contain;
  }

  .page-header {
    display: none;
  }

  .memory-layout {
    gap: 42px;
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 16px;
  }

  .editor-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .primary-button,
  .text-button {
    min-height: 44px;
    padding-right: 16px;
    padding-left: 16px;
  }

  .memory-switch {
    min-height: 44px;
    white-space: normal;
  }

  .memory-editor {
    height: min(48dvh, 420px);
    min-height: 260px;
    padding: 16px;
    font-size: 16px;
    resize: none;
  }

  .profile-panel {
    padding-top: 36px;
  }
}
</style>
