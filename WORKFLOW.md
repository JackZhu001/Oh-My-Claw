# CodeMate Agent 工作流（2026 刷新版）

## 1. 主循环（ReAct + Function Calling）

1. 接收用户输入
2. 判断是否需要任务规划（Planner）
3. 注入系统提示（基础提示 + 记忆召回 + 技能索引）
4. 调用 LLM（优先 function calling）
5. 若有工具调用：执行工具并回填 `tool` 消息
6. 若无工具调用：输出最终答案
7. 记录 trace / metrics / heartbeat
8. LoopGuard 判断连续失败/提前结束

---

## 2. 复杂任务路径

复杂任务会触发：

- 自动计划生成
- `todo_write` 进度追踪
- 多轮工具调用（读文档、查目录、写文件）
- LoopGuard 纠偏（连续失败、提前结束）

---

## 3. 上下文工程路径

- **Micro Compact**：每轮对旧工具输出做轻量压缩
- **Auto Compact**：达到阈值后压缩历史并保留最近关键轮次
- **Manual Compact**：`/compact` 手动触发

工具输出同时由 Observation Truncator 进行按工具类型截断。

---

## 4. 子代理路径

- TaskTool 触发子代理
- SubagentRunner 在独立会话中运行
- 限制可用工具，避免副作用
- 返回结构化摘要给主 Agent

---

## 5. 团队协作路径

- `TeamRuntime` 负责 inbox、任务板、事件日志
- 自动读取 inbox 注入上下文
- 可选 task auto-claim

---

## 6. 心跳与看门狗

- 关键阶段心跳：round / llm / tool
- 超时看门狗：LLM 或工具执行超时告警
- `/heartbeat` 可查看状态

---

## 7. MiniMax 兼容分支

当 provider=minimax：

- 历史消息做协议安全规整（system/tool/tool_calls）
- 兼容解析 `<minimax:tool_call>` 文本协议
- 若接口报错，逐级降级重试

---

## 8. 失败处理策略

- 参数验证失败：返回明确错误 + 用法提示
- 连续失败阈值：注入干预消息，促使更换策略
- 循环检测：识别重复工具签名并告警/打断
