# CodeMate AI

> 基于 **Function Calling** 范式的智能代码分析助手

CodeMate AI 是一个使用智谱 AI GLM-4 模型构建的代码分析 Agent。通过原生的 Function Calling API，它能够准确调用工具来理解项目结构、搜索代码并分析文件。

## 特性

- ✅ **原生 Function Calling**: 使用 OpenAI 兼容的 API，无需解析文本
- ✅ **模块化工具系统**: 工具按类别组织（文件/搜索/Shell）
- ✅ **Pydantic 数据验证**: 所有数据模型使用 Pydantic 进行验证
- ✅ **简洁的 CLI**: 基于 Rich 的美观命令行界面
- ✅ **三层日志架构**:
  - 运行时日志 (Rich 美化输出)
  - Trace 轨迹日志 (JSONL + Markdown 双格式)
  - Metrics 统计 (Token、成本、性能指标)
- ✅ **Token 统计**: 跟踪 API 使用量和预估成本

## 快速开始

### 1. 安装

```bash
# 克隆项目
git clone <repository-url>
cd codemate-agent

# 激活 conda 环境
conda activate codemate
# 或创建环境: conda create -n codemate python=3.11 -y

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的智谱 API Key：

```
GLM_API_KEY=your_api_key_here
GLM_MODEL=glm-4-flash
MAX_ROUNDS=50
TEMPERATURE=0.7

# 日志配置
LOG_LEVEL=INFO
TRACE_ENABLED=true
TRACE_DIR=logs/traces
METRICS_ENABLED=true
METRICS_DIR=logs/sessions
```

### 3. 运行

```bash
# 交互模式
./run.sh

# 单次查询
./run.sh "分析 examples/sample_project/"

# 指定模型
./run.sh --model glm-4-plus "你的问题"
```

## 可用工具

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件内容 |
| `list_dir` | 列出目录内容 |
| `file_info` | 获取文件信息 |
| `write_file` | 写入文件 |
| `search_code` | 搜索代码内容 |
| `find_definition` | 查找函数/类定义 |
| `analyze_project` | 分析项目结构 |

## 项目结构

```
codemate-agent/
├── codemate_agent/
│   ├── agent/           # Agent 实现
│   ├── llm/             # LLM 客户端
│   ├── logging/         # 日志系统
│   │   ├── logger.py    # 基础运行时日志
│   │   ├── trace_logger.py  # Trace 轨迹日志
│   │   └── metrics.py   # Metrics 统计
│   ├── tools/           # 工具系统
│   │   ├── file/        # 文件工具
│   │   ├── search/      # 搜索工具
│   │   └── shell/       # Shell 工具
│   ├── schema.py        # 数据模型
│   ├── config.py        # 配置管理
│   └── cli.py           # CLI 入口
├── logs/                # 日志输出目录
│   ├── traces/          # JSONL + MD 轨迹文件
│   └── sessions/        # Metrics 统计文件
├── tests/               # 单元测试
├── examples/            # 示例项目
├── PROJECT_REPORT.md    # 开发报告
└── README.md
```

## 使用示例

```bash
# 交互模式
codemate

# 分析项目
codemate "这个项目是用什么语言写的？"

# 读取文件
codemate "读取 examples/sample_project/main.py 并总结功能"

# 搜索代码
codemate "搜索所有包含 'Todo' 的代码"
```

## 日志系统

CodeMate Agent 实现了三层日志架构：

### 1. 运行时日志
基于 Rich 的彩色终端输出，支持动态日志级别。

### 2. Trace 轨迹日志
记录完整的 Agent 执行过程，支持会话回放：

```bash
# 查看 JSONL 格式（便于程序分析）
cat logs/traces/trace-s-20260116-123456-abcd.jsonl

# 查看 Markdown 格式（便于人工阅读）
cat logs/traces/trace-s-20260116-123456-abcd.md
```

### 3. Metrics 统计
每次会话结束时自动显示：

```
📊 ──────────────────────────────────────────
   CodeMate Agent 会话统计
──────────────────────────────────────────
  会话 ID     : s-20260116-123456-abcd
  模型        : glm-4-flash
  持续时间    : 45.2 秒

  🪙 Token 使用
     Input   : 3,456
     Output  : 1,234
     Total   : 4,690

  💰 预估成本 : ¥0.0234

  🔄 执行统计
     总轮数     : 5
     LLM 调用   : 5
     工具调用   : 8
       调用详情 :
         - list_dir: 1
         - read_file: 5
         - search_code: 2
     错误次数   : 0
──────────────────────────────────────────
```

## 技术栈

- **Python** 3.10+
- **GLM-4** API
- **Pydantic** 2.x
- **Rich** 终端 UI
- **prompt-toolkit** 交互式输入

## 开发

```bash
# 运行测试
python -m unittest tests.test_logging

# 代码格式化
black codemate_agent/

# 代码检查
ruff check codemate_agent/
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
