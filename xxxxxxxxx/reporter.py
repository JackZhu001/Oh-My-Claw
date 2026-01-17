"""
报告生成器 - 生成格式化的分析报告
"""

from typing import List
from datetime import datetime

# 处理相对导入
try:
    from .issue import CodeIssue, IssueSeverity
except ImportError:
    from issue import CodeIssue, IssueSeverity


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        self.severity_order = {
            IssueSeverity.HIGH: 0,
            IssueSeverity.MEDIUM: 1,
            IssueSeverity.LOW: 2,
        }
    
    def generate_text_report(self, issues: List[CodeIssue]) -> str:
        """
        生成文本格式的报告
        
        Args:
            issues: 问题列表
            
        Returns:
            str: 格式化的报告文本
        """
        if not issues:
            return "未发现代码问题！代码质量良好。"
        
        # 按严重程度和文件路径排序
        sorted_issues = sorted(
            issues,
            key=lambda x: (self.severity_order[x.severity], x.file_path, x.line_number)
        )
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("代码重构建议报告")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        report_lines.append(f"共发现 {len(issues)} 个问题")
        report_lines.append("")
        
        # 按严重程度分组
        high_issues = [i for i in sorted_issues if i.severity == IssueSeverity.HIGH]
        medium_issues = [i for i in sorted_issues if i.severity == IssueSeverity.MEDIUM]
        low_issues = [i for i in sorted_issues if i.severity == IssueSeverity.LOW]
        
        if high_issues:
            report_lines.append("【高严重程度问题】")
            report_lines.append("-" * 80)
            for issue in high_issues:
                report_lines.extend(self._format_issue(issue))
                report_lines.append("")
        
        if medium_issues:
            report_lines.append("【中严重程度问题】")
            report_lines.append("-" * 80)
            for issue in medium_issues:
                report_lines.extend(self._format_issue(issue))
                report_lines.append("")
        
        if low_issues:
            report_lines.append("【低严重程度问题】")
            report_lines.append("-" * 80)
            for issue in low_issues:
                report_lines.extend(self._format_issue(issue))
                report_lines.append("")
        
        # 统计信息
        report_lines.append("=" * 80)
        report_lines.append("问题统计:")
        report_lines.append(f"  高: {len(high_issues)} 个")
        report_lines.append(f"  中: {len(medium_issues)} 个")
        report_lines.append(f"  低: {len(low_issues)} 个")
        report_lines.append("=" * 80)
        
        return '\n'.join(report_lines)
    
    def _format_issue(self, issue: CodeIssue) -> List[str]:
        """格式化单个问题"""
        lines = []
        lines.append(f"文件: {issue.file_path}:{issue.line_number}")
        lines.append(f"严重程度: {issue.severity.value.upper()}")
        lines.append(f"问题类型: {issue.issue_type.value}")
        lines.append(f"描述: {issue.description}")
        lines.append(f"建议: {issue.suggestion}")
        if issue.code_snippet:
            lines.append(f"代码片段:")
            lines.append("  " + issue.code_snippet.replace('\n', '\n  '))
        return lines
    
    def generate_markdown_report(self, issues: List[CodeIssue]) -> str:
        """
        生成 Markdown 格式的报告
        
        Args:
            issues: 问题列表
            
        Returns:
            str: Markdown 格式的报告
        """
        if not issues:
            return "未发现代码问题！代码质量良好。"
        
        sorted_issues = sorted(
            issues,
            key=lambda x: (self.severity_order[x.severity], x.file_path, x.line_number)
        )
        
        report_lines = []
        report_lines.append("# 代码重构建议报告")
        report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"\n共发现 {len(issues)} 个问题\n")
        
        high_issues = [i for i in sorted_issues if i.severity == IssueSeverity.HIGH]
        medium_issues = [i for i in sorted_issues if i.severity == IssueSeverity.MEDIUM]
        low_issues = [i for i in sorted_issues if i.severity == IssueSeverity.LOW]
        
        if high_issues:
            report_lines.append("## 🔴 高严重程度问题")
            report_lines.append("")
            for issue in high_issues:
                report_lines.extend(self._format_markdown_issue(issue))
        
        if medium_issues:
            report_lines.append("## 🟡 中严重程度问题")
            report_lines.append("")
            for issue in medium_issues:
                report_lines.extend(self._format_markdown_issue(issue))
        
        if low_issues:
            report_lines.append("## 🟢 低严重程度问题")
            report_lines.append("")
            for issue in low_issues:
                report_lines.extend(self._format_markdown_issue(issue))
        
        report_lines.append("## 📊 问题统计")
        report_lines.append(f"- 🔴 高: {len(high_issues)} 个")
        report_lines.append(f"- 🟡 中: {len(medium_issues)} 个")
        report_lines.append(f"- 🟢 低: {len(low_issues)} 个")
        
        return '\n'.join(report_lines)
    
    def _format_markdown_issue(self, issue: CodeIssue) -> List[str]:
        """格式化单个问题为 Markdown"""
        lines = []
        lines.append(f"### {issue.file_path}:{issue.line_number}")
        lines.append("")
        lines.append(f"- **严重程度**: {issue.severity.value.upper()}")
        lines.append(f"- **问题类型**: {issue.issue_type.value}")
        lines.append(f"- **描述**: {issue.description}")
        lines.append(f"- **建议**: {issue.suggestion}")
        if issue.code_snippet:
            lines.append(f"- **代码片段**:")
            lines.append("```python")
            lines.append(issue.code_snippet)
            lines.append("```")
        lines.append("")
        return lines
    
    def generate_json_report(self, issues: List[CodeIssue]) -> str:
        """
        生成 JSON 格式的报告
        
        Args:
            issues: 问题列表
            
        Returns:
            str: JSON 格式的报告
        """
        import json
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_issues": len(issues),
            "issues": [issue.to_dict() for issue in issues],
            "summary": {
                "high": len([i for i in issues if i.severity == IssueSeverity.HIGH]),
                "medium": len([i for i in issues if i.severity == IssueSeverity.MEDIUM]),
                "low": len([i for i in issues if i.severity == IssueSeverity.LOW]),
            }
        }
        
        return json.dumps(report, indent=2, ensure_ascii=False)
    
    def save_report(self, issues: List[CodeIssue], output_path: str, format: str = "text"):
        """
        保存报告到文件
        
        Args:
            issues: 问题列表
            output_path: 输出文件路径
            format: 报告格式 (text, markdown, json)
        """
        if format == "text":
            content = self.generate_text_report(issues)
        elif format == "markdown":
            content = self.generate_markdown_report(issues)
        elif format == "json":
            content = self.generate_json_report(issues)
        else:
            raise ValueError(f"不支持的格式: {format}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
