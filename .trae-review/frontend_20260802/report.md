# 代码评审报告

- 仓库：LabAgent
- 检测模式：前端全量静态审查
- 检测范围：frontend/ full_file
- 生成时间：2026-08-02 17:13
- 检查文件：77
- 变更行数：16518

## 评审结论

共发现 5 个缺陷，其中3 个 P1 建议本次迭代修复，2 个 P2 建议排期修复。

## 缺陷统计

- P0（阻断，必须优先处理）：0
- P1（严重，建议本次迭代修复）：3
- P2（一般，建议排期修复）：2
- 合计：5

## 缺陷详情

### 1. [P1][安全漏洞] 公共 Markdown 渲染器允许原始 HTML，形成脚本注入入口

- 位置：`frontend/src/utils/markdown.js:6-8`
- 置信度：10/10

**问题描述**

renderMarkdown 的结果被 MessageItem、SkillsManagement 和 WorkspacePreviewPanel 直接交给 v-html。模型输出、Skill 文档和工作区 Markdown 均可能包含不可信内容，攻击者可注入带事件处理器的原始 HTML，并在当前页面上下文执行脚本；JWT 又保存在 localStorage，风险可进一步扩大为凭证泄露。

**修复建议**

默认设置 html: false；如果确需支持少量 HTML，统一接入白名单净化器，并限制 URL 协议、为外链补充 rel="noopener noreferrer"。增加 img onerror、svg、javascript: 等恶意载荷测试。

---

### 2. [P1][并发问题] 知识库搜索的旧请求可覆盖最新结果

- 位置：`frontend/src/views/KnowledgeManagement.vue:402-413`
- 置信度：9/10

**问题描述**

防抖只限制请求发起频率，没有处理已发出的并发请求。用户先搜索 A 再快速搜索 B 时，若 A 的响应更晚返回，第 413 行会用 A 的结果覆盖 B，界面关键词与列表不一致。

**修复建议**

为搜索请求维护 AbortController 或递增 request_id；仅允许最后一次请求更新 fileList 和 loading，并在组件卸载时取消请求。

---

### 3. [P1][并发问题] 快速切换 Skill 时旧详情响应会写入当前弹窗

- 位置：`frontend/src/views/SkillsManagement.vue:117-129`
- 置信度：9/10

**问题描述**

showSkillDetail 每次点击都共享 currentSkill、skillDetail 和 detailLoading。先点 A 后点 B，若 A 请求最后完成，会在标题仍为 B 时写入 A 的详情，并可能提前关闭 B 的加载态。

**修复建议**

切换 Skill 时取消前一个请求，或捕获本次 skill.name/request_id，响应落地前确认仍是当前 Skill；loading 也应只由最后一次请求复位。

---

### 4. [P2][性能问题] final 事件与流关闭会重复执行会话收尾请求

- 位置：`frontend/src/components/ChatInput.vue:889-895`
- 置信度：9/10

**问题描述**

收到 final 事件时会调用 finalizeStreamTask，而 SSE 随后正常结束又触发 onComplete，再次调用同一函数。函数即使取不到 streamTask 仍会执行 loadConversationsFromDB，导致每轮正常对话重复刷新会话列表，并存在后返回的旧列表覆盖新状态的窗口。

**修复建议**

让 finalizeStreamTask 幂等化并在任务已删除时直接返回，或仅在 onComplete 中收尾；final 事件只记录最终状态和启动标题轮询。

---

### 5. [P2][性能问题] 删除或重置会话时未释放历史图片 Blob URL

- 位置：`frontend/src/stores/chat.js:403-406`
- 置信度：9/10

**问题描述**

历史图片在第 800 行通过 URL.createObjectURL 创建，但 removeConversationState 和 reset 直接丢弃状态，没有释放 URL。用户持续浏览并删除含图片的会话时，Blob 会一直被页面持有，造成可复现的内存增长。

**修复建议**

在删除 conversation state、强制刷新历史和 reset 前统一遍历消息及预览标签，对 blob: URL 调用 URL.revokeObjectURL；将该逻辑抽为 releaseConversationResources。

---
