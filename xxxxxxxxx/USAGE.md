# RefactorSuggest 使用指南

## 快速开始

### 1. 作为 Python 模块使用

```python
from analyzer import CodeAnalyzer
from smell_detector import SmellDetector
from suggester import RefactorSuggester
from reporter import ReportGenerator

# 分析代码
analyzer = CodeAnalyzer('your_file.py')
metrics = analyzer.analyze()

# 检测代码异味
detector = SmellDetector()
smells = detector.detect(metrics)

# 生成重构建议
suggester = RefactorSuggester()
issues = suggester.suggest(smells)

# 生成报告
reporter = ReportGenerator()
print(reporter.generate_text_report(issues))
```

### 2. 命令行使用

```bash
# 分析单个文件
python run.py your_file.py

# 只显示高严重度问题
python run.py your_file.py --severity high

# 分析多个文件
python run.py file1.py file2.py file3.py

# 生成 Markdown 格式报告
python run.py your_file.py --format markdown

# 保存报告到文件
python run.py your_file.py --output report.txt
```

## 功能特性

### 支持的代码异味检测

1. **过长函数** (Long Function)
   - 默认阈值：30 行
   - 50 行以上为高严重度

2. **过高圈复杂度** (High Cyclomatic Complexity)
   - 默认阈值：10
   - 15 以上为高严重度

3. **参数过多** (Too Many Parameters)
   - 默认阈值：5 个参数

4. **嵌套过深** (Deep Nesting)
   - 默认阈值：4 层
   - 7 层以上为高严重度

5. **重复代码** (Duplicate Code)
   - 检测 5 行以上的重复代码块

6. **缺少文档字符串** (Missing Docstring)
   - 检测没有文档字符串的函数

7. **类过大** (Large Class)
   - 默认阈值：15 个方法

### 报告格式

- **文本格式**：适合终端显示
- **Markdown 格式**：适合文档和网页
- **JSON 格式**：适合程序处理和集成

### 严重程度分级

- **高 (HIGH)**：需要立即重构
- **中 (MEDIUM)**：建议尽快重构
- **低 (LOW)**：有时间时优化

## 项目结构

```
RefactorSuggest/
├── analyzer.py           # 代码分析器
├── smell_detector.py     # 代码异味检测器
├── suggester.py          # 重构建议生成器
├── reporter.py           # 报告生成器
├── issue.py             # 问题数据模型
├── run.py              # 命令行入口
├── cli.py              # CLI 模块
├── __init__.py         # 包初始化
├── __main__.py         # 模块入口
├── requirements.txt    # 依赖列表
├── README.md          # 项目说明
├── USAGE.md           # 使用指南
└── tests/             # 测试目录
    ├── test_example.py      # 测试示例文件
    └── test_refactor_suggest.py  # 测试套件
```

## 测试

运行完整测试套件：

```bash
cd RefactorSuggest
python tests/test_refactor_suggest.py
```

测试 CLI 功能：

```bash
python test_cli.py
```

## 输出示例

```
================================================================================
代码重构建议报告
生成时间: 2026-01-17 20:06:27
================================================================================
共发现 4 个问题

【高严重程度问题】
--------------------------------------------------------------------------------
文件: tests/test_example.py:6
严重程度: HIGH
问题类型: long_function
描述: 函数过长，难以理解和维护
建议: 将函数拆分为多个更小的函数，每个函数只做一件事
其他建议: 提取重复的代码块为独立函数; 使用策略模式或命令模式替代长函数; 考虑使用类来封装相关的数据和操作

文件: tests/test_example.py:6
严重程度: HIGH
问题类型: high_complexity
描述: 圈复杂度过高，逻辑过于复杂
建议: 使用卫语句(Guard Clauses)减少嵌套层级
其他建议: 提取复杂条件为独立的判断函数; 使用多态替代复杂的条件判断; 将复杂的布尔表达式拆分为多个有意义的变量

================================================================================
问题统计:
  高: 4 个
  中: 0 个
  低: 0 个
================================================================================
```

## 配置阈值

可以在相应的类中修改配置阈值：

```python
# analyzer.py - CodeAnalyzer 类
MAX_FUNCTION_LENGTH = 30
MAX_COMPLEXITY = 10
MAX_PARAMETERS = 5
MAX_NESTING_DEPTH = 4

# smell_detector.py - SmellDetector 类
MAX_CLASS_METHODS = 15
```

## 注意事项

1. 工具使用 Python 标准库 `ast` 模块解析代码，无需额外依赖
2. 支持所有 Python 3.x 版本
3. 对于大型项目，建议按模块分别分析
4. 重复代码检测使用简单的文本匹配，可能存在误报

## 未来改进

- [ ] 添加更多代码异味检测规则
- [ ] 支持自定义配置文件
- [ ] 集成到 CI/CD 流程
- [ ] 提供 IDE 插件
- [ ] 支持代码自动修复
