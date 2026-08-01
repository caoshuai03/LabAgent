<template>
  <div class="knowledge-container">
    <Sidebar />
    <div class="knowledge-main">
      <div
        :class="[
          'knowledge-content',
          {
            'dragging-upload': isDraggingUpload,
            'sidebar-collapsed': chatStore.sidebarCollapsed,
          },
        ]"
        @dragenter.prevent="handleUploadDragEnter"
        @dragover.prevent
        @dragleave.prevent="handleUploadDragLeave"
        @drop.prevent="handleUploadDrop"
      >
        <div v-if="isDraggingUpload" class="upload-drop-hint" aria-hidden="true">
          <UploadIcon :size="22" />
          <span>松开以上传知识库文件</span>
        </div>
        <div v-if="uploading" class="uploading-overlay" role="status" aria-live="polite">
          <div class="uploading-modal">
            <div class="uploading-content">
              <div class="uploading-text">
                {{ uploadProgress === null ? '文件上传中...' : `文件上传中 ${uploadProgress}%` }}
              </div>
              <div class="upload-progress-track">
                <div
                  :class="['upload-progress-bar', { indeterminate: uploadProgress === null }]"
                  :style="uploadProgress === null ? undefined : { width: `${uploadProgress}%` }"
                />
              </div>
            </div>
          </div>
        </div>
        <!-- 顶部操作栏 -->
        <div v-if="!loading" class="toolbar">
          <div class="toolbar-left">
            <!-- 上传按钮：管理员可直接上传，普通用户点击显示气泡提示 -->
            <div class="header-actions">
              <button
                class="action-button upload"
                @click="handleUploadClick"
                :disabled="!isAdmin || uploading"
                @mouseenter="showAdminTip = !isAdmin"
                @mouseleave="showAdminTip = false"
                v-tooltip="!isAdmin ? '仅管理员可上传，请联系管理员' : ''"
              >
                <UploadIcon :size="16" />
                <span>上传文件</span>
              </button>
            </div>
            <input
              ref="fileInput"
              type="file"
              multiple
              accept=".pdf,.txt,.md,.markdown"
              @change="handleFileSelect"
              style="display: none"
            />
            <!-- 更新文件选择：按记录 id 定位替换，单文件 -->
            <input
              ref="updateFileInput"
              type="file"
              accept=".pdf,.txt,.md,.markdown"
              @change="handleUpdateFileSelect"
              style="display: none"
            />
            <!-- 搜索框 -->
            <div class="search-box">
              <SearchIcon :size="18" />
              <input v-model="searchKeyword" type="text" placeholder="搜索" @input="handleSearch" />
              <button v-if="searchKeyword" @click="clearSearch" class="clear-search">×</button>
            </div>
          </div>
          <div class="toolbar-right">
            <button
              v-if="isAdmin && selectedIds.length > 0"
              @click="handleBatchDelete"
              class="batch-btn danger"
              :disabled="deleting"
            >
              <TrashIcon :size="16" />
              <span>批量删除</span>
            </button>
            <button
              v-if="selectedIds.length > 0"
              @click="handleBatchDownload"
              class="batch-btn"
              :disabled="downloading"
            >
              <DownloadIcon :size="16" />
              <span>批量下载</span>
            </button>
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <span>加载中...</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="displayFileList.length === 0 && !searchKeyword" class="empty-state">
          <h3>暂无记录</h3>
        </div>

        <!-- 搜索无结果状态 -->
        <div v-else-if="displayFileList.length === 0 && searchKeyword" class="empty-state">
          <div class="empty-icon">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
          </div>
          <h3>未找到相关文件</h3>
          <p>尝试使用其他关键词搜索</p>
        </div>

        <!-- 文件列表 -->
        <div v-else-if="displayFileList.length > 0" class="file-list">
          <div
            v-for="file in displayFileList"
            :key="file.task_id || file.id"
            :ref="(element) => setFileCardRef(element, file)"
            :class="[
              'file-card',
              {
                selected: selectedIds.includes(file.id),
                highlighted: String(file.task_id) === highlightedTaskId,
                'has-task': file.task_id,
              },
            ]"
            @click="file.id != null && !isFileProcessing(file) && handleRowClick(file.id)"
          >
            <div class="file-header">
              <div class="file-info">
                <h3 class="file-name" v-tooltip="file.file_name">{{ file.file_name }}</h3>
                <p class="file-time">{{ formatDate(file.create_time) }}</p>
                <div v-if="file.task_id" class="task-state">
                  <span :class="['task-badge', taskStatusClass(file)]">
                    <span v-if="!knowledgeUploadStore.isTerminal(file.status)" class="task-spinner" />
                    {{ taskStatusText(file) }}
                  </span>
                  <span v-if="shouldShowTaskStage(file)" class="task-stage">
                    {{ taskStageText(file.stage) }}
                  </span>
                  <span v-if="file.error_message" class="task-error">{{ file.error_message }}</span>
                </div>
              </div>
              <div v-if="isAdmin" class="file-actions" @click.stop>
                <button
                  v-if="file.task_id && knowledgeUploadStore.isFailed(file.status)"
                  @click="handleRetryTask(file.task_id)"
                  class="retry-btn"
                  :disabled="retryingTaskId === String(file.task_id)"
                >
                  {{ retryingTaskId === String(file.task_id) ? '重试中...' : '重试' }}
                </button>
                <button
                  v-if="file.id != null"
                  @click="handleUpdateClick(file.id)"
                  class="icon-btn"
                  :disabled="uploading || isFileProcessing(file)"
                  v-tooltip="'更新文件'"
                >
                  <UploadIcon :size="16" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 旧表格保留作为备用 -->
        <div v-if="false" class="table-container">
          <table class="file-table">
            <thead>
              <tr>
                <th class="checkbox-col">
                  <input type="checkbox" :checked="isAllSelected" @change="handleSelectAll" />
                </th>
                <th class="name-col">文件名</th>
                <th class="time-col">上传时间</th>
                <th class="action-col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading" class="loading-row">
                <td colspan="4" class="loading-cell">
                  <div class="loading-spinner">加载中...</div>
                </td>
              </tr>
              <!-- 空状态 -->
              <div v-else-if="fileList.length === 0 && !searchKeyword" class="empty-state">
                <div class="empty-icon">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="64"
                    height="64"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path
                      d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
                    ></path>
                  </svg>
                </div>
                <h3>暂无记录，点击新建下方按钮创建一个</h3>
                <button @click="handleUploadClick" class="primary-button" :disabled="uploading">
                  <UploadIcon :size="16" />
                  <span>上传文件</span>
                </button>
              </div>

              <!-- 搜索无结果状态 -->
              <div v-else-if="fileList.length === 0 && searchKeyword" class="empty-state">
                <div class="empty-icon">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="64"
                    height="64"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <circle cx="11" cy="11" r="8"></circle>
                    <path d="m21 21-4.35-4.35"></path>
                  </svg>
                </div>
                <h3>未找到相关文件</h3>
                <p>尝试使用其他关键词搜索</p>
              </div>
              <tr
                v-else
                v-for="file in fileList"
                :key="file.id"
                :class="{ selected: selectedIds.includes(file.id) }"
                @click="handleRowClick(file.id)"
              >
                <td class="checkbox-col" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedIds.includes(file.id)"
                    @change="handleSelectFile(file.id, $event.target.checked)"
                  />
                </td>
                <td class="name-col">
                  <div class="file-name" v-tooltip="file.file_name">
                    {{ file.file_name }}
                  </div>
                </td>
                <td class="time-col">
                  {{ formatDate(file.create_time) }}
                </td>
                <td class="action-col" @click.stop>
                  <button
                    @click="handleDownload(file.id)"
                    class="action-button download"
                    :disabled="downloading"
                    v-tooltip="'下载'"
                  >
                    <DownloadIcon :size="16" />
                  </button>
                  <button
                    v-if="isAdmin"
                    @click="handleDelete(file.id, file.file_name)"
                    class="action-button delete"
                    :disabled="deleting"
                    v-tooltip="'删除'"
                  >
                    <TrashIcon :size="16" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { knowledgeApi } from '../api/knowledge'
import { useChatStore } from '../stores/chat'
import { useKnowledgeUploadStore } from '../stores/knowledgeUpload'
import { useUserStore } from '../stores/user'
import Sidebar from '../components/Sidebar.vue'
import { sleep } from '../utils/async'
import UploadIcon from '../components/icons/UploadIcon.vue'
import DownloadIcon from '../components/icons/DownloadIcon.vue'
import TrashIcon from '../components/icons/TrashIcon.vue'
import SearchIcon from '../components/icons/SearchIcon.vue'
import { useConfirm } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'

// 初始化 chatStore 和 userStore
const chatStore = useChatStore()
const userStore = useUserStore()
const knowledgeUploadStore = useKnowledgeUploadStore()
const route = useRoute()
const { confirm } = useConfirm()

// 全局 toast：统一成功/失败反馈
const toast = useToast()
const showMessage = (message, type = 'success') => {
  toast.showToast(message, type)
}

// 计算属性：是否为管理员
const isAdmin = computed(() => userStore.isAdmin())

// 气泡提示状态
const showAdminTip = ref(false)
let tipTimer = null

// 状态
const fileList = ref([...knowledgeUploadStore.fileRecords])
const searchKeyword = ref('')
const selectedIds = ref([])
const loading = ref(false)
const uploading = ref(false)
const isDraggingUpload = ref(false)
const deleting = ref(false)
const downloading = ref(false)
const uploadProgress = ref(null)
const retryingTaskId = ref(null)
const highlightedTaskId = ref('')
const fileInput = ref(null)
const updateFileInput = ref(null)
const fileCardRefs = new Map()
// 当前待更新的记录 id，供 handleUpdateFileSelect 使用
const updatingId = ref(null)
let highlightTimer = null
let dragDepth = 0

const displayFileList = computed(() => {
  const records = fileList.value.map((file) => ({ ...file }))
  knowledgeUploadStore.tasks.forEach((task) => {
    const index = records.findIndex(
      (file) =>
        (file.task_id && String(file.task_id) === String(task.task_id)) ||
        (task.kb_file_id != null && String(file.id) === String(task.kb_file_id)),
    )
    if (index >= 0) {
      records.splice(index, 1, { ...records[index], ...task })
    } else if (!searchKeyword.value) {
      records.unshift({
        ...task,
        id: task.kb_file_id ?? task.id,
        file_name: task.file_name || task.name || '待处理文件',
      })
    }
  })
  return records
})

const isAllSelected = computed(() => {
  const selectableFiles = displayFileList.value.filter(
    (file) => file.id != null && !isFileProcessing(file),
  )
  return selectableFiles.length > 0 && selectedIds.value.length === selectableFiles.length
})

// 防抖搜索
let searchTimer = null
const handleSearch = () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    fetchFileList()
  }, 300)
}

const clearSearch = () => {
  searchKeyword.value = ''
  fetchFileList()
}

const fetchFileList = async () => {
  loading.value = fileList.value.length === 0 || Boolean(searchKeyword.value)
  try {
    const params = {}
    if (searchKeyword.value) {
      params.file_name = searchKeyword.value
    }
    const response = await knowledgeApi.getFileList(params)
    if (response.data.code === 0) {
      const data = response.data.data
      // 兼容后端全量返回 records/list，以及历史可能直接返回数组的结构
      fileList.value = Array.isArray(data) ? data : data.records || data.list || []
      if (!searchKeyword.value) {
        knowledgeUploadStore.setFileRecords(fileList.value)
      }
    } else {
      console.error('获取文件列表失败:', response.data.message)
      showMessage('获取文件列表失败: ' + (response.data.message || '未知错误'), 'error')
    }
  } catch (error) {
    console.error('获取文件列表错误:', error)
    showMessage('获取文件列表失败: ' + (error.message || '网络错误'), 'error')
  } finally {
    loading.value = false
  }
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

const taskStatusText = (file) => {
  if (knowledgeUploadStore.isSuccess(file.status)) return '处理完成'
  if (knowledgeUploadStore.isFailed(file.status)) return '处理失败'
  const statusLabels = {
    pending: '等待处理',
    queued: '排队中',
    processing: '处理中',
    running: '处理中',
  }
  return statusLabels[String(file.status || '').toLowerCase()] || '处理中'
}

const taskStageText = (stage) => {
  const stageLabels = {
    queued: '等待后台处理',
    parsing: '正在解析文档',
    splitting: '正在切分文档',
    indexing: '正在向量化',
    finalizing: '正在完成入库',
    completed: '已可以使用',
    failed: '处理未完成',
  }
  return stageLabels[String(stage || '').toLowerCase()] || ''
}

const shouldShowTaskStage = (file) =>
  ['parsing', 'splitting', 'indexing', 'finalizing'].includes(
    String(file.stage || '').toLowerCase(),
  )

const isFileProcessing = (file) =>
  ['pending', 'queued', 'processing', 'running'].includes(
    String(file.file_status || file.status || '').toLowerCase(),
  )

const taskStatusClass = (file) => {
  if (knowledgeUploadStore.isSuccess(file.status)) return 'success'
  if (knowledgeUploadStore.isFailed(file.status)) return 'failed'
  return 'processing'
}

const setFileCardRef = (element, file) => {
  if (!file.task_id) return
  const key = String(file.task_id)
  if (element) {
    fileCardRefs.set(key, element)
  } else {
    fileCardRefs.delete(key)
  }
}

const locateUploadTask = async () => {
  const taskId = route.query.upload_task_id
  if (!taskId) return
  await nextTick()
  const key = String(taskId)
  const element = fileCardRefs.get(key)
  if (!element) return
  element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  highlightedTaskId.value = key
  clearTimeout(highlightTimer)
  highlightTimer = setTimeout(() => {
    highlightedTaskId.value = ''
  }, 3000)
}

// 上传按钮点击处理：管理员直接上传，普通用户显示气泡提示
const handleUploadClick = () => {
  if (isAdmin.value) {
    // 管理员：打开文件选择
    fileInput.value?.click()
  } else {
    // 普通用户：显示气泡提示
    showAdminTip.value = true
    // 3秒后自动隐藏
    if (tipTimer) clearTimeout(tipTimer)
    tipTimer = setTimeout(() => {
      showAdminTip.value = false
    }, 3000)
  }
}

const uploadFiles = async (files) => {
  if (files.length === 0) return

  uploading.value = true
  uploadProgress.value = 0
  try {
    const totalBytes = Math.max(
      files.reduce((sum, file) => sum + file.size, 0),
      1,
    )
    let uploadedBytes = 0
    const failedFiles = []
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      try {
        const response = await knowledgeApi.uploadFiles(formData, (progressEvent) => {
          const currentLoaded = Math.min(progressEvent.loaded, file.size)
          uploadProgress.value = Math.min(
            100,
            Math.round(((uploadedBytes + currentLoaded) * 100) / totalBytes),
          )
        })
        if (response.data.code === 0) {
          knowledgeUploadStore.registerUploadResult(response.data.data)
        } else {
          failedFiles.push({
            file_name: file.name,
            message: response.data.message || '未知错误',
          })
        }
      } catch (error) {
        const message =
          error?.response?.status === 413
            ? '文件超过上传大小限制'
            : error?.response?.data?.message || error.message || '网络错误'
        failedFiles.push({ file_name: file.name, message })
        console.error(`上传文件 ${file.name} 错误:`, error)
      } finally {
        uploadedBytes += file.size
        uploadProgress.value = Math.min(100, Math.round((uploadedBytes * 100) / totalBytes))
      }
    }
    await fetchFileList()
    if (failedFiles.length > 0) {
      const firstFailure = failedFiles[0]
      const suffix = failedFiles.length > 1 ? `，另有 ${failedFiles.length - 1} 个文件失败` : ''
      showMessage(`${firstFailure.file_name} 上传失败：${firstFailure.message}${suffix}`, 'error')
    }
  } catch (error) {
    console.error('上传文件错误:', error)
    // axios 超时一般会是 ECONNABORTED
    if (error?.code === 'ECONNABORTED') {
      showMessage('文件上传超时，请稍后重试', 'error')
    } else if (error?.response?.status === 413) {
      showMessage('文件过大，上传失败（413）', 'error')
    } else if (error?.response?.status) {
      showMessage(
        `文件上传失败（${error.response.status}）: ` +
          (error.response.data?.message || error.message || '网络错误'),
        'error',
      )
    } else {
      showMessage('文件上传失败: ' + (error.message || '网络错误'), 'error')
    }
  } finally {
    uploading.value = false
    uploadProgress.value = null
  }
}

const handleFileSelect = async (event) => {
  const files = Array.from(event.target.files || [])
  try {
    await uploadFiles(files)
  } finally {
    // 上传结束后统一清空选择，避免重复选择同一文件时 change 不触发。
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

const handleUploadDragEnter = () => {
  dragDepth += 1
  if (isAdmin.value && !uploading.value) {
    isDraggingUpload.value = true
  }
}

const handleUploadDragLeave = () => {
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) {
    isDraggingUpload.value = false
  }
}

const handleUploadDrop = async (event) => {
  dragDepth = 0
  isDraggingUpload.value = false
  if (!isAdmin.value) {
    showMessage('仅管理员可上传，请联系管理员', 'warning')
    return
  }
  if (uploading.value) return
  await uploadFiles(Array.from(event.dataTransfer?.files || []))
}

// 更新文件按钮点击：记录待更新 id 并打开文件选择
const handleUpdateClick = (id) => {
  if (!isAdmin.value) {
    showMessage('仅管理员可操作知识库，请联系管理员', 'warning')
    return
  }
  updatingId.value = id
  updateFileInput.value?.click()
}

// 选择新文件后按 kb_file_id 增量更新该文档
const handleUpdateFileSelect = async (event) => {
  const file = event.target.files?.[0]
  if (!file || updatingId.value == null) return

  uploading.value = true
  try {
    const response = await knowledgeApi.updateFile(updatingId.value, file)
    if (response.data.code === 0) {
      showMessage(response.data.message || '文件更新成功')
      await fetchFileList()
    } else {
      showMessage('文件更新失败: ' + (response.data.message || '未知错误'), 'error')
    }
  } catch (error) {
    console.error('更新文件错误:', error)
    showMessage('文件更新失败: ' + (error?.response?.data?.message || error.message || '网络错误'), 'error')
  } finally {
    uploading.value = false
    updatingId.value = null
    if (updateFileInput.value) {
      updateFileInput.value.value = ''
    }
  }
}

const handleSelectFile = (id, checked) => {
  if (checked) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value.push(id)
    }
  } else {
    selectedIds.value = selectedIds.value.filter((i) => i !== id)
  }
}

const handleSelectAll = (event) => {
  if (event.target.checked) {
    selectedIds.value = displayFileList.value
      .filter((file) => file.id != null && !isFileProcessing(file))
      .map((file) => file.id)
  } else {
    selectedIds.value = []
  }
}

const handleRowClick = (id) => {
  const index = selectedIds.value.indexOf(id)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
}

const handleRetryTask = async (taskId) => {
  retryingTaskId.value = String(taskId)
  try {
    await knowledgeUploadStore.retryTask(taskId)
    showMessage('已重新提交处理任务', 'info')
  } catch (error) {
    console.error('重试知识库上传任务失败:', error)
    showMessage(
      '重试失败: ' + (error?.response?.data?.message || error.message || '网络错误'),
      'error',
    )
  } finally {
    retryingTaskId.value = null
  }
}

const handleDelete = async (id, fileName) => {
  if (!isAdmin.value) {
    showMessage('仅管理员可操作知识库，请联系管理员', 'warning')
    return
  }
  const confirmed = await confirm({
    title: '删除文件',
    message: `确定要删除文件“${fileName}”吗？`,
    description: '删除后，文件及其知识库索引将无法恢复。',
    confirm_text: '确认删除',
    tone: 'danger',
  })
  if (!confirmed) return

  await deleteFiles([id])
}

const handleBatchDelete = async () => {
  if (!isAdmin.value) {
    showMessage('仅管理员可操作知识库，请联系管理员', 'warning')
    return
  }
  if (selectedIds.value.length === 0) return
  const confirmed = await confirm({
    title: '批量删除文件',
    message: `确定要删除选中的 ${selectedIds.value.length} 个文件吗？`,
    description: '删除后，所选文件及其知识库索引将无法恢复。',
    confirm_text: '确认删除',
    tone: 'danger',
  })
  if (!confirmed) return

  await deleteFiles([...selectedIds.value])
}

const deleteFiles = async (ids) => {
  deleting.value = true
  try {
    const response = await knowledgeApi.deleteFiles(ids)
    if (response.data.code === 0) {
      showMessage(response.data.message || '删除成功')
      selectedIds.value = []
      fetchFileList()
    } else {
      showMessage('删除失败: ' + (response.data.message || '未知错误'), 'error')
    }
  } catch (error) {
    console.error('删除文件错误:', error)
    showMessage('删除失败: ' + (error.message || '网络错误'), 'error')
  } finally {
    deleting.value = false
  }
}

const handleDownload = async (id) => {
  await downloadFiles([id])
}

const handleBatchDownload = async () => {
  if (selectedIds.value.length === 0) return
  await downloadFiles([...selectedIds.value])
}

const downloadFiles = async (ids) => {
  downloading.value = true
  try {
    // 获取要下载的文件信息
    const filesToDownload = fileList.value.filter((file) => ids.includes(file.id))

    for (const file of filesToDownload) {
      try {
        // 优先使用新的文件流下载API
        const response = await knowledgeApi.downloadFile(file.id)

        // 处理blob下载
        if (response.data instanceof Blob) {
          const blob = response.data
          const url = window.URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url
          link.download = file.file_name || `file_${file.id}`
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          window.URL.revokeObjectURL(url)

          // 添加延迟避免浏览器阻止多个下载
          await sleep(200)
        }
      } catch (apiError) {
        console.error(`API下载文件 ${file.id} 失败:`, apiError)

        // API失败时，尝试使用OSS URL作为备选方案
        if (file.url) {
          try {
            const link = document.createElement('a')
            link.href = file.url
            link.download = file.file_name || `file_${file.id}`
            link.target = '_blank'
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)

            await sleep(200)
          } catch (urlError) {
            console.error(`URL下载文件 ${file.id} 也失败:`, urlError)
            showMessage(`下载文件 "${file.file_name}" 失败`, 'error')
          }
        } else {
          showMessage(`下载文件 "${file.file_name}" 失败: 无可用下载方式`, 'error')
        }
      }
    }
  } catch (error) {
    console.error('下载文件错误:', error)
    showMessage('下载失败: ' + (error.message || '网络错误'), 'error')
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  chatStore.initialize()
  fetchFileList()
})

watch(
  () => [
    route.query.upload_task_id,
    displayFileList.value.map((file) => file.task_id || '').join(','),
  ],
  locateUploadTask,
  { immediate: true, flush: 'post' },
)

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  clearTimeout(tipTimer)
  clearTimeout(highlightTimer)
})
</script>

<style lang="scss" scoped>
.knowledge-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background-color: var(--bg-primary);
  transition: background-color 0.3s ease;
}

.knowledge-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  min-width: 0;
}

.knowledge-content {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow: hidden;
  transition: padding-left 0.2s ease;

  &.dragging-upload {
    box-shadow: inset 0 0 0 2px rgba(144, 19, 139, 0.24);
  }

  &.sidebar-collapsed {
    padding-left: 60px;
  }
}

.upload-drop-hint {
  position: absolute;
  inset: 24px;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px dashed rgba(144, 19, 139, 0.4);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--accent-color);
  font-size: 14px;
  font-weight: 500;
  pointer-events: none;
}

// 上传遮罩层：上传期间阻止用户重复操作，并提供明确的等待反馈
.uploading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;

  .uploading-modal {
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 20px 22px;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
    max-width: 80vw;
    min-width: min(360px, calc(100vw - 48px));
  }

  .uploading-content {
    width: 100%;
  }

  .uploading-text {
    color: var(--text-primary);
    font-size: 14px;
    margin-bottom: 10px;
  }

  .upload-progress-track {
    height: 6px;
    overflow: hidden;
    border-radius: 999px;
    background: rgba(144, 19, 139, 0.12);
  }

  .upload-progress-bar {
    height: 100%;
    border-radius: inherit;
    background: #90138b;
    transition: width 0.2s ease;

    &.indeterminate {
      width: 45%;
      animation: uploadProgressIndeterminate 1.2s ease-in-out infinite;
    }
  }
}

@keyframes uploadProgressIndeterminate {
  0% {
    transform: translateX(-110%);
  }
  100% {
    transform: translateX(240%);
  }
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
  gap: 0;
  padding: 80px 0;
  color: var(--text-secondary);

  h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
  }
}

// 顶部操作栏
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    transition: padding-left 0.2s ease;
  }

  // 上传按钮包装器（用于定位气泡提示）
  .header-actions {
    position: relative;
    display: inline-block;
  }

  // 普通用户上传按钮禁用样式
  .primary-button.disabled-style {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .action-button {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border: none;
    border-radius: 6px;
    background: rgba(144, 19, 139, 0.1);
    color: #90138b;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;

    &:hover:not(:disabled) {
      background: rgba(144, 19, 139, 0.15);
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateX(-50%) translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
  }

  .toolbar-right {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  .primary-button {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 20px;
    background-color: #90138b;
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s ease;

    &:hover:not(:disabled) {
      background-color: #9b2a96;
    }

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    width: 280px;
    transition: all 0.2s ease;

    &:focus-within {
      border-color: rgba(144, 19, 139, 0.3);
    }

    svg {
      color: var(--text-secondary);
      flex-shrink: 0;
    }

    input {
      flex: 1;
      border: none;
      background: transparent;
      color: var(--text-primary);
      font-size: 14px;
      outline: none;

      &::placeholder {
        color: var(--text-secondary);
      }
    }

    .clear-search {
      background: transparent;
      border: none;
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 20px;
      line-height: 1;
      padding: 0;
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;

      &:hover {
        color: var(--text-primary);
      }
    }
  }

  .batch-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border: none;
    border-radius: 6px;
    background: rgba(144, 19, 139, 0.1);
    color: #90138b;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;

    &:hover:not(:disabled) {
      background: rgba(144, 19, 139, 0.15);
    }

    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }

    &.danger {
      background: rgba(220, 53, 69, 0.1);
      color: #dc3545;

      &:hover:not(:disabled) {
        background: rgba(220, 53, 69, 0.15);
      }
    }
  }
}

// ==================== 文件列表 ====================
.file-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  overflow: auto;
}

.file-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 14px 18px;
  background-color: var(--bg-secondary);
  transition: all 0.2s;
  cursor: pointer;

  &:hover {
    background-color: rgba(144, 19, 139, 0.03);
  }

  &.selected,
  &.highlighted {
    background-color: rgba(144, 19, 139, 0.08);
    border-color: rgba(144, 19, 139, 0.2);
  }
}

.file-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;

  @media (max-width: 768px) {
    flex-direction: column;
    align-items: flex-start;
  }
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 6px 0;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-time {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.task-state {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 9px;
  font-size: 12px;
}

.task-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  font-weight: 500;

  &.processing {
    color: #90138b;
    background: rgba(144, 19, 139, 0.1);
  }

  &.success {
    color: #047857;
    background: rgba(16, 185, 129, 0.11);
  }

  &.failed {
    color: #dc3545;
    background: rgba(220, 53, 69, 0.1);
  }
}

.task-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(144, 19, 139, 0.25);
  border-top-color: #90138b;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.task-stage {
  color: var(--text-secondary);
}

.task-error {
  flex-basis: 100%;
  color: #dc3545;
  word-break: break-word;
}

.file-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.retry-btn {
  padding: 5px 10px;
  border: 1px solid rgba(220, 53, 69, 0.2);
  border-radius: 6px;
  background: rgba(220, 53, 69, 0.08);
  color: #dc3545;
  font-size: 12px;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: rgba(220, 53, 69, 0.14);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background-color: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover:not(:disabled) {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  &.danger {
    &:hover:not(:disabled) {
      background-color: rgba(220, 53, 69, 0.1);
      color: #dc3545;
    }
  }
}

// 表格容器（备用）
.table-container {
  flex: 1;
  overflow: auto;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.file-table {
  width: 100%;
  border-collapse: collapse;

  thead {
    background-color: var(--bg-tertiary);
    position: sticky;
    top: 0;
    z-index: 10;

    th {
      padding: 12px 16px;
      text-align: left;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 1px solid var(--border-color);
    }
  }

  tbody {
    tr {
      border-bottom: 1px solid var(--border-color);
      transition: background-color 0.2s ease;

      &:hover {
        background-color: var(--bg-hover);
      }

      &.selected {
        background-color: var(--bg-active);
      }

      &.loading-row,
      &.empty-row {
        &:hover {
          background-color: transparent;
        }
      }
    }

    td {
      padding: 12px 16px;
      font-size: 14px;
      color: var(--text-primary);
    }
  }

  .checkbox-col {
    width: 50px;
    text-align: center;

    input[type='checkbox'] {
      cursor: pointer;
    }
  }

  .name-col {
    min-width: 200px;

    .file-name {
      cursor: pointer;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 400px;
    }
  }

  .time-col {
    width: 180px;
    color: var(--text-secondary);
    font-size: 13px;
  }

  .action-col {
    width: 150px;
  }

  .loading-cell,
  .empty-cell {
    text-align: center;
    padding: 48px 16px;

    .loading-spinner {
      color: var(--text-secondary);
    }

    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      color: var(--text-secondary);

      svg {
        opacity: 0.5;
      }

      p {
        margin: 0;
        font-size: 14px;
      }
    }
  }
}

// ==================== 动画 ====================
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

// 响应式设计
@media (max-width: 768px) {
  .knowledge-content {
    padding: 12px;

    &.sidebar-collapsed {
      padding-left: 12px;
    }
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;

    .toolbar-left,
    .toolbar-center,
    .toolbar-right {
      width: 100%;
    }

    .toolbar-right {
      flex-direction: column;
    }
  }

  .file-table {
    font-size: 12px;

    th,
    td {
      padding: 8px;
    }

    .name-col .file-name {
      max-width: 150px;
    }

    .time-col {
      width: 120px;
      font-size: 11px;
    }

    .action-col {
      width: 100px;
    }
  }
}
</style>
