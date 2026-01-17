"""
数据模型定义
"""

from enum import Enum
from dataclasses import dataclass


class Severity(Enum):
    """问题严重程度"""
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


@dataclass
class CodeIssue:
    """代码问题"""
    severity: Severity
    description: str
    recommendation: str
    line_number: int
    issue_type: str
    details: str = ""
