/**
 * @author: caoshuai.cs
 * @date: 2026-07-16 16:44
 * @description: 通用异步辅助工具
 */
export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
