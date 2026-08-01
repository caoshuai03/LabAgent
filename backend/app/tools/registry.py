"""
@author: caoshuai.cs
@date: 2026-07-15 00:41
@description: Agent 工具统一注册、元数据和用户可见性管理
"""
from dataclasses import dataclass

from langchain_core.tools import BaseTool

from app.core.config import settings
from app.schemas.tool import ToolDefinitionVO
from app.services.skill_service import skill_catalog
from app.tools.file_tools import FILE_TOOLS
from app.tools.knowledge_tool import KNOWLEDGE_TOOLS
from app.tools.memory_tools import MEMORY_TOOLS
from app.tools.shell_tool import execute_shell
from app.tools.skill_tools import SKILL_TOOLS


@dataclass(frozen=True)
class ToolMetadata:
    """工具元数据。"""

    source: str
    risk_level: str
    read_only: bool


class ToolRegistry:
    """统一管理框架工具和可见性。"""

    def __init__(self) -> None:
        tools = [*FILE_TOOLS, *KNOWLEDGE_TOOLS, execute_shell, *SKILL_TOOLS, *MEMORY_TOOLS]
        self._tools: dict[str, BaseTool] = {}
        for tool_item in tools:
            if tool_item.name in self._tools:
                raise ValueError(f"工具名重复: {tool_item.name}")
            self._tools[tool_item.name] = tool_item
        self._metadata = {
            "write_file": ToolMetadata("langchain_file", "medium", False),
            "search_knowledge_base": ToolMetadata("rag", "low", True),
            "execute_shell": ToolMetadata("langchain_shell", "high", False),
            "activate_skill": ToolMetadata("skill", "low", True),
            "read_skill_resource": ToolMetadata("skill", "low", True),
        }

    def all_tools(self) -> list[BaseTool]:
        """返回 ToolNode 可执行的全部已注册工具。"""
        return list(self._tools.values())

    def model_tools(self) -> list[BaseTool]:
        """返回可绑定给模型的工具。"""
        if not settings.agent_tools_enabled:
            return []
        names: list[str] = ["search_knowledge_base"]
        names.extend(tool_item.name for tool_item in MEMORY_TOOLS)
        if settings.skills_enabled and skill_catalog.list_summaries():
            names.extend(tool_item.name for tool_item in SKILL_TOOLS)
        if settings.file_tools_enabled:
            names.extend(tool_item.name for tool_item in FILE_TOOLS)
        if settings.shell_tool_enabled:
            names.append("execute_shell")
        return [self._tools[name] for name in names]

    def metadata(self, tool_name: str) -> ToolMetadata | None:
        """查询工具元数据。"""
        return self._metadata.get(tool_name)

    def definitions(self) -> list[ToolDefinitionVO]:
        """返回工具定义。"""
        visible_names = {tool_item.name for tool_item in self.model_tools()}
        result: list[ToolDefinitionVO] = []
        for name, tool_item in self._tools.items():
            metadata = self._metadata[name]
            enabled = name in visible_names
            requires_approval = (
                settings.shell_delete_require_approval if name == "execute_shell"
                else settings.file_write_require_approval if name == "write_file"
                else False
            )
            result.append(
                ToolDefinitionVO(
                    name=name,
                    description=tool_item.description,
                    source=metadata.source,
                    risk_level=metadata.risk_level,
                    read_only=metadata.read_only,
                    requires_approval=requires_approval,
                    enabled=enabled,
                )
            )
        return result


tool_registry = ToolRegistry()
