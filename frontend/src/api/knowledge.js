import apiClient from './index'

/**
 * 知识库管理API
 */
export const knowledgeApi = {
  /**
   * 上传文件
   * @param {FormData} formData - 包含文件的FormData对象
   * @returns {Promise} 上传结果
   */
  uploadFiles: (formData, onUploadProgress) => {
    return apiClient.post('/v1/knowledge/file/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress,
    })
  },

  /**
   * 查询上传任务
   * @param {boolean} activeOnly - 是否只查询未结束任务
   * @returns {Promise} 上传任务列表
   */
  getUploadTasks: (activeOnly = true) => {
    return apiClient.get('/v1/knowledge/upload-tasks', {
      params: { active_only: activeOnly },
    })
  },

  /**
   * 查询单个上传任务
   * @param {string|number} taskId - 上传任务 ID
   * @returns {Promise} 上传任务
   */
  getUploadTask: (taskId) => {
    return apiClient.get(`/v1/knowledge/upload-tasks/${encodeURIComponent(taskId)}`)
  },

  /**
   * 重试失败的上传任务
   * @param {string|number} taskId - 上传任务 ID
   * @returns {Promise} 重试后的上传任务
   */
  retryUploadTask: (taskId) => {
    return apiClient.post(`/v1/knowledge/upload-tasks/${encodeURIComponent(taskId)}/retry`)
  },

  /**
   * 更新已有文档（按 kb_file_id 定位做增量更新，不新增记录）
   * @param {number} kbFileId - 待更新文档的记录 ID（列表行的 id）
   * @param {File} file - 新文件
   * @returns {Promise} 更新后的文件记录
   */
  updateFile: (kbFileId, file) => {
    const formData = new FormData()
    formData.append('kb_file_id', kbFileId)
    formData.append('file', file)
    return apiClient.post('/v1/knowledge/file/update', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  /**
   * 查询文件列表（默认全量返回）
   * @param {Object} params - 查询参数
   * @param {string} [params.file_name] - 文件名（可选，用于搜索）
   * @returns {Promise} 文件列表数据
   */
  getFileList: (params) => {
    return apiClient.get('/v1/knowledge/contents', { params })
  },

  /**
   * 删除文件
   * 后端按重复 query 参数接收 ids。
   * @param {Array<number>} ids - 文件ID数组
   * @returns {Promise} 删除结果
   */
  deleteFiles: (ids) => {
    const params = new URLSearchParams()
    ids.forEach((id) => params.append('ids', id))
    return apiClient.delete(`/v1/knowledge/delete?${params.toString()}`)
  },

  /**
   * 下载文件
   * 后端按重复 query 参数接收 ids。
   * @param {Array<number>} ids - 文件ID数组
   * @returns {Promise} 文件blob数据
   */
  downloadFiles: (ids) => {
    const params = new URLSearchParams()
    ids.forEach((id) => params.append('ids', id))
    return apiClient.get(`/v1/knowledge/download?${params.toString()}`, {
      responseType: 'blob',
    })
  },

  /**
   * 下载单个文件（使用文件流）
   * @param {number} id - 文件ID
   * @returns {Promise} 文件blob数据
   */
  downloadFile: (id) => {
    return apiClient.get(`/v1/knowledge/downloadFile/${id}`, {
      responseType: 'blob',
    })
  },
}
