"""
代码问题数据模型
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class IssueSeverity(Enum):
    """问题严重程度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueType(Enum):
    """问题类型"""
    LONG_FUNCTION = "long_function"
    HIGH_COMPLEXITY = "high_complexity"
    DUPLICATE_CODE = "duplicate_code"
    LONG_LINE = "long_line"
    TOO_MANY_PARAMETERS = "too_many_parameters"
    DEEP_NESTING = "deep_nesting"
    MAGIC_NUMBER = "magic_number"
    UNUSED_IMPORT = "unused_import"
    LARGE_CLASS = "large_class"


@dataclass
class CodeIssue:
    """代码问题"""
    file_path: str
    issue_type: IssueType
    severity: IssueSeverity
    line_number: int
    description: str
    suggestion: str
    code_snippet: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "file_path": self.file_path,
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "line_number": self.line_number,
            "description": self.description,
            "suggestion": self.suggestion,
            "code_snippet": self.code_snippet,
        }
