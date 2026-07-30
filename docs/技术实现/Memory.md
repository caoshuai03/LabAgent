<!--
 @author: caoshuai.cs
 @date: 2026-07-31
 @description: LabAgent 短期上下文压缩与用户长期记忆实现参考
-->

# Memory

## 1. 两层模型

LabAgent 将 Memory 分为：

- 会话短期记忆：LangGraph checkpoint 中的消息和结构化摘要。
- 用户长期记忆：`MEMORY_ROOT` 下按用户隔离的 Markdown 文件。

业务消息表仍保存完整可见历史。上下文压缩只改变后续模型工作的 checkpoint 状态，不删除用户在聊天记录中看到的原始消息。

## 2. 短期上下文

### 2.1 预算

`conversation_compaction_service.py` 以固定 `o200k_base` tokenizer 估算：

- 系统提示。
- 会话摘要。
- 消息内容。
- Tool Schema。

当前实现按 200K 上下文窗口、80% 触发线和 10% 摘要预算工作。这些是代码约定，不是环境配置。修改时需同时验证不同模型的实际上下文限制。

### 2.2 自动压缩

每次模型调用前，`compact_context` 节点检查总 token。超过阈值时：

1. 找到可压缩的较早消息。
2. 保留最近完整对话和未闭合工具协议。
3. 用结构化模型输出生成/更新会话摘要。
4. 限制摘要 token。
5. 使用 `RemoveMessage(REMOVE_ALL_MESSAGES)` 清除旧 checkpoint 消息，再写回保留消息。
6. 把摘要保存到 `conversation_summary` 并在后续系统上下文中注入。

压缩不能把 AI 工具调用与对应 ToolMessage 拆开。没有足够可压缩消息或压缩收益不足时保持原状态。

### 2.3 主动压缩

`POST /api/v1/ai/sessions/{session_id}/compress` 允许用户主动压缩当前会话。服务先校验会话归属，再读取 checkpoint、执行相同压缩逻辑并返回压缩前后 token、移除消息数和摘要预览。

## 3. 长期记忆目录

每个用户的目录：

```text
data/memory/users/{user_id}/
├── AGENTS.md
├── MEMORY_INDEX.md
├── facts.md
├── preferences.md
└── experiences/
    └── {memory_id}.md
```

- `AGENTS.md`：用户手工维护的个人说明，每轮固定注入。
- `MEMORY_INDEX.md`：事实、偏好和经验的轻量目录，每轮固定注入。
- `facts.md`：相对稳定的用户事实。
- `preferences.md`：交互和输出偏好。
- `experiences/`：包含问题、解决过程、结果和可复用经验的独立记录。

正文不全部固定注入；Agent 先看索引，再按需使用 Memory 工具查找和读取，控制上下文体积。

## 4. 写入与管理

`MemoryService` 提供：

- 初始化用户目录和默认文件。
- 原子写入，避免进程中断留下半文件。
- 事实、偏好和经验的结构化解析与索引重建。
- 长度、类型、状态、ID 和相对路径校验。
- 编辑、启用/停用和删除。
- find、grep 和分段 read。

普通 API：

| 接口 | 作用 |
|---|---|
| `GET /memory/agents` | 读取当前用户 `AGENTS.md` |
| `PUT /memory/agents` | 更新当前用户 `AGENTS.md` |
| `GET /memory/items` | 分页查询事实、偏好和经验 |
| `PUT /memory/items/{memory_id}` | 编辑内容或状态 |
| `DELETE /memory/items/{memory_id}` | 删除一条记忆 |

Agent 工具包括 `memory_find`、`memory_grep`、`memory_read`、`remember_memory` 和 `forget_memory`。所有操作只作用于 JWT 用户对应目录。

## 5. 自动提取

一次 Agent 回答成功完成后，`MemoryExtractionScheduler` 按用户和会话调度空闲后台任务：

1. 读取尚未处理的新业务消息。
2. 用结构化模型输出提取事实、偏好和可复用经验。
3. 允许返回空结果，禁止为了“有记忆”强行提取。
4. 根据来源消息、标题和内容去重后写入。
5. 更新处理进度，避免重复扫描全部历史。

自动提取只写事实、偏好和经验，不修改用户 `AGENTS.md`。任务失败记录日志但不影响已完成的对话响应；应用退出时等待或关闭调度任务。

## 6. 安全与隐私

- 用户 ID 只能来自认证上下文。
- 路径不接受任意绝对地址、`..` 或符号链接越界。
- 文件、单项内容、搜索词和读取行数均有限制。
- 日志只记录用户 ID、会话 ID 和数量，不输出完整私人记忆。
- 长期记忆进入 Prompt 前被标记为用户上下文，不能覆盖系统规则和工具权限。
- 自动提取应避免保存密码、Token、API Key 和无长期价值的临时信息。

## 7. 代码入口

| 模块 | 职责 |
|---|---|
| `services/context_token_counter.py` | 上下文 token 估算 |
| `services/conversation_compaction_service.py` | 摘要与消息裁剪 |
| `services/memory_service.py` | Markdown 长期记忆 |
| `services/memory_extraction_service.py` | 后台结构化提取 |
| `tools/memory_tools.py` | Agent 记忆工具 |
| `api/v1/memory.py` | 管理 API |
| `views/MemoryManagement.vue` | 用户管理页 |

向量化长期记忆、可审计撤销和更细粒度保留策略属于未来优化，不作为当前能力描述。
