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
          <span>松开以上传知识库文件或文件夹</span>
        </div>
        <header v-if="!loading" class="page-header">
          <div>
            <h1>知识库</h1>
            <p>
              共 {{ totalFileCount }} 个文件
              <span v-if="processingFileCount > 0">· {{ processingFileCount }} 个处理中</span>
            </p>
          </div>
          <button
            class="action-button upload"
            @click="handleUploadClick"
            :disabled="!isAdmin || uploading"
            @mouseenter="showAdminTip = !isAdmin"
            @mouseleave="showAdminTip = false"
            v-tooltip="!isAdmin ? '仅管理员可上传，请联系管理员' : ''"
          >
            <UploadIcon :size="16" />
            <span>
              {{
                uploadBatchActive
                  ? `上传中 ${uploadCurrentNumber}/${uploadTotalCount}`
                  : uploading
                    ? '更新中'
                    : '上传文件'
              }}
            </span>
          </button>
        </header>
        <!-- 顶部操作栏 -->
        <div v-if="!loading" class="toolbar">
          <div class="toolbar-left">
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
              <input
                v-model="searchKeyword"
                type="text"
                placeholder="搜索文件"
                aria-label="搜索知识库文件"
                @input="handleSearch"
              />
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
          <div class="empty-file-mark">MD</div>
          <h3>知识库还没有文件</h3>
          <p>上传 PDF、TXT 或 Markdown 文件后即可检索</p>
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
          <div class="file-list-header">
            <div class="select-cell">
              <input
                type="checkbox"
                :checked="isAllSelected"
                aria-label="选择当前页全部文件"
                @change="handleSelectAll"
              />
            </div>
            <button
              type="button"
              :class="['sortable-header', { active: sortBy === 'file_name' }]"
              @click="handleSort('file_name')"
            >
              文件
              <span>{{ sortIndicator('file_name') }}</span>
            </button>
            <span>状态</span>
            <button
              type="button"
              :class="['sortable-header', { active: sortBy === 'total_chunks' }]"
              @click="handleSort('total_chunks')"
            >
              切片
              <span>{{ sortIndicator('total_chunks') }}</span>
            </button>
            <button
              type="button"
              :class="['sortable-header', { active: sortBy === 'create_time' }]"
              @click="handleSort('create_time')"
            >
              上传时间
              <span>{{ sortIndicator('create_time') }}</span>
            </button>
            <span class="actions-label">操作</span>
          </div>
          <div class="file-list-body">
            <div
              v-for="file in displayFileList"
              :key="file.local_id || file.task_id || file.id"
              :ref="(element) => setFileCardRef(element, file)"
              :class="[
                'file-card',
                {
                  selected: selectedIds.includes(file.id),
                  previewing: activePreviewFile?.id === file.id,
                  highlighted: String(file.task_id) === highlightedTaskId,
                  'has-task': file.task_id,
                },
              ]"
              @click="file.id != null && !isFileProcessing(file) && handleRowClick(file.id)"
            >
              <div class="select-cell" @click.stop>
                <input
                  v-if="file.id != null"
                  type="checkbox"
                  :checked="selectedIds.includes(file.id)"
                  :disabled="isFileProcessing(file)"
                  :aria-label="`选择 ${file.file_name}`"
                  @change="handleSelectFile(file.id, $event.target.checked)"
                />
              </div>
              <div
                class="file-info"
                :class="{ previewable: file.id != null && !isFileProcessing(file) }"
                @click.stop="togglePreview(file)"
              >
                <span :class="['file-type-mark', fileTypeClass(file.file_name)]">
                  {{ fileTypeLabel(file.file_name) }}
                </span>
                <div class="file-title">
                  <h3 class="file-name" v-tooltip="file.file_name">{{ file.file_name }}</h3>
                  <span v-if="file.error_message" class="task-error">
                    {{ file.error_message }}
                  </span>
                </div>
              </div>
              <div class="task-state">
                <span :class="['task-badge', taskStatusClass(file)]">
                  <span v-if="taskStatusClass(file) === 'processing'" class="task-spinner" />
                  {{ taskStatusText(file) }}
                </span>
                <span v-if="file.upload_status === 'uploading'" class="task-stage">
                  {{ file.upload_progress }}%
                </span>
                <span v-else-if="shouldShowTaskStage(file)" class="task-stage">
                  {{ taskStageText(file.stage) }}
                </span>
              </div>
              <span class="chunk-count">{{ formatChunkCount(file.total_chunks) }}</span>
              <time class="file-time" :datetime="file.create_time">
                {{ formatDate(file.create_time) }}
              </time>
              <div class="file-actions" @click.stop>
                <button
                  v-if="file.upload_status === 'failed'"
                  @click="handleRetryLocalUpload(file)"
                  class="retry-btn"
                  :disabled="uploading"
                >
                  重试上传
                </button>
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
                  @click="togglePreview(file)"
                  class="icon-btn"
                  :disabled="isFileProcessing(file)"
                  :aria-label="activePreviewFile?.id === file.id ? '关闭预览' : '预览'"
                  v-tooltip="
                    isFileProcessing(file)
                      ? '处理完成后可预览'
                      : activePreviewFile?.id === file.id
                        ? '关闭预览'
                        : '预览'
                  "
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"></path>
                    <circle cx="12" cy="12" r="2.5"></circle>
                  </svg>
                </button>
                <button
                  v-if="file.id != null"
                  @click="handleDownload(file.id)"
                  class="icon-btn"
                  :disabled="downloading || isFileProcessing(file)"
                  v-tooltip="isFileProcessing(file) ? '处理完成后可下载' : '下载'"
                >
                  <DownloadIcon :size="16" />
                </button>
                <button
                  v-if="isAdmin && file.id != null"
                  @click="handleUpdateClick(file.id)"
                  class="icon-btn"
                  :disabled="uploading || isFileProcessing(file)"
                  v-tooltip="'更新文件'"
                >
                  <UploadIcon :size="16" />
                </button>
                <button
                  v-if="isAdmin && file.local_id && file.upload_status === 'failed'"
                  @click="removePendingUpload(file.local_id)"
                  class="icon-btn danger"
                  :disabled="uploading"
                  v-tooltip="'移除失败记录'"
                >
                  <TrashIcon :size="16" />
                </button>
                <button
                  v-else-if="isAdmin && file.id != null"
                  @click="handleDelete(file.id, file.file_name)"
                  class="icon-btn danger"
                  :disabled="deleting || isFileProcessing(file)"
                  v-tooltip="isFileProcessing(file) ? '处理中暂不能删除' : '删除'"
                >
                  <TrashIcon :size="16" />
                </button>
              </div>
            </div>
          </div>
        </div>
        <footer v-if="!loading && totalFiles > 0" class="pagination">
          <div class="page-size">
            <span>每页</span>
            <div class="page-size-selector" v-click-outside="closePageSizeDropdown">
              <button
                type="button"
                class="page-size-trigger"
                aria-label="每页文件数量"
                aria-haspopup="listbox"
                :aria-expanded="showPageSizeDropdown"
                @click="togglePageSizeDropdown"
                @keydown.esc="closePageSizeDropdown"
              >
                <span>{{ pageSize }}</span>
                <ChevronDownIcon
                  :size="12"
                  class="page-size-chevron"
                  :class="{ 'is-open': showPageSizeDropdown }"
                />
              </button>
              <transition name="page-size-dropdown">
                <div
                  v-show="showPageSizeDropdown"
                  class="page-size-menu"
                  role="listbox"
                  aria-label="选择每页文件数量"
                  @keydown.esc="closePageSizeDropdown"
                >
                  <button
                    v-for="option in PAGE_SIZE_OPTIONS"
                    :key="option"
                    type="button"
                    class="page-size-option"
                    :class="{ active: pageSize === option }"
                    role="option"
                    :aria-selected="pageSize === option"
                    @click="selectPageSize(option)"
                  >
                    <svg
                      class="page-size-check"
                      :class="{ visible: pageSize === option }"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2.5"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      aria-hidden="true"
                    >
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <span>{{ option }}</span>
                  </button>
                </div>
              </transition>
            </div>
            <span>条</span>
          </div>
          <div class="page-controls">
            <span>共 {{ totalFiles }} 条</span>
            <button
              type="button"
              aria-label="上一页"
              :disabled="currentPage <= 1"
              @click="changePage(currentPage - 1)"
            >
              <span aria-hidden="true">‹</span>
            </button>
            <span>{{ currentPage }} / {{ totalPages }}</span>
            <button
              type="button"
              aria-label="下一页"
              :disabled="currentPage >= totalPages"
              @click="changePage(currentPage + 1)"
            >
              <span aria-hidden="true">›</span>
            </button>
          </div>
        </footer>

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
      <KnowledgePreviewPanel
        v-if="activePreviewFile"
        :file="activePreviewFile"
        @close="closePreview"
        @download="handleDownload"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { knowledgeApi } from '../api/knowledge'
import { useChatStore } from '../stores/chat'
import { useKnowledgeUploadStore } from '../stores/knowledgeUpload'
import { useUserStore } from '../stores/user'
import Sidebar from '../components/Sidebar.vue'
import KnowledgePreviewPanel from '../components/KnowledgePreviewPanel.vue'
import { sleep } from '../utils/async'
import { assertDownloadableBlob, downloadBlob } from '../utils/blobResponse'
import UploadIcon from '../components/icons/UploadIcon.vue'
import DownloadIcon from '../components/icons/DownloadIcon.vue'
import TrashIcon from '../components/icons/TrashIcon.vue'
import SearchIcon from '../components/icons/SearchIcon.vue'
import ChevronDownIcon from '../components/icons/ChevronDownIcon.vue'
import { useConfirm } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'
import { readJsonStorage } from '../utils/storage'
import {
  collectDroppedFiles,
  partitionKnowledgeFiles,
} from '../utils/knowledgeUploadFiles'

const PAGE_SIZE_OPTIONS = [20, 50, 100]
const PAGE_SIZE_STORAGE_KEY = 'knowledge_page_size'
const SORT_FIELDS = ['file_name', 'total_chunks', 'create_time']
const SORT_ORDERS = ['asc', 'desc']
const SORT_STORAGE_KEY = 'knowledge_sort'
const storedPageSize = Number(readJsonStorage(PAGE_SIZE_STORAGE_KEY, 20))
const storedSort = readJsonStorage(SORT_STORAGE_KEY)
const hasValidStoredSort =
  SORT_FIELDS.includes(storedSort?.sort_by) && SORT_ORDERS.includes(storedSort?.sort_order)

// 初始化 chatStore 和 userStore
const chatStore = useChatStore()
const userStore = useUserStore()
const knowledgeUploadStore = useKnowledgeUploadStore()
const route = useRoute()
const router = useRouter()
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
const totalFiles = ref(fileList.value.length)
const searchKeyword = ref(String(route.query.file_name || ''))
const sortBy = ref(hasValidStoredSort ? storedSort.sort_by : null)
const sortOrder = ref(hasValidStoredSort ? storedSort.sort_order : null)
const currentPage = ref(1)
const pageSize = ref(PAGE_SIZE_OPTIONS.includes(storedPageSize) ? storedPageSize : 20)
const showPageSizeDropdown = ref(false)
const selectedIds = ref([])
const loading = ref(false)
const uploading = ref(false)
const isDraggingUpload = ref(false)
const deleting = ref(false)
const downloading = ref(false)
const uploadCompletedCount = ref(0)
const uploadTotalCount = ref(0)
const pendingUploads = ref([])
const retryingTaskId = ref(null)
const highlightedTaskId = ref('')
const activePreviewFile = ref(null)
const fileInput = ref(null)
const updateFileInput = ref(null)
const fileCardRefs = new Map()
// 当前待更新的记录 id，供 handleUpdateFileSelect 使用
const updatingId = ref(null)
let highlightTimer = null
let locatedUploadTaskId = ''
let dragDepth = 0

const uploadBatchActive = computed(() => uploading.value && uploadTotalCount.value > 0)
const uploadCurrentNumber = computed(() =>
  Math.min(uploadCompletedCount.value + 1, uploadTotalCount.value),
)
const totalFileCount = computed(() =>
  Math.max(totalFiles.value, fileList.value.length),
)
const totalPages = computed(() => Math.max(1, Math.ceil(totalFiles.value / pageSize.value)))
const processingFileCount = computed(
  () => displayFileList.value.filter((file) => isFileProcessing(file)).length,
)

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
    } else if (!searchKeyword.value && currentPage.value === 1) {
      records.unshift({
        ...task,
        id: task.kb_file_id ?? task.id,
        file_name: task.file_name || task.name || '待处理文件',
      })
    }
  })
  return currentPage.value === 1 ? [...pendingUploads.value, ...records] : records
})

const isAllSelected = computed(() => {
  const selectableFiles = displayFileList.value.filter(
    (file) => file.id != null && !isFileProcessing(file),
  )
  return (
    selectableFiles.length > 0 &&
    selectableFiles.every((file) => selectedIds.value.includes(file.id))
  )
})

// 防抖搜索
let searchTimer = null
let fileListRequestVersion = 0
const handleSearch = () => {
  resetPageContext()
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    fetchFileList()
  }, 300)
}

const clearSearch = () => {
  searchKeyword.value = ''
  resetPageContext()
  fetchFileList()
}

const resetPageContext = () => {
  fileListRequestVersion += 1
  currentPage.value = 1
  selectedIds.value = []
  closePreview()
}

const sortIndicator = (field) => {
  if (sortBy.value !== field) return '↕'
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

const handleSort = (field) => {
  if (sortBy.value !== field) {
    sortBy.value = field
    sortOrder.value = 'asc'
  } else if (sortOrder.value === 'asc') {
    sortOrder.value = 'desc'
  } else {
    sortBy.value = null
    sortOrder.value = null
  }
  if (sortBy.value && sortOrder.value) {
    localStorage.setItem(
      SORT_STORAGE_KEY,
      JSON.stringify({ sort_by: sortBy.value, sort_order: sortOrder.value }),
    )
  } else {
    localStorage.removeItem(SORT_STORAGE_KEY)
  }
  resetPageContext()
  fetchFileList()
}

const closePageSizeDropdown = () => {
  showPageSizeDropdown.value = false
}

const togglePageSizeDropdown = () => {
  showPageSizeDropdown.value = !showPageSizeDropdown.value
}

const selectPageSize = (size) => {
  closePageSizeDropdown()
  if (pageSize.value === size) return

  pageSize.value = size
  localStorage.setItem(PAGE_SIZE_STORAGE_KEY, JSON.stringify(size))
  resetPageContext()
  fetchFileList()
}

const changePage = (page) => {
  const nextPage = Math.min(Math.max(page, 1), totalPages.value)
  if (nextPage === currentPage.value) return
  currentPage.value = nextPage
  selectedIds.value = []
  closePreview()
  fetchFileList()
}

const fetchFileList = async () => {
  const requestVersion = ++fileListRequestVersion
  loading.value = fileList.value.length === 0 || Boolean(searchKeyword.value)
  try {
    const params = {}
    if (searchKeyword.value) {
      params.file_name = searchKeyword.value
    }
    params.sort_by = sortBy.value || 'create_time'
    params.sort_order = sortOrder.value || 'desc'
    params.page = currentPage.value
    params.page_size = pageSize.value
    const response = await knowledgeApi.getFileList(params)
    if (requestVersion !== fileListRequestVersion) return
    if (response.data.code === 0) {
      const data = response.data.data
      // 兼容后端全量返回 records/list，以及历史可能直接返回数组的结构
      fileList.value = Array.isArray(data) ? data : data.records || data.list || []
      totalFiles.value = Array.isArray(data) ? data.length : data.total ?? fileList.value.length
      const maxPage = Math.max(1, Math.ceil(totalFiles.value / pageSize.value))
      if (currentPage.value > maxPage) {
        currentPage.value = maxPage
        await fetchFileList()
        return
      }
      if (!searchKeyword.value) {
        knowledgeUploadStore.setFileRecords(fileList.value)
      }
    } else {
      console.error('获取文件列表失败:', response.data.message)
      showMessage('获取文件列表失败: ' + (response.data.message || '未知错误'), 'error')
    }
  } catch (error) {
    if (requestVersion !== fileListRequestVersion) return
    console.error('获取文件列表错误:', error)
    showMessage('获取文件列表失败: ' + (error.message || '网络错误'), 'error')
  } finally {
    if (requestVersion === fileListRequestVersion) {
      loading.value = false
    }
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
  if (file.upload_status === 'waiting') return '等待上传'
  if (file.upload_status === 'uploading') return '上传中'
  if (file.upload_status === 'failed') return '上传失败'
  const status = file.file_status || file.status
  if (knowledgeUploadStore.isSuccess(status)) return '已完成'
  if (knowledgeUploadStore.isFailed(status)) return '处理失败'
  const statusLabels = {
    pending: '等待处理',
    queued: '排队中',
    processing: '处理中',
    running: '处理中',
  }
  return statusLabels[String(status || '').toLowerCase()] || '已完成'
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
  ['waiting', 'uploading'].includes(file.upload_status) ||
  ['pending', 'queued', 'processing', 'running'].includes(
    String(file.file_status || file.status || '').toLowerCase(),
  )

const taskStatusClass = (file) => {
  if (file.upload_status === 'failed') return 'failed'
  const status = file.file_status || file.status
  if (knowledgeUploadStore.isFailed(status)) return 'failed'
  if (!file.upload_status && knowledgeUploadStore.isSuccess(status)) return 'success'
  return 'processing'
}

const fileTypeLabel = (fileName) => {
  const extension = String(fileName || '').split('.').pop()?.toLowerCase()
  if (extension === 'markdown') return 'MD'
  return ['pdf', 'txt', 'md'].includes(extension) ? extension.toUpperCase() : 'FILE'
}

const fileTypeClass = (fileName) => `type-${fileTypeLabel(fileName).toLowerCase()}`

const formatChunkCount = (totalChunks) =>
  Number.isInteger(totalChunks) && totalChunks >= 0 ? totalChunks : '—'

const togglePreview = (file) => {
  if (file?.id == null || isFileProcessing(file)) return
  activePreviewFile.value = activePreviewFile.value?.id === file.id ? null : file
}

const closePreview = () => {
  activePreviewFile.value = null
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
  if (!taskId) {
    locatedUploadTaskId = ''
    return
  }
  await nextTick()
  const key = String(taskId)
  if (key === locatedUploadTaskId) return
  const element = fileCardRefs.get(key)
  if (!element) return
  locatedUploadTaskId = key
  element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  highlightedTaskId.value = key
  clearTimeout(highlightTimer)
  highlightTimer = setTimeout(() => {
    highlightedTaskId.value = ''
  }, 3000)
  const nextQuery = { ...route.query }
  delete nextQuery.upload_task_id
  void router.replace({ query: nextQuery })
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
  const { supported, unsupported } = partitionKnowledgeFiles(files)
  if (unsupported.length > 0) {
    showMessage(
      `已跳过 ${unsupported.length} 个不支持的文件，仅支持 PDF、TXT、Markdown`,
      'warning',
    )
  }
  if (supported.length === 0) return

  const uploadItems = supported.map((file, index) =>
    reactive({
      local_id: `upload-${Date.now()}-${index}`,
      file,
      file_name: file.name,
      create_time: new Date().toISOString(),
      upload_status: 'waiting',
      upload_progress: 0,
      error_message: null,
    }),
  )
  pendingUploads.value.unshift(...uploadItems)
  uploading.value = true
  uploadCompletedCount.value = 0
  uploadTotalCount.value = supported.length
  try {
    let succeededCount = 0
    const failedFiles = []
    for (const uploadItem of uploadItems) {
      const { file } = uploadItem
      uploadItem.upload_status = 'uploading'
      const formData = new FormData()
      formData.append('file', file)
      try {
        const response = await knowledgeApi.uploadFiles(formData, (progressEvent) => {
          uploadItem.upload_progress = Math.min(
            100,
            Math.round((Math.min(progressEvent.loaded, file.size) * 100) / Math.max(file.size, 1)),
          )
        })
        if (response.data.code === 0) {
          knowledgeUploadStore.registerUploadResult(response.data.data)
          pendingUploads.value = pendingUploads.value.filter(
            (item) => item.local_id !== uploadItem.local_id,
          )
          succeededCount += 1
        } else {
          uploadItem.upload_status = 'failed'
          uploadItem.error_message = response.data.message || '未知错误'
          failedFiles.push({
            file_name: file.name,
            message: uploadItem.error_message,
          })
        }
      } catch (error) {
        const message =
          error?.response?.status === 413
            ? '文件超过上传大小限制'
            : error?.response?.data?.message || error.message || '网络错误'
        uploadItem.upload_status = 'failed'
        uploadItem.error_message = message
        failedFiles.push({ file_name: file.name, message })
        console.error(`上传文件 ${file.name} 错误:`, error)
      } finally {
        uploadCompletedCount.value += 1
      }
    }
    await fetchFileList()
    if (failedFiles.length > 0) {
      const firstFailure = failedFiles[0]
      const suffix = failedFiles.length > 1 ? `，另有 ${failedFiles.length - 1} 个文件失败` : ''
      const successSuffix = succeededCount > 0 ? `；其余 ${succeededCount} 个已进入处理` : ''
      showMessage(
        `${firstFailure.file_name} 上传失败：${firstFailure.message}${suffix}${successSuffix}`,
        'error',
      )
    } else {
      showMessage(`${succeededCount} 个文件已上传，正在后台处理`, 'info')
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
    uploadCompletedCount.value = 0
    uploadTotalCount.value = 0
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
  try {
    const files = await collectDroppedFiles(event.dataTransfer)
    if (files.length === 0) {
      showMessage('文件夹中没有可上传的文件', 'warning')
      return
    }
    await uploadFiles(files)
  } catch (error) {
    console.error('读取拖拽文件夹失败:', error)
    showMessage('读取文件夹失败，请检查文件访问权限后重试', 'error')
  }
}

const removePendingUpload = (localId) => {
  pendingUploads.value = pendingUploads.value.filter((item) => item.local_id !== localId)
}

const handleRetryLocalUpload = async (uploadItem) => {
  removePendingUpload(uploadItem.local_id)
  await uploadFiles([uploadItem.file])
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
    showMessage(
      '文件更新失败: ' + (error?.response?.data?.message || error.message || '网络错误'),
      'error',
    )
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
      if (activePreviewFile.value && ids.includes(activePreviewFile.value.id)) {
        closePreview()
      }
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
    const filesToDownload = displayFileList.value.filter((file) => ids.includes(file.id))

    for (const file of filesToDownload) {
      try {
        // 优先使用新的文件流下载API
        const response = await knowledgeApi.downloadFile(file.id)
        const blob = await assertDownloadableBlob(response.data)
        downloadBlob(blob, file.file_name || `file_${file.id}`)

        // 添加延迟避免浏览器阻止多个下载
        await sleep(200)
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
  height: var(--app-height, 100vh);
  width: 100vw;
  overflow: hidden;
  background-color: var(--bg-primary);
  transition: background-color 0.3s ease;
}

.knowledge-main {
  flex: 1;
  display: flex;
  flex-direction: row;
  height: var(--app-height, 100vh);
  overflow: hidden;
  min-width: 0;
}

.knowledge-content {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 28px 32px 24px;
  overflow: hidden;
  transition: padding-left 0.2s ease;

  &.dragging-upload {
    box-shadow: inset 0 0 0 2px var(--border-color-hover);
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
  border: 1px dashed var(--border-color-hover);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  pointer-events: none;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;

  h1 {
    margin: 0;
    color: var(--text-primary);
    font-size: 21px;
    font-weight: 650;
    letter-spacing: -0.02em;
  }

  p {
    margin: 5px 0 0;
    color: var(--text-secondary);
    font-size: 12px;
  }
}

.action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 34px;
  padding: 7px 13px;
  border: 1px solid var(--primary-color);
  border-radius: 7px;
  background: var(--primary-color);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color 0.16s ease,
    border-color 0.16s ease;
  white-space: nowrap;

  &:hover:not(:disabled) {
    background: color-mix(in srgb, var(--primary-color) 88%, white);
  }

  &:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--primary-color) 35%, transparent);
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.48;
    cursor: not-allowed;
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
    border-top-color: var(--text-secondary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 80px 0;
  color: var(--text-secondary);

  h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
  }

  p {
    margin: 0;
    font-size: 13px;
  }
}

.empty-file-mark {
  display: grid;
  place-items: center;
  width: 42px;
  height: 50px;
  margin-bottom: 6px;
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

// 顶部操作栏
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 38px;
  margin-bottom: 12px;

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    transition: padding-left 0.2s ease;
  }

  // 普通用户上传按钮禁用样式
  .primary-button.disabled-style {
    opacity: 0.6;
    cursor: not-allowed;
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
    background-color: var(--primary-color);
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s ease;

    &:hover:not(:disabled) {
      background-color: color-mix(in srgb, var(--primary-color) 88%, white);
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
    padding: 7px 12px;
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 7px;
    width: 300px;
    transition: all 0.2s ease;

    &:focus-within {
      border-color: var(--border-color-hover);
      box-shadow: 0 0 0 2px var(--bg-secondary);
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
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;

    &:hover:not(:disabled) {
      background: var(--bg-hover);
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
  --file-grid: 36px minmax(240px, 1fr) 160px 72px 176px 152px;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border-color);
  border-radius: 9px;
  background: var(--bg-primary);
  overflow: auto;
}

.file-list-header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: grid;
  grid-template-columns: var(--file-grid);
  align-items: center;
  min-width: 860px;
  min-height: 39px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;

  .actions-label {
    text-align: right;
  }
}

.sortable-header {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 4px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  letter-spacing: inherit;
  cursor: pointer;

  span {
    width: 12px;
    color: var(--text-tertiary);
    font-size: 10px;
    text-align: center;
  }

  &:hover,
  &.active {
    color: var(--text-primary);
  }

  &:focus-visible {
    outline: 2px solid var(--border-color-hover);
    outline-offset: 3px;
    border-radius: 2px;
  }
}

.file-list-body {
  min-width: 860px;
}

.file-card {
  display: grid;
  grid-template-columns: var(--file-grid);
  align-items: center;
  min-height: 60px;
  padding: 7px 12px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  transition: background-color 0.16s ease;
  cursor: pointer;

  &:last-child {
    border-bottom: 0;
  }

  &:hover {
    background-color: var(--bg-tertiary);
  }

  &.selected,
  &.previewing,
  &.highlighted {
    background-color: var(--bg-active);
  }
}

.select-cell {
  display: flex;
  align-items: center;
  justify-content: center;

  input {
    width: 14px;
    height: 14px;
    accent-color: var(--text-secondary);
    cursor: pointer;

    &:disabled {
      cursor: not-allowed;
      opacity: 0.45;
    }
  }
}

.file-info {
  display: flex;
  align-items: center;
  gap: 11px;
  flex: 1;
  min-width: 0;

  &.previewable {
    cursor: pointer;
  }
}

.file-type-mark {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 31px;
  height: 36px;
  border: 1px solid var(--border-color);
  border-radius: 5px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 8px;
  font-weight: 750;
  letter-spacing: 0.04em;

  &.type-pdf {
    border-color: var(--border-color);
    background: var(--bg-secondary);
    color: var(--text-secondary);
  }

  &.type-txt {
    border-color: var(--border-color);
    background: var(--bg-secondary);
    color: var(--text-secondary);
  }
}

.file-title {
  min-width: 0;
}

.file-name {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 560;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-time {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.task-state {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  font-size: 11px;
}

.task-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 7px;
  border-radius: 999px;
  font-weight: 500;

  &.processing {
    color: var(--text-secondary);
    background: var(--bg-secondary);
  }

  &.success {
    color: #26734d;
    background: rgba(38, 115, 77, 0.09);
  }

  &.failed {
    color: #dc3545;
    background: rgba(220, 53, 69, 0.1);
  }
}

.task-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid var(--border-color-hover);
  border-top-color: var(--text-secondary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.task-stage {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-error {
  display: block;
  max-width: 420px;
  margin-top: 3px;
  color: #dc3545;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: break-word;
}

.chunk-count {
  color: var(--text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.file-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
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

  svg {
    width: 16px;
    height: 16px;
  }

  &:hover:not(:disabled) {
    background-color: var(--bg-hover);
    color: var(--text-primary);
  }

  &:focus-visible {
    outline: 2px solid var(--border-color-hover);
    outline-offset: 1px;
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

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 42px;
  padding-top: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.page-size,
.page-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-size-selector {
  position: relative;
}

.page-size-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 58px;
  height: 28px;
  padding: 0 8px 0 10px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;

  &:hover {
    border-color: var(--border-color-hover);
    background: var(--bg-hover);
  }

  &:focus-visible {
    outline: 2px solid var(--border-color-hover);
    outline-offset: 1px;
  }
}

.page-size-chevron {
  color: var(--text-secondary);
  transition: transform 0.16s ease;

  &.is-open {
    transform: rotate(180deg);
  }
}

.page-size-menu {
  position: absolute;
  left: 0;
  bottom: calc(100% + 6px);
  z-index: 30;
  width: 86px;
  padding: 5px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-primary);
  box-shadow: 0 8px 24px rgba(17, 24, 39, 0.14);
}

.page-size-option {
  display: grid;
  grid-template-columns: 16px 1fr;
  align-items: center;
  gap: 6px;
  width: 100%;
  height: 32px;
  padding: 0 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;

  &:hover,
  &:focus-visible {
    background: var(--bg-hover);
    outline: none;
  }

  &.active {
    color: var(--primary-color);
    font-weight: 600;
  }
}

.page-size-check {
  width: 14px;
  height: 14px;
  opacity: 0;

  &.visible {
    opacity: 1;
  }
}

.page-size-dropdown-enter-active,
.page-size-dropdown-leave-active {
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.page-size-dropdown-enter-from,
.page-size-dropdown-leave-to {
  opacity: 0;
  transform: translateY(3px);
}

.page-controls button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  cursor: pointer;

  span {
    font-size: 18px;
    line-height: 1;
  }

  &:hover:not(:disabled) {
    background: var(--bg-secondary);
  }

  &:focus-visible {
    outline: 2px solid var(--border-color-hover);
    outline-offset: 1px;
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
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
    padding: calc(64px + env(safe-area-inset-top)) 12px max(12px, env(safe-area-inset-bottom));

    &.sidebar-collapsed {
      padding-left: 12px;
    }
  }

  .page-header {
    align-items: flex-start;
    margin-bottom: 16px;

    .action-button {
      min-height: 38px;
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

    .toolbar-left {
      flex-direction: column;
      align-items: stretch;
    }

    .toolbar-right {
      flex-direction: row;

      .batch-btn {
        flex: 1;
        justify-content: center;
      }
    }

    .search-box {
      width: 100%;
    }

    .batch-btn {
      justify-content: center;
      min-height: 44px;
    }

    .search-box {
      min-height: 44px;

      input {
        min-width: 0;
        font-size: 16px;
      }

      .clear-search {
        width: 32px;
        height: 32px;
      }
    }
  }

  .file-list {
    overscroll-behavior-y: contain;
  }

  .file-list-header {
    display: none;
  }

  .file-list-body {
    min-width: 0;
  }

  .file-card {
    grid-template-columns: 26px minmax(0, 1fr) auto;
    grid-template-rows: auto auto;
    gap: 5px 8px;
    min-height: 68px;
    padding: 9px 10px;

    > .select-cell {
      grid-column: 1;
      grid-row: 1 / 3;
    }

    > .file-info {
      grid-column: 2;
      grid-row: 1;
    }

    > .task-state {
      grid-column: 2;
      grid-row: 2;
    }

    > .chunk-count,
    > .file-time {
      display: none;
    }
  }

  .file-actions {
    grid-column: 3;
    grid-row: 1 / 3;
    justify-content: flex-end;
  }

  .pagination {
    align-items: flex-end;
    flex-direction: column-reverse;
    gap: 8px;
  }

  .page-size,
  .page-controls {
    width: 100%;
    justify-content: space-between;
  }

  .retry-btn,
  .icon-btn {
    min-width: 44px;
    min-height: 44px;
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
