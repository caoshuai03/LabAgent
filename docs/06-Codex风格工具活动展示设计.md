<!--
 @author: caoshuai.cs
 @date: 2026-07-15 02:11
 @description: Codex风格命令执行与文件读取活动展示设计
-->

# Codex 风格命令执行与文件读取展示设计

> 本文档是第四阶段工具链的前端体验优化设计，参考用户提供的 Codex 工具活动截图，并结合 LabAgent 当前实现进行分析。
> 本设计只关注命令执行、目录查看、文件读取和文件搜索的展示，不实现文件 Diff、代码修改统计或复杂的 AI Coding 活动面板。
> 2026-07-15 已完成第一版落地：实现工具活动聚合、两级折叠、Shell命令与输出预览、历史恢复和输出脱敏。

---

## 一、目标与范围

当前 LabAgent 使用以下形式展示工具：

```text
调用 Tool：execute_shell | Shell执行完成，耗时 15ms
```

目标调整为更容易理解的活动展示：

```text
运行了多个命令                                      ˅
  ▣ 已运行  ls -la                                  ˅
  ▣ 已运行  python tmp/quick_sort.py                 ˃
```

展开单条命令后：

```text
Shell

$ ls -la
total 20
drwxr-xr-x 2 root root 4096 input
drwxr-xr-x 2 root root 4096 output
drwxr-xr-x 2 root root 4096 tmp
```

本次设计范围只有：

1. 同一条助手消息中的工具调用显示为一个可折叠活动组。
2. 聚合标题只重点描述“查看文件”和“运行命令”。
3. Shell 明细行直接展示实际命令，不突出内部工具名 `execute_shell`。
4. Shell 明细行可以再次展开，查看完整命令和受控执行输出。
5. 保留运行中、等待审批、成功、失败、超时、拒绝和取消状态。
6. 实时 SSE 与历史消息尽量保持一致。
7. 删除类操作的确认卡片显示在当前助手消息下方，不使用全屏遮罩弹窗。

明确不做：

- 不展示文件 Diff。
- 不展示 `+4 -0`等代码行变化统计。
- 不区分文件是“创建”还是“修改”来生成复杂标题。
- 不实现文件 Diff 抽屉、代码浏览器或类似 IDE 的交互。
- 不为每一种工具建立复杂的展示元数据模型。

---

## 二、参考界面拆解

截图中存在两级展开：

### 2.1 活动组展开

第一行是当前助手回复的工具活动摘要：

```text
运行了多个命令  ˅
```

点击后控制整个工具活动列表的显示和隐藏。

### 2.2 单条命令展开

每条 Shell 活动显示：

```text
▣ 已运行  sed -n '1,240p' .gitignore ...  ˅
```

点击后展开一个纯文本终端区域：

- 标题固定为 `Shell`。
- 内容包含完整命令。
- 命令前使用 `$`标识。
- 命令下面展示 stdout/stderr 的受控预览。
- 内容过长时终端区域内部滚动，不撑高整个聊天页面。

### 2.3 信息层级

界面首先告诉用户“Agent 做了什么”，其次才显示结果：

1. 运行了命令或查看了文件。
2. 具体执行了什么命令、读取了什么路径。
3. 用户需要时再展开查看完整输出。

---

## 三、当前实现与差距

### 3.1 当前已经具备

- `MessageItem.vue`已经能匹配 `tool_call`与 `tool_result`。
- `tool_call.arguments`已经包含 Shell 命令和文件路径。
- SSE 已有运行、成功、失败、超时、拒绝和取消状态。
- 历史消息的 `tool_calls`已经包含工具名、参数、状态、摘要和耗时。
- Shell 工具的 `ToolMessage`结果信封中已经包含完整的受控 `output`。

### 3.2 实施前差距（第一版已补齐）

1. 前端现在显示“调用 Tool”，没有根据工具类型生成用户可理解的活动标题。
2. 工具列表没有整体折叠能力。
3. Shell 行没有直接显示 `arguments.commands`中的命令。
4. Shell 行没有单独展开详情的能力。
5. 后端解析 `ToolMessage`后，只把 `result_summary`发送给前端，丢弃了已有的 `output`。
6. 数据库没有保存受控输出预览，因此刷新页面后无法恢复终端详情。

---

## 四、前端最小改造方案

不需要拆成多个复杂组件。建议只新增一个：

```text
MessageItem.vue
└── ToolActivityPanel.vue
```

### 4.1 `MessageItem.vue`

- 保留消息正文、引用来源和反馈按钮。
- 将当前消息的 `toolEvents`传给 `ToolActivityPanel.vue`。
- 删除现有“调用 Tool：工具名”的展示模板。

### 4.2 `ToolActivityPanel.vue`

一个组件完成以下职责：

- 按 `tool_call_id`匹配调用和结果。
- 按事件到达顺序展示活动。
- 生成活动组标题。
- 管理活动组展开状态。
- 管理每一条 Shell 命令的展开状态。
- 根据状态显示“正在运行、已运行、运行失败、执行超时”等文案。

不需要再拆 `Header`、`Item`、`Details`三个组件；当单个组件明显过大时再拆分。

### 4.3 状态结构

组件内部只需要：

```javascript
const groupExpanded = ref(true)
const expandedToolCallIds = ref(new Set())
```

其中：

- `groupExpanded`控制整个活动列表。
- `expandedToolCallIds`控制具体哪些 Shell 行已经展开。

### 4.4 命令来源

命令直接来自现有事件：

```javascript
event.payload.arguments.commands
```

可能是字符串，也可能是字符串数组。前端只做类型归一化，不解析命令内容：

```javascript
const commands = Array.isArray(value) ? value : [value]
```

折叠行显示完整命令的单行省略效果；展开区域显示原始脱敏命令。

---

## 五、活动标题规则

标题由前端根据结构化工具活动生成，不由模型生成。

只统计以下两类活动：

- Shell：`execute_shell`。
- 文件查看：`list_directory`、`read_file`、`file_search`。

### 5.1 完成状态

| 活动组合 | 标题 |
| :--- | :--- |
| 只有 1 条 Shell 命令 | 运行了命令 |
| 有多条 Shell 命令 | 运行了多个命令 |
| 只有文件查看工具 | 查看了文件 |
| 文件查看 + 1 条 Shell 命令 | 查看了文件，运行了命令 |
| 文件查看 + 多条 Shell 命令 | 查看了文件，运行了多个命令 |
| 只有其他工具 | 执行了工具操作 |

Shell 命令数量按 `commands`数组展开后的实际条数统计，不只按 `execute_shell`调用次数统计。

### 5.2 运行中与审批

| 状态 | 标题 |
| :--- | :--- |
| Shell 等待审批 | 等待确认命令 |
| Shell 正在执行 | 正在运行命令 |
| 文件工具正在执行 | 正在查看文件 |
| 文件查看与 Shell 同时存在 | 正在处理文件和命令 |

### 5.3 异常状态

| 状态 | 标题 |
| :--- | :--- |
| Shell 执行失败 | 命令执行失败 |
| Shell 执行超时 | 命令执行超时 |
| 用户拒绝 Shell | 已拒绝运行命令 |
| 文件查看失败 | 文件查看失败 |
| 有成功也有失败 | 部分工具执行失败 |

文件写入、复制、移动和删除仍可在明细中使用现有摘要展示，但不参与“编辑了文件”一类 AI Coding 标题生成。

---

## 六、活动明细展示

### 6.1 Shell 折叠行

```text
▣ 已运行  ls -la                                      ˃
```

字段来源：

| 展示内容 | 来源 |
| :--- | :--- |
| 图标 | 前端固定终端图标 |
| 状态文案 | `tool_result.success`和 `status` |
| 命令 | `tool_call.arguments.commands` |
| 展开箭头 | 前端本地展开状态 |

命令使用 CSS：

```css
white-space: nowrap;
overflow: hidden;
text-overflow: ellipsis;
```

不能在 JavaScript 中永久截断命令，否则展开后无法显示完整内容。

### 6.2 Shell 展开区域

```text
Shell

$ ls -la
total 20
drwxr-xr-x 2 root root 4096 input
drwxr-xr-x 2 root root 4096 output
drwxr-xr-x 2 root root 4096 tmp
```

展示规则：

- 使用 `<pre>`或等价纯文本区域。
- 不进行 Markdown 渲染。
- 不使用 `v-html`。
- 设置最大高度和内部滚动。
- 失败时在输出末尾显示受控错误信息。
- 成功但没有 stdout 时显示“命令执行成功，无额外输出”。

当前 Tool Runner 的输出已经包含：

```text
$ 命令
stdout/stderr
```

因此第一版可以直接展示后端提供的 `output_preview`，不需要前端再次拼接终端文本。

### 6.3 文件查看行

保持简单展示：

```text
已查看  .
已读取  input/task.md
已搜索  *.py
```

第一版不要求文件查看行继续展开文件正文，避免保存和展示大段敏感文件内容。

### 6.4 其他工具

`write_file`、`copy_file`、`move_file`和 `file_delete`继续显示现有结果摘要，例如：

```text
已写入文件 output/result.txt
已删除文件 tmp/test.txt
```

不显示 Diff，不生成代码行统计。

---

## 七、后端最小改造方案

### 7.1 当前问题

工具结果信封已经包含：

```json
{
  "success": true,
  "output": "$ ls -la\ntotal 20 ...",
  "summary": "Shell执行完成，耗时 15ms",
  "duration_ms": 15
}
```

但 `AiService`处理 `ToolMessage`时只发送：

```json
{
  "result_summary": "Shell执行完成，耗时 15ms",
  "duration_ms": 15
}
```

已有的 `output`在 SSE 转换时被丢弃，所以前端无法展开终端结果。

### 7.2 SSE 实现

在 `tool_result`中增加一个可选字段：

```json
{
  "event_type": "tool_result",
  "tool_call_id": "call-id",
  "tool_name": "execute_shell",
  "success": true,
  "result_summary": "Shell执行完成，耗时 15ms",
  "output_preview": "$ ls -la\ntotal 20 ...",
  "duration_ms": 15
}
```

后端直接从现有结果信封读取：

```python
output_preview = truncate_text(str(redact_value(result.get("output") or "")))
```

只对需要展开的工具发送输出预览。第一版建议：

- `execute_shell`发送 `output_preview`。
- 其他工具暂不发送正文预览。

这样不需要 `display_metadata`或其他复杂 JSON 结构。

### 7.3 历史恢复实现

在 `chat_tool_call`增加一个简单字段：

```text
output_preview TEXT NULL
```

同步修改：

- Alembic 数据库迁移。
- `ChatToolCall` ORM。
- `ToolCallService.update_status()`。
- `ChatToolCallVO`。
- 历史消息前端转换。

只保存脱敏、截断后的预览，不保存无限长度的完整 Shell 输出。

第一版已采用该方案，实时和历史展示保持一致，同时没有增加通用展示元数据模型。

### 7.4 脱敏要求

Shell 输出可能包含 `.env`、Token、密码或连接串。输出进入 SSE 或数据库前必须：

1. 复用并加强现有 `redact_value()`。
2. 覆盖 `TOKEN=...`、`PASSWORD=...`、`SECRET=...`、`API_KEY=...`等常见格式。
3. 继续执行最大长度截断。
4. 日志中不打印完整输出。

命令参数也必须使用后端已经脱敏后的 `arguments`，前端不能从其他日志来源补全敏感值。

---

## 八、实时与历史数据处理

### 8.1 实时 SSE

```text
tool_call
→ 前端创建命令行，状态为等待执行
→ status(tool_running)
→ 更新为正在运行
→ tool_result
→ 更新为已运行，并保存 output_preview
```

### 8.2 历史消息

历史接口继续返回 `tool_calls`。采用推荐方案 B 后，每条记录增加：

```json
{
  "tool_name": "execute_shell",
  "arguments": {"commands": "ls -la"},
  "status": "success",
  "result_summary": "Shell执行完成，耗时 15ms",
  "output_preview": "$ ls -la\ntotal 20 ..."
}
```

前端继续把历史记录转换成现有 `tool_call + tool_result`事件，即可复用同一个活动面板。

### 8.3 审批恢复

审批前后的事件继续追加到同一条助手消息，所以第一版不需要增加新的活动组 ID。现有 `tool_call_id`足以匹配命令、状态和结果。

---

## 九、展开规则

### 9.1 活动组

- 工具正在运行：默认展开。
- 等待审批：默认展开。
- 失败、超时或拒绝：默认展开。
- 全部完成：保持用户当前选择，不自动跳动。
- 历史消息：默认展开，用户可手动折叠。

### 9.2 Shell 单项

- 默认折叠，只显示命令摘要。
- 用户点击命令行或箭头后展开。
- 正在运行时可以展开查看已有输出；第一版若后端未流式发送工具输出，则在完成后一次性展示。
- 执行失败时建议自动展开，直接显示错误。

---

## 十、第一版实施内容

1. 前端新增 `ToolActivityPanel.vue`，复用现有 `toolEvents`。
2. 根据 `execute_shell/read_file/list_directory/file_search`生成简单标题。
3. Shell 行显示 `arguments.commands`并增加单项展开状态。
4. 后端 `tool_result`增加 `output_preview`。
5. 前端展开区域展示 `output_preview`。
6. 增加 `chat_tool_call.output_preview`，完成历史恢复。
7. 加强 Shell 输出脱敏。
8. 补充前后端测试和真实浏览器验收。

---

## 十一、测试设计

### 11.1 前端测试

- 单条命令标题为“运行了命令”。
- 多条命令标题为“运行了多个命令”。
- 文件查看标题为“查看了文件”。
- 文件查看和 Shell 能生成组合标题。
- 点击活动组箭头能折叠和展开列表。
- 点击 Shell 行能展开完整命令和输出。
- 长命令折叠时省略、展开时保持完整。
- 失败、超时、拒绝和取消状态显示正确。
- 输出中的 HTML 只作为纯文本展示。

### 11.2 后端测试

- `tool_result`可以返回截断后的 `output_preview`。
- 非 Shell 工具默认不返回大段正文预览。
- Shell 输出中的 Token、密码和密钥被脱敏。
- 历史接口可以恢复 `output_preview`。
- 空输出和执行失败不会被错误描述为目录为空。

---

## 十二、验收标准

1. 页面不再以“调用 Tool：execute_shell”作为主要文案。
2. 单条助手消息中的命令和文件查看活动显示在同一个可折叠区域。
3. Shell 行直接显示实际执行命令。
4. Shell 行可以再次展开，显示完整命令和受控输出。
5. 多条命令显示“运行了多个命令”。
6. 文件读取、目录列表和搜索统一使用“查看了文件”相关标题。
7. 不展示文件 Diff、代码行增删统计或复杂 AI Coding 信息。
8. 命令和输出经过脱敏、截断，并使用纯文本渲染。
9. 采用推荐历史方案后，刷新页面仍可展开查看执行输出预览。

---

## 十三、结论

本次改造不需要构建复杂的通用活动系统。前端增加一个简单的 `ToolActivityPanel.vue`即可完成聚合标题、两级折叠和命令展示；后端只需把当前已经存在于 `ToolMessage`中的 `output`作为受控 `output_preview`透传，并可选持久化到 `chat_tool_call`。

标题只关注 LabAgent 当前最重要的两类行为：查看文件和运行命令。文件写入、复制、移动和删除保留现有摘要即可，不引入 Diff 或 AI Coding 专用展示逻辑。
