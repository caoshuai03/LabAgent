## Group 1: 聊天正文长内容
分组维度: 业务功能
核心功能: Markdown 正文、代码块、表格和引用展示
审查重点: 横向溢出、内部纵向滚动、消息容器撑宽
文件:
- frontend/src/components/MessageItem.vue
- frontend/src/utils/markdown.js

## Group 2: 思考与工具长内容
分组维度: 业务功能
核心功能: 思考、工具活动与工具授权参数展示
审查重点: 长行展示、滚动方向、卡片宽度约束
文件:
- frontend/src/components/ReasoningPanel.vue
- frontend/src/components/ToolActivityPanel.vue
- frontend/src/components/ToolApprovalInline.vue

## Group 3: 预览区域长内容
分组维度: 业务功能
核心功能: 工作区与知识库文件预览
审查重点: 内容横向溢出与面板级纵向滚动
文件:
- frontend/src/components/WorkspacePreviewPanel.vue
- frontend/src/components/KnowledgePreviewPanel.vue
