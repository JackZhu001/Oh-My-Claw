"""
命令行接口模块
"""

import argparse
import sys
from .analyzer import RefactorSuggest
from .reporter import Reporter


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="RefactorSuggest - Python 代码重构建议工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s file.py                    # 分析单个文件
  %(prog)s file1.py file2.py          # 分析多个文件
  %(prog)s -d src/                    # 分析整个目录
  %(prog)s -d src/ -o report.md       # 生成 Markdown 报告
  %(prog)s -d src/ -f json -o report.json  # 生成 JSON 报告
        """
    )
    
    parser.add_argument(
        "files",
        nargs="*",
        help="要分析的 Python 文件路径"
    )
    
    parser.add_argument(
        "-d", "--directory",
        help="分析指定目录中的所有 Python 文件"
    )
    
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        default=True,
        help="递归分析子目录（默认开启）"
    )
    
    parser.add_argument(
        "-f", "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="报告格式（默认: text）"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出报告到指定文件"
    )
    
    parser.add_argument(
        "--max-length",
        type=int,
        default=50,
        help="函数最大行数阈值（默认: 50）"
    )
    
    parser.add_argument(
        "--max-complexity",
        type=int,
        default=10,
        help="圈复杂度阈值（默认: 10）"
    )
    
    parser.add_argument(
        "--max-params",
        type=int,
        default=5,
        help="函数参数数量阈值（默认: 5）"
    )
    
    args = parser.parse_args()
    
    # 创建分析器实例
    analyzer = RefactorSuggest()
    analyzer.max_function_length = args.max_length
    analyzer.max_complexity = args.max_complexity
    analyzer.max_param_count = args.max_params
    
    # 执行分析
    results = {}
    
    if args.directory:
        print(f"正在分析目录: {args.directory}")
        results = analyzer.analyze_directory(args.directory, args.recursive)
    elif args.files:
        print(f"正在分析 {len(args.files)} 个文件...")
        results = analyzer.analyze_multiple_files(args.files)
    else:
        parser.print_help()
        sys.exit(1)
    
    # 生成报告
    print("\n生成报告...")
    report = Reporter.generate_report(results, args.format)
    
    # 输出报告
    if args.output:
        Reporter.save_report(report, args.output)
    else:
        print("\n" + report)


if __name__ == "__main__":
    main()
