"""
RefactorSuggest - Python代码重构建议工具

该工具用于分析Python代码质量，检测代码异味，并提供具体的重构建议。
"""

__version__ = "1.0.0"
__author__ = "CodeMate"

from .analyzer import CodeAnalyzer
from .smell_detector import SmellDetector
from .suggester import RefactorSuggester
from .reporter import ReportGenerator
from .cli import main

__all__ = [
    'CodeAnalyzer',
    'SmellDetector',
    'RefactorSuggester',
    'ReportGenerator',
    'main',
    'cli'
]
