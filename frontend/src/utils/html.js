/**
 * @author: caoshuai.cs
 * @date: 2026-07-16 16:44
 * @description: HTML 安全处理工具，统一提供转义能力
 */
const HTML_ESCAPE_MAP = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#039;',
}

export function escapeHtml(value) {
  if (typeof value !== 'string') return ''
  return value.replace(/[&<>"']/g, (char) => HTML_ESCAPE_MAP[char])
}
