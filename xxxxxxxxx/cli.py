"""
命令行接口模块

提供命令行工具来使用 RefactorSuggest
"""

import argparse
import sys
import os
from pathlib import Path
from typing import List

# 处理相对导入
try:
    from .analyzer import CodeAnalyzer
    from .smell_detector import SmellDetector
    from .suggester import RefactorSuggester
    from .reporter import ReportGenerator
except ImportError:
    from analyzer import CodeAnalyzer
    from smell_detector import SmellDetector
    from suggester import RefactorSuggester
    from reporter import ReportGenerator


def parse_args():
    """
    解析命令行参数
    
    Returns:
        解析后的参数
    """
    parser = argparse.ArgumentParser(
        description='RefactorSuggest - Python代码重构建议工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  分析单个文件:
    python -m RefactorSuggest file.py
  
  分析多个文件:
    python -m RefactorSuggest file1.py file2.py file3.py
  
  分析整个目录:
    python -m RefactorSuggest --dir ./src
  
  保存报告到文件:
    python -m RefactorSuggest file.py --output report.txt
  
  生成 Markdown 格式报告:
    python -m RefactorSuggest file.py --format markdown --output report.md
  
  生成 JSON 格式报告:
    python -m RefactorSuggest file.py --format json --output report.json
        """
    )
    
    parser.add_argument(
        'files',
        nargs='*',
        help='要分析的Python文件路径'
    )
    
    parser.add_argument(
        '--dir',
        type=str,
        help='分析指定目录下的所有Python文件'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='输出报告到指定文件'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        choices=['text', 'markdown', 'json'],
        default='text',
        help='报告格式 (默认: text)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细输出'
    )
    
    parser.add_argument(
        '--severity',
        type=str,
        choices=['high', 'medium', 'low', 'all'],
        default='all',
        help='只显示指定严重程度的问题 (默认: all)'
    )
    
    return parser.parse_args()


def get_python_files(directory: str) -> List[str]:
    """
    获取目录中的所有Python文件
    
    Args:
        directory: 目录路径
        
    Returns:
        Python文件路径列表
    """
    python_files = []
    path = Path(directory)
    
    if not path.exists():
        print(f"错误: 目录不存在: {directory}", file=sys.stderr)
        return python_files
    
    if not path.is_dir():
        print(f"错误: 不是目录: {directory}", file=sys.stderr)
        return python_files
    
    # 递归查找所有 .py 文件
    for file_path in path.rglob('*.py'):
        # 跳过 __pycache__ 目录
        if '__pycache__' not in str(file_path):
            python_files.append(str(file_path))
    
    return sorted(python_files)


def analyze_file(file_path: str, verbose: bool = False) -> List:
    """
    分析单个Python文件
    
    Args:
        file_path: 文件路径
        verbose: 是否显示详细输出
        
    Returns:
        问题列表
    """
    if verbose:
        print(f"正在分析: {file_path}")
    
    try:
        # 分析代码
        analyzer = CodeAnalyzer(file_path)
        metrics = analyzer.analyze()
        
        # 检测代码异味
        detector = SmellDetector()
        smells = detector.detect(metrics)
        
        # 生成重构建议
        suggester = RefactorSuggester()
        issues = suggester.suggest(smells)
        
        return issues
        
    except FileNotFoundError:
        print(f"错误: 文件不存在: {file_path}", file=sys.stderr)
        return []
    except SyntaxError as e:
        print(f"错误: 语法错误 {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"错误: 分析失败 {file_path}: {e}", file=sys.stderr)
        return []


def filter_issues_by_severity(issues: List, severity: str) -> List:
    """
    根据严重程度过滤问题
    
    Args:
        issues: 问题列表
        severity: 严重程度阈值 (high, medium, low, all)
        
    Returns:
        过滤后的问题列表
    """
    try:
        from .issue import IssueSeverity
    except ImportError:
        from issue import IssueSeverity
    
    if severity == 'all':
        return issues
    
    severity_map = {
        'high': [IssueSeverity.HIGH],
        'medium': [IssueSeverity.HIGH, IssueSeverity.MEDIUM],
        'low': [IssueSeverity.HIGH, IssueSeverity.MEDIUM, IssueSeverity.LOW]
    }
    
    allowed_severities = severity_map.get(severity, [])
    return [issue for issue in issues if issue.severity in allowed_severities]


def main():
    """主函数"""
    args = parse_args()
    
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
        print("使用 --help 查看帮助信息", file=sys.stderr)
        sys.exit(1)
    
    # 分析所有文件
    all_issues = []
    for file_path in files_to_analyze:
        issues = analyze_file(file_path, args.verbose)
        all_issues.extend(issues)
    
    # 根据严重程度过滤
    all_issues = filter_issues_by_severity(all_issues, args.severity)
    
    # 生成报告
    reporter = ReportGenerator()
    
    if args.output:
        # 保存报告到文件
        try:
            reporter.save_report(all_issues, args.output, args.format)
            print(f"报告已保存到: {args.output}")
            
            # 同时在控制台显示摘要
            if args.verbose:
                print("\n" + "=" * 80)
                print(reporter.generate_text_report(all_issues))
        except Exception as e:
            print(f"错误: 保存报告失败: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # 在控制台显示报告
        if args.format == 'text':
            print(reporter.generate_text_report(all_issues))
        elif args.format == 'markdown':
            print(reporter.generate_markdown_report(all_issues))
        elif args.format == 'json':
            print(reporter.generate_json_report(all_issues))
    
    # 根据问题数量设置退出码
    high_count = len([i for i in all_issues if i.severity.value == 'high'])
    if high_count > 0:
        sys.exit(1)  # 有高严重度问题
    else:
        sys.exit(0)  # 无问题或只有中低严重度问题


if __name__ == '__main__':
    main()
