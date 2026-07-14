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
 * @returns {number} toast id
 */
const showToast = (message, type = 'info', duration = DEFAULT_DURATION) => {
  const id = ++seed
  toasts.value.push({ id, message, type })

  if (duration > 0) {
    setTimeout(() => removeToast(id), duration)
  }

  return id
}

const removeToast = (id) => {
  const index = toasts.value.findIndex((item) => item.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
}

export const useToast = () => {
  return {
    toasts,
    showToast,
    removeToast,
    success: (message, duration) => showToast(message, 'success', duration),
    error: (message, duration) => showToast(message, 'error', duration),
    warning: (message, duration) => showToast(message, 'warning', duration),
    info: (message, duration) => showToast(message, 'info', duration),
  }
}
