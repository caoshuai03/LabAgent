<!--
 @author: caoshuai.cs
 @date: 2026-07-24 01:10
 @description: LabAgent RAG 评测流程沉淀——纯向量 baseline 与当前混合检索链路对比
-->

# 11 - RAG 评测流程

## 1. 当前结论先说明

当前评测链路已经跑通：知识库样例上传后，脚本可以基于同一批问题分别跑 `baseline` 和 `current`，保存每个 case 的问题、标准答案、黄金证据、召回上下文和模型回答，并生成 Markdown 报告。

后续日常测试建议统一使用 Ollama 模型，先重点观察召回链路和回答行为，避免 GPT-5.5 网关、限流、temperature 兼容和环境切换影响调试效率。当前脚本已通过 LiteLLM + Instructor 的 JSON mode 适配 Ollama 作为 RAGAS judge。

当前样例知识库和评测集都很简单，10 条 case 基本都能命中黄金证据，所以 `Recall@5` 区分度不强。本次更有参考价值的是：`current` 的 `ContextPrecision` 高于 `baseline`，说明 MultiQuery + 向量/BM25 混合召回 + rerank 对减少召回噪声有帮助。

最近一次报告：[gpt55_ragas_report.md](./rag_eval/reports/gpt55_ragas_report.md)

| 方法 | Recall@5 | ContextPrecision | ContextRecall | Faithfulness |
| --- | ---: | ---: | ---: | ---: |
| baseline | 100.0% | 92.5% | 100.0% | 84.9% |
| current | 100.0% | 97.5% | 100.0% | 79.2% |

解释：

1. `Recall@5` 都是 100%，主要因为当前样例太简单，不能证明 current 召回覆盖能力显著更强。
2. `ContextPrecision` 从 92.5% 提升到 97.5%，说明 current 召回上下文更干净，噪声更少。
3. `Faithfulness` current 低一些，说明 current 的回答更可能出现未被召回上下文充分支撑的展开，需要后续通过更强约束 prompt 或更细粒度样例继续观察。

## 2. 对比对象

评测只对比两组，保证口径清晰：

| 方法 | 含义 |
| --- | --- |
| `baseline` | 纯向量检索，只用 pgvector 相似度召回，不做 MultiQuery、BM25、RRF、rerank |
| `current` | 当前链路：MultiQuery + 向量/BM25 混合召回 + RRF + rerank |

脚本默认使用评测专用强制检索模式，不依赖 Agent 自主决定是否调用知识库工具。这样可以避免“模型没选工具”干扰检索链路评测。

## 3. 评测集字段

人工维护的评测集字段保持 4 个：

| 字段 | 含义 |
| --- | --- |
| `id` | 用例编号 |
| `user_input` | 用户问题 |
| `reference` | 标准答案，用于答案质量判断 |
| `reference_context` | 黄金证据片段，用于判断召回是否命中 |

脚本运行后会生成这些中间结果：

| 字段 | 含义 |
| --- | --- |
| `retrieved_contexts` | 实际召回到的上下文列表 |
| `response` | 模型基于召回上下文生成的回答 |
| `recall_at_5` | top 5 召回是否命中黄金证据，命中为 1.0，未命中为 0.0 |
| `retrieval_hit` | `recall_at_5` 的布尔形式 |

## 4. 指标含义

| 指标 | 含义 | 越高越好 |
| --- | --- | --- |
| `Recall@5` | top 5 召回里是否覆盖黄金证据 | 是 |
| `ContextPrecision` | 召回上下文是否更相关、更少噪声 | 是 |
| `ContextRecall` | 标准答案需要的信息是否被召回覆盖 | 是 |
| `Faithfulness` | 回答是否被召回上下文支撑，是否少幻觉 | 是 |
| `ResponseRelevancy` | 回答是否围绕用户问题 | 是 |
| `AnswerCorrectness` | 回答是否接近标准答案 | 是 |

`--ragas-llm-only` 只跑 `ContextPrecision`、`ContextRecall`、`Faithfulness`。如果 Ollama embedding 环境也稳定，可以去掉该参数，继续跑 `ResponseRelevancy` 和 `AnswerCorrectness`。

## 5. Ollama 日常测试命令

进入后端目录：

```bash
cd /Users/bytedance/learnAgent/LabAgent/backend
```

第一步：跑 baseline/current 的召回、回答和 Recall@5，保存中间结果：

```bash
uv run python scripts/rag_eval.py \
  --cases ../docs/rag_eval/RAG评测集样例.md \
  --top-k 5 \
  --user-id 1 \
  --answer-model qwen3:8b \
  --judge-model qwen3:8b \
  --skip-ragas \
  --answers-output ../docs/rag_eval/reports/ollama_answers.json \
  --output ../docs/rag_eval/reports/ollama_answers_preview.md
```

第二步：基于中间结果，用 Ollama 作为 RAGAS judge 跑三项不依赖 embedding 的指标：

```bash
uv run python scripts/rag_eval.py \
  --answers-input ../docs/rag_eval/reports/ollama_answers.json \
  --judge-model qwen3:8b \
  --ragas-llm-only \
  --output ../docs/rag_eval/reports/ollama_ragas_report.md
```

如果 Ollama embedding 也可用，并希望跑完整 RAGAS 指标，可以去掉 `--ragas-llm-only`：

```bash
uv run python scripts/rag_eval.py \
  --answers-input ../docs/rag_eval/reports/ollama_answers.json \
  --judge-model qwen3:8b \
  --output ../docs/rag_eval/reports/ollama_full_ragas_report.md
```

如果只是验证环境是否跑通，可以先用前 5 条样例，RAGAS batch size 调到 5：

```bash
uv run python scripts/rag_eval.py \
  --answers-input ../docs/rag_eval/reports/ollama_answers.json \
  --judge-model qwen3:8b \
  --limit-cases 5 \
  --ragas-batch-size 5 \
  --output ../docs/rag_eval/reports/ollama_ragas_5cases_report.md
```

如果只想基于已有中间结果重新生成预览报告，不补跑 RAGAS：

```bash
uv run python scripts/rag_eval.py \
  --answers-input ../docs/rag_eval/reports/ollama_answers.json \
  --judge-model qwen3:8b \
  --skip-ragas \
  --output ../docs/rag_eval/reports/ollama_answers_preview.md
```

说明：Ollama RAGAS judge 走 `litellm` dev 依赖，模型名内部按 LiteLLM 约定转换为 `ollama/{judge_model}`。结构化输出使用 `instructor.Mode.JSON`，避免 Ollama 不返回 tool_call 导致 RAGAS 指标为空。`OLLAMA_EMBEDDING_TIMEOUT` 控制 embedding 请求超时，`OLLAMA_JUDGE_TIMEOUT` 控制 RAGAS judge 请求超时；batch size 调大后建议把 judge timeout 保持在 120 秒左右。

## 6. GPT-5.5 补跑 RAGAS 命令

如果需要生成 RAGAS 指标报告，并且当前环境可访问 GPT-5.5：

```bash
uv run python scripts/rag_eval.py \
  --answers-input ../docs/rag_eval/reports/ollama_answers.json \
  --judge-model gpt-5.5-2026-04-24 \
  --ragas-llm-only \
  --output ../docs/rag_eval/reports/gpt55_ragas_report.md
```

执行细节：

1. 第二阶段会读取第一阶段保存的 `retrieved_contexts` 和 `response`，不会重新跑检索。
2. 默认会用 `--judge-model` 重新计算 `Recall@5` / `retrieval_hit`。
3. `--ragas-llm-only` 不依赖 embedding，只输出 `ContextPrecision`、`ContextRecall`、`Faithfulness`。
4. 当前 GPT-5.5 网关只接受默认温度，脚本已适配 `temperature=1`、`top_p=1`、`max_tokens=4096`。
5. RAGAS 默认按 `batch_size=1` 串行执行；需要加速时可以通过 `--ragas-batch-size` 调大，先用 `--limit-cases 5 --ragas-batch-size 5` 冒烟验证。

## 7. 后续要改进的评测集

当前样例太简单，不适合支撑强结论。后续至少补充这些类型：

1. 近义问题：用户表达与知识库措辞不同，验证 MultiQuery 的收益。
2. 干扰文档：多个相似实验、相似截止时间，验证 rerank 和 ContextPrecision。
3. 多跳问题：答案分散在多个片段，验证 ContextRecall。
4. 负例问题：知识库没有答案，验证模型是否拒绝编造。
5. 长文档问题：验证 chunk 切分和 top_k 对召回的影响。

等评测集复杂度上来后，再讨论 `Recall@5` 提升多少个百分点会更可信。当前只能说链路已跑通，且在样例集上 current 的上下文精确度更高。

## 8. 参考资料

- [Ragas 首页](https://docs.ragas.io/en/stable/)
- [Evaluation Dataset](https://docs.ragas.io/en/stable/concepts/components/eval_dataset/)
- [Evaluation Sample](https://docs.ragas.io/en/stable/concepts/components/eval_sample/)
- [Context Precision](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)
- [Context Recall](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/)
- [Faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)
