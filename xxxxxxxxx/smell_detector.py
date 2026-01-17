"""
代码异味检测器模块

负责检测各种代码异味，如过长函数、复杂度过高、重复代码等。
"""

from typing import List
from enum import Enum
from dataclasses import dataclass

# 处理相对导入
try:
    from .analyzer import CodeMetrics
except ImportError:
    from analyzer import CodeMetrics


class Severity(Enum):
    """问题严重程度"""
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class SmellType(Enum):
    """代码异味类型"""
    LONG_FUNCTION = "函数过长"
    HIGH_COMPLEXITY = "圈复杂度过高"
    TOO_MANY_PARAMETERS = "参数过多"
    DEEP_NESTING = "嵌套过深"
    DUPLICATE_CODE = "重复代码"
    MISSING_DOCSTRING = "缺少文档字符串"
    LARGE_CLASS = "类过大"


@dataclass
class CodeSmell:
    """代码异味对象"""
    smell_type: SmellType
    severity: Severity
    file_path: str
    start_line: int
    end_line: int
    description: str
    details: dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class SmellDetector:
    """代码异味检测器"""
    
    # 配置阈值
    MAX_FUNCTION_LENGTH = 30
    MAX_COMPLEXITY = 10
    MAX_PARAMETERS = 5
    MAX_NESTING_DEPTH = 4
    MAX_CLASS_METHODS = 15
    
    def __init__(self):
        """初始化检测器"""
        self.smells = []
    
    def detect(self, metrics: CodeMetrics) -> List[CodeSmell]:
        """
        检测代码异味
        
        Args:
            metrics: 代码度量指标
            
        Returns:
            检测到的代码异味列表
        """
        self.smells = []
        
        # 检测函数相关问题
        self._detect_long_functions(metrics)
        self._detect_high_complexity(metrics)
        self._detect_too_many_parameters(metrics)
        self._detect_deep_nesting(metrics)
        self._detect_missing_docstrings(metrics)
        
        # 检测类相关问题
        self._detect_large_classes(metrics)
        
        # 检测重复代码
        self._detect_duplicate_code(metrics)
        
        return self.smells
    
    def _detect_long_functions(self, metrics: CodeMetrics):
        """检测过长的函数"""
        for func in metrics.functions:
            if func.length > self.MAX_FUNCTION_LENGTH:
                severity = Severity.HIGH if func.length > 50 else Severity.MEDIUM
                smell = CodeSmell(
                    smell_type=SmellType.LONG_FUNCTION,
                    severity=severity,
                    file_path=metrics.file_path,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    description=f"函数 {func.name} 长度为 {func.length} 行，超过推荐值 {self.MAX_FUNCTION_LENGTH} 行",
                    details={
                        'function_name': func.name,
                        'actual_length': func.length,
                        'max_length': self.MAX_FUNCTION_LENGTH
                    }
                )
                self.smells.append(smell)
    
    def _detect_high_complexity(self, metrics: CodeMetrics):
        """检测圈复杂度过高的函数"""
        for func in metrics.functions:
            if func.cyclomatic_complexity > self.MAX_COMPLEXITY:
                severity = Severity.HIGH if func.cyclomatic_complexity > 15 else Severity.MEDIUM
                smell = CodeSmell(
                    smell_type=SmellType.HIGH_COMPLEXITY,
                    severity=severity,
                    file_path=metrics.file_path,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    description=f"函数 {func.name} 的圈复杂度为 {func.cyclomatic_complexity}，超过推荐值 {self.MAX_COMPLEXITY}",
                    details={
                        'function_name': func.name,
                        'actual_complexity': func.cyclomatic_complexity,
                        'max_complexity': self.MAX_COMPLEXITY
                    }
                )
                self.smells.append(smell)
    
    def _detect_too_many_parameters(self, metrics: CodeMetrics):
        """检测参数过多的函数"""
        for func in metrics.functions:
            if func.parameter_count > self.MAX_PARAMETERS:
                severity = Severity.MEDIUM
                smell = CodeSmell(
                    smell_type=SmellType.TOO_MANY_PARAMETERS,
                    severity=severity,
                    file_path=metrics.file_path,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    description=f"函数 {func.name} 有 {func.parameter_count} 个参数，超过推荐值 {self.MAX_PARAMETERS}",
                    details={
                        'function_name': func.name,
                        'actual_params': func.parameter_count,
                        'max_params': self.MAX_PARAMETERS
                    }
                )
                self.smells.append(smell)
    
    def _detect_deep_nesting(self, metrics: CodeMetrics):
        """检测嵌套过深的代码"""
        for func in metrics.functions:
            if func.nesting_depth > self.MAX_NESTING_DEPTH:
                severity = Severity.MEDIUM if func.nesting_depth <= 6 else Severity.HIGH
                smell = CodeSmell(
                    smell_type=SmellType.DEEP_NESTING,
                    severity=severity,
                    file_path=metrics.file_path,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    description=f"函数 {func.name} 的最大嵌套深度为 {func.nesting_depth}，超过推荐值 {self.MAX_NESTING_DEPTH}",
                    details={
                        'function_name': func.name,
                        'actual_depth': func.nesting_depth,
                        'max_depth': self.MAX_NESTING_DEPTH
                    }
                )
                self.smells.append(smell)
    
    def _detect_missing_docstrings(self, metrics: CodeMetrics):
        """检测缺少文档字符串的函数"""
        for func in metrics.functions:
            if not func.docstring:
                smell = CodeSmell(
                    smell_type=SmellType.MISSING_DOCSTRING,
                    severity=Severity.LOW,
                    file_path=metrics.file_path,
                    start_line=func.start_line,
                    end_line=func.start_line,
                    description=f"函数 {func.name} 缺少文档字符串",
                    details={
                        'function_name': func.name
                    }
                )
                self.smells.append(smell)
    
    def _detect_large_classes(self, metrics: CodeMetrics):
        """检测过大的类"""
        for cls in metrics.classes:
            if cls.method_count > self.MAX_CLASS_METHODS:
                severity = Severity.MEDIUM
                smell = CodeSmell(
                    smell_type=SmellType.LARGE_CLASS,
                    severity=severity,
                    file_path=metrics.file_path,
                    start_line=cls.start_line,
                    end_line=cls.end_line,
                    description=f"类 {cls.name} 有 {cls.method_count} 个方法，超过推荐值 {self.MAX_CLASS_METHODS}",
                    details={
                        'class_name': cls.name,
                        'actual_methods': cls.method_count,
                        'max_methods': self.MAX_CLASS_METHODS
                    }
                )
                self.smells.append(smell)
    
    def _detect_duplicate_code(self, metrics: CodeMetrics):
        """检测重复代码"""
        for dup in metrics.duplicate_blocks:
            positions = dup['positions']
            if len(positions) > 1:
                severity = Severity.MEDIUM if len(positions) == 2 else Severity.HIGH
                smell = CodeSmell(
                    smell_type=SmellType.DUPLICATE_CODE,
                    severity=severity,
                    file_path=metrics.file_path,
                    start_line=min(positions),
                    end_line=max(positions) + 4,  # 估算结束行
                    description=f"检测到 {len(positions)} 处重复代码块，出现在第 {', '.join(map(str, positions))} 行",
                    details={
                        'duplicate_count': len(positions),
                        'positions': positions,
                        'block_preview': dup['block'][:100]
                    }
                )
                self.smells.append(smell)
