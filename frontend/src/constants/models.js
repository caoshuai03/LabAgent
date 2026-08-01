/**
 * @author: caoshuai.cs
 * @date: 2026-07-16 16:44
 * @description: 前端可选模型配置，统一维护默认模型和展示名称
 */
export const DEFAULT_MODEL = 'auto'

export const AVAILABLE_MODELS = [
  { label: 'Auto Mode', value: DEFAULT_MODEL, icon: 'auto' },
  { label: 'Qwen3.5-35B', value: 'qwen3.5:35b', icon: 'qwen' },
  { label: 'GPT-5.5', value: 'gpt-5.5-2026-04-24', icon: 'openai' },
]
