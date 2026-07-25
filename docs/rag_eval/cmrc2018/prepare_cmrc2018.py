"""
@author: caoshuai.cs
@date: 2026-07-25 00:00
@description: 下载并转换 CMRC2018 数据集，生成知识库 Markdown 语料与 RAG 评测集。
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from datasets import load_dataset

_DATASET_NAME = "hfl/cmrc2018"
_DEFAULT_KB_COUNT = 1000
_DEFAULT_EVAL_COUNT = 100
_DEFAULT_SEED = 42
_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


@dataclass(slots=True)
class PreparedArtifact:
    """数据集转换后的产物清单。"""

    dataset_name: str
    generated_at: str
    shuffle_seed: int
    raw_test_count: int
    valid_test_count: int
    unique_test_context_count: int
    kb_count: int
    eval_count: int
    raw_test_jsonl: str
    kb_markdown: str
    eval_markdown: str
    eval_jsonl: str
    manifest_json: str


def _normalize_text(value: Any) -> str:
    """将任意值规整为单行文本。"""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text


def _extract_answer(answers: Any) -> str:
    """提取答案字段。"""
    if isinstance(answers, dict):
        texts = answers.get("text")
        if isinstance(texts, list) and texts:
            return _normalize_text(texts[0])
        if isinstance(texts, str):
            return _normalize_text(texts)
    return ""


def _collapse_lines(text: str) -> str:
    """压平多行文本，便于写入 Markdown 表格。"""
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def _escape_markdown_cell(text: str) -> str:
    """转义 Markdown 表格单元格。"""
    return _collapse_lines(text).replace("|", "｜")


def _blockquote(text: str) -> str:
    """把文本转为 Markdown 引用块。"""
    lines = [_normalize_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return "> "
    return "\n".join(f"> {line}" for line in lines)


def _build_kb_markdown(rows: list[dict[str, Any]], generated_at: str) -> str:
    """生成知识库用 Markdown 语料。"""
    lines = [
        "<!--",
        " @author: caoshuai.cs",
        f" @date: {generated_at}",
        " @description: CMRC2018 知识库 Markdown 语料，供手动上传到 LabAgent 知识库。",
        "-->",
        "",
        "# CMRC2018 知识库语料",
        "",
        f"本文件基于 `{_DATASET_NAME}` 的 test split 抽取 1000 条样本，采用问答对加参考上下文的格式。",
        "",
    ]
    for index, row in enumerate(rows, start=1):
        question = _normalize_text(row["question"])
        answer = _extract_answer(row["answers"])
        context = _normalize_text(row["context"])
        lines.extend(
            [
                f"## {index}. {row['id']}",
                "",
                f"**问题**：{question}",
                "",
                f"**答案**：{answer}",
                "",
                "**参考上下文**：",
                "",
                _blockquote(context),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _build_eval_markdown(rows: list[dict[str, Any]], generated_at: str) -> str:
    """生成评测集 Markdown 表格。"""
    lines = [
        "<!--",
        " @author: caoshuai.cs",
        f" @date: {generated_at}",
        " @description: CMRC2018 RAG 评测集，供 LabAgent 现有评测脚本直接读取。",
        "-->",
        "",
        "# CMRC2018 评测集",
        "",
        f"本文件抽取 `{_DEFAULT_EVAL_COUNT}` 条样本，字段可直接对接 `backend/app/eval/rag_eval.py`。",
        "",
        "| id | user_input | reference | reference_context |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        question = _escape_markdown_cell(row["question"])
        answer = _escape_markdown_cell(_extract_answer(row["answers"]))
        context = _escape_markdown_cell(row["context"])
        lines.append(f"| {row['id']} | {question} | {answer} | {context} |")
    return "\n".join(lines).rstrip() + "\n"


def _select_rows(split: Any, count: int, seed: int) -> list[dict[str, Any]]:
    """按固定随机种子抽样。"""
    rows: list[dict[str, Any]] = []
    for row in split.shuffle(seed=seed):
        item = dict(row)
        if not _is_valid_qa_row(item):
            continue
        rows.append(item)
        if len(rows) >= count:
            break
    return rows


def _is_valid_qa_row(row: dict[str, Any]) -> bool:
    """判断是否为完整问答样本。"""
    return bool(
        _normalize_text(row.get("id"))
        and _normalize_text(row.get("question"))
        and _normalize_text(row.get("context"))
        and _extract_answer(row.get("answers"))
    )


def _write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    """写出 JSONL 文件。"""
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            payload = {
                "id": row["id"],
                "user_input": _normalize_text(row["question"]),
                "reference": _extract_answer(row["answers"]),
                "reference_context": _normalize_text(row["context"]),
            }
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_raw_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    """写出原始 test split 备份。"""
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            payload = {
                "id": row["id"],
                "context": _normalize_text(row["context"]),
                "question": _normalize_text(row["question"]),
                "answer": _extract_answer(row["answers"]),
            }
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_artifacts(
    *,
    kb_count: int,
    eval_count: int,
    seed: int,
    output_dir: Path,
) -> PreparedArtifact:
    """下载并生成全部产物。"""
    dataset = load_dataset(_DATASET_NAME)
    test_rows = [dict(row) for row in dataset["test"]]
    valid_test_rows = [row for row in test_rows if _is_valid_qa_row(row)]
    selected_rows = _select_rows(dataset["test"], max(kb_count, eval_count), seed)
    kb_rows = selected_rows[: min(kb_count, len(selected_rows))]
    eval_rows = selected_rows[: min(eval_count, len(selected_rows))]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_test_jsonl = output_dir / "cmrc2018_test_raw.jsonl"
    kb_markdown = output_dir / "cmrc2018_kb_markdown.md"
    eval_markdown = output_dir / "cmrc2018_eval_100.md"
    eval_jsonl = output_dir / "cmrc2018_eval_100.jsonl"
    manifest_path = output_dir / "cmrc2018_manifest.json"

    _write_raw_jsonl(test_rows, raw_test_jsonl)
    kb_markdown.write_text(_build_kb_markdown(kb_rows, generated_at), encoding="utf-8")
    eval_markdown.write_text(_build_eval_markdown(eval_rows, generated_at), encoding="utf-8")
    _write_jsonl(eval_rows, eval_jsonl)

    unique_contexts = {row["context"] for row in test_rows}
    artifact = PreparedArtifact(
        dataset_name=_DATASET_NAME,
        generated_at=generated_at,
        shuffle_seed=seed,
        raw_test_count=len(test_rows),
        valid_test_count=len(valid_test_rows),
        unique_test_context_count=len(unique_contexts),
        kb_count=len(kb_rows),
        eval_count=len(eval_rows),
        raw_test_jsonl=str(raw_test_jsonl),
        kb_markdown=str(kb_markdown),
        eval_markdown=str(eval_markdown),
        eval_jsonl=str(eval_jsonl),
        manifest_json=str(manifest_path),
    )
    manifest_path.write_text(json.dumps(asdict(artifact), ensure_ascii=False, indent=2), encoding="utf-8")
    return artifact


def build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数。"""
    parser = argparse.ArgumentParser(description="下载并转换 CMRC2018 数据集")
    parser.add_argument("--kb-count", type=int, default=_DEFAULT_KB_COUNT, help="知识库 Markdown 抽样数量")
    parser.add_argument("--eval-count", type=int, default=_DEFAULT_EVAL_COUNT, help="评测集抽样数量")
    parser.add_argument("--seed", type=int, default=_DEFAULT_SEED, help="抽样随机种子")
    parser.add_argument("--output-dir", default=str(_OUTPUT_DIR), help="产物输出目录")
    return parser


def main(argv: list[str] | None = None) -> int:
    """脚本入口。"""
    args = build_arg_parser().parse_args(argv)
    artifact = build_artifacts(
        kb_count=max(1, args.kb_count),
        eval_count=max(1, args.eval_count),
        seed=args.seed,
        output_dir=Path(args.output_dir).expanduser(),
    )
    print(json.dumps(asdict(artifact), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
