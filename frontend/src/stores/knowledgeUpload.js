/**
 * @author: caoshuai.cs
 * @date: 2026-07-25
 * @description: 知识库异步上传任务状态与跨页面动态轮询
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import router from '../router'
import { knowledgeApi } from '../api/knowledge'
import { useToast } from '../composables/useToast'

const SUCCESS_STATUSES = new Set(['ready', 'success', 'succeeded', 'completed', 'done'])
const FAILED_STATUSES = new Set(['failed', 'error'])
const TERMINAL_STATUSES = new Set([...SUCCESS_STATUSES, ...FAILED_STATUSES])

const normalizeStatus = (status) => String(status || '').toLowerCase()

const taskKey = (task) => String(task?.task_id ?? '')

const responseRecords = (data) => {
  if (Array.isArray(data)) return data
  if (!data || typeof data !== 'object') return []
  return data.records || data.list || []
}

export const useKnowledgeUploadStore = defineStore('knowledgeUpload', () => {
  const tasks = ref([])
  const fileRecords = ref([])
  const polling = ref(false)
  const consecutiveErrors = ref(0)
  const toast = useToast()
  let pollTimer = null
  let requestInFlight = false
  let visibilityListenerBound = false

  const activeTasks = computed(() =>
    tasks.value.filter((task) => !TERMINAL_STATUSES.has(normalizeStatus(task.status))),
  )

  const isSuccess = (status) => SUCCESS_STATUSES.has(normalizeStatus(status))
  const isFailed = (status) => FAILED_STATUSES.has(normalizeStatus(status))
  const isTerminal = (status) => TERMINAL_STATUSES.has(normalizeStatus(status))

  const locateTask = (taskId) => {
    router.push({
      name: 'Knowledge',
      query: { upload_task_id: String(taskId) },
    })
  }

  const notifyTerminalTask = (task) => {
    const taskId = taskKey(task)
    if (!taskId) return
    const fileName = task.file_name || task.name || '知识库文件'
    const options = { onClick: () => locateTask(taskId) }
    if (isSuccess(task.status)) {
      toast.showToast(`“${fileName}”处理完成，点击查看`, 'success', 6000, options)
    } else if (isFailed(task.status)) {
      toast.showToast(`“${fileName}”处理失败，点击查看`, 'error', 8000, options)
    }
  }

  const upsertTask = (task, notifyTransition = false) => {
    const key = taskKey(task)
    if (!key) return
    const index = tasks.value.findIndex((item) => taskKey(item) === key)
    const previous = index >= 0 ? tasks.value[index] : null
    const merged = previous ? { ...previous, ...task } : task
    if (index >= 0) {
      tasks.value.splice(index, 1, merged)
    } else {
      tasks.value.unshift(merged)
    }
    if (notifyTransition && previous && !isTerminal(previous.status) && isTerminal(merged.status)) {
      notifyTerminalTask(merged)
    }
  }

  const registerUploadResult = (data) => {
    const records = Array.isArray(data) ? data : [data]
    records.filter(Boolean).forEach((task) => upsertTask(task))
    if (records.some((task) => taskKey(task) && !isTerminal(task.status))) {
      startPolling(true)
    }
  }

  const setFileRecords = (records) => {
    fileRecords.value = Array.isArray(records) ? records : []
  }

  const nextPollDelay = () => {
    if (consecutiveErrors.value > 0) {
      return Math.min(30000, 3000 * 2 ** (consecutiveErrors.value - 1))
    }
    if (document.hidden) return 5000
    const hasRunningTask = activeTasks.value.some((task) =>
      ['processing', 'running', 'embedding', 'indexing'].includes(normalizeStatus(task.status)),
    )
    if (hasRunningTask) return 1500
    return 3000
  }

  const scheduleNextPoll = () => {
    if (!polling.value) return
    window.clearTimeout(pollTimer)
    pollTimer = window.setTimeout(pollTasks, nextPollDelay())
  }

  const pollTasks = async () => {
    if (!polling.value || requestInFlight) return
    requestInFlight = true
    try {
      const response = await knowledgeApi.getUploadTasks(true)
      if (response.data.code !== 0) {
        throw new Error(response.data.message || '查询上传任务失败')
      }
      const records = responseRecords(response.data.data)
      records.forEach((task) => upsertTask(task, true))

      const returnedKeys = new Set(records.map(taskKey))
      const missingActiveTasks = activeTasks.value.filter((task) => !returnedKeys.has(taskKey(task)))
      await Promise.all(
        missingActiveTasks.map(async (task) => {
          const detailResponse = await knowledgeApi.getUploadTask(task.task_id)
          if (detailResponse.data.code === 0 && detailResponse.data.data) {
            upsertTask(detailResponse.data.data, true)
          }
        }),
      )
      consecutiveErrors.value = 0
    } catch (error) {
      consecutiveErrors.value += 1
      console.error('轮询知识库上传任务失败:', error)
    } finally {
      requestInFlight = false
      if (activeTasks.value.length > 0 || consecutiveErrors.value > 0) {
        scheduleNextPoll()
      } else {
        stopPolling()
      }
    }
  }

  const handleVisibilityChange = () => {
    if (!document.hidden && polling.value) {
      window.clearTimeout(pollTimer)
      pollTasks()
    }
  }

  function startPolling(immediate = false) {
    if (!visibilityListenerBound) {
      document.addEventListener('visibilitychange', handleVisibilityChange)
      visibilityListenerBound = true
    }
    polling.value = true
    window.clearTimeout(pollTimer)
    if (immediate) {
      pollTasks()
    } else {
      scheduleNextPoll()
    }
  }

  const stopPolling = () => {
    polling.value = false
    window.clearTimeout(pollTimer)
  }

  const retryTask = async (taskId) => {
    const response = await knowledgeApi.retryUploadTask(taskId)
    if (response.data.code !== 0) {
      throw new Error(response.data.message || '重试上传任务失败')
    }
    upsertTask(response.data.data)
    startPolling(true)
    return response.data.data
  }

  return {
    tasks,
    fileRecords,
    activeTasks,
    isSuccess,
    isFailed,
    isTerminal,
    upsertTask,
    registerUploadResult,
    setFileRecords,
    startPolling,
    stopPolling,
    retryTask,
  }
})
