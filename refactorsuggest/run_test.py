#!/usr/bin/env python3
"""
测试 RefactorSuggest 工具
"""

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

from analyzer import RefactorSuggest
from reporter import Reporter


def main():
    print("=" * 80)
    print("RefactorSuggest - Python 代码重构建议工具测试")
    print("=" * 80)
    print()
    
    # 创建分析器实例
    analyzer = RefactorSuggest()
    
    # 分析测试文件
    test_file = "test_example.py"
    print(f"正在分析文件: {test_file}")
    print()
    
    issues = analyzer.analyze_file(test_file)
    
    # 生成报告
    results = {test_file: issues}
    
    # 生成文本报告
    print("\n生成文本格式报告:")
    print("-" * 80)
    text_report = Reporter.generate_report(results, "text")
    print(text_report)
    
    # 生成 Markdown 报告
    print("\n\n生成 Markdown 格式报告:")
    print("-" * 80)
    md_report = Reporter.generate_report(results, "markdown")
    print(md_report)
    
    # 保存报告
    Reporter.save_report(text_report, "report.txt")
    Reporter.save_report(md_report, "report.md")
    
    print("\n测试完成！")


if __name__ == "__main__":
    main()
