#!/usr/bin/env python3
"""
@author: caoshuai.cs
@date: 2026-07-23 04:09
@description: LabAgent RAG 评测脚本入口
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.rag_eval import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
