/**
 * @author: caoshuai.cs
 * @date: 2026-07-16 16:44
 * @description: 浏览器本地存储读取工具，避免异常数据影响应用初始化
 */
export function readJsonStorage(key, fallback = null) {
  const value = localStorage.getItem(key)
  if (!value) return fallback

  try {
    return JSON.parse(value)
  } catch {
    localStorage.removeItem(key)
    return fallback
  }
}
