"""
RefactorSuggest 工具测试脚本
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from xxxxxxxxx.analyzer import CodeAnalyzer
from xxxxxxxxx.smell_detector import SmellDetector
from xxxxxxxxx.suggester import RefactorSuggester
from xxxxxxxxx.reporter import ReportGenerator


def test_basic_analysis():
    """测试基本分析功能"""
    print("=" * 80)
    print("测试 1: 基本代码分析")
    print("=" * 80)
    
    test_file = os.path.join(os.path.dirname(__file__), 'test_example.py')
    
    # 分析代码
    analyzer = CodeAnalyzer(test_file)
    metrics = analyzer.analyze()
    
    print(f"\n文件: {metrics.file_path}")
    print(f"总行数: {metrics.total_lines}")
    print(f"代码行数: {metrics.code_lines}")
    print(f"注释行数: {metrics.comment_lines}")
    print(f"空白行数: {metrics.blank_lines}")
    print(f"\n函数数量: {len(metrics.functions)}")
    print(f"类数量: {len(metrics.classes)}")
    print(f"导入数量: {len(metrics.imports)}")
    
    # 显示函数信息
    print("\n函数列表:")
    for func in metrics.functions:
        print(f"  - {func.name}: {func.length} 行, "
              f"复杂度: {func.cyclomatic_complexity}, "
              f"参数: {func.parameter_count}, "
              f"嵌套深度: {func.nesting_depth}")
    
    print("\n✓ 基本分析测试通过\n")


def test_smell_detection():
    """测试代码异味检测"""
    print("=" * 80)
    print("测试 2: 代码异味检测")
    print("=" * 80)
    
    test_file = os.path.join(os.path.dirname(__file__), 'test_example.py')
    
    # 分析代码
    analyzer = CodeAnalyzer(test_file)
    metrics = analyzer.analyze()
    
    # 检测代码异味
    detector = SmellDetector()
    smells = detector.detect(metrics)
    
    print(f"\n检测到 {len(smells)} 个代码异味:\n")
    
    for i, smell in enumerate(smells, 1):
        print(f"{i}. {smell.smell_type.value} [{smell.severity.value}]")
        print(f"   位置: {smell.file_path}:{smell.start_line}-{smell.end_line}")
        print(f"   描述: {smell.description}")
        print()
    
    print("✓ 代码异味检测测试通过\n")


def test_refactor_suggestions():
    """测试重构建议生成"""
    print("=" * 80)
    print("测试 3: 重构建议生成")
    print("=" * 80)
    
    test_file = os.path.join(os.path.dirname(__file__), 'test_example.py')
    
    # 分析代码
    analyzer = CodeAnalyzer(test_file)
    metrics = analyzer.analyze()
    
    # 检测代码异味
    detector = SmellDetector()
    smells = detector.detect(metrics)
    
    # 生成重构建议
    suggester = RefactorSuggester()
    issues = suggester.suggest(smells)
    
    print(f"\n生成 {len(issues)} 个重构建议:\n")
    
    for i, issue in enumerate(issues, 1):
        print(f"{i}. [{issue.severity.value.upper()}] {issue.issue_type.value}")
        print(f"   文件: {issue.file_path}:{issue.line_number}")
        print(f"   描述: {issue.description}")
        print(f"   建议: {issue.suggestion}")
        print()
    
    print("✓ 重构建议生成测试通过\n")


def test_report_generation():
    """测试报告生成"""
    print("=" * 80)
    print("测试 4: 报告生成")
    print("=" * 80)
    
    test_file = os.path.join(os.path.dirname(__file__), 'test_example.py')
    
    # 分析代码
    analyzer = CodeAnalyzer(test_file)
    metrics = analyzer.analyze()
    
    # 检测代码异味
    detector = SmellDetector()
    smells = detector.detect(metrics)
    
    # 生成重构建议
    suggester = RefactorSuggester()
    issues = suggester.suggest(smells)
    
    # 生成报告
    reporter = ReportGenerator()
    
    # 文本格式报告
    print("\n【文本格式报告】")
    print("-" * 80)
    text_report = reporter.generate_text_report(issues)
    print(text_report)
    
    # Markdown 格式报告
    print("\n【Markdown 格式报告】")
    print("-" * 80)
    md_report = reporter.generate_markdown_report(issues)
    print(md_report[:500] + "...\n")
    
    # JSON 格式报告
    print("\n【JSON 格式报告】")
    print("-" * 80)
    json_report = reporter.generate_json_report(issues)
    print(json_report[:500] + "...\n")
    
    print("✓ 报告生成测试通过\n")


def test_multiple_files():
    """测试多文件分析"""
    print("=" * 80)
    print("测试 5: 多文件分析")
    print("=" * 80)
    
    test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 分析 RefactorSuggest 目录下的所有 Python 文件
    import glob
    python_files = glob.glob(os.path.join(test_dir, '*.py'))
    
    print(f"\n找到 {len(python_files)} 个 Python 文件\n")
    
    all_issues = []
    for file_path in python_files:
        try:
            analyzer = CodeAnalyzer(file_path)
            metrics = analyzer.analyze()
            
            detector = SmellDetector()
            smells = detector.detect(metrics)
            
            suggester = RefactorSuggester()
            issues = suggester.suggest(smells)
            
            all_issues.extend(issues)
            print(f"  {os.path.basename(file_path)}: {len(issues)} 个问题")
        except Exception as e:
            print(f"  {os.path.basename(file_path)}: 分析失败 - {e}")
    
    print(f"\n总计: {len(all_issues)} 个问题")
    print("✓ 多文件分析测试通过\n")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("RefactorSuggest 工具测试套件")
    print("=" * 80 + "\n")
    
    try:
        test_basic_analysis()
        test_smell_detection()
        test_refactor_suggestions()
        test_report_generation()
        test_multiple_files()
        
        print("=" * 80)
        print("✓ 所有测试通过！")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    run_all_tests()
