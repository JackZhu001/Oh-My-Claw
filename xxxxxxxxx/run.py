#!/usr/bin/env python
"""
RefactorSuggest 独立运行脚本
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入并执行
import argparse
from analyzer import CodeAnalyzer
from smell_detector import SmellDetector
from suggester import RefactorSuggester
from reporter import ReportGenerator
from issue import IssueSeverity
from pathlib import Path
from typing import List

def get_python_files(directory: str) -> List[str]:
    """获取目录中的所有Python文件"""
    python_files = []
    path = Path(directory)
    
    if not path.exists():
        print(f"错误: 目录不存在: {directory}", file=sys.stderr)
        return python_files
    
    if not path.is_dir():
        print(f"错误: 不是目录: {directory}", file=sys.stderr)
        return python_files
    
    for file_path in path.rglob('*.py'):
        if '__pycache__' not in str(file_path):
            python_files.append(str(file_path))
    
    return sorted(python_files)

def analyze_file(file_path: str, verbose: bool = False) -> List:
    """分析单个Python文件"""
    if verbose:
        print(f"正在分析: {file_path}")
    
    try:
        analyzer = CodeAnalyzer(file_path)
        metrics = analyzer.analyze()
        
        detector = SmellDetector()
        smells = detector.detect(metrics)
        
        suggester = RefactorSuggester()
        issues = suggester.suggest(smells)
        
        return issues
        
    except Exception as e:
        print(f"错误: 分析失败 {file_path}: {e}", file=sys.stderr)
        return []

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='RefactorSuggest - Python代码重构建议工具')
    parser.add_argument('files', nargs='*', help='要分析的Python文件路径')
    parser.add_argument('--dir', type=str, help='分析指定目录下的所有Python文件')
    parser.add_argument('--output', type=str, help='输出报告到指定文件')
    parser.add_argument('--format', type=str, choices=['text', 'markdown', 'json'], default='text', help='报告格式')
    parser.add_argument('--verbose', action='store_true', help='显示详细输出')
    parser.add_argument('--severity', type=str, choices=['high', 'medium', 'low', 'all'], default='all', help='严重程度过滤')
    
    args = parser.parse_args()
    
    # 收集要分析的文件
    files_to_analyze = []
    
    if args.dir:
        files_to_analyze = get_python_files(args.dir)
        if not files_to_analyze:
            print(f"警告: 在目录 {args.dir} 中未找到Python文件", file=sys.stderr)
            sys.exit(1)
    elif args.files:
        files_to_analyze = args.files
    else:
        print("错误: 请指定要分析的文件或使用 --dir 参数", file=sys.stderr)
        sys.exit(1)
    
    # 分析所有文件
    all_issues = []
    for file_path in files_to_analyze:
        issues = analyze_file(file_path, args.verbose)
        all_issues.extend(issues)
    
    # 根据严重程度过滤
    if args.severity != 'all':
        severity_map = {
            'high': [IssueSeverity.HIGH],
            'medium': [IssueSeverity.HIGH, IssueSeverity.MEDIUM],
            'low': [IssueSeverity.HIGH, IssueSeverity.MEDIUM, IssueSeverity.LOW]
        }
        allowed_severities = severity_map.get(args.severity, [])
        all_issues = [issue for issue in all_issues if issue.severity in allowed_severities]
    
    # 生成报告
    reporter = ReportGenerator()
    
    if args.output:
        reporter.save_report(all_issues, args.output, args.format)
        print(f"报告已保存到: {args.output}")
        if args.verbose:
            print("\n" + "=" * 80)
            print(reporter.generate_text_report(all_issues))
    else:
        if args.format == 'text':
            print(reporter.generate_text_report(all_issues))
        elif args.format == 'markdown':
            print(reporter.generate_markdown_report(all_issues))
        elif args.format == 'json':
            print(reporter.generate_json_report(all_issues))
    
    # 设置退出码
    high_count = len([i for i in all_issues if i.severity.value == 'high'])
    sys.exit(1 if high_count > 0 else 0)

if __name__ == '__main__':
    main()
