#!/usr/bin/env python3
"""
RefactorSuggest - Python 代码重构建议工具

该工具分析 Python 文件的代码质量，检测常见代码异味，并生成具体的重构建议。
"""

from .analyzer import RefactorSuggest
from .models import CodeIssue, Severity

__version__ = "1.0.0"
__all__ = ["RefactorSuggest", "CodeIssue", "Severity"]
