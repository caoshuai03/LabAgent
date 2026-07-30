<template>
  <div class="skills-container">
    <Sidebar />
    <div class="skills-main">
      <div class="skills-content">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <span>加载中...</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="skills.length === 0" class="empty-state">
          <div class="empty-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
            </svg>
          </div>
          <h3>暂无技能</h3>
        </div>

        <!-- Skills列表 -->
        <div v-else class="skills-list">
          <div
            v-for="skill in skills"
            :key="skill.name"
            class="skill-card"
            @click="showSkillDetail(skill)"
          >
            <div class="skill-header">
              <h3 class="skill-name">{{ skill.name }}</h3>
            </div>
            <p class="skill-description">{{ skill.description }}</p>
          </div>
        </div>

        <!-- Skill 详情对话框 -->
        <div v-if="detailDialogVisible" class="dialog-overlay" @click="detailDialogVisible = false">
          <div class="dialog-content" @click.stop>
            <div class="dialog-header">
              <h2>{{ currentSkill?.name }}</h2>
              <button class="close-btn" @click="detailDialogVisible = false">✕</button>
            </div>
            <div v-if="currentSkill" class="skill-detail">
              <div v-if="detailLoading" class="detail-loading">详情加载中...</div>
              <div class="detail-section">
                <h4>技能简介</h4>
                <p class="description">{{ currentSkill.description }}</p>
              </div>

              <div v-if="!detailLoading && skillDetail?.content" class="detail-section">
                <h4>详细说明</h4>
                <div class="markdown-content" v-html="renderedContent"></div>
              </div>

              <div v-if="!detailLoading && skillDetail?.resources?.length" class="detail-section">
                <h4>按需资源</h4>
                <ul class="resource-list">
                  <li v-for="resource in skillDetail.resources" :key="resource">{{ resource }}</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getSkillDetail, getSkills } from '../api/skills'
import Sidebar from '../components/Sidebar.vue'
import { useChatStore } from '../stores/chat'
import { renderMarkdown } from '../utils/markdown'
import { useToast } from '../composables/useToast'

const chatStore = useChatStore()
const toast = useToast()

const skills = ref([])
const loading = ref(false)
const detailDialogVisible = ref(false)
const currentSkill = ref(null)
const skillDetail = ref(null)
const detailLoading = ref(false)

const renderedContent = computed(() => {
  if (!skillDetail.value?.content) return ''
  return renderMarkdown(skillDetail.value.content)
})

const loadSkills = async () => {
  loading.value = true
  try {
    const response = await getSkills()
    skills.value = response.data.data || []
  } catch (error) {
    console.error('加载技能失败:', error)
    toast.error('加载技能失败')
  } finally {
    loading.value = false
  }
}

const showSkillDetail = async (skill) => {
  currentSkill.value = skill
  detailDialogVisible.value = true
  skillDetail.value = null
  detailLoading.value = true
  try {
    const response = await getSkillDetail(skill.name)
    skillDetail.value = response.data.data
  } catch (error) {
    console.error('加载技能详情失败:', error)
    toast.error('加载技能详情失败')
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  chatStore.initialize()
  loadSkills()
})
</script>

<style lang="scss" scoped>
.skills-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: var(--bg-primary);
  transition: background-color 0.3s ease;
}

.skills-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  min-width: 0;
}

.skills-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow: auto;
}

// ==================== 加载 & 空状态 ====================
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-secondary);

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: #90138b;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px 0;
  color: var(--text-secondary);

  .empty-icon {
    color: var(--text-secondary);
    opacity: 0.4;
  }

  h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
  }
}

// ==================== Skills列表 ====================
.skills-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skill-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  background-color: var(--bg-secondary);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: rgba(144, 19, 139, 0.3);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(144, 19, 139, 0.1);
  }
}

.skill-header {
  margin-bottom: 8px;
}

.skill-name {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.skill-description {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

// ==================== 弹窗样式 ====================
.dialog-overlay {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-content {
  width: 600px;
  max-width: 90vw;
  max-height: 85vh;
  background-color: var(--bg-primary);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: linear-gradient(180deg, rgba(144, 19, 139, 0.04), transparent);

  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: 0.2px;
  }

  .close-btn {
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.2s;

    &:hover {
      background-color: var(--bg-hover);
    }
  }
}

.skill-detail {
  padding: 20px 24px 24px;
  overflow-y: auto;
}

.detail-loading {
  padding: 12px 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.resource-list {
  margin: 0;
  padding-left: 20px;
  color: var(--text-secondary);
  font-family: monospace;
  font-size: 13px;
  line-height: 1.8;
}

.detail-section {
  margin-bottom: 20px;
  padding: 6px 0 0;
  border: none;
  border-radius: 0;
  background: transparent;

  &:last-child {
    margin-bottom: 0;
  }

  h4 {
    font-size: 15px;
    font-weight: 800;
    color: var(--text-primary);
    margin: 0 0 12px 0;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    letter-spacing: 0.2px;

    &::before {
      content: '';
      width: 5px;
      height: 16px;
      border-radius: 999px;
      background: #90138b;
      flex-shrink: 0;
    }
  }

  .description {
    margin: 0;
    font-size: 14px;
    color: var(--text-secondary);
    line-height: 1.8;
    white-space: pre-wrap;
  }
}

.markdown-content {
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

// ==================== 动画 ====================
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

// ==================== 响应式 ====================
@media (max-width: 768px) {
  .skills-content {
    padding: 12px;
  }

  .dialog-content {
    width: 95vw;
  }

  .dialog-header,
  .skill-detail {
    padding-left: 16px;
    padding-right: 16px;
  }

  .detail-section {
    padding-top: 4px;
  }
}
</style>
