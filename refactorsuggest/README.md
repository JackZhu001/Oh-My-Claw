# RefactorSuggest - Python 代码重构建议工具

RefactorSuggest 是一个静态代码分析工具，用于检测 Python 代码中的常见问题并生成具体的重构建议。

## 功能特性

- ✅ 分析指定 Python 文件的代码质量
- ✅ 检测常见代码异味：
  - 过长函数
  - 复杂度过高
  - 参数过多
  - 类过大
  - 重复定义
  - 语法错误
- ✅ 生成具体的重构建议
- ✅ 支持一次性分析多个文件
- ✅ 支持目录递归分析
- ✅ 输出格式化报告（文本、Markdown、JSON）
- ✅ 报告包含问题严重程度、描述、建议和行号

## 安装

无需安装额外依赖，只需 Python 3.6+ 即可运行。

## 使用方法

### 命令行使用

```bash
# 分析单个文件
python -m refactorsuggest file.py

# 分析多个文件
python -m refactorsuggest file1.py file2.py file3.py

# 分析整个目录（递归）
python -m refactorsuggest -d src/

# 生成 Markdown 报告
python -m refactorsuggest -d src/ -f markdown -o report.md

# 生成 JSON 报告
python -m refactorsuggest -d src/ -f json -o report.json

# 自定义阈值
python -m refactorsuggest file.py --max-length 30 --max-complexity 8 --max-params 4
```

### 程序化使用

```python
from refactorsuggest import RefactorSuggest, Reporter

# 创建分析器实例
analyzer = RefactorSuggest()

# 分析单个文件
issues = analyzer.analyze_file("example.py")

# 分析多个文件
results = analyzer.analyze_multiple_files(["file1.py", "file2.py"])

# 分析整个目录
results = analyzer.analyze_directory("src/", recursive=True)

# 生成报告
report = Reporter.generate_report(results, format="markdown")

# 保存报告
Reporter.save_report(report, "report.md")
```

## 检测规则

### 1. 过长函数
- **阈值**: 默认 50 行
- **严重程度**: 中
- **建议**: 将函数拆分为更小的函数

### 2. 复杂度过高
- **阈值**: 默认圈复杂度 10
- **严重程度**: 高
- **建议**: 简化控制流，提取复杂逻辑到独立函数

### 3. 参数过多
- **阈值**: 默认 5 个参数
- **严重程度**: 中
- **建议**: 使用数据类或字典封装参数，或拆分函数

### 4. 类过大
- **阈值**: 默认 20 个方法
- **严重程度**: 中
- **建议**: 使用继承或组合来拆分类

### 5. 重复定义
- **严重程度**: 高
- **建议**: 重命名或删除重复的定义

## 报告格式

### 文本格式

```
================================================================================
RefactorSuggest 代码重构建议报告
================================================================================

文件: example.py
--------------------------------------------------------------------------------

  [严重程度: 高] 函数 'very_long_function' 复杂度过高 (复杂度: 25)
  类型: 复杂度过高
  行号: 6
  详情: 当前复杂度: 25，建议最大: 10
  建议: 简化控制流，提取复杂逻辑到独立函数

  [严重程度: 中] 函数 'very_long_function' 过长 (85 行)
  类型: 过长函数
  行号: 6
  详情: 当前长度: 85 行，建议最大: 50 行
  建议: 将函数拆分为更小的函数，建议每函数不超过 50 行

================================================================================
统计摘要
================================================================================
分析文件数: 1
发现问题总数: 2
  - 高严重程度: 1
  - 中严重程度: 1
  - 低严重程度: 0
================================================================================
```

### Markdown 格式

```markdown
# RefactorSuggest 代码重构建议报告

## 文件: `example.py`

### 🔴 函数 'very_long_function' 复杂度过高 (复杂度: 25)
- **类型**: 复杂度过高
- **行号**: 6
- **详情**: 当前复杂度: 25，建议最大: 10
- **建议**: 简化控制流，提取复杂逻辑到独立函数

### 🟡 函数 'very_long_function' 过长 (85 行)
- **类型**: 过长函数
- **行号**: 6
- **详情**: 当前长度: 85 行，建议最大: 50 行
- **建议**: 将函数拆分为更小的函数，建议每函数不超过 50 行

---

## 统计摘要

- 分析文件数: 1
- 发现问题总数: 2
  - 🔴 高严重程度: 1
  - 🟡 中严重程度: 1
  - 🟢 低严重程度: 0
```

### JSON 格式

```json
{
  "summary": {
    "total_files": 1,
    "total_issues": 2,
    "severity_counts": {
      "high": 1,
      "medium": 1,
      "low": 0
    }
  },
  "files": {
    "example.py": [
      {
        "severity": "高",
        "description": "函数 'very_long_function' 复杂度过高 (复杂度: 25)",
        "recommendation": "简化控制流，提取复杂逻辑到独立函数",
        "line_number": 6,
        "issue_type": "复杂度过高",
        "details": "当前复杂度: 25，建议最大: 10"
      }
    ]
  }
}
```

## 项目结构

```
refactorsuggest/
├── __init__.py       # 包初始化文件
├── models.py         # 数据模型定义
├── analyzer.py       # 代码分析器核心逻辑
├── reporter.py       # 报告生成器
├── cli.py           # 命令行接口
├── main.py          # 主程序入口
├── test_example.py  # 测试示例代码
└── README.md        # 本文档
```

## 示例

测试工具的功能：

```bash
# 分析测试示例文件
python -m refactorsuggest refactorsuggest/test_example.py
```

这将显示对测试代码的分析结果，包括：
- 过长函数检测
- 高复杂度函数检测
- 参数过多检测
- 类过大检测

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `files` | 要分析的 Python 文件路径 | - |
| `-d, --directory` | 分析指定目录中的所有 Python 文件 | - |
| `-r, --recursive` | 递归分析子目录 | True |
| `-f, --format` | 报告格式 (text/markdown/json) | text |
| `-o, --output` | 输出报告到指定文件 | - |
| `--max-length` | 函数最大行数阈值 | 50 |
| `--max-complexity` | 圈复杂度阈值 | 10 |
| `--max-params` | 函数参数数量阈值 | 5 |

## 许可证

MIT License
