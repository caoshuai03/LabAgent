"""
@author: caoshuai.cs
@date: 2026-07-15 02:11
@description: 工具结果输出脱敏与截断测试
"""
import json

from app.tools.result import redact_value, result_envelope


def test_redact_shell_environment_assignments() -> None:
    """Shell输出中的常见敏感环境变量必须脱敏。"""
    output = "TOOL_RUNNER_TOKEN=abc123\nPASSWORD='secret-value'\nNORMAL=value"

    assert redact_value(output) == "TOOL_RUNNER_TOKEN=***\nPASSWORD=***\nNORMAL=value"


def test_result_envelope_redacts_shell_output() -> None:
    """结果信封不能保留Shell输出中的敏感值。"""
    result = result_envelope(success=True, output="API_KEY=my-key", summary="ok")
    payload = json.loads(result)

    assert "my-key" not in result
    assert payload["output"] == "***"


def test_result_envelope_marks_internal_rejection() -> None:
    """内部拒绝结果应保留精确状态和仅后端消费标记。"""
    result = result_envelope(
        success=False,
        summary="工具未执行",
        error="只允许使用工作区相对路径",
        error_type="policy_rejected",
        status="rejected",
        internal=True,
    )
    payload = json.loads(result)

    assert payload["status"] == "rejected"
    assert payload["internal"] is True
