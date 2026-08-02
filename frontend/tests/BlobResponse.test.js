/**
 * @author: caoshuai.cs
 * @date: 2026-08-02 19:15
 * @description: Blob 下载响应识别与浏览器下载测试
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { assertDownloadableBlob, downloadBlob } from '../src/utils/blobResponse'

describe('blobResponse', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('拒绝被包装成 Blob 的后端错误响应', async () => {
    const blob = new Blob(
      [JSON.stringify({ code: 50000, data: null, message: '系统内部异常' })],
      { type: 'application/json' },
    )

    await expect(assertDownloadableBlob(blob)).rejects.toThrow('系统内部异常')
  })

  it('触发文件下载并延迟回收 Blob URL', () => {
    vi.useFakeTimers()
    const createObjectURL = vi.fn(() => 'blob:download')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const blob = new Blob(['content'], { type: 'text/plain' })

    downloadBlob(blob, '课程资料.txt')

    expect(click).toHaveBeenCalledOnce()
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    vi.runAllTimers()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:download')
  })
})
