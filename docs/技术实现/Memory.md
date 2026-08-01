<!--
 @author: caoshuai.cs
 @date: 2026-07-31
 @description: LabAgent 短期上下文压缩与用户长期 Profile 实现参考
-->

# Memory

## 1. 两层模型

LabAgent 将 Memory 分为：

- 会话短期记忆：LangGraph checkpoint 中的消息和结构化摘要。
- 用户长期记忆：`MEMORY_ROOT` 下按用户隔离的 `AGENTS.md` 与 `USER_PROFILE.md`。

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
├── USER_PROFILE.md
└── .meta/
    └── extraction_state.json
```

- `AGENTS.md`：用户手工维护的个人说明，每轮固定注入。
- `USER_PROFILE.md`：系统从对话中沉淀的少量稳定事实、偏好、工作方式、技术背景和项目规则。开启长期记忆时每轮固定注入；关闭后不注入、不自动更新。

长期记忆不再拆分 facts、preferences 和 experiences，也不暴露文件搜索工具。Profile 有固定长度上限，避免长期记忆无限增长。

## 4. 写入与管理

`MemoryService` 提供：

- 初始化用户目录和默认文件。
- 原子写入，避免进程中断留下半文件。
- AGENTS 与 USER_PROFILE 的长度校验。
- USER_PROFILE 敏感凭证过滤。
- 用户级长期记忆开关。
- 后台提取进度记录。

普通 API：

| 接口 | 作用 |
|---|---|
| `GET /memory/agents` | 读取当前用户 `AGENTS.md` |
| `PUT /memory/agents` | 更新当前用户 `AGENTS.md` |
| `GET /memory/profile` | 只读查看当前用户 `USER_PROFILE.md` |
| `GET /memory/settings` | 读取当前用户长期记忆开关 |
| `PUT /memory/settings` | 更新当前用户长期记忆开关 |

Agent 不再注册 `memory_find`、`memory_grep`、`memory_read`、`remember_memory` 和 `forget_memory`。长期记忆通过系统上下文固定注入。

## 5. 自动提取

一次 Agent 回答成功完成后，`MemoryExtractionScheduler` 按用户和会话调度空闲后台任务：

1. 先检查用户级 `long_term_memory_enabled`，关闭时直接跳过。
2. 读取尚未处理的新业务消息。
3. 读取当前 `USER_PROFILE.md`。
4. 用结构化模型输出更新后的 `USER_PROFILE.md`。
5. 允许保持不变，禁止为了“有记忆”强行新增内容。
6. 更新处理进度，避免重复扫描全部历史。

自动提取只更新 `USER_PROFILE.md`，不修改用户 `AGENTS.md`，也不提供手动编辑 `USER_PROFILE.md` 的接口。任务失败记录日志但不影响已完成的对话响应；应用退出时等待或关闭调度任务。

## 6. 安全与隐私

- 用户 ID 只能来自认证上下文。
- Profile 长度有限制，且拒绝明显凭证。
- 日志只记录用户 ID、会话 ID 和数量，不输出完整私人记忆。
- 长期记忆进入 Prompt 前被标记为用户上下文，不能覆盖系统规则和工具权限。
- 自动提取应避免保存密码、Token、API Key 和无长期价值的临时信息。

## 7. 代码入口

| 模块 | 职责 |
|---|---|
| `services/context_token_counter.py` | 上下文 token 估算 |
| `services/conversation_compaction_service.py` | 摘要与消息裁剪 |
| `services/memory_service.py` | AGENTS 与 USER_PROFILE 存储 |
| `services/memory_extraction_service.py` | 后台 Profile 更新 |
| `tools/memory_tools.py` | 保留空工具列表，Memory 采用固定注入 |
| `api/v1/memory.py` | 管理 API |
| `views/MemoryManagement.vue` | 用户管理页 |

向量化长期记忆、可审计撤销和更细粒度保留策略属于未来优化，不作为当前能力描述。
