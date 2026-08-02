# 待评审文件列表

scope: diff_only

diff_direction: base → source（`-` 行 = 旧代码/已删除，`+` 行 = 新代码/待评审）

总文件数: 69
排除文件数: 22（隐藏文件/目录 1 个, 二进制/媒体文件 3 个, 生成/测试目录 15 个, 依赖/包管理 2 个, 空文件 1 个）

| 文件路径 | 变更行数 |
| -------- | -------- |
| backend/alembic/script.py.mako | +5, -6 |
| backend/alembic/versions/0001_initial.py | +3, -5 |
| backend/app/api/v1/knowledge.py | +54, -7 |
| backend/app/api/v1/memory.py | +4, -4 |
| backend/app/core/config.py | +5, -1 |
| backend/app/graph/chat_graph.py | +46, -23 |
| backend/app/models/kb_file.py | +11, -1 |
| backend/app/repositories/kb_file_repository.py | +59, -2 |
| backend/app/schemas/knowledge.py | +6, -0 |
| backend/app/schemas/memory.py | +4, -4 |
| backend/app/services/ai_service.py | +8, -0 |
| backend/app/services/conversation_compaction_service.py | +13, -4 |
| backend/app/services/document_loader.py | +75, -1 |
| backend/app/services/document_splitter.py | +88, -8 |
| backend/app/services/knowledge_cache.py | +6, -1 |
| backend/app/services/knowledge_service.py | +71, -3 |
| backend/app/services/model_provider.py | +49, -0 |
| backend/app/services/rag_retrieval.py | +31, -13 |
| backend/app/services/skill_service.py | +11, -4 |
| backend/app/tools/file_tools.py | +54, -3 |
| backend/app/tools/knowledge_tool.py | +14, -4 |
| backend/app/tools/shell_tool.py | +45, -3 |
| backend/app/tools/skill_tools.py | +1, -0 |
| backend/pyproject.toml | +1, -0 |
| "docs/\345\212\237\350\203\275\344\273\213\347\273\215/\344\272\247\345\223\201\344\270\216\346\236\266\346\236\204.md" | +3, -3 |
| "docs/\345\212\237\350\203\275\344\273\213\347\273\215/\346\240\270\345\277\203\345\212\237\350\203\275.md" | +3, -3 |
| "docs/\346\212\200\346\234\257\345\256\236\347\216\260/Memory.md" | +3, -1 |
| "docs/\346\212\200\346\234\257\345\256\236\347\216\260/\351\203\250\347\275\262\344\270\216\346\250\241\345\236\213\346\216\245\345\205\245.md" | +2, -0 |
| frontend/Dockerfile | +2, -2 |
| frontend/src/App.vue | +6, -0 |
| frontend/src/api/knowledge.js | +5, -1 |
| frontend/src/api/memory.js | +1, -1 |
| frontend/src/components/ChatInput.vue | +27, -1 |
| frontend/src/components/ConversationItem.vue | +123, -3 |
| frontend/src/components/ConversationList.vue | +13, -1 |
| frontend/src/components/MessageItem.vue | +164, -11 |
| frontend/src/components/MessageList.vue | +119, -8 |
| frontend/src/components/ReasoningPanel.vue | +20, -37 |
| frontend/src/components/ToolActivityPanel.vue | +23, -3 |
| frontend/src/components/ToolApprovalInline.vue | +17, -5 |
| frontend/src/components/WorkspacePreviewPanel.vue | +332, -27 |
| frontend/src/main.js | +2, -0 |
| frontend/src/stores/chat.js | +97, -11 |
| frontend/src/utils/markdown.js | +56, -2 |
| frontend/src/views/KnowledgeManagement.vue | +991, -234 |
| frontend/src/views/Login.vue | +123, -87 |
| frontend/src/views/MemoryManagement.vue | +58, -16 |
