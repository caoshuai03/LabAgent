<!--
 @author: caoshuai.cs
 @date: 2026-07-30 00:00
 @description: 用户 AGENTS.md 与事实、偏好、历史经验长期记忆管理页面
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
        <section class="agents-panel">
          <div class="section-heading agents-heading">
            <div>
              <h2>AGENTS.md</h2>
            </div>
            <div class="agents-actions">
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
            class="agents-editor"
            spellcheck="false"
            aria-label="编辑我的 AGENTS.md"
          ></textarea>
        </section>

        <section class="items-panel">
          <div class="section-heading items-heading">
            <div>
              <h2>记忆</h2>
              <p>从对话中保留的事实、偏好和经验，可随时编辑、停用或删除。</p>
            </div>
            <select v-model="activeType" class="type-filter" @change="loadItems">
              <option value="">全部</option>
              <option value="fact">用户事实</option>
              <option value="preference">用户偏好</option>
              <option value="experience">历史经验</option>
            </select>
          </div>

          <div v-if="loading" class="state-text">加载中...</div>
          <div v-else-if="items.length === 0" class="state-text">暂无记忆</div>
          <div v-else class="memory-list">
            <article v-for="item in items" :key="item.memory_id" class="memory-card">
              <div class="card-header">
                <span class="memory-type">{{ typeLabel(item.memory_type) }}</span>
                <span v-if="item.status === 'disabled'" class="disabled-tag">已停用</span>
              </div>
              <input
                v-if="editingId === item.memory_id"
                v-model="editTitle"
                class="edit-title"
                maxlength="200"
              />
              <h3 v-else>{{ item.title }}</h3>
              <textarea
                v-if="editingId === item.memory_id"
                v-model="editContent"
                class="edit-content"
                maxlength="8000"
              ></textarea>
              <p v-else class="memory-content">{{ item.content }}</p>
              <div class="card-meta">
                <span>{{ formatTime(item.updated_at) }}</span>
                <span v-if="item.source_session_id">来源会话可追溯</span>
              </div>
              <div class="card-actions">
                <template v-if="editingId === item.memory_id">
                  <button class="text-button" @click="cancelEdit">取消</button>
                  <button class="primary-button small" @click="saveItem(item)">保存</button>
                </template>
                <template v-else>
                  <button class="text-button" @click="startEdit(item)">编辑</button>
                  <button class="text-button" @click="toggleItem(item)">
                    {{ item.status === 'active' ? '停用' : '启用' }}
                  </button>
                  <button class="text-button danger" @click="removeItem(item)">删除</button>
                </template>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import { useChatStore } from '../stores/chat'
import { useConfirm } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'
import {
  deleteMemoryItem,
  getAgentsMemory,
  getMemoryItems,
  updateAgentsMemory,
  updateMemoryItem,
} from '../api/memory'

defineOptions({ name: 'MemoryManagement' })

const chatStore = useChatStore()
const { confirm } = useConfirm()
const toast = useToast()
const agentsContent = ref('')
const savedAgentsContent = ref('')
const agentsSaving = ref(false)
const items = ref([])
const loading = ref(false)
const activeType = ref('')
const editingId = ref('')
const editTitle = ref('')
const editContent = ref('')

const typeLabel = (type) =>
  ({
    fact: '用户事实',
    preference: '用户偏好',
    experience: '历史经验',
  })[type] || type

const formatTime = (value) => {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN')
}

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

const loadItems = async () => {
  loading.value = true
  try {
    const params = { page: 1, page_size: 100 }
    if (activeType.value) params.memory_type = activeType.value
    const response = await getMemoryItems(params)
    items.value = response.data.data?.records || []
  } catch (error) {
    toast.error(error.response?.data?.message || '加载长期记忆失败')
  } finally {
    loading.value = false
  }
}

const startEdit = (item) => {
  editingId.value = item.memory_id
  editTitle.value = item.title
  editContent.value = item.content
}

const cancelEdit = () => {
  editingId.value = ''
}

const saveItem = async (item) => {
  try {
    await updateMemoryItem(item.memory_id, {
      title: editTitle.value,
      content: editContent.value,
    })
    editingId.value = ''
    await loadItems()
    toast.success('长期记忆已更新')
  } catch (error) {
    toast.error(error.response?.data?.message || '更新长期记忆失败')
  }
}

const toggleItem = async (item) => {
  try {
    await updateMemoryItem(item.memory_id, {
      status: item.status === 'active' ? 'disabled' : 'active',
    })
    await loadItems()
  } catch (error) {
    toast.error(error.response?.data?.message || '更新记忆状态失败')
  }
}

const removeItem = async (item) => {
  const confirmed = await confirm({
    title: '删除记忆',
    message: `确定要删除“${item.title}”吗？`,
    description: '删除后，这条记忆将无法恢复。',
    confirm_text: '确认删除',
    tone: 'danger',
  })
  if (!confirmed) return

  try {
    await deleteMemoryItem(item.memory_id)
    await loadItems()
    toast.success('长期记忆已删除')
  } catch (error) {
    toast.error(error.response?.data?.message || '删除长期记忆失败')
  }
}

onMounted(() => {
  chatStore.initialize()
  loadAgents()
  loadItems()
})
</script>

<style lang="scss" scoped>
.memory-page {
  display: flex;
  width: 100vw;
  height: 100vh;
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

.agents-panel,
.items-panel {
  min-width: 0;
}

.items-panel {
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

.agents-heading h2 {
  margin-bottom: 0;
}

.agents-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.agents-editor {
  width: 100%;
  min-height: 460px;
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

  &.small {
    padding: 6px 12px;
  }
}

.type-filter {
  height: 34px;
  padding: 0 30px 0 11px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
}

.memory-list {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border-color);
}

.memory-card {
  padding: 20px 2px;
  border-bottom: 1px solid var(--border-color);

  h3 {
    margin: 10px 0 7px;
    color: var(--text-primary);
    font-size: 15px;
    font-weight: 600;
  }
}

.card-header,
.card-meta,
.card-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.memory-type,
.disabled-tag {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(144, 19, 139, 0.08);
  color: var(--primary-color);
  font-size: 11px;
}

.disabled-tag {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.memory-content {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
}

.card-meta {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 11px;
}

.card-actions {
  justify-content: flex-end;
  margin-top: 8px;
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

  &.danger {
    color: #dc2626;
  }
}

.edit-title,
.edit-content {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  outline: none;

  &:focus {
    border-color: rgba(144, 19, 139, 0.5);
  }
}

.edit-content {
  min-height: 140px;
  margin-top: 8px;
  resize: vertical;
}

.state-text {
  padding: 56px 0;
  border-top: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
}

@media (max-width: 900px) {
  .memory-main {
    padding: 32px 24px 56px;
  }

  .page-header {
    margin-bottom: 34px;
  }

  .agents-editor {
    min-height: 400px;
  }
}

@media (max-width: 600px) {
  .memory-main {
    padding: 28px 16px 48px;
  }

  .page-header {
    margin-bottom: 30px;

    h1 {
      font-size: 24px;
    }
  }

  .memory-layout {
    gap: 42px;
  }

  .section-heading {
    align-items: flex-start;
    gap: 16px;
  }

  .agents-editor {
    min-height: 340px;
    padding: 16px;
  }

  .items-panel {
    padding-top: 36px;
  }

  .items-heading {
    flex-direction: column;
  }

  .type-filter {
    width: 100%;
  }
}
</style>
