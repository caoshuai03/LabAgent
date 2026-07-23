<!--
 @author: caoshuai.cs
 @date: 2026-07-24 01:44
 @description: LabAgent RAG 评测报告
-->

# RAG 评测报告

本次共评测 5 条问题。

## 1. 总体结果

| 方法 | Recall@5 | ContextPrecision | ContextRecall | Faithfulness | ResponseRelevancy | AnswerCorrectness |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 100.0% | 100.0% | 100.0% | 100.0% | 64.3% | 70.4% |
| current | 100.0% | 100.0% | 100.0% | 83.3% | 64.3% | 77.9% |

## 2. RAGAS 状态

- 纯向量检索 baseline: 已完成
- 当前检索链路: 已完成

## 3. 逐题对比

| id | 问题 | baseline Recall@5 | current Recall@5 | baseline 来源 | current 来源 |
| --- | --- | --- | --- | --- | --- |
| rag_eval_001 | 实验三什么时候提交？ | 100.0% | 100.0% | 实验课程知识库样例.md | 实验课程知识库样例.md |
| rag_eval_002 | 实验三报告必须写哪些内容？ | 100.0% | 100.0% | 实验课程知识库样例.md | 实验课程知识库样例.md |
| rag_eval_003 | 我只交代码不交报告可以吗？ | 100.0% | 100.0% | 实验课程知识库样例.md | 实验课程知识库样例.md |
| rag_eval_004 | 平台上保存草稿算正式提交吗？ | 100.0% | 100.0% | 实验课程知识库样例.md | 实验课程知识库样例.md |
| rag_eval_005 | 老师为什么看不到我的实验提交记录？ | 100.0% | 100.0% | 实验课程知识库样例.md | 实验课程知识库样例.md |

## 4. 失败/差异样例

本次没有明显失败样例。
