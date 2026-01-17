"""
报告生成器模块
"""

from typing import List
from models import CodeIssue, Severity


class Reporter:
    """报告生成器"""
    
    @staticmethod
    def generate_report(results: dict, output_format: str = "text") -> str:
        """
        生成格式化的报告
        
        Args:
            results: 分析结果字典 {file_path: [CodeIssue]}
            output_format: 输出格式 (text, markdown, json)
            
        Returns:
            str: 格式化的报告
        """
        if output_format == "markdown":
            return Reporter._generate_markdown_report(results)
        elif output_format == "json":
            return Reporter._generate_json_report(results)
        else:
            return Reporter._generate_text_report(results)
    
    @staticmethod
    def _generate_text_report(results: dict) -> str:
        """生成文本格式报告"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("RefactorSuggest 代码重构建议报告")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        total_issues = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        
        for file_path, issues in results.items():
            if not issues:
                continue
                
            total_issues += len(issues)
            report_lines.append(f"文件: {file_path}")
            report_lines.append("-" * 80)
            
            # 按严重程度排序
            sorted_issues = sorted(issues, key=lambda x: (
                {"高": 0, "中": 1, "低": 2}[x.severity.value],
                x.line_number
            ))
            
            for issue in sorted_issues:
                if issue.severity == Severity.HIGH:
                    high_count += 1
                elif issue.severity == Severity.MEDIUM:
                    medium_count += 1
                else:
                    low_count += 1
                
                report_lines.append(f"\n  [严重程度: {issue.severity.value}] {issue.description}")
                report_lines.append(f"  类型: {issue.issue_type}")
                report_lines.append(f"  行号: {issue.line_number}")
                if issue.details:
                    report_lines.append(f"  详情: {issue.details}")
                report_lines.append(f"  建议: {issue.recommendation}")
            
            report_lines.append("\n")
        
        # 统计信息
        report_lines.append("=" * 80)
        report_lines.append("统计摘要")
        report_lines.append("=" * 80)
        report_lines.append(f"分析文件数: {len(results)}")
        report_lines.append(f"发现问题总数: {total_issues}")
        report_lines.append(f"  - 高严重程度: {high_count}")
        report_lines.append(f"  - 中严重程度: {medium_count}")
        report_lines.append(f"  - 低严重程度: {low_count}")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    @staticmethod
    def _generate_markdown_report(results: dict) -> str:
        """生成 Markdown 格式报告"""
        report_lines = []
        report_lines.append("# RefactorSuggest 代码重构建议报告\n")
        
        total_issues = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        
        for file_path, issues in results.items():
            if not issues:
                continue
                
            total_issues += len(issues)
            report_lines.append(f"## 文件: `{file_path}`\n")
            
            # 按严重程度排序
            sorted_issues = sorted(issues, key=lambda x: (
                {"高": 0, "中": 1, "低": 2}[x.severity.value],
                x.line_number
            ))
            
            for issue in sorted_issues:
                if issue.severity == Severity.HIGH:
                    high_count += 1
                elif issue.severity == Severity.MEDIUM:
                    medium_count += 1
                else:
                    low_count += 1
                
                severity_badge = {
                    "高": "🔴",
                    "中": "🟡",
                    "低": "🟢"
                }.get(issue.severity.value, "⚪")
                
                report_lines.append(f"### {severity_badge} {issue.description}")
                report_lines.append(f"- **类型**: {issue.issue_type}")
                report_lines.append(f"- **行号**: {issue.line_number}")
                if issue.details:
                    report_lines.append(f"- **详情**: {issue.details}")
                report_lines.append(f"- **建议**: {issue.recommendation}")
                report_lines.append("")
        
        # 统计信息
        report_lines.append("---\n")
        report_lines.append("## 统计摘要\n")
        report_lines.append(f"- 分析文件数: {len(results)}")
        report_lines.append(f"- 发现问题总数: {total_issues}")
        report_lines.append(f"  - 🔴 高严重程度: {high_count}")
        report_lines.append(f"  - 🟡 中严重程度: {medium_count}")
        report_lines.append(f"  - 🟢 低严重程度: {low_count}")
        
        return "\n".join(report_lines)
    
    @staticmethod
    def _generate_json_report(results: dict) -> str:
        """生成 JSON 格式报告"""
        import json
        
        report_data = {
            "summary": {
                "total_files": len(results),
                "total_issues": sum(len(issues) for issues in results.values()),
                "severity_counts": {
                    "high": 0,
                    "medium": 0,
                    "low": 0
                }
            },
            "files": {}
        }
        
        for file_path, issues in results.items():
            file_issues = []
            for issue in issues:
                if issue.severity == Severity.HIGH:
                    report_data["summary"]["severity_counts"]["high"] += 1
                elif issue.severity == Severity.MEDIUM:
                    report_data["summary"]["severity_counts"]["medium"] += 1
                else:
                    report_data["summary"]["severity_counts"]["low"] += 1
                
                file_issues.append({
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "recommendation": issue.recommendation,
                    "line_number": issue.line_number,
                    "issue_type": issue.issue_type,
                    "details": issue.details
                })
            
            report_data["files"][file_path] = file_issues
        
        return json.dumps(report_data, ensure_ascii=False, indent=2)
    
    @staticmethod
    def save_report(report: str, output_file: str):
        """
        保存报告到文件
        
        Args:
            report: 报告内容
            output_file: 输出文件路径
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {output_file}")
