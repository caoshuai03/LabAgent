/**
 * @author: caoshuai.cs
 * @date: 2026-08-02 19:10
 * @description: Blob 响应错误识别与浏览器文件下载工具
 */
export const readBlobText = (blob) => {
  if (typeof blob.text === 'function') return blob.text()
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('读取文件失败'))
    reader.readAsText(blob)
  })
}

export const assertDownloadableBlob = async (data) => {
  const blob = data instanceof Blob ? data : new Blob([data])
  if (!String(blob.type || '').toLowerCase().includes('application/json')) {
    return blob
  }

  try {
    const payload = JSON.parse(await readBlobText(blob))
    if (Number(payload?.code) !== 0) {
      throw new Error(payload?.message || '文件下载失败')
    }
  } catch (error) {
    if (error instanceof SyntaxError) return blob
    throw error
  }
  return blob
}

export const downloadBlob = (blob, fileName) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.setTimeout(() => window.URL.revokeObjectURL(url), 0)
}
