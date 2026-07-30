/**
 * @author: caoshuai.cs
 * @date: 2026-07-31 01:42
 * @description: 全局确认弹窗状态与调用方法，统一替代浏览器原生 confirm
 */
import { ref } from 'vue'

const dialog = ref(null)
const pendingRequests = []

const showNext = () => {
  if (dialog.value || pendingRequests.length === 0) return

  const request = pendingRequests.shift()
  dialog.value = {
    ...request.options,
    resolve: request.resolve,
  }
}

const confirm = (options) =>
  new Promise((resolve) => {
    const normalizedOptions = {
      title: '确认操作',
      confirm_text: '确认',
      cancel_text: '取消',
      tone: 'default',
      ...(typeof options === 'string' ? { message: options } : options),
    }

    pendingRequests.push({ options: normalizedOptions, resolve })
    showNext()
  })

const settle = (confirmed) => {
  if (!dialog.value) return

  const resolve = dialog.value.resolve
  dialog.value = null
  resolve(confirmed)
  showNext()
}

export const useConfirm = () => ({
  dialog,
  confirm,
  confirmAction: () => settle(true),
  cancelAction: () => settle(false),
})
