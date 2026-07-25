/**
 * @author: caoshuai.cs
 * @date: 2026-07-14
 * @description: 全局轻量 toast 提示（无第三方依赖），统一成功/失败/警告/信息反馈，适配紫色主题
 */
import { ref } from 'vue'

// 全局单例的 toast 队列，供 ToastContainer 渲染
const toasts = ref([])

let seed = 0

const DEFAULT_DURATION = 3000

/**
 * 弹出一条 toast
 * @param {string} message - 提示文案
 * @param {('success'|'error'|'warning'|'info')} [type='info'] - 类型
 * @param {number} [duration=3000] - 自动消失毫秒数，<=0 表示不自动消失
 * @param {{onClick?: Function}} [options] - 可选点击回调
 * @returns {number} toast id
 */
const showToast = (message, type = 'info', duration = DEFAULT_DURATION, options = {}) => {
  const id = ++seed
  const toast = {
    id,
    message,
    type,
    duration,
    remaining: duration,
    started_at: Date.now(),
    timer: null,
    onClick: options.onClick,
  }
  toasts.value.push(toast)
  startTimer(toast)

  return id
}

const removeToast = (id) => {
  const index = toasts.value.findIndex((item) => item.id === id)
  if (index > -1) {
    clearTimeout(toasts.value[index].timer)
    toasts.value.splice(index, 1)
  }
}

const startTimer = (toast) => {
  if (toast.remaining <= 0) return
  toast.started_at = Date.now()
  toast.timer = setTimeout(() => removeToast(toast.id), toast.remaining)
}

const pauseToast = (id) => {
  const toast = toasts.value.find((item) => item.id === id)
  if (!toast?.timer) return
  clearTimeout(toast.timer)
  toast.timer = null
  toast.remaining = Math.max(0, toast.remaining - (Date.now() - toast.started_at))
}

const resumeToast = (id) => {
  const toast = toasts.value.find((item) => item.id === id)
  if (!toast || toast.timer || toast.duration <= 0) return
  startTimer(toast)
}

const activateToast = (id) => {
  const toast = toasts.value.find((item) => item.id === id)
  if (!toast) return
  if (typeof toast.onClick === 'function') {
    toast.onClick()
  }
  removeToast(id)
}

export const useToast = () => {
  return {
    toasts,
    showToast,
    removeToast,
    pauseToast,
    resumeToast,
    activateToast,
    success: (message, duration) => showToast(message, 'success', duration),
    error: (message, duration) => showToast(message, 'error', duration),
    warning: (message, duration) => showToast(message, 'warning', duration),
    info: (message, duration) => showToast(message, 'info', duration),
  }
}
