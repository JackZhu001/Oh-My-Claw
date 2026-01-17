# CodeMate AI 项目开发报告

**版本**: v0.3.0
**日期**: 2025-01-16
**开发者**: [Yuxi Zhu]

---

## 一、项目概述

CodeMate AI 是一个基于 **Function Calling** 范式的智能代码分析助手。通过使用智谱 AI GLM-4 模型，它能够理解项目结构、搜索代码、分析文件并提供有价值的开发建议。

### 1.1 核心特性

- ✅ **原生 Function Calling**: 使用 OpenAI 兼容的 API 格式，无需解析文本
- ✅ **模块化工具系统**: 工具按类别组织，易于扩展
- ✅ **Pydantic 数据验证**: 所有数据模型使用 Pydantic 进行验证
- ✅ **简洁的 CLI**: 基于 Rich 的美观命令行界面
- ✅ **三层日志架构**:
  - 运行时日志 (Rich 美化输出)
  - Trace 轨迹日志 (JSONL + Markdown 双格式)
  - Metrics 统计 (Token、成本、性能指标)
- ✅ **Token 统计**: 跟踪 API 使用量和预估成本
- ✅ **单元测试**: 19+ 测试用例覆盖核心功能

### 1.2 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 主要编程语言 |
| GLM-4 | - | LLM 模型 |
| Pydantic | 2.x | 数据验证 |
| Rich | - | 终端 UI |
| prompt-toolkit | - | 交互式输入 |
| unittest | - | 单元测试框架 |

---

## 二、架构设计

### 2.1 项目结构

```
codemate-agent/
├── codemate_agent/
│   ├── __init__.py
│   ├── schema.py              # Pydantic 数据模型
│   ├── config.py              # 配置管理
│   ├── cli.py                 # CLI 入口
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   └── agent.py           # Function Calling Agent
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py          # GLM API 客户端
│   │
│   ├── logging/               # 日志系统 (新增)
│   │   ├── __init__.py
│   │   ├── logger.py          # Rich 基础日志
│   │   ├── trace_logger.py    # Trace 轨迹日志
│   │   └── metrics.py         # Metrics 统计
│   │
│   └── tools/
│       ├── __init__.py
│       ├── base.py            # 工具基类
│       ├── registry.py        # 工具注册器
│       │
│       ├── file/              # 文件操作工具
│       │   ├── read_file.py
│       │   ├── list_dir.py
│       │   ├── write_file.py
│       │   └── delete_file.py
│       │
│       ├── search/            # 搜索工具
│       │   └── search_code.py
│       │
│       └── shell/             # Shell 工具
│           └── run_shell.py
│
├── logs/                       # 日志输出目录 (新增)
│   ├── traces/                # JSONL + MD 轨迹文件
│   └── sessions/              # Metrics 统计文件
│
├── tests/                      # 测试
│   ├── __init__.py
│   └── test_logging.py        # 日志系统测试
│
├── examples/                   # 示例项目
├── pyproject.toml             # 项目配置
├── requirements.txt            # 依赖列表
├── .env.example               # 环境变量模板
├── run.sh                     # 启动脚本
├── README.md                  # 项目文档
└── PROJECT_REPORT.md          # 本报告
```

### 2.2 核心流程

```
┌─────────────────────────────────────────────────────────────┐
│                      用户输入                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    CodeMateAgent                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  1. 构建 OpenAI 格式的工具列表                      │   │
│  │  2. 调用 GLM API (带 tools 参数)                     │   │
│  │  3. 解析 tool_calls                                   │   │
│  │  4. 执行工具                                          │   │
│  │  5. 将结果返回给 LLM                                 │   │
│  │  6. 重复直到完成                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、核心模块实现

### 3.1 数据模型 (schema.py)

使用 Pydantic 定义所有数据结构：

```python
class Message(BaseModel):
    """聊天消息"""
    role: str
    content: str
    tool_calls: Optional[list[ToolCall]] = None

class LLMResponse(BaseModel):
    """LLM 响应"""
    content: str
    tool_calls: Optional[list[ToolCall]] = None
    usage: Optional[TokenUsage] = None
```

### 3.2 工具基类 (tools/base.py)

工具基类支持转换为 OpenAI Function Calling Schema：

```python
class Tool(ABC):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters(self) -> dict: ...

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
```

### 3.3 LLM 客户端 (llm/client.py)

支持原生 Function Calling 的 GLM 客户端：

```python
class GLMClient:
    def complete(self, messages: List[Message],
                 tools: Optional[List[Dict]] = None) -> LLMResponse:
        # 调用 GLM API
        # 返回包含 tool_calls 的响应
```

### 3.4 Agent 实现 (agent/agent.py)

基于原生 Function Calling 的 Agent：

```python
class CodeMateAgent:
    def run(self, query: str) -> str:
        # 1. 添加用户消息
        # 2. 调用 LLM（带工具）
        # 3. 如果有 tool_calls，执行工具
        # 4. 将结果返回给 LLM
        # 5. 重复直到没有 tool_calls
```

### 3.5 日志系统 (logging/)

**三层日志架构设计**：

```python
# 1. 基础运行时日志 - Rich 美化输出
logger = setup_logger("codemate.agent", level="INFO")
logger.info("处理用户输入...")

# 2. Trace 轨迹日志 - 记录完整执行过程
trace_logger = TraceLogger(session_id, trace_dir)
trace_logger.log_event(TraceEventType.USER_INPUT, {"text": "..."})
trace_logger.finalize()  # 生成 JSONL + Markdown 报告

# 3. Metrics 统计 - Token、成本、性能
metrics = SessionMetrics(session_id, model="glm-4")
metrics.record_llm_call(usage)
metrics.finalize()
metrics.print_summary()
```

**支持的事件类型**：
- `session_start/end` - 会话生命周期
- `user_input` - 用户输入
- `llm_request/response` - LLM 交互
- `tool_call/result/error` - 工具执行
- `error/warning` - 错误和警告

---

## 四、与 Mini-Agent 的对比

| 特性 | Mini-Agent | CodeMate (v0.3) |
|------|-----------|----------------|
| **范式** | 文本 ReAct | 原生 Function Calling |
| **LLM** | MiniMax M2.1 | 智谱 GLM-4 |
| **数据模型** | Pydantic | Pydantic |
| **日志系统** | 基础 logging | 三层日志架构 |
| **Trace 轨迹** | ❌ | ✅ JSONL + Markdown |
| **Metrics 统计** | 基础 Token | Token + 成本 + 性能 |
| **工具组织** | 单文件 | 按类别分目录 |
| **单元测试** | 部分 | ✅ 19+ 测试用例 |
| **配置管理** | YAML | .env + Pydantic |

---

## 五、改进点总结

### 5.1 架构改进

1. **从 ReAct 文本解析 → 原生 Function Calling**
   - 更可靠的工具调用
   - 更少的 Token 消耗
   - 更好的错误处理

2. **引入 Pydantic 数据模型**
   - 类型安全
   - 自动验证
   - 更好的 IDE 支持

3. **工具按类别组织**
   - 更清晰的代码结构
   - 更容易维护

### 5.2 新增功能

1. **三层日志架构**
   ```python
   # 运行时日志 + Trace 轨迹 + Metrics 统计
   ```

2. **Token 统计与成本估算**
   ```python
   metrics.estimated_cost  # 预估成本（元）
   metrics.total_tokens    # 总 Token 数
   ```

3. **会话回放能力**
   - JSONL 格式便于程序分析
   - Markdown 格式便于人工审查

---

## 六、使用指南

### 6.1 安装

```bash
# 激活 conda 环境
conda activate codemate

# 安装依赖
pip install -r requirements.txt
```

### 6.2 配置

创建 `.env` 文件：

```bash
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

### 6.3 运行

```bash
# 交互模式
./run.sh

# 单次查询
./run.sh "分析 examples/sample_project/"

# 指定模型
./run.sh --model glm-4-plus "你的问题"
```

### 6.4 日志查看

```bash
# 查看 Trace 轨迹
cat logs/traces/trace-s-*.md

# 查看 Metrics 统计
cat logs/sessions/metrics-s-*.json
```

---

## 七、未来规划

### 7.1 短期（v0.4）

- [x] 添加日志系统 ✅ (已完成)
- [x] 添加单元测试 ✅ (已完成)
- [ ] 添加 Session Note（持久化记忆）
- [ ] 对话历史持久化
- [ ] 完善工具参数定义

### 7.2 中期（v0.5）

- [ ] MCP 协议支持
- [ ] 流式输出显示
- [ ] 代码重构建议功能
- [ ] 项目分析工具

### 7.3 长期（v0.6+）

- [ ] Web 界面（Streamlit）
- [ ] RAG 增强检索
- [ ] 多 Agent 协作
- [ ] 代码审查模式

---

## 八、面试亮点

这个项目在求职时可以展示以下亮点：

1. **理解 Agent 范式**
   - 了解 ReAct 和 Function Calling 的区别
   - 能够选择合适的技术方案

2. **工程能力**
   - 模块化设计
   - 清晰的代码结构
   - 适当的抽象层次

3. **日志系统设计**
   - 三层日志架构设计
   - Trace 轨迹记录与回放
   - 成本追踪与性能监控

4. **测试意识**
   - 编写单元测试
   - 测试覆盖核心功能
   - 理解测试驱动开发

5. **技术深度**
   - 理解 OpenAI API 标准
   - 能够集成第三方 LLM
   - 工具系统设计

6. **可扩展性**
   - 易于添加新工具
   - 易于切换 LLM 提供商
   - 为未来功能预留接口

---

## 九、参考资料

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [智谱 AI 文档](https://open.bigmodel.cn/dev/api)
- [Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent)
- [HelloAgents](https://github.com/aiwaves-cn/HelloAgents)

---

**报告结束**
