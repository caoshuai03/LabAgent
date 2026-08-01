"""
@author: caoshuai.cs
@date: 2026-07-30 00:00
@description: 长期记忆采用固定注入 USER_PROFILE.md，不再暴露文件搜索工具
"""
from langchain_core.tools import BaseTool


MEMORY_TOOLS: list[BaseTool] = []
