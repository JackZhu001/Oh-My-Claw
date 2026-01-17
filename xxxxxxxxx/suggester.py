"""
重构建议生成器模块

根据检测到的代码异味，生成具体的重构建议。
"""

from typing import List

# 处理相对导入
try:
    from .smell_detector import CodeSmell, SmellType
    from .issue import CodeIssue, IssueSeverity, IssueType
except ImportError:
    from smell_detector import CodeSmell, SmellType
    from issue import CodeIssue, IssueSeverity, IssueType


class RefactorSuggester:
    """重构建议生成器"""
    
    # 代码异味类型到问题类型的映射
    SMELL_TO_ISSUE_TYPE = {
        SmellType.LONG_FUNCTION: IssueType.LONG_FUNCTION,
        SmellType.HIGH_COMPLEXITY: IssueType.HIGH_COMPLEXITY,
        SmellType.TOO_MANY_PARAMETERS: IssueType.TOO_MANY_PARAMETERS,
        SmellType.DEEP_NESTING: IssueType.DEEP_NESTING,
        SmellType.DUPLICATE_CODE: IssueType.DUPLICATE_CODE,
        SmellType.MISSING_DOCSTRING: IssueType.LONG_LINE,
        SmellType.LARGE_CLASS: IssueType.LARGE_CLASS,
    }
    
    # 严重程度映射
    SEVERITY_MAP = {
        "高": IssueSeverity.HIGH,
        "中": IssueSeverity.MEDIUM,
        "低": IssueSeverity.LOW,
    }
    
    def __init__(self):
        """初始化建议生成器"""
        self.suggestion_templates = self._load_suggestion_templates()
    
    def _load_suggestion_templates(self) -> dict:
        """
        加载重构建议模板
        
        Returns:
            建议模板字典
        """
        return {
            SmellType.LONG_FUNCTION: {
                "description": "函数过长，难以理解和维护",
                "suggestions": [
                    "将函数拆分为多个更小的函数，每个函数只做一件事",
                    "提取重复的代码块为独立函数",
                    "使用策略模式或命令模式替代长函数",
                    "考虑使用类来封装相关的数据和操作"
                ]
            },
            SmellType.HIGH_COMPLEXITY: {
                "description": "圈复杂度过高，逻辑过于复杂",
                "suggestions": [
                    "使用卫语句(Guard Clauses)减少嵌套层级",
                    "提取复杂条件为独立的判断函数",
                    "使用多态替代复杂的条件判断",
                    "将复杂的布尔表达式拆分为多个有意义的变量"
                ]
            },
            SmellType.TOO_MANY_PARAMETERS: {
                "description": "参数过多，函数调用复杂",
                "suggestions": [
                    "引入参数对象，将相关参数封装为一个类或字典",
                    "使用建造者模式(Builder Pattern)",
                    "考虑使用可变参数(*args, **kwargs)",
                    "重新设计函数职责，减少不必要的参数"
                ]
            },
            SmellType.DEEP_NESTING: {
                "description": "嵌套层级过深，代码可读性差",
                "suggestions": [
                    "使用卫语句提前返回",
                    "提取嵌套代码为独立函数",
                    "使用多态替代条件判断",
                    "考虑使用状态模式"
                ]
            },
            SmellType.DUPLICATE_CODE: {
                "description": "存在重复代码，维护成本高",
                "suggestions": [
                    "提取重复代码为独立函数",
                    "使用模板方法模式",
                    "考虑使用继承或组合来共享代码",
                    "将重复逻辑抽象为工具函数"
                ]
            },
            SmellType.MISSING_DOCSTRING: {
                "description": "缺少文档字符串，影响代码可读性",
                "suggestions": [
                    "为函数添加清晰的文档字符串，说明功能、参数和返回值",
                    "遵循 Google 或 NumPy 风格的文档字符串格式",
                    "确保文档字符串与代码实现保持一致"
                ]
            },
            SmellType.LARGE_CLASS: {
                "description": "类过大，承担了过多职责",
                "suggestions": [
                    "使用单一职责原则，将大类拆分为多个小类",
                    "提取相关方法到辅助类",
                    "考虑使用组合替代继承",
                    "将数据和行为分离"
                ]
            }
        }
    
    def suggest(self, smells: List[CodeSmell]) -> List[CodeIssue]:
        """
        为代码异味生成重构建议
        
        Args:
            smells: 代码异味列表
            
        Returns:
            代码问题列表
        """
        issues = []
        
        for smell in smells:
            issue = self._convert_smell_to_issue(smell)
            issues.append(issue)
        
        return issues
    
    def _convert_smell_to_issue(self, smell: CodeSmell) -> CodeIssue:
        """
        将代码异味转换为代码问题
        
        Args:
            smell: 代码异味
            
        Returns:
            代码问题
        """
        # 获取建议模板
        template = self.suggestion_templates.get(smell.smell_type, {})
        
        # 生成具体建议
        if template and "suggestions" in template:
            # 根据严重程度选择建议
            suggestions = template["suggestions"]
            if suggestions:
                suggestion = suggestions[0]  # 取第一个建议
                if len(suggestions) > 1:
                    suggestion += f"\n其他建议: {'; '.join(suggestions[1:])}"
            else:
                suggestion = "请参考最佳实践进行重构"
        else:
            suggestion = "请参考最佳实践进行重构"
        
        # 获取描述
        description = template.get("description", smell.description)
        
        # 映射严重程度
        severity = self.SEVERITY_MAP.get(smell.severity.value, IssueSeverity.MEDIUM)
        
        # 映射问题类型
        issue_type = self.SMELL_TO_ISSUE_TYPE.get(
            smell.smell_type,
            IssueType.LONG_FUNCTION
        )
        
        # 提取代码片段（如果有）
        code_snippet = None
        if smell.details and "code_snippet" in smell.details:
            code_snippet = smell.details["code_snippet"]
        
        return CodeIssue(
            file_path=smell.file_path,
            issue_type=issue_type,
            severity=severity,
            line_number=smell.start_line,
            description=description,
            suggestion=suggestion,
            code_snippet=code_snippet
        )
    
    def generate_detailed_suggestion(self, smell: CodeSmell) -> dict:
        """
        生成详细的重构建议
        
        Args:
            smell: 代码异味
            
        Returns:
            详细建议字典
        """
        template = self.suggestion_templates.get(smell.smell_type, {})
        
        return {
            "smell_type": smell.smell_type.value,
            "severity": smell.severity.value,
            "location": f"{smell.file_path}:{smell.start_line}-{smell.end_line}",
            "description": template.get("description", smell.description),
            "suggestions": template.get("suggestions", []),
            "details": smell.details,
            "refactoring_techniques": self._get_refactoring_techniques(smell.smell_type)
        }
    
    def _get_refactoring_techniques(self, smell_type: SmellType) -> List[str]:
        """
        获取适用于特定代码异味的重构技术
        
        Args:
            smell_type: 代码异味类型
            
        Returns:
            重构技术列表
        """
        techniques = {
            SmellType.LONG_FUNCTION: [
                "Extract Method (提取方法)",
                "Replace Temp with Query (以查询替代临时变量)",
                "Introduce Parameter Object (引入参数对象)",
                "Replace Method with Method Object (以方法对象替代方法)"
            ],
            SmellType.HIGH_COMPLEXITY: [
                "Decompose Conditional (分解条件表达式)",
                "Consolidate Conditional Expression (合并条件表达式)",
                "Replace Conditional with Polymorphism (以多态替代条件式)",
                "Introduce Null Object (引入Null对象)"
            ],
            SmellType.TOO_MANY_PARAMETERS: [
                "Introduce Parameter Object (引入参数对象)",
                "Preserve Whole Object (保持对象完整)",
                "Replace Parameter with Methods (以方法替代参数)"
            ],
            SmellType.DEEP_NESTING: [
                "Replace Nested Conditional with Guard Clauses (以卫语句替代嵌套条件)",
                "Decompose Conditional (分解条件表达式)",
                "Consolidate Duplicate Conditional Fragments (合并重复的条件片段)"
            ],
            SmellType.DUPLICATE_CODE: [
                "Extract Method (提取方法)",
                "Pull Up Method (方法上移)",
                "Form Template Method (塑造模板方法)",
                "Replace Inheritance with Delegation (用委托替代继承)"
            ],
            SmellType.MISSING_DOCSTRING: [
                "Add Documentation (添加文档)",
                "Rename Method (重命名方法)",
                "Introduce Assertion (引入断言)"
            ],
            SmellType.LARGE_CLASS: [
                "Extract Class (提炼类)",
                "Extract Subclass (提炼子类)",
                "Extract Interface (提炼接口)",
                "Decompose Conditional (分解条件)"
            ]
        }
        
        return techniques.get(smell_type, [])
