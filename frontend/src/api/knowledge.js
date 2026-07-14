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
  uploadFiles: (formData) => {
    return apiClient.post('/v1/knowledge/file/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
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
   * @param {Array<number>} ids - 文件ID数组
   * @returns {Promise} 删除结果
   */
  deleteFiles: (ids) => {
    // Spring Boot接受List参数时，需要将数组转换为查询字符串格式
    const params = new URLSearchParams()
    ids.forEach((id) => params.append('ids', id))
    return apiClient.delete(`/v1/knowledge/delete?${params.toString()}`)
  },

  /**
   * 下载文件
   * @param {Array<number>} ids - 文件ID数组
   * @returns {Promise} 文件blob数据
   */
  downloadFiles: (ids) => {
    // Spring Boot接受List参数时，需要将数组转换为查询字符串格式
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
