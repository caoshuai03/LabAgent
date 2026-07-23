"""
@author: caoshuai.cs
@date: 2026-07-23 04:09
@description: RAG 评测脚本的评测集解析、报告生成与双检索分支编排测试
"""
import pytest

from app.eval import rag_eval
from app.eval.rag_eval import (
    RagEvalRunner,
    build_markdown_report,
    load_eval_cases,
    load_evaluation_report,
    recompute_recall_metrics,
    write_evaluation_report_json,
)


def test_load_eval_cases_from_markdown_sample() -> None:
    """应能读取文档里的 Markdown 表格评测集。"""
    cases = load_eval_cases("../docs/rag_eval/RAG评测集样例.md")

    assert len(cases) == 10
    assert cases[0].case_id == "rag_eval_001"
    assert cases[0].user_input == "实验三什么时候提交？"


@pytest.mark.asyncio
async def test_runner_keeps_baseline_and_current_separate(monkeypatch) -> None:
    """baseline 与 current 应走不同检索分支，但共用同一批问题。"""
    calls: list[tuple[str, str, int, str, int]] = []

    async def _fake_run_forced_retrieval_answer(
        question: str, *, model_name: str, user_id: int, retrieval_mode: str, top_k: int
    ) -> tuple[str, list[str], str]:
        calls.append((question, model_name, user_id, retrieval_mode, top_k))
        if retrieval_mode == "vector_only":
            return "baseline answer", ["来源: baseline.md\n黄金证据"], "baseline.md"
        return "current answer", ["来源: current.md\n黄金证据"], "current.md"

    async def _fake_judge(*args, **kwargs) -> bool:
        return True

    monkeypatch.setattr(rag_eval, "_run_forced_retrieval_answer", _fake_run_forced_retrieval_answer)
    monkeypatch.setattr(rag_eval, "_judge_recall_at_k", _fake_judge)

    runner = RagEvalRunner(
        case_path="../docs/rag_eval/RAG评测集样例.md",
        top_k=5,
        answer_model_name="gpt-5.5-2026-04-24",
        judge_model_name="gpt-5.5-2026-04-24",
        user_id=42,
        skip_ragas=True,
    )
    report = await runner.run()

    assert report.case_count == 10
    assert report.baseline.recall_at_5 == 1.0
    assert report.current.recall_at_5 == 1.0
    assert report.baseline.case_results[0].first_source == "baseline.md"
    assert report.current.case_results[0].first_source == "current.md"
    assert (
        "实验三什么时候提交？",
        "gpt-5.5-2026-04-24",
        42,
        "vector_only",
        5,
    ) in calls
    assert (
        "实验三什么时候提交？",
        "gpt-5.5-2026-04-24",
        42,
        "current",
        5,
    ) in calls


def test_build_markdown_report_contains_required_metrics() -> None:
    """报告应包含本次要求输出的全部指标名。"""
    case_result = rag_eval.MethodCaseResult(
        case_id="case_001",
        user_input="问题",
        reference="标准答案",
        reference_context="黄金证据",
        retrieved_contexts=["黄金证据"],
        response="回答",
        recall_at_5=1.0,
        retrieval_hit=True,
        first_source="sample.md",
    )
    summary = rag_eval.MethodSummary(
        method_name="baseline",
        case_results=[case_result],
        recall_at_5=1.0,
        ragas_metrics={
            "context_precision": 0.8,
            "context_recall": 0.9,
            "faithfulness": 0.7,
            "response_relevancy": 0.6,
            "answer_correctness": 0.5,
        },
    )
    report = rag_eval.EvaluationReport(
        case_count=1,
        generated_at="2026-07-23 04:09",
        baseline=summary,
        current=summary,
    )

    markdown = build_markdown_report(report)

    assert "Recall@5" in markdown
    assert "ContextPrecision" in markdown
    assert "ContextRecall" in markdown
    assert "Faithfulness" in markdown
    assert "ResponseRelevancy" in markdown
    assert "AnswerCorrectness" in markdown


def test_evaluation_report_json_roundtrip(tmp_path) -> None:
    """第一阶段回答结果应能保存为 JSON，并在第二阶段恢复。"""
    case_result = rag_eval.MethodCaseResult(
        case_id="case_001",
        user_input="问题",
        reference="标准答案",
        reference_context="黄金证据",
        retrieved_contexts=["黄金证据"],
        response="回答",
        recall_at_5=1.0,
        retrieval_hit=True,
        first_source="sample.md",
    )
    summary = rag_eval.MethodSummary(
        method_name="baseline",
        case_results=[case_result],
        recall_at_5=1.0,
    )
    report = rag_eval.EvaluationReport(
        case_count=1,
        generated_at="2026-07-24 01:00",
        baseline=summary,
        current=summary,
    )

    output_path = write_evaluation_report_json(report, tmp_path / "answers.json")
    loaded = load_evaluation_report(output_path)

    assert loaded.case_count == 1
    assert loaded.baseline.case_results[0].response == "回答"
    assert loaded.current.case_results[0].retrieved_contexts == ["黄金证据"]


@pytest.mark.asyncio
async def test_recompute_recall_metrics_updates_saved_values(monkeypatch) -> None:
    """第二阶段应能用新的 judge 模型重算 Recall@5。"""
    case_result = rag_eval.MethodCaseResult(
        case_id="case_001",
        user_input="问题",
        reference="标准答案",
        reference_context="黄金证据",
        retrieved_contexts=["不相关内容"],
        response="回答",
        recall_at_5=1.0,
        retrieval_hit=True,
        first_source="sample.md",
    )
    summary = rag_eval.MethodSummary(
        method_name="baseline",
        case_results=[case_result],
        recall_at_5=1.0,
    )
    report = rag_eval.EvaluationReport(
        case_count=1,
        generated_at="2026-07-24 01:00",
        baseline=summary,
        current=summary,
    )

    async def _fake_judge(*args, **kwargs) -> bool:
        return False

    monkeypatch.setattr(rag_eval, "_judge_recall_at_k", _fake_judge)

    await recompute_recall_metrics(report, "gpt-5.5-2026-04-24")

    assert report.baseline.recall_at_5 == 0.0
    assert report.baseline.case_results[0].retrieval_hit is False
