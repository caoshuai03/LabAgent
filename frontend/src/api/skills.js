import apiClient from './index'

/**
 * 获取所有 Skills 列表
 */
export const getSkills = () => {
  return apiClient.get('/v1/skills')
}

/**
 * 获取指定 Skill 的完整说明
 */
export const getSkillDetail = (name) => {
  return apiClient.get(`/v1/skills/${encodeURIComponent(name)}`)
}
