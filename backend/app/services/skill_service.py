"""
@author: caoshuai.cs
@date: 2026-07-30
@description: 基于 Agent Skills 规范的本地 Skill 扫描、缓存、激活与资源安全读取
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path, PurePosixPath
from threading import RLock

from skills_ref import read_properties, validate

from app.core.config import settings
from app.schemas.skill import SkillDetailVO, SkillRefreshVO, SkillSummaryVO

_RESOURCE_DIRECTORIES = frozenset({"references", "scripts", "assets"})
_MAX_LISTED_RESOURCES = 200


class SkillError(ValueError):
    """Skill 加载或使用失败。"""


@dataclass(frozen=True)
class SkillDefinition:
    """已校验并缓存的 Skill 定义。"""

    name: str
    description: str
    content: str
    directory: Path
    license: str | None
    compatibility: str | None
    allowed_tools: str | None
    resources: tuple[str, ...]


class SkillCatalog:
    """以原子快照方式管理应用内置 Skill。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        self._diagnostics: tuple[str, ...] = ()
        self._lock = RLock()

    def refresh(self) -> SkillRefreshVO:
        """重新扫描目录；单个 Skill 无效时跳过，不影响其他有效 Skill。"""
        root = Path(settings.skills_directory).expanduser().resolve()
        definitions: dict[str, SkillDefinition] = {}
        diagnostics: list[str] = []
        if not settings.skills_enabled:
            with self._lock:
                self._skills = {}
                self._diagnostics = ()
            return SkillRefreshVO(loaded_count=0, skipped_count=0)
        if not root.exists():
            diagnostics.append("Skills 目录不存在")
        elif not root.is_dir():
            diagnostics.append("Skills 路径不是目录")
        else:
            entries = sorted(root.iterdir(), key=lambda item: item.name)
            if len(entries) > settings.skills_max_count:
                diagnostics.append(
                    f"Skills 目录项超过上限，仅扫描前 {settings.skills_max_count} 个"
                )
                entries = entries[: settings.skills_max_count]
            for entry in entries:
                if not entry.is_dir() or entry.is_symlink():
                    continue
                try:
                    definition = self._load_definition(entry)
                    if definition.name in definitions:
                        raise SkillError(f"Skill 名称重复: {definition.name}")
                    definitions[definition.name] = definition
                except (OSError, UnicodeError, ValueError) as exc:
                    safe_message = str(exc).replace(str(root), "<skills>")
                    diagnostics.append(f"{entry.name}: {safe_message}")
        with self._lock:
            self._skills = definitions
            self._diagnostics = tuple(diagnostics)
        return SkillRefreshVO(
            loaded_count=len(definitions),
            skipped_count=len(diagnostics),
            diagnostics=diagnostics,
        )

    def list_summaries(self) -> list[SkillSummaryVO]:
        """返回供管理页和 API 使用的 Skill 摘要。"""
        with self._lock:
            definitions = tuple(self._skills.values())
        return [
            SkillSummaryVO(name=item.name, description=item.description)
            for item in definitions
        ]

    def get(self, name: str) -> SkillDefinition:
        """按规范名称获取 Skill。"""
        with self._lock:
            definition = self._skills.get(name)
        if definition is None:
            raise SkillError("Skill 不存在或未通过校验")
        return definition

    def detail(self, name: str) -> SkillDetailVO:
        """返回 Skill 完整详情。"""
        definition = self.get(name)
        return SkillDetailVO(
            name=definition.name,
            description=definition.description,
            content=definition.content,
            license=definition.license,
            compatibility=definition.compatibility,
            allowed_tools=definition.allowed_tools,
            resources=list(definition.resources),
        )

    def catalog_prompt(self, excluded_names: set[str] | None = None) -> str:
        """生成只包含未激活 Skill 名称和简介的一级渐进披露目录。"""
        excluded = excluded_names or set()
        summaries = [
            item for item in self.list_summaries()
            if item.name not in excluded
        ]
        if not summaries:
            return ""
        lines = [
            "<available_skills>",
            "以下 Skill 仅提供目录信息；任务匹配时先调用 activate_skill，再遵循其正文。",
        ]
        for item in summaries:
            lines.append(f"- {escape(item.name)}: {escape(item.description)}")
        lines.append("</available_skills>")
        return "\n".join(lines)

    def read_resource(self, name: str, resource_path: str) -> str:
        """在已知 Skill 目录内安全读取 UTF-8 文本资源。"""
        definition = self.get(name)
        relative = PurePosixPath(resource_path)
        if (
            not resource_path
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] not in _RESOURCE_DIRECTORIES
            or len(relative.parts) - 1 > settings.skills_resource_max_depth
        ):
            raise SkillError("Skill 资源路径不合法")
        skill_root = definition.directory.resolve()
        unresolved = definition.directory.joinpath(*relative.parts)
        current = definition.directory
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise SkillError("禁止读取符号链接资源")
        try:
            target = unresolved.resolve(strict=True)
        except OSError as exc:
            raise SkillError("Skill 资源不存在") from exc
        if not target.is_relative_to(skill_root) or not target.is_file():
            raise SkillError("Skill 资源路径越界或不是文件")
        if target.stat().st_size > settings.skills_max_resource_file_bytes:
            raise SkillError("Skill 资源文件超过大小上限")
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SkillError("Skill 资源不是 UTF-8 文本") from exc

    def _load_definition(self, directory: Path) -> SkillDefinition:
        """校验并加载一个 Skill 目录。"""
        skill_file = directory / "SKILL.md"
        if skill_file.is_symlink():
            raise SkillError("SKILL.md 不允许是符号链接")
        if not skill_file.exists():
            raise SkillError("缺少 SKILL.md")
        if skill_file.stat().st_size > settings.skills_max_skill_file_bytes:
            raise SkillError("SKILL.md 超过大小上限")
        validation_errors = validate(directory)
        if validation_errors:
            raise SkillError("; ".join(validation_errors[:3]))
        properties = read_properties(directory)
        raw_content = skill_file.read_text(encoding="utf-8")
        sections = raw_content.split("---", 2)
        if len(sections) != 3:
            raise SkillError("SKILL.md frontmatter 格式错误")
        content = sections[2].strip()
        if not content:
            raise SkillError("SKILL.md 正文不能为空")
        resources = self._list_resources(directory)
        allowed_tools = properties.allowed_tools
        return SkillDefinition(
            name=properties.name,
            description=properties.description,
            content=content,
            directory=directory.resolve(),
            license=properties.license,
            compatibility=properties.compatibility,
            allowed_tools=(
                " ".join(allowed_tools)
                if isinstance(allowed_tools, list)
                else allowed_tools
            ),
            resources=resources,
        )

    def _list_resources(self, directory: Path) -> tuple[str, ...]:
        """列出允许按需读取的资源相对路径。"""
        resources: list[str] = []
        for resource_directory in sorted(_RESOURCE_DIRECTORIES):
            base = directory / resource_directory
            if not base.is_dir() or base.is_symlink():
                continue
            for target in sorted(base.rglob("*")):
                relative = target.relative_to(directory)
                if len(relative.parts) - 1 > settings.skills_resource_max_depth:
                    continue
                if target.is_file() and not target.is_symlink():
                    resources.append(relative.as_posix())
                    if len(resources) >= _MAX_LISTED_RESOURCES:
                        return tuple(resources)
        return tuple(resources)


class SkillService:
    """面向 Agent 图的 Skill 激活与提示词组装。"""

    def activate(
        self,
        name: str,
        current_activations: list[dict[str, str]],
    ) -> tuple[list[dict[str, str]], SkillDefinition, bool]:
        """激活 Skill，并执行数量与上下文体积限制。"""
        definition = skill_catalog.get(name)
        for activation in current_activations:
            if activation.get("name") == name:
                return current_activations, definition, True
        if len(current_activations) >= settings.skills_max_activations_per_run:
            raise SkillError("单次 Agent 运行激活的 Skill 数量已达上限")
        active_chars = sum(len(item.get("content", "")) for item in current_activations)
        if active_chars + len(definition.content) > settings.skills_max_active_chars:
            raise SkillError("激活 Skill 后的上下文长度超过上限")
        updated = [
            *current_activations,
            {
                "name": definition.name,
                "description": definition.description,
                "content": definition.content,
            },
        ]
        return updated, definition, False

    def active_prompt(self, activations: list[dict[str, str]]) -> str:
        """生成当前运行已激活 Skill 的二级渐进披露内容。"""
        if not activations:
            return ""
        parts = [
            "<active_skills>",
            "以下 Skill 已在当前运行中激活并可直接使用，不要再次调用 activate_skill。",
        ]
        for activation in activations:
            parts.extend(
                [
                    f'<skill_content name="{escape(activation.get("name", ""), quote=True)}">',
                    activation.get("content", ""),
                    "</skill_content>",
                ]
            )
        parts.append("</active_skills>")
        return "\n".join(parts)


skill_catalog = SkillCatalog()
skill_service = SkillService()
