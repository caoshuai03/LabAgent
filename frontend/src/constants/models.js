/**
 * @author: caoshuai.cs
 * @date: 2026-07-16 16:44
 * @description: 前端可选模型配置，统一维护默认模型和展示名称
 */
export const DEFAULT_MODEL = 'qwen3:8b'

export const AVAILABLE_MODELS = [
  { label: 'Qwen3-8B', value: DEFAULT_MODEL },
  { label: 'GPT-5.5', value: 'gpt-5.5-2026-04-24' },
  { label: 'Ernie 4.5-300B', value: 'ernie-4.5-turbo-128k-preview' },
  { label: 'DeepSeek V3', value: 'deepseek-v3' },
  { label: 'DeepSeek R1', value: 'deepseek-r1' },
]
