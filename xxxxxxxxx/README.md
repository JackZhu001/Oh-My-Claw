# RefactorSuggest - Python代码重构建议工具

一个强大的Python代码质量分析工具，能够检测代码异味并提供具体的重构建议。

## 功能特性

- ✅ 分析指定Python文件的代码质量
- ✅ 检测常见代码异味：
  - 过长函数
  - 过高圈复杂度
  - 重复代码
  - 过多参数
  - 过深嵌套
  - 过长列表/字典/集合
- ✅ 生成具体的重构建议
- ✅ 支持一次性分析多个文件
- ✅ 输出格式化报告，包含：
  - 问题严重程度（高/中/低）
  - 具体问题描述
  - 推荐的重构方案
  - 涉及的代码行号

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 命令行使用

分析单个文件：
```bash
python -m RefactorSuggest your_file.py
```

分析多个文件：
```bash
python -m RefactorSuggest file1.py file2.py file3.py
```

分析整个目录：
```bash
python -m RefactorSuggest --dir ./src
```

### 作为模块使用

```python
from RefactorSuggest import CodeAnalyzer, SmellDetector, RefactorSuggester, ReportGenerator

# 分析代码
analyzer = CodeAnalyzer('your_file.py')
metrics = analyzer.analyze()

# 检测代码异味
detector = SmellDetector()
issues = detector.detect(metrics)

# 生成重构建议
suggester = RefactorSuggester()
suggestions = suggester.suggest(issues)

# 生成报告
reporter = ReportGenerator()
report = reporter.generate(suggestions)
print(report)
```

## 输出示例

```
╔══════════════════════════════════════════════════════════════════╗
║                    RefactorSuggest 分析报告                      ║
╚══════════════════════════════════════════════════════════════════╝

文件: example.py
───────────────────────────────────────────────────────────────────

[🔴 高严重度] 函数过长
   位置: 第 15-67 行
   描述: 函数 process_data() 长度为 52 行，超过推荐值 30 行
   建议: 将函数拆分为多个更小的函数，每个函数只做一件事

[🟡 中严重度] 圈复杂度过高
   位置: 第 23-45 行
   描述: 函数 validate_input() 的圈复杂度为 12，超过推荐值 10
   建议: 使用卫语句(Guard Clauses)减少嵌套层级，或提取复杂条件

[🟢 低严重度] 重复代码
   位置: 第 30-35 行, 第 50-55 行
   描述: 检测到 5 行重复代码块
   建议: 提取重复代码为独立函数

───────────────────────────────────────────────────────────────────
总计: 3 个问题 (1 高, 1 中, 1 低)
```

## 项目结构

```
RefactorSuggest/
├── __init__.py           # 包初始化
├── analyzer.py           # 代码分析器
├── smell_detector.py     # 代码异味检测器
├── suggester.py          # 重构建议生成器
├── reporter.py           # 报告生成器
├── cli.py                # 命令行接口
├── requirements.txt      # 依赖列表
└── README.md            # 项目说明
```

## 许可证

MIT License
