/**
 * @author: caoshuai.cs
 * @date: 2026-08-02 17:59
 * @description: 知识库拖拽目录展开与上传文件筛选测试
 */
import { describe, expect, it } from 'vitest'
import {
  collectDroppedFiles,
  partitionKnowledgeFiles,
} from '../src/utils/knowledgeUploadFiles'

const fileEntry = (file) => ({
  isFile: true,
  isDirectory: false,
  file: (resolve) => resolve(file),
})

const directoryEntry = (batches) => ({
  isFile: false,
  isDirectory: true,
  createReader: () => {
    let index = 0
    return {
      readEntries: (resolve) => resolve(batches[index++] || []),
    }
  },
})

describe('knowledgeUploadFiles', () => {
  it('递归展开拖拽文件夹中的文件', async () => {
    const markdown = new File(['# 章节'], 'lesson.md', { type: 'text/markdown' })
    const text = new File(['实验说明'], 'readme.txt', { type: 'text/plain' })
    const nestedDirectory = directoryEntry([[fileEntry(text)], []])
    const rootDirectory = directoryEntry([[fileEntry(markdown)], [nestedDirectory], []])
    const dataTransfer = {
      items: [{ webkitGetAsEntry: () => rootDirectory }],
      files: [],
    }

    const files = await collectDroppedFiles(dataTransfer)

    expect(files.map((file) => file.name)).toEqual(['lesson.md', 'readme.txt'])
  })

  it('区分支持与不支持的文件类型', () => {
    const files = [
      new File(['markdown'], 'lesson.MD'),
      new File(['pdf'], 'guide.pdf'),
      new File(['image'], 'cover.png'),
    ]

    const result = partitionKnowledgeFiles(files)

    expect(result.supported.map((file) => file.name)).toEqual(['lesson.MD', 'guide.pdf'])
    expect(result.unsupported.map((file) => file.name)).toEqual(['cover.png'])
  })
})
