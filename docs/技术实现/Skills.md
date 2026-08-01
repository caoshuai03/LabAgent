<!--
 @author: caoshuai.cs
 @date: 2026-07-31
 @description: LabAgent Markdown Skills 规范与运行时实现参考
-->

# Skills

## 1. 定位

Skill 是一组可复用、可审查的任务说明，适合沉淀实验步骤、调试方法、报告规范和课程特定流程。它不等同于：

- Tool：Tool 执行确定性操作，Skill 指导 Agent 如何完成一类任务。
- RAG：RAG 检索事实资料，Skill 提供方法和流程。
- Memory：Memory 保存特定用户的长期信息，Skill 是应用级共享能力。

## 2. 目录规范

应用内置 Skills 默认位于 `backend/skills/`：

```text
skill-name/
├── SKILL.md
├── references/    # 可按需读取的文本参考
├── scripts/       # 受控脚本资源
└── assets/        # 资源文件
```

`SKILL.md` 使用 YAML frontmatter：

```markdown
---
name: java-debug-helper
description: 分析 Java 编译和运行错误，给出可验证的排查步骤
---

# Java 调试助手

……
```

名称、描述、正文和目录通过 `skills-ref` 与项目规则校验。实际样例见 `backend/skills/java-debug-helper/` 和 `backend/skills/lab-report-writer/`。

## 3. 三级渐进披露

1. 目录：系统提示只注入 Skill 名称和简介。
2. 正文：模型调用 `activate_skill`，或用户通过输入框斜杠菜单主动选择后，完整正文进入本次运行状态。
3. 资源：只有正文需要时才调用 `read_skill_resource` 读取具体参考。

激活状态保存在 LangGraph state 中，同一运行内后续工具轮次继续可见。系统通过激活数量和总字符数限制上下文膨胀。

主动选择时，前端只读取 Skill 名称和简介，并通过对话请求的 `skill_names` 字段提交名称；后端在首次模型调用前使用同一 Skill 目录完成白名单校验与正文注入，正文不会下发到聊天页面。

## 4. 代码入口

| 模块 | 职责 |
|---|---|
| `services/skill_service.py` | 扫描、校验、缓存、目录提示、激活和资源读取 |
| `tools/skill_tools.py` | `activate_skill`、`read_skill_resource` |
| `api/v1/skills.py` | 列表、详情和管理员刷新 |
| `graph/chat_graph.py` | 注入目录/正文、保存激活状态、发送 SSE |
| `schemas/skill.py` | API 数据模型 |

应用启动时扫描目录；失败的 Skill 被跳过并记录诊断，不阻断整个服务。管理员刷新使用线程隔离同步文件扫描。

## 5. 安全边界

- Skill 正文属于管理员维护内容，但不能覆盖系统安全规则、身份权限和 ToolPolicy。
- 禁止符号链接 `SKILL.md` 和资源目录穿越。
- 资源路径必须位于允许目录，拒绝绝对路径和 `..`。
- 限制 Skill 文件大小、资源大小、资源深度、总数量、单次激活数和激活字符数。
- 资源按 UTF-8 文本读取；脚本不会因为出现在 Skill 中就自动获得执行权。
- API 刷新仅管理员可用，普通用户只读取已通过校验的内容。

## 6. 新增 Skill 检查清单

1. 使用稳定的短横线名称，并让目录名与 `name` 一致。
2. `description` 明确写出触发场景，不使用宽泛描述。
3. 正文描述目标、步骤、输入输出和失败处理，不复制大段通用知识。
4. 大型参考材料放入 `references/`，正文只写何时读取。
5. 需要工具时明确工具边界，但不要假设未注册工具存在。
6. 刷新目录并检查诊断信息。
7. 测试匹配任务、无关任务、资源越界和上下文上限。

## 7. 当前边界

当前实现是应用内置、只读加载的 Markdown Skills。多租户分发、在线创建/编辑、签名发布和版本市场尚未实现，相关方向见[优化路线](../未来优化/优化路线.md)。
