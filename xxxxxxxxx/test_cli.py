#!/usr/bin/env python
"""
测试命令行功能
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import CodeAnalyzer
from smell_detector import SmellDetector
from suggester import RefactorSuggester
from reporter import ReportGenerator
from issue import IssueSeverity

# 测试文件
test_file = "tests/test_example.py"

# 分析代码
analyzer = CodeAnalyzer(test_file)
metrics = analyzer.analyze()

# 检测代码异味
detector = SmellDetector()
smells = detector.detect(metrics)

# 生成重构建议
suggester = RefactorSuggester()
issues = suggester.suggest(smells)

# 过滤高严重度问题
high_issues = [i for i in issues if i.severity == IssueSeverity.HIGH]

# 生成报告
reporter = ReportGenerator()

print("=" * 80)
print("【文本格式报告】")
print("=" * 80)
print(reporter.generate_text_report(high_issues))

print("\n" + "=" * 80)
print("【Markdown 格式报告】")
print("=" * 80)
md_report = reporter.generate_markdown_report(high_issues)
print(md_report[:800] + "...\n")

print("=" * 80)
print("【JSON 格式报告】")
print("=" * 80)
json_report = reporter.generate_json_report(high_issues)
print(json_report[:600] + "...\n")

# 保存报告
reporter.save_report(high_issues, "report.txt", "text")
reporter.save_report(high_issues, "report.md", "markdown")
reporter.save_report(high_issues, "report.json", "json")

print("报告已保存到:")
print("  - report.txt (文本格式)")
print("  - report.md (Markdown格式)")
print("  - report.json (JSON格式)")
