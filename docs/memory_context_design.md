# CodeMate 记忆系统与上下文工程（详细说明）

本文档描述 CodeMate 的记忆分层、压缩机制、工具输出截断策略与配置项。

## 1. 设计目标

1. 长链路任务不中断、不中断主线
2. 上下文逼近上限时平滑降载，而不是硬截断
3. 历史可回溯（summary + transcript）
4. 用户可手动介入（`/compact`）

---

## 2. 三层记忆模型

### 2.1 短时记忆（Short-term）

**定义**：当前会话内、直接送入 LLM 的消息历史。  
**实现载体**：`self.messages`（`Message` 列表）。

短时记忆包含两类信息：
- 对话轮次（user / assistant）
- 工具调用反馈（tool）

---

### 2.2 工作记忆（Working Memory）

**定义**：任务执行状态（todo 进度、已完成项、阻塞项）。  
**实现方式**：压缩过程中注入当前 TODO 状态，降低任务状态丢失概率。

建议实践：
- 将里程碑与未完成项维持为结构化文本
- 每次关键状态变化后更新
- “状态事实”与“自然语言对话”分离

---

### 2.3 长时记忆（Long-term）

**定义**：跨会话持久信息。  
**实现方式**：
- 会话数据持久化
- `/memory` 可查看长期记忆内容
- 自动压缩时完整 transcript 落盘（默认 `~/.codemate/transcripts/`）

---

## 3. 上下文压缩系统（Context Compressor）

关键文件：`codemate_agent/context/compressor.py`

### 3.1 Layer 1: Micro Compact（每轮微压缩）

目标：控制工具输出膨胀，优先保留最近轮次的可操作信息。

行为：
1. 识别对话轮次
2. 仅处理 `role="tool"` 的旧输出
3. 默认保留最近 `MICRO_COMPACT_KEEP` 轮完整工具输出
4. 更早工具输出做 Soft Trim / Hard Clear
5. 允许白名单 / 黑名单工具控制裁剪

**Soft Trim**：保留头尾片段（`MICRO_TRIM_HEAD` / `MICRO_TRIM_TAIL`）  
**Hard Clear**：直接替换为占位符（表示可回读）

触发条件：
- Soft Trim：裁剪比例达到 `MICRO_SOFT_TRIM_RATIO`
- Hard Clear：裁剪比例达到 `MICRO_HARD_CLEAR_RATIO` 且可裁剪字符量 >= `MICRO_HARD_CLEAR_MIN_CHARS`

---

### 3.2 Layer 2: Auto Compact（自动压缩）

触发策略：
- 默认阈值：`context_window * COMPRESSION_THRESHOLD`
- 或使用固定阈值 `TOKEN_THRESHOLD`（>0 时生效）

执行策略：
1. 将完整会话写入 transcript 文件
2. 保留 `system + 最近 N 轮`
3. 更早历史摘要化并回注到上下文
4. 注入 TODO 状态，保持任务连续性

---

### 3.3 Layer 3: Manual Compact（手动压缩）

CLI 支持 `/compact`，可在任意时刻手动触发压缩。

适用场景：
- 即将进入大文件改造
- 准备开启新子任务，先清理上下文

---

## 4. 工具输出截断（Observation Truncator）

关键文件：`codemate_agent/context/truncator.py`

工具输出是上下文膨胀最大来源。CodeMate 会按工具类型做智能截断：
- `list_dir`：结构感知，保留浅层目录
- `search_files`：采样保留
- `run_shell`：优先保留尾部（错误常在尾部）
- `read_file` / `search_code`：首尾保留

截断后的输出仍保留足够结构与关键片段，减少 token 压力。

---

## 5. 关键配置项

常见参数：
- `CONTEXT_WINDOW`
- `COMPRESSION_THRESHOLD`
- `TOKEN_THRESHOLD`
- `MIN_RETAIN_ROUNDS`
- `MICRO_COMPACT_KEEP`
- `MICRO_COMPACT_TOOL_ALLOWLIST`
- `MICRO_COMPACT_TOOL_DENYLIST`
- `MICRO_SOFT_TRIM_RATIO`
- `MICRO_HARD_CLEAR_RATIO`
- `MICRO_HARD_CLEAR_MIN_CHARS`
- `MICRO_TRIM_HEAD`
- `MICRO_TRIM_TAIL`
- `TRANSCRIPT_DIR`

建议：
- 多工具密集场景：提高 `MICRO_COMPACT_KEEP` 到 4~6
- 大仓库长任务：`COMPRESSION_THRESHOLD` 在 0.70~0.80 较稳

---

## 6. 参考业界实践（简述）

结合 Claude Code / Codex / Aider 的公开资料，常见共识是：

1. 会话上下文是短时的，需要外部文件承接长期规则/偏好
2. 文档化记忆优先（项目级规则文件 + 自动摘要索引）
3. 按需读取细节，避免把所有历史细节一直塞在 prompt 里

CodeMate 当前已覆盖：
- 会话压缩
- transcript 可回读
- 手动压缩入口
- 工具输出智能截断

---

## 7. Roadmap（建议）

1. 工作记忆结构化固化（todo/阻塞/下一步）
2. 长时记忆索引化（主题/决策/问题/结果）
3. 用户偏好画像文档化（类似 CLAUDE.md）
4. 检索增强上下文拼装（先召回摘要，再回读原文）
