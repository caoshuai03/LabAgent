/**
 * @author: caoshuai.cs
 * @date: 2026-07-30 00:00
 * @description: 当前用户 AGENTS.md 与个性化记忆管理 API
 */
import apiClient from './index'

export const getAgentsMemory = () => apiClient.get('/v1/memory/agents')

export const updateAgentsMemory = (content) => {
  return apiClient.put('/v1/memory/agents', { content })
}

export const getUserProfileMemory = () => apiClient.get('/v1/memory/profile')

export const getMemorySettings = () => apiClient.get('/v1/memory/settings')

export const updateMemorySettings = (longTermMemoryEnabled) => {
  return apiClient.put('/v1/memory/settings', {
    long_term_memory_enabled: longTermMemoryEnabled,
  })
}
