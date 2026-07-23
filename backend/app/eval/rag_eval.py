"""
@author: caoshuai.cs
@date: 2026-07-23 04:09
@description: RAG 评测执行器——纯向量 baseline vs 当前检索链路，支持 GPT-5.5 生成与 RAGAS 指标输出
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from openai import AsyncAzureOpenAI, AsyncOpenAI

from app.core.config import settings
from app.graph.checkpointer import close_checkpointer, init_checkpointer
from app.services import rag_retrieval, rag_store
from app.services.model_provider import model_provider

logger = logging.getLogger("labagent")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CASE_PATH = _PROJECT_ROOT / "docs/rag_eval/RAG评测集样例.md"
_DEFAULT_REPORT_DIR = _PROJECT_ROOT / "docs/rag_eval/reports"
_DEFAULT_TOP_K = 5
_DEFAULT_EVAL_USER_ID = 1
_ANSWER_MODEL_NAME = settings.azure_chat_model
_JUDGE_MODEL_NAME = settings.azure_chat_model
_AZURE_MODEL_NAMES = {settings.azure_chat_model, "gpt-5.5-2026-04-24"}
_OPENAI_MODEL_NAMES = {
    settings.openai_chat_model,
    "ernie-4.5-turbo-128k-preview",
    "deepseek-v3",
    "deepseek-r1",
    "qwen3-235b-a22b",
    "llama-2-70b",
}
_RECALL_JUDGE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是检索评测裁判。只判断召回片段里是否已经包含能支撑黄金证据的内容。"
            "如果包含，回答 yes；如果不包含，回答 no。只输出 yes 或 no。",
        ),
        (
            "human",
            "问题：{question}\n\n黄金证据：\n{reference_context}\n\n召回片段：\n{retrieved_contexts}",
        ),
    ]
)
_FORCED_RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是 LabAgent 实验教学助手。请严格基于给定参考资料回答用户问题；"
            "如果参考资料不足以回答，请明确说明资料不足，不要编造。",
        ),
        (
            "human",
            "问题：{question}\n\n参考资料：\n{retrieved_contexts}",
        ),
    ]
)


@dataclass(slots=True)
class EvalCase:
    """黄金评测样本。"""

    case_id: str
    user_input: str
    reference: str
    reference_context: str


@dataclass(slots=True)
class MethodCaseResult:
    """单条样本在某种检索方法下的执行结果。"""

    case_id: str
    user_input: str
    reference: str
    reference_context: str
    retrieved_contexts: list[str]
    response: str
    recall_at_5: float
    retrieval_hit: bool
    first_source: str = ""


@dataclass(slots=True)
class MethodSummary:
    """某种检索方法的整体结果。"""

    method_name: str
    case_results: list[MethodCaseResult] = field(default_factory=list)
    recall_at_5: float = 0.0
    ragas_metrics: dict[str, float] | None = None
    ragas_error: str | None = None


@dataclass(slots=True)
class EvaluationReport:
    """整份评测报告。"""

    case_count: int
    generated_at: str
    baseline: MethodSummary
    current: MethodSummary


def _resolve_input_path(path_value: str | Path) -> Path:
    """解析输入路径，允许相对当前工作目录。"""
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    candidate = Path.cwd() / path
    if candidate.exists():
        return candidate
    project_candidate = _PROJECT_ROOT / path
    if project_candidate.exists():
        return project_candidate
    return path


def _split_markdown_row(row: str) -> list[str]:
    """按 Markdown 表格行拆分列。"""
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _load_cases_from_markdown(path: Path) -> list[EvalCase]:
    """从 Markdown 表格读取评测集。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith("|") and "user_input" in stripped and "reference_context" in stripped:
            header_index = index
            break
    if header_index is None:
        raise ValueError(f"未找到评测集表头: {path}")
    header = _split_markdown_row(lines[header_index])
    cases: list[EvalCase] = []
    for line in lines[header_index + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if cases:
                break
            continue
        if set(stripped) <= {"|", "-", " "}:
            continue
        cells = _split_markdown_row(line)
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells, strict=False))
        case_id = row.get("id", "").strip()
        user_input = row.get("user_input", "").strip()
        reference = row.get("reference", "").strip()
        reference_context = row.get("reference_context", "").strip()
        if not (case_id and user_input and reference and reference_context):
            continue
        cases.append(
            EvalCase(
                case_id=case_id,
                user_input=user_input,
                reference=reference,
                reference_context=reference_context,
            )
        )
    if not cases:
        raise ValueError(f"评测集为空: {path}")
    return cases


def _load_cases_from_jsonl(path: Path) -> list[EvalCase]:
    """从 JSONL 读取评测集。"""
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cases.append(
            EvalCase(
                case_id=str(item["id"]).strip(),
                user_input=str(item["user_input"]).strip(),
                reference=str(item["reference"]).strip(),
                reference_context=str(item["reference_context"]).strip(),
            )
        )
    if not cases:
        raise ValueError(f"评测集为空: {path}")
    return cases


def _load_cases_from_csv(path: Path) -> list[EvalCase]:
    """从 CSV 读取评测集。"""
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            cases.append(
                EvalCase(
                    case_id=str(row["id"]).strip(),
                    user_input=str(row["user_input"]).strip(),
                    reference=str(row["reference"]).strip(),
                    reference_context=str(row["reference_context"]).strip(),
                )
            )
    if not cases:
        raise ValueError(f"评测集为空: {path}")
    return cases


def load_eval_cases(path_value: str | Path = _DEFAULT_CASE_PATH) -> list[EvalCase]:
    """读取评测集，默认兼容 Markdown / JSONL / CSV。"""
    path = _resolve_input_path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"评测集文件不存在: {path}")
    suffix = path.suffix.lower()
    if suffix == ".md":
        return _load_cases_from_markdown(path)
    if suffix == ".jsonl":
        return _load_cases_from_jsonl(path)
    if suffix == ".csv":
        return _load_cases_from_csv(path)
    raise ValueError(f"不支持的评测集格式: {path.suffix}")


def _normalize_text(text: str) -> str:
    """用于弱匹配的文本归一化。"""
    return re.sub(r"\s+", "", re.sub(r"[^\w\u4e00-\u9fff]+", "", text)).lower()


def _extract_text(message: Any) -> str:
    """从模型返回值中提取文本。"""
    if isinstance(message, str):
        return message
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        if parts:
            return "".join(parts)
    return str(content)


def _mean_or_zero(values: list[float]) -> float:
    """安全求均值。"""
    return mean(values) if values else 0.0


def _format_score(score: float | None) -> str:
    """格式化为百分比字符串。"""
    if score is None or not math.isfinite(score):
        return "—"
    return f"{score * 100:.1f}%"


async def _invoke_chain(prompt: ChatPromptTemplate, model: Any, payload: dict[str, Any]) -> str:
    """异步调用 LangChain 链路并提取文本。"""
    result = await (prompt | model).ainvoke(payload)
    return _extract_text(result).strip()


async def _judge_recall_at_k(question: str, reference_context: str, retrieved_contexts: list[str], model_name: str = _JUDGE_MODEL_NAME) -> bool:
    """判断 top_k 召回里是否包含黄金证据。"""
    normalized_reference = _normalize_text(reference_context)
    for context in retrieved_contexts:
        normalized_context = _normalize_text(context)
        if normalized_reference and normalized_reference in normalized_context:
            return True
        if normalized_context and normalized_context in normalized_reference:
            return True

    model = model_provider.get_chat_model(model_name)
    contexts_text = "\n\n".join(retrieved_contexts)
    answer = await _invoke_chain(
        _RECALL_JUDGE_PROMPT,
        model,
        {
            "question": question,
            "reference_context": reference_context,
            "retrieved_contexts": contexts_text,
        },
    )
    return answer.strip().lower().startswith("yes")


def _parse_sse_event(raw_event: str) -> dict[str, Any] | None:
    """解析 AiService 产生的 SSE data 事件。"""
    for line in raw_event.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line.removeprefix("data:").strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


async def _run_agent_answer(
    question: str,
    *,
    model_name: str,
    user_id: int,
    retrieval_mode: str,
    top_k: int,
) -> tuple[str, list[str], str]:
    """直接走 LabAgent 的 Agent 服务流，返回最终回答和实际检索来源。"""
    from app.services.ai_service import AiService

    service = AiService()
    tokens: list[str] = []
    contexts: list[str] = []
    first_source = ""
    async for raw_event in service.stream_chat(
        question,
        session_id=None,
        user_id=user_id,
        model=model_name,
        rag_retrieval_mode=retrieval_mode,
        rag_retrieval_top_k=top_k,
    ):
        event = _parse_sse_event(raw_event)
        if event is None:
            continue
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type == "token":
            content = payload.get("content")
            if isinstance(content, str):
                tokens.append(content)
        if event_type == "sources":
            sources = payload.get("sources")
            if not isinstance(sources, list):
                continue
            for source in sources:
                if not isinstance(source, dict):
                    continue
                file_name = str(source.get("file_name") or "")
                snippet = str(source.get("snippet") or "")
                if not snippet:
                    continue
                if not first_source:
                    first_source = file_name
                contexts.append(f"来源: {file_name}\n{snippet}")
        if event_type == "error":
            message = payload.get("message")
            raise RuntimeError(str(message or "Agent 执行失败"))
    return "".join(tokens).strip(), contexts, first_source


async def _run_forced_retrieval_answer(
    question: str,
    *,
    model_name: str,
    user_id: int,
    retrieval_mode: str,
    top_k: int,
) -> tuple[str, list[str], str]:
    """评测专用：强制执行检索分支，再基于检索结果生成回答。"""
    if retrieval_mode == "vector_only":
        retriever = rag_store.build_vector_retriever(top_k)
        documents = await asyncio.to_thread(lambda: list(retriever.invoke(question)))
    else:
        documents = await rag_retrieval.retrieve(question)
        documents = await rag_retrieval.rerank(question, documents)
        documents = documents[:top_k]

    contexts: list[str] = []
    first_source = ""
    for document in documents:
        source = str(document.metadata.get("source") or document.metadata.get("file_name") or "")
        if source and not first_source:
            first_source = source
        contexts.append(f"来源: {source or '未知来源'}\n{document.page_content or ''}")

    contexts_text = "\n\n".join(contexts) if contexts else "（未检索到相关资料）"
    model = model_provider.get_chat_model(model_name)
    response = await _invoke_chain(
        _FORCED_RAG_PROMPT,
        model,
        {
            "question": question,
            "retrieved_contexts": contexts_text,
        },
    )
    return response, contexts, first_source


async def _build_method_results(
    cases: list[EvalCase],
    *,
    method_name: str,
    retrieval_mode: str,
    top_k: int,
    answer_model_name: str,
    judge_model_name: str,
    user_id: int,
    force_retrieval: bool,
) -> MethodSummary:
    """跑单种方法的完整链路。"""
    case_results: list[MethodCaseResult] = []
    recall_scores: list[float] = []
    run_answer = _run_forced_retrieval_answer if force_retrieval else _run_agent_answer
    for case in cases:
        response, retrieved_contexts, first_source = await run_answer(
            case.user_input,
            model_name=answer_model_name,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
        )
        retrieved_contexts = retrieved_contexts[:top_k]
        recall_hit = await _judge_recall_at_k(case.user_input, case.reference_context, retrieved_contexts, judge_model_name)
        recall_score = 1.0 if recall_hit else 0.0
        recall_scores.append(recall_score)
        case_results.append(
            MethodCaseResult(
                case_id=case.case_id,
                user_input=case.user_input,
                reference=case.reference,
                reference_context=case.reference_context,
                retrieved_contexts=retrieved_contexts,
                response=response,
                recall_at_5=recall_score,
                retrieval_hit=recall_hit,
                first_source=str(first_source),
            )
        )
    return MethodSummary(
        method_name=method_name,
        case_results=case_results,
        recall_at_5=_mean_or_zero(recall_scores),
    )


def _extract_ragas_metric_map(result: Any) -> dict[str, float]:
    """兼容不同 ragas 返回值形态，抽取指标均值。"""
    metric_map: dict[str, list[float]] = {}

    if hasattr(result, "to_pandas"):
        dataframe = result.to_pandas()
        for column in getattr(dataframe, "columns", []):
            if column == "sample_id":
                continue
            series = dataframe[column].dropna()
            values = [float(value) for value in series.tolist() if isinstance(value, (int, float))]
            if values:
                metric_map[column] = values

    if not metric_map and isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, list):
                metric_map[key] = [float(item) for item in value if isinstance(item, (int, float))]
            elif isinstance(value, (int, float)):
                metric_map[key] = [float(value)]

    if not metric_map and hasattr(result, "scores"):
        scores = getattr(result, "scores")
        if isinstance(scores, list):
            for item in scores:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if isinstance(value, (int, float)):
                            metric_map.setdefault(key, []).append(float(value))

    return {key: _mean_or_zero(values) for key, values in metric_map.items()}


def _build_ragas_dataset(records: list[MethodCaseResult]) -> Any:
    """按 RAGAS 单轮样本结构构造数据集。"""
    from ragas import EvaluationDataset, SingleTurnSample

    samples = [
        SingleTurnSample(
            user_input=record.user_input,
            retrieved_contexts=record.retrieved_contexts,
            response=record.response,
            reference=record.reference,
            reference_contexts=[record.reference_context],
        )
        for record in records
    ]
    return EvaluationDataset(samples=samples)


def _build_ragas_llm(judge_model_name: str) -> Any:
    """构建 RAGAS 0.4 collections 指标要求的 InstructorLLM。"""
    from ragas.llms.base import llm_factory

    if judge_model_name in _AZURE_MODEL_NAMES:
        logid = settings.azure_logid or f"labagent-rag-eval-{uuid.uuid4().hex}"
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_endpoint,
            azure_deployment=judge_model_name,
            api_version=settings.azure_api_version,
            api_key=settings.azure_api_key,
            default_headers={"X-TT-LOGID": logid},
            timeout=60,
            max_retries=0,
        )
        return llm_factory(judge_model_name, provider="openai", client=client, temperature=1, top_p=1, max_tokens=4096)

    if judge_model_name in _OPENAI_MODEL_NAMES:
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=60,
            max_retries=0,
        )
        return llm_factory(judge_model_name, provider="openai", client=client, temperature=1, top_p=1, max_tokens=4096)

    import instructor
    import litellm

    client = instructor.from_litellm(litellm.completion, mode=instructor.Mode.JSON)
    return llm_factory(
        f"ollama/{judge_model_name}",
        provider="ollama",
        client=client,
        adapter="litellm",
        api_base=settings.ollama_base_url,
        api_key="ollama",
        temperature=0,
        timeout=settings.ollama_judge_timeout,
        max_tokens=4096,
    )


def _run_ragas_sync(
    records: list[MethodCaseResult],
    judge_model_name: str,
    ragas_llm_only: bool = False,
    batch_size: int = 1,
) -> dict[str, float]:
    """同步跑 RAGAS 指标。"""
    from ragas import evaluate
    try:
        from ragas.metrics.collections import (
            AnswerCorrectness,
            AnswerRelevancy,
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
        )
    except ImportError:
        from ragas.metrics import (  # type: ignore[attr-defined, no-redef]
            AnswerCorrectness,
            AnswerRelevancy,
            Faithfulness,
            LLMContextPrecisionWithReference,
            LLMContextRecall,
        )
    from ragas.embeddings.base import LangchainEmbeddingsWrapper

    dataset = _build_ragas_dataset(records)
    ragas_llm = _build_ragas_llm(judge_model_name)
    metrics = [
        LLMContextPrecisionWithReference(llm=ragas_llm, name="context_precision"),
        LLMContextRecall(llm=ragas_llm),
        Faithfulness(llm=ragas_llm),
    ]
    ragas_embeddings = None
    if not ragas_llm_only:
        ragas_embeddings = LangchainEmbeddingsWrapper(model_provider.get_embedding_model())
        metrics.extend(
            [
                AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
                AnswerCorrectness(llm=ragas_llm, embeddings=ragas_embeddings),
            ]
        )
    result = evaluate(dataset, metrics=metrics, llm=ragas_llm, embeddings=ragas_embeddings, batch_size=batch_size)
    metric_map = _extract_ragas_metric_map(result)
    if "answer_relevancy" in metric_map:
        metric_map["response_relevancy"] = metric_map.pop("answer_relevancy")
    return metric_map


async def run_ragas_metrics(
    records: list[MethodCaseResult],
    judge_model_name: str,
    ragas_llm_only: bool = False,
    batch_size: int = 1,
) -> tuple[dict[str, float] | None, str | None]:
    """异步包装 RAGAS 指标计算，缺少依赖或环境时返回错误信息。"""
    try:
        metrics = await asyncio.to_thread(_run_ragas_sync, records, judge_model_name, ragas_llm_only, batch_size)
        return metrics, None
    except ModuleNotFoundError as exc:
        return None, f"ragas 依赖未安装: {exc}"
    except Exception as exc:  # noqa: BLE001 - 评测脚本应尽量保留结果并给出原因
        logger.exception("RAGAS 指标计算失败")
        return None, str(exc)


def _build_summary_table(summary: MethodSummary) -> str:
    """构建方法指标小表。"""
    lines = [
        f"| {summary.method_name} | {_format_score(summary.recall_at_5)} | {_format_score((summary.ragas_metrics or {}).get('context_precision'))} | "
        f"{_format_score((summary.ragas_metrics or {}).get('context_recall'))} | "
        f"{_format_score((summary.ragas_metrics or {}).get('faithfulness'))} | "
        f"{_format_score((summary.ragas_metrics or {}).get('response_relevancy'))} | "
        f"{_format_score((summary.ragas_metrics or {}).get('answer_correctness'))} |"
    ]
    return "\n".join(lines)


def _build_ragas_status(method_label: str, summary: MethodSummary) -> str:
    """构建 RAGAS 执行状态文案。"""
    if summary.ragas_error:
        return f"- {method_label}: {summary.ragas_error}"
    if summary.ragas_metrics is None:
        return f"- {method_label}: 未运行，待补跑"
    if not summary.ragas_metrics:
        return f"- {method_label}: 已运行，但未返回有效指标"
    return f"- {method_label}: 已完成"


def build_markdown_report(report: EvaluationReport) -> str:
    """生成最终 Markdown 报告。"""
    lines: list[str] = [
        "<!--",
        " @author: caoshuai.cs",
        f" @date: {report.generated_at}",
        " @description: LabAgent RAG 评测报告",
        "-->",
        "",
        "# RAG 评测报告",
        "",
        f"本次共评测 {report.case_count} 条问题。",
        "",
        "## 1. 总体结果",
        "",
        "| 方法 | Recall@5 | ContextPrecision | ContextRecall | Faithfulness | ResponseRelevancy | AnswerCorrectness |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        _build_summary_table(report.baseline),
        _build_summary_table(report.current),
        "",
    ]

    lines.extend(
        [
            "## 2. RAGAS 状态",
            "",
        ]
    )
    lines.append(_build_ragas_status("纯向量检索 baseline", report.baseline))
    lines.append(_build_ragas_status("当前检索链路", report.current))
    lines.append("")

    lines.extend(
        [
            "## 3. 逐题对比",
            "",
            "| id | 问题 | baseline Recall@5 | current Recall@5 | baseline 来源 | current 来源 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for baseline_record, current_record in zip(report.baseline.case_results, report.current.case_results, strict=False):
        lines.append(
            f"| {baseline_record.case_id} | {baseline_record.user_input} | "
            f"{_format_score(baseline_record.recall_at_5)} | {_format_score(current_record.recall_at_5)} | "
            f"{baseline_record.first_source or '—'} | {current_record.first_source or '—'} |"
        )

    lines.extend(
        [
            "",
            "## 4. 失败/差异样例",
            "",
        ]
    )
    failed_records = [
        (b, c)
        for b, c in zip(report.baseline.case_results, report.current.case_results, strict=False)
        if b.recall_at_5 != c.recall_at_5 or b.recall_at_5 == 0.0 or c.recall_at_5 == 0.0
    ]
    if not failed_records:
        lines.append("本次没有明显失败样例。")
    else:
        for baseline_record, current_record in failed_records:
            lines.extend(
                [
                    f"### {baseline_record.case_id}",
                    f"- 问题：{baseline_record.user_input}",
                    f"- 标准答案：{baseline_record.reference}",
                    f"- 黄金证据：{baseline_record.reference_context}",
                    f"- baseline 答案：{baseline_record.response}",
                    f"- current 答案：{current_record.response}",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def _default_report_path() -> Path:
    """生成默认报告路径。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _DEFAULT_REPORT_DIR / f"{timestamp}_rag_eval_report.md"


def _default_answers_path() -> Path:
    """生成默认回答中间结果路径。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _DEFAULT_REPORT_DIR / f"{timestamp}_rag_eval_answers.json"


def _load_method_case_result(item: dict[str, Any]) -> MethodCaseResult:
    """从 JSON 字典恢复单条方法结果。"""
    return MethodCaseResult(
        case_id=str(item.get("case_id") or ""),
        user_input=str(item.get("user_input") or ""),
        reference=str(item.get("reference") or ""),
        reference_context=str(item.get("reference_context") or ""),
        retrieved_contexts=[str(context) for context in item.get("retrieved_contexts") or []],
        response=str(item.get("response") or ""),
        recall_at_5=float(item.get("recall_at_5") or 0.0),
        retrieval_hit=bool(item.get("retrieval_hit")),
        first_source=str(item.get("first_source") or ""),
    )


def _load_method_summary(item: dict[str, Any]) -> MethodSummary:
    """从 JSON 字典恢复单种方法结果。"""
    ragas_metrics = item.get("ragas_metrics")
    return MethodSummary(
        method_name=str(item.get("method_name") or ""),
        case_results=[_load_method_case_result(result) for result in item.get("case_results") or []],
        recall_at_5=float(item.get("recall_at_5") or 0.0),
        ragas_metrics={str(key): float(value) for key, value in ragas_metrics.items()} if isinstance(ragas_metrics, dict) else None,
        ragas_error=str(item["ragas_error"]) if item.get("ragas_error") else None,
    )


def load_evaluation_report(path_value: str | Path) -> EvaluationReport:
    """读取第一阶段保存的回答中间结果。"""
    path = _resolve_input_path(path_value)
    item = json.loads(path.read_text(encoding="utf-8"))
    return EvaluationReport(
        case_count=int(item.get("case_count") or 0),
        generated_at=str(item.get("generated_at") or ""),
        baseline=_load_method_summary(item["baseline"]),
        current=_load_method_summary(item["current"]),
    )


def write_evaluation_report_json(report: EvaluationReport, output_path: str | Path | None = None) -> Path:
    """写出可继续跑 RAGAS 的回答中间结果。"""
    target_path = _resolve_input_path(output_path) if output_path else _default_answers_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path


def limit_evaluation_report(report: EvaluationReport, limit_cases: int) -> None:
    """限制报告参与后续补跑的样例数。"""
    if limit_cases <= 0:
        return
    for summary in (report.baseline, report.current):
        summary.case_results = summary.case_results[:limit_cases]
        summary.recall_at_5 = _mean_or_zero([record.recall_at_5 for record in summary.case_results])
        summary.ragas_metrics = None
        summary.ragas_error = None
    report.case_count = min(report.case_count, limit_cases)


async def fill_ragas_metrics(
    report: EvaluationReport,
    judge_model_name: str,
    ragas_llm_only: bool = False,
    batch_size: int = 1,
) -> None:
    """基于已有回答结果补跑 RAGAS 指标。"""
    baseline_metrics, baseline_error = await run_ragas_metrics(
        report.baseline.case_results,
        judge_model_name,
        ragas_llm_only,
        batch_size,
    )
    current_metrics, current_error = await run_ragas_metrics(
        report.current.case_results,
        judge_model_name,
        ragas_llm_only,
        batch_size,
    )
    report.baseline.ragas_metrics = baseline_metrics
    report.baseline.ragas_error = baseline_error
    report.current.ragas_metrics = current_metrics
    report.current.ragas_error = current_error


async def recompute_recall_metrics(report: EvaluationReport, judge_model_name: str) -> None:
    """基于已有召回上下文重新计算 Recall@5 和命中标记。"""
    for summary in (report.baseline, report.current):
        recall_scores: list[float] = []
        for record in summary.case_results:
            recall_hit = await _judge_recall_at_k(
                record.user_input,
                record.reference_context,
                record.retrieved_contexts,
                judge_model_name,
            )
            record.retrieval_hit = recall_hit
            record.recall_at_5 = 1.0 if recall_hit else 0.0
            recall_scores.append(record.recall_at_5)
        summary.recall_at_5 = _mean_or_zero(recall_scores)


class RagEvalRunner:
    """RAG 评测执行器。"""

    def __init__(
        self,
        *,
        case_path: str | Path = _DEFAULT_CASE_PATH,
        top_k: int = _DEFAULT_TOP_K,
        user_id: int = _DEFAULT_EVAL_USER_ID,
        answer_model_name: str = _ANSWER_MODEL_NAME,
        judge_model_name: str = _JUDGE_MODEL_NAME,
        skip_ragas: bool = False,
        ragas_llm_only: bool = False,
        ragas_batch_size: int = 1,
        limit_cases: int = 0,
        force_retrieval: bool = True,
    ) -> None:
        self.case_path = _resolve_input_path(case_path)
        self.top_k = top_k
        self.user_id = user_id
        self.answer_model_name = answer_model_name
        self.judge_model_name = judge_model_name
        self.skip_ragas = skip_ragas
        self.ragas_llm_only = ragas_llm_only
        self.ragas_batch_size = max(1, ragas_batch_size)
        self.limit_cases = max(0, limit_cases)
        self.force_retrieval = force_retrieval

    def load_cases(self) -> list[EvalCase]:
        """读取黄金评测集。"""
        cases = load_eval_cases(self.case_path)
        if self.limit_cases:
            return cases[: self.limit_cases]
        return cases

    async def run(self) -> EvaluationReport:
        """执行两组方法评测并生成报告对象。"""
        cases = self.load_cases()
        baseline = await _build_method_results(
            cases,
            method_name="baseline",
            retrieval_mode="vector_only",
            top_k=self.top_k,
            answer_model_name=self.answer_model_name,
            judge_model_name=self.judge_model_name,
            user_id=self.user_id,
            force_retrieval=self.force_retrieval,
        )
        current = await _build_method_results(
            cases,
            method_name="current",
            retrieval_mode="current",
            top_k=self.top_k,
            answer_model_name=self.answer_model_name,
            judge_model_name=self.judge_model_name,
            user_id=self.user_id,
            force_retrieval=self.force_retrieval,
        )

        if not self.skip_ragas:
            report = EvaluationReport(
                case_count=len(cases),
                generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
                baseline=baseline,
                current=current,
            )
            await fill_ragas_metrics(report, self.judge_model_name, self.ragas_llm_only, self.ragas_batch_size)
            return report

        return EvaluationReport(
            case_count=len(cases),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            baseline=baseline,
            current=current,
        )

    def write_report(self, report: EvaluationReport, output_path: str | Path | None = None) -> Path:
        """写出 Markdown 报告。"""
        target_path = _resolve_input_path(output_path) if output_path else _default_report_path()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(build_markdown_report(report), encoding="utf-8")
        return target_path


def build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数。"""
    parser = argparse.ArgumentParser(description="LabAgent RAG 评测脚本")
    parser.add_argument(
        "--cases",
        default=str(_DEFAULT_CASE_PATH),
        help="评测集文件路径，支持 Markdown / JSONL / CSV",
    )
    parser.add_argument(
        "--output",
        default="",
        help="报告输出路径，默认写入 docs/rag_eval/reports 下的时间戳文件",
    )
    parser.add_argument(
        "--answers-output",
        default="",
        help="回答中间结果 JSON 输出路径；用于先跑回答、后续换环境再跑 RAGAS",
    )
    parser.add_argument(
        "--answers-input",
        default="",
        help="读取已生成的回答中间结果 JSON，只补跑 RAGAS 并输出报告",
    )
    parser.add_argument(
        "--skip-recall-judge",
        action="store_true",
        help="读取 answers-input 时不重新计算 Recall@5，直接使用中间结果中的旧值",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=_DEFAULT_TOP_K,
        help="召回 top_k，baseline 和 current 都使用该值做最终上下文截断",
    )
    parser.add_argument(
        "--answer-model",
        default=_ANSWER_MODEL_NAME,
        help="答案生成模型，默认 GPT-5.5",
    )
    parser.add_argument(
        "--judge-model",
        default=_JUDGE_MODEL_NAME,
        help="评测 judge 模型，默认 GPT-5.5",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=_DEFAULT_EVAL_USER_ID,
        help="评测时调用 Agent 使用的用户ID，默认 1",
    )
    parser.add_argument(
        "--skip-ragas",
        action="store_true",
        help="跳过 RAGAS 指标，仅输出检索与回答结果",
    )
    parser.add_argument(
        "--ragas-llm-only",
        action="store_true",
        help="只跑不依赖 embedding 的 RAGAS 指标：ContextPrecision、ContextRecall、Faithfulness",
    )
    parser.add_argument(
        "--ragas-batch-size",
        type=int,
        default=1,
        help="RAGAS evaluate 的 batch_size，默认 1；本地 Ollama 稳定后可调大",
    )
    parser.add_argument(
        "--limit-cases",
        type=int,
        default=0,
        help="只评测前 N 条样例，默认 0 表示不限制；适合冒烟测试",
    )
    parser.add_argument(
        "--agent-retrieval",
        action="store_true",
        help="使用 Agent 自主决定是否调用检索工具；默认评测时强制执行检索分支",
    )
    return parser


async def run_from_args(args: argparse.Namespace) -> Path:
    """从命令行参数运行评测。"""
    if args.answers_input:
        report = load_evaluation_report(args.answers_input)
        limit_evaluation_report(report, args.limit_cases)
        if not args.skip_recall_judge:
            await recompute_recall_metrics(report, args.judge_model)
        if not args.skip_ragas:
            report.generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            await fill_ragas_metrics(report, args.judge_model, args.ragas_llm_only, max(1, args.ragas_batch_size))
        runner = RagEvalRunner()
        output_path = runner.write_report(report, args.output or None)
        logger.info("RAG 评测报告已生成: %s", output_path)
        return output_path

    if args.agent_retrieval:
        await init_checkpointer()
    try:
        runner = RagEvalRunner(
            case_path=args.cases,
            top_k=args.top_k,
            user_id=args.user_id,
            answer_model_name=args.answer_model,
            judge_model_name=args.judge_model,
            skip_ragas=args.skip_ragas,
            ragas_llm_only=args.ragas_llm_only,
            ragas_batch_size=args.ragas_batch_size,
            limit_cases=args.limit_cases,
            force_retrieval=not args.agent_retrieval,
        )
        report = await runner.run()
        if args.answers_output:
            answers_path = write_evaluation_report_json(report, args.answers_output)
            logger.info("RAG 评测回答中间结果已生成: %s", answers_path)
        output_path = runner.write_report(report, args.output or None)
        logger.info("RAG 评测报告已生成: %s", output_path)
        return output_path
    finally:
        if args.agent_retrieval:
            await close_checkpointer()


def main(argv: list[str] | None = None) -> int:
    """脚本入口。"""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        output_path = asyncio.run(run_from_args(args))
    except KeyboardInterrupt:
        return 130
    print(output_path)
    return 0
