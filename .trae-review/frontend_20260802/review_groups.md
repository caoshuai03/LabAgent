## Group 1: API、认证、路由与状态
分组维度: 代码层级 + 调用链路
审查重点: BaseResponse 语义、蛇形契约、鉴权状态、并发请求、对象 URL 生命周期
文件:
- frontend/src/api/
- frontend/src/router/
- frontend/src/stores/
- frontend/src/App.vue

## Group 2: 内容渲染与安全
分组维度: 业务功能 + 调用链路
审查重点: Markdown/HTML、XSS、外链、工具结果和文件内容渲染
文件:
- frontend/src/utils/
- frontend/src/components/MessageItem.vue
- frontend/src/components/WorkspacePreviewPanel.vue
- frontend/src/components/ReasoningPanel.vue
- frontend/src/components/ToolActivityPanel.vue
- frontend/src/views/SkillsManagement.vue

## Group 3: 页面交互、性能与测试
分组维度: 业务功能
审查重点: 异步生命周期、竞态、重复请求、性能、可访问性、测试缺口
文件:
- frontend/src/components/
- frontend/src/views/
- frontend/tests/
- frontend/package.json
- frontend/vite.config.js
