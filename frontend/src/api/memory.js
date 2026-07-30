/**
 * @author: caoshuai.cs
 * @date: 2026-07-30 00:00
 * @description: 当前用户 AGENTS.md 与长期记忆管理 API
 */
import apiClient from './index'

export const getAgentsMemory = () => apiClient.get('/v1/memory/agents')

export const updateAgentsMemory = (content) => {
  return apiClient.put('/v1/memory/agents', { content })
}

export const getMemoryItems = (params = {}) => {
  return apiClient.get('/v1/memory/items', { params })
}

export const updateMemoryItem = (memoryId, data) => {
  return apiClient.put(`/v1/memory/items/${memoryId}`, data)
}

export const deleteMemoryItem = (memoryId) => {
  return apiClient.delete(`/v1/memory/items/${memoryId}`)
}
