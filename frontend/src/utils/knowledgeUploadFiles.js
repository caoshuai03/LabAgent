/**
 * @author: caoshuai.cs
 * @date: 2026-08-02 17:59
 * @description: 知识库拖拽上传的目录展开与文件类型筛选
 */

const SUPPORTED_EXTENSIONS = new Set(['pdf', 'txt', 'md', 'markdown'])

const fileFromEntry = (entry) =>
  new Promise((resolve, reject) => {
    entry.file(resolve, reject)
  })

const readDirectoryEntries = async (directoryEntry) => {
  const reader = directoryEntry.createReader()
  const entries = []
  while (true) {
    const batch = await new Promise((resolve, reject) => {
      reader.readEntries(resolve, reject)
    })
    if (batch.length === 0) return entries
    entries.push(...batch)
  }
}

const filesFromEntry = async (entry) => {
  if (entry.isFile) return [await fileFromEntry(entry)]
  if (!entry.isDirectory) return []
  const children = await readDirectoryEntries(entry)
  const nestedFiles = await Promise.all(children.map(filesFromEntry))
  return nestedFiles.flat()
}

export const collectDroppedFiles = async (dataTransfer) => {
  const items = Array.from(dataTransfer?.items || [])
  const entries = items
    .map((item) => item.webkitGetAsEntry?.())
    .filter(Boolean)

  if (entries.length === 0) {
    return Array.from(dataTransfer?.files || [])
  }

  const files = await Promise.all(entries.map(filesFromEntry))
  return files.flat()
}

export const partitionKnowledgeFiles = (files) => {
  const supported = []
  const unsupported = []
  files.forEach((file) => {
    const extension = file.name.split('.').pop()?.toLowerCase()
    if (SUPPORTED_EXTENSIONS.has(extension)) {
      supported.push(file)
    } else {
      unsupported.push(file)
    }
  })
  return { supported, unsupported }
}
